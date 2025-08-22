"""Product Info Agent: handles menu lookups and recommendations using the database."""
from .base_agent import BaseAgent
from typing import Dict, Any, List
from ..data.database import SessionLocal
from ..data.models import Product
from ..schemas.io_models import Citation
from sqlalchemy import or_

class ProductInfoAgent(BaseAgent):
    name = "product_info"

    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: List[Dict[str, Any]]) -> Dict[str, Any]:
        print(f"[WORKFLOW] Executing ProductInfoAgent...")
        db = SessionLocal()
        try:
            q = query or ""
            facts: Dict[str, Any] = {"items": []}
            citations: List[Citation] = []

            # Extract entities from session
            entities = {}
            if isinstance(session, list) and session:
                for msg in reversed(session):
                    if isinstance(msg, dict) and msg.get("role") == "nlu" and isinstance(msg.get("message"), dict):
                        entities = msg.get("message", {})
                        break
            
            price_min = entities.get("price_min")
            price_max = entities.get("price_max")
            requested_time = entities.get("time")

            # Build database query
            db_query = db.query(Product)

            # Search query against name, description, and category
            if q:
                search_term = f"%{q}%"
                # Simple category heuristics
                category_terms = [cat for cat in ["cakes", "pastries", "breads", "specialty"] if cat.rstrip('s') in q or cat in q]
                if category_terms:
                    db_query = db_query.filter(Product.category.ilike(f"%{category_terms[0]}%"))
                else:
                    db_query = db_query.filter(
                        or_(
                            Product.name.ilike(search_term),
                            Product.description.ilike(search_term)
                        )
                    )

            # Apply price filtering
            if price_min is not None:
                db_query = db_query.filter(Product.price >= float(price_min))
            if price_max is not None:
                db_query = db_query.filter(Product.price <= float(price_max))

            matches = db_query.all()

            # Format facts if matches found
            if matches:
                items_out = []
                for m in matches:
                    items_out.append({
                        "name": m.name,
                        "price": m.price,
                        "description": m.description,
                        "category": m.category,
                        "in_stock": m.quantity_in_stock > 0
                    })
                facts["items"] = items_out
                if requested_time:
                    facts["requested_time"] = requested_time
                
                citations.append(Citation(source="database:products", snippet=", ".join([it["name"] for it in items_out[:5]])))
                return self._ok(intent="product_info", facts=facts, context_docs=[], citations=citations)

            # No matches -> ask for clarification
            return self._clarify(intent="product_info", question="Which item or category are you interested in? e.g. 'chocolate cake' or 'pastries under $4'")
        finally:
            db.close()
