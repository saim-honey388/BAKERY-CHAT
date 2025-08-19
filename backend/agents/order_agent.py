"""Order Agent: minimal slot-filling and order persistence (stub).

Orders are appended to a CSV file for simplicity.
"""
from .base_agent import BaseAgent
from typing import Dict, Any
import csv
import os

ORDERS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "orders.csv")

class OrderAgent(BaseAgent):
    name = "order"

    def __init__(self):
        os.makedirs(os.path.dirname(ORDERS_PATH), exist_ok=True)
        if not os.path.exists(ORDERS_PATH):
            with open(ORDERS_PATH, "w", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["item", "quantity", "time", "pickup_or_delivery", "order_id"])

    def handle(self, query: str, session: Dict[str, Any]):
        # very small slot extraction
        from ..nlu.entity_extractor import EntityExtractor
        ent = EntityExtractor().extract(query)
        item = ent.get("product") or ent.get("product_name") or "unknown item"
        qty = ent.get("quantity") or 1
        time = ent.get("time") or "ASAP"
        pickup = "pickup" if "pickup" in query.lower() or "pick up" in query.lower() else "delivery"

        missing = [k for k in ["product", "quantity"] if not ent.get(k)]
        if missing:
            return self._clarify("order", f"Please tell me the {' and '.join(missing)} for your order.")

        order_id = "BK-" + str(abs(hash(str((item, qty, time)))) % 100000)
        try:
            with open(ORDERS_PATH, "a", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([item, qty, time, pickup, order_id])
            facts = {"order_id": order_id, "item": item, "quantity": qty, "time": time, "fulfillment": pickup}
            return self._ok(intent="order", facts=facts, context_docs=[], citations=[])
        except Exception:
            return self._ok(intent="order", facts={"error": "failed to persist order"}, context_docs=[], citations=[])
