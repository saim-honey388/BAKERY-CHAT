"""Returning User Agent: handles post-session order lookups via LLM-generated SQL (read-only).

Behavior:
- If user asks about order status or to repeat ordered items, we let the LLM craft a SELECT-only SQL query
  against our SQLite DB (via SQLAlchemy engine) to fetch the appropriate records.
- We strictly sandbox execution to SELECT-only statements to avoid any writes.
- If insufficient identifiers are present (e.g., no order number), the LLM is instructed to respectfully
  ask for more details: order number first; if unknown, ask for name + phone; if still unknown, ask for
  pickup/delivery time and items ordered; if still unknown, default to latest order for that customer.

Note: This agent does not modify any existing logic; it is additive.
"""

from .base_agent import BaseAgent
from typing import Dict, Any, List, Optional
from ..schemas.io_models import AgentResult
from ..data.database import SessionLocal
from sqlalchemy import text
from ..app.dual_api_system import DualAPISystem
import datetime
import re


class ReturningUserAgent(BaseAgent):
    name = "returning_user"

    def handle(self, session_id: str, query: str, session: List[Dict[str, Any]] = [], memory_context: Dict[str, Any] = None) -> AgentResult:
        print("[WORKFLOW] Executing ReturningUserAgent...")

        # Compose schema overview for the LLM
        schema_overview = self._get_schema_overview()

        # Optionally parse a confirmed_at hint from the query (e.g., "2025-09-09 11:38 AM")
        confirmed_at_hint_iso = None
        try:
            import re as _re
            from datetime import datetime as _dt
            m = _re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)", query or "")
            if m:
                date_str, hh, mm, ap = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).lower()
                if ap == 'pm' and hh != 12:
                    hh += 12
                if ap == 'am' and hh == 12:
                    hh = 0
                confirmed_at_hint_iso = f"{date_str} {hh:02d}:{mm:02d}:00"
        except Exception as _e:
            print(f"[TIME PARSE ERROR] {_e}")

        # Build system instruction for safe SQL
        instruction = (
            "ROLE: Generate exactly one safe, read-only SQL SELECT for SQLite to answer the user's order lookup.\n"
            "SAFETY: Absolutely forbid UPDATE/INSERT/DELETE/ALTER/DROP/CREATE/ATTACH/PRAGMA/VACUUM/REINDEX/UNION/WITH/INTERSECT/EXCEPT. No subqueries, no CTEs, no multiple statements. One SELECT only.\n"
            "SCHEMA-FIRST: Use ONLY the provided schema and real column names. Do NOT invent columns. Qualify columns with table aliases: orders o, customers c, order_items oi, products p.\n"
            "COMPLEX QUERIES: You are expected to write complex SELECTs using JOINs, multi-condition WHERE (AND/OR), BETWEEN ranges for time windows, LIKE for partial names, ORDER BY and LIMIT, and selecting the precise columns needed. No subqueries/CTEs.\n"
            "PURPOSE SELECTION: If the user asks to list or read items, use purpose 'order_items' (or 'order_receipt') and JOIN o,c,oi,p to return product_name, description, quantity, price_at_time_of_order. If the user only asks for status, use 'order_status'.\n"
            "IDENTIFICATION: If the user provides an order id/number, use it directly to fetch the order (do not ask for phone/name). If the user provides only a name and/or phone_number, ALSO ask for a pickup/delivery time or an order_date window to narrow results; when provided, include that time constraint in the SELECT. If multiple matches remain, ask for 1-2 items they ordered to disambiguate. If still ambiguous and the user refuses to specify, default to the latest order.\n"
            "RESULT SHAPES:\n- order_status: SELECT o.id, o.status, o.pickup_or_delivery, o.total_amount, o.confirmed_at, o.pickup_delivery_time, c.name, c.phone_number FROM ... WHERE ... LIMIT 1\n- order_items/order_receipt: JOIN o,c,oi,p and include product_name, description, quantity, price_at_time_of_order\n- latest_order: ORDER BY o.order_date DESC LIMIT 1\n- order_history/list_orders: ORDER BY o.order_date DESC LIMIT 50\n- order_total: SELECT o.id, o.total_amount ... LIMIT 1\n"
            "TIME LITERALS: Use ISO 'YYYY-MM-DD HH:MM:SS' for time filters and BETWEEN for windows (e.g., o.order_date BETWEEN '2025-09-09 10:00:00' AND '2025-09-09 14:00:00').\n"
            "LITERALS ONLY: Do NOT use placeholders or bind params ('?', ':param'). Return a fully inlined SELECT with literal values in WHERE.\n"
            "OUTPUT JSON: Return strictly valid JSON with keys: sql (string), purpose (one of: 'order_status'|'order_items'|'order_receipt'|'order_total'|'order_time'|'order_history'|'list_orders'|'latest_order'), optional message (string), optional clarify_question (string).\n"
            "VALIDATION: If you cannot produce a compliant SELECT, do NOT guess—return clarify_question asking for order number or name+phone and a time window/items. When you can produce SQL, return it without extra text."
        )

        hints = ""
        if confirmed_at_hint_iso:
            hints += f"CONFIRMED_AT_HINT: {confirmed_at_hint_iso} (use BETWEEN ±10 minutes on o.confirmed_at)\n"

        prompt = (
            f"Database schema (SQLite):\n{schema_overview}\n\n"
            f"User query: {query}\n\n"
            f"{hints}{instruction}"
        )

        dual_api = DualAPISystem()
        llm_raw = dual_api.generate_response_with_primary_api(prompt)

        # Extract JSON block from LLM response
        json_payload = self._extract_json(llm_raw)
        if not json_payload:
            # Ask for order number first (let LLM output the question via prompt rules)
            return self._ok(
                intent="returning_user_lookup",
                facts={
                    "asking_for": "order_number",
                    "note": "Need order number first; otherwise ask name+phone and time window to narrow."
                }
            )

        # Clarification path
        clarify_q = (json_payload.get("clarify_question") if isinstance(json_payload, dict) else None) or None
        if clarify_q and not json_payload.get("sql"):
            return self._clarify(intent="returning_user_lookup", question=clarify_q)

        # Execute SQL safely if provided
        sql = json_payload.get("sql") if isinstance(json_payload, dict) else None
        purpose = json_payload.get("purpose") if isinstance(json_payload, dict) else None
        if not sql or not purpose:
            return self._ok(
                intent="returning_user_lookup",
                facts={
                    "asking_for": "order_number",
                    "note": "Need order number first; otherwise ask name+phone and time window to narrow."
                }
            )

        if not self._is_safe_select(sql):
            return self._ok(
                intent="returning_user_lookup",
                facts={
                    "asking_for": "order_number",
                    "note": "Unsafe query; ask for order number or name+phone plus time window."
                }
            )
        # Reject queries that use placeholders; require fully inlined SQL
        lowered_sql = sql.lower()
        if "?" in lowered_sql or ":" in lowered_sql:
            # Single retry: reinforce instruction and re-generate SQL with literals
            try:
                print("[RETURNING_USER RETRY] Placeholders detected; retrying with stronger instruction")
                instruction_retry = instruction + "\nABSOLUTE RULE: Inline all literal values. No placeholders or bind parameters."
                prompt_retry = (
                    f"Database schema (SQLite):\n{schema_overview}\n\n"
                    f"User query: {query}\n\n"
                    f"{hints}{instruction_retry}"
                )
                llm_raw_retry = DualAPISystem().generate_response_with_primary_api(prompt_retry)
                json_retry = self._extract_json(llm_raw_retry)
                if json_retry and isinstance(json_retry, dict) and json_retry.get("sql"):
                    sql = json_retry.get("sql")
                    print(f"[RETURNING_USER SQL RETRY] {sql}")
                    lowered_sql = sql.lower()
                    # If still placeholders or unsafe, proceed to attempt execution and handle error; do not return early
                else:
                    print("[RETURNING_USER RETRY] Failed to produce SQL on retry; will ask after execution attempt")
            except Exception as _retry_e:
                print(f"[RETURNING_USER RETRY ERROR] {_retry_e}")

        session_db = SessionLocal()
        try:
            print(f"[RETURNING_USER SQL] {sql}")
            rows = session_db.execute(text(sql)).fetchall()
            # Print row count and a readable snapshot to the console for debugging
            try:
                print(f"[RETURNING_USER ROWS] count={len(rows)}")
                preview_max = 5
                for idx, r in enumerate(rows[:preview_max]):
                    print(f"[RETURNING_USER ROW {idx+1}] {dict(r._mapping)}")
                if len(rows) > preview_max:
                    print(f"[RETURNING_USER ROWS] ... {len(rows) - preview_max} more")
            except Exception as _prerr:
                print(f"[RETURNING_USER ROWS PRINT ERROR] {_prerr}")
        except Exception as e:
            print(f"[SQL ERROR] {e}")
            session_db.close()
            return self._ok(
                intent="returning_user_lookup",
                facts={
                    "asking_for": "order_number",
                    "note": "SQL error; ask for order number or name+phone plus time window."
                }
            )
        finally:
            session_db.close()

        # Build response
        if not rows:
            # Signal the prompt to ask for order number first
            return self._ok(
                intent="returning_user_lookup",
                facts={
                    "asking_for": "order_number",
                    "note": "No rows; ask for order number first, else name+phone + time window + items."
                }
            )

        # Optional LLM-crafted message for tone
        llm_message = json_payload.get("message") if isinstance(json_payload, dict) else None

        # Summarize depending on purpose
        if purpose == "order_status":
            summary = self._summarize_status(rows[0])
            if llm_message:
                summary["message"] = llm_message
            else:
                summary["message"] = self._chef_message_for_status(summary)
            return self._ok(intent="order_status", facts=summary)

        if purpose == "order_items":
            summary = self._summarize_items(rows)
            if llm_message:
                summary["message"] = llm_message
            else:
                summary["message"] = self._chef_message_for_items(summary)
            return self._ok(intent="order_items", facts=summary)

        if purpose == "order_receipt":
            receipt_text = self._render_receipt_from_rows(rows)
            facts = {"receipt_text": receipt_text}
            if llm_message:
                facts["message"] = llm_message
            return self._ok(intent="order_receipt", facts=facts)

        if purpose == "order_total":
            m = rows[0]._mapping
            facts = {
                "order_id": m.get("id"),
                "total_amount": m.get("total_amount"),
            }
            if llm_message:
                facts["message"] = llm_message
            return self._ok(intent="order_total", facts=facts)

        if purpose == "order_time":
            m = rows[0]._mapping
            facts = {
                "order_id": m.get("id"),
                "order_date": str(m.get("order_date")) if m.get("order_date") is not None else None,
                "confirmed_at": str(m.get("confirmed_at")) if m.get("confirmed_at") is not None else None,
                "pickup_delivery_time": str(m.get("pickup_delivery_time")) if m.get("pickup_delivery_time") is not None else None,
            }
            if llm_message:
                facts["message"] = llm_message
            return self._ok(intent="order_time", facts=facts)

        if purpose == "order_history" or purpose == "list_orders":
            candidates = self._summarize_candidates(rows)
            return self._ok(intent="order_history", facts={"orders": candidates})

        if purpose == "latest_order":
            # Assume first row is latest due to ORDER BY in SQL
            summary = self._summarize_status(rows[0])
            if llm_message:
                summary["message"] = llm_message
            else:
                summary["message"] = self._chef_message_for_status(summary, latest=True)
            return self._ok(intent="latest_order", facts=summary)

        # Default: return raw rows in a safe shape
        return self._ok(intent="returning_user_lookup", facts={"rows": [dict(r._mapping) for r in rows]})

    def _chef_message_for_status(self, status: Dict[str, Any], latest: bool = False) -> str:
        order_id = status.get("order_id") or status.get("id")
        stat = status.get("status")
        fulfill = status.get("fulfillment")
        when = status.get("pickup_delivery_time")
        prefix = "Your latest order" if latest else f"Order #{order_id}"
        bits = []
        if stat:
            bits.append(f"is currently {stat}.")
        if fulfill and when:
            bits.append(f"Scheduled for {fulfill} at {when}.")
        line = " ".join(bits) if bits else "is all set."
        return f"Chef here—{prefix} {line} Anything else I can whisk up for you?"

    def _chef_message_for_items(self, summary: Dict[str, Any]) -> str:
        order = summary.get("order", {})
        order_id = order.get("order_id") or order.get("id")
        items = summary.get("items", [])
        if not items:
            return "Chef here—your order looks light as a feather; I don’t see any items yet."
        names = ", ".join([it.get("product") for it in items if it.get("product")][:3])
        more = "" if len(items) <= 3 else " and more"
        return f"Chef here—Order #{order_id} includes {names}{more}. A delicious choice!"

    def _chef_message_for_times(self, facts: Dict[str, Any]) -> str:
        order_id = facts.get("order_id")
        conf = facts.get("confirmed_at")
        sched = facts.get("pickup_delivery_time")
        parts = []
        if conf:
            parts.append(f"confirmed at {conf}")
        if sched:
            parts.append(f"scheduled for {sched}")
        when = ", ".join(parts) or "timing details on file"
        return f"Chef here—Order #{order_id} has {when}."

    def _get_schema_overview(self) -> str:
        return (
            "customers(id INTEGER PK, name TEXT, phone_number TEXT UNIQUE)\n"
            "orders(id INTEGER PK, customer_id INTEGER FK->customers.id, order_date DATETIME, status TEXT, "
            "pickup_or_delivery TEXT, total_amount REAL, pickup_delivery_time DATETIME, confirmed_at DATETIME)\n"
            "order_items(id INTEGER PK, order_id INTEGER FK->orders.id, product_id INTEGER FK->products.id, quantity INTEGER, price_at_time_of_order REAL)\n"
            "products(id INTEGER PK, name TEXT, description TEXT, price REAL, category TEXT, quantity_in_stock INTEGER)"
        )

    def _extract_json(self, text_block: str) -> Optional[Dict[str, Any]]:
        try:
            import json
            match = re.search(r"\{[\s\S]*\}", text_block)
            if not match:
                return None
            return json.loads(match.group(0))
        except Exception:
            return None

    def _is_safe_select(self, sql: str) -> bool:
        s = sql.strip().lower()
        if not s.startswith("select"):
            return False
        # Disallow multiple statements
        if ";" in s.strip().rstrip(";"):
            return False
        forbidden = [
            "update", "insert", "delete", "drop", "alter", "create", "attach", "pragma", "vacuum", "reindex",
            "union", "with", "intersect", "except"
        ]
        return not any(tok in s for tok in forbidden)

    def _summarize_status(self, row) -> Dict[str, Any]:
        m = row._mapping
        return {
            "order_id": m.get("id"),
            "status": m.get("status"),
            "fulfillment": m.get("pickup_or_delivery"),
            "total_amount": m.get("total_amount"),
            "confirmed_at": str(m.get("confirmed_at")) if m.get("confirmed_at") is not None else None,
            "pickup_delivery_time": str(m.get("pickup_delivery_time")) if m.get("pickup_delivery_time") is not None else None,
            "customer_name": m.get("name"),
            "customer_phone": m.get("phone_number"),
        }

    def _summarize_items(self, rows) -> Dict[str, Any]:
        items = []
        order_meta = {
            "order_id": None,
            "status": None,
            "order_date": None,
            "fulfillment": None,
            "total_amount": None,
            "confirmed_at": None,
            "pickup_delivery_time": None,
            "customer_name": None,
            "customer_phone": None,
        }
        for r in rows:
            m = r._mapping
            order_meta["order_id"] = order_meta["order_id"] or m.get("id")
            order_meta["status"] = order_meta["status"] or m.get("status")
            order_meta["order_date"] = order_meta["order_date"] or m.get("order_date")
            order_meta["fulfillment"] = order_meta["fulfillment"] or m.get("pickup_or_delivery")
            order_meta["total_amount"] = order_meta["total_amount"] or m.get("total_amount")
            order_meta["confirmed_at"] = order_meta["confirmed_at"] or m.get("confirmed_at")
            order_meta["pickup_delivery_time"] = order_meta["pickup_delivery_time"] or m.get("pickup_delivery_time")
            order_meta["customer_name"] = order_meta["customer_name"] or m.get("name")
            order_meta["customer_phone"] = order_meta["customer_phone"] or m.get("phone_number")

            pname = m.get("product_name") or m.get("name")  # fallback
            if pname:
                desc = m.get("description")
                quantity = m.get("quantity")
                items.append({
                    "product": pname,
                    "quantity": quantity,
                    "note": (desc[:80] + "...") if isinstance(desc, str) and len(desc) > 80 else desc
                })

        return {"order": order_meta, "items": items}

    def _summarize_candidates(self, rows) -> List[Dict[str, Any]]:
        result = []
        for r in rows:
            m = r._mapping
            result.append({
                "order_id": m.get("id"),
                "order_date": str(m.get("order_date")) if m.get("order_date") is not None else None,
                "status": m.get("status"),
                "fulfillment": m.get("pickup_or_delivery"),
                "total_amount": m.get("total_amount"),
                "confirmed_at": str(m.get("confirmed_at")) if m.get("confirmed_at") is not None else None,
                "pickup_delivery_time": str(m.get("pickup_delivery_time")) if m.get("pickup_delivery_time") is not None else None,
                "customer_name": m.get("name"),
                "customer_phone": m.get("phone_number"),
            })
        return result

    def _render_receipt_from_rows(self, rows) -> str:
        facts = self._summarize_items(rows)
        meta = facts.get("order", {})
        items = facts.get("items", [])
        lines = []
        lines.append(f"Order Receipt — Order #{meta.get('order_id')}")
        if meta.get("confirmed_at"):
            lines.append(f"Confirmed At: {meta.get('confirmed_at')}")
        if meta.get("pickup_delivery_time"):
            lines.append(f"Scheduled: {meta.get('pickup_delivery_time')} ({meta.get('fulfillment')})")
        lines.append(f"Customer: {meta.get('customer_name')} | {meta.get('customer_phone')}")
        lines.append("")
        lines.append("Items:")
        for it in items:
            lines.append(f"- {it.get('quantity')} x {it.get('product')}" + (f" — {it.get('note')}" if it.get('note') else ""))
        lines.append("")
        total = meta.get("total_amount")
        if total is not None:
            try:
                lines.append(f"Total: ${float(total):.2f}")
            except Exception:
                lines.append(f"Total: {total}")
        return "\n".join(lines)


