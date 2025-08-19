"""Product Info Agent: handles menu lookups and recommendations (minimal)."""
from .base_agent import BaseAgent
from typing import Dict, Any, List
from ..data.menu_store import get_menu_store
from ..schemas.io_models import Citation

class ProductInfoAgent(BaseAgent):
    name = "product_info"

    def __init__(self):
        self.menu = get_menu_store()

    def handle(self, query: str, session: Dict[str, Any]):
        """Search the menu and return structured product facts.

        Strategy:
        - Use token/description search (menu.search_items)
        - If no exact matches, use fuzzy best match
        - Apply price filters from the session/entities if present
        - Return facts: items: [{name, price, description, category}, ...]
        """
        q = query or ""
        facts: Dict[str, Any] = {"items": []}
        citations: List[Citation] = []

        # extract entities forwarded in the session by Controller
        entities = {}
        try:
            if isinstance(session, list) and session:
                # find last 'nlu' role message if present
                for msg in reversed(session):
                    if isinstance(msg, dict) and msg.get("role") == "nlu" and isinstance(msg.get("message"), dict):
                        entities = msg.get("message", {})
                        break
        except Exception:
            entities = {}

        price_min = entities.get("price_min")
        price_max = entities.get("price_max")
        requested_time = entities.get("time")

        # Try token-based search first
        matches = self.menu.search_items(q)

        # If no token matches, try fuzzy best match
        if not matches:
            best, score, idx = self.menu.find_best_match(q)
            if best and idx is not None and score >= 0.5:
                matches = [self.menu.items[idx]]

        # If still no matches, try category-based lookup (e.g., "cakes", "pastries")
        if not matches:
            # simple category heuristics
            for cat in ["cakes", "pastries", "breads", "specialty"]:
                if cat.rstrip('s') in q or cat in q:
                    matches = self.menu.get_items_by_category(cat)
                    break

        # Apply price filtering if present
        if matches and (price_min is not None or price_max is not None):
            filtered = []
            for m in matches:
                p = m.get("price")
                if p is None:
                    continue
                if price_min is not None and p < float(price_min):
                    continue
                if price_max is not None and p > float(price_max):
                    continue
                filtered.append(m)
            matches = filtered

        # If matches found, format facts
        if matches:
            items_out = []
            for m in matches:
                items_out.append({
                    "name": m.get("item"),
                    "price": m.get("price"),
                    "description": m.get("description"),
                    "category": m.get("category"),
                })
            facts["items"] = items_out
            # include requested_time if agent received it
            if requested_time:
                facts["requested_time"] = requested_time
            citations.append(Citation(source="menu.csv", snippet=", ".join([it["name"] for it in items_out[:5]])))
            return self._ok(intent="product_info", facts=facts, context_docs=[], citations=citations)

        # No matches -> ask for clarification
        return self._clarify(intent="product_info", question="Which item or category are you interested in? e.g. 'chocolate cake' or 'pastries under $4'")
