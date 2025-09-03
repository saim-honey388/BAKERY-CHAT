"""Product Info Agent: handles menu lookups and recommendations using the database."""
from .base_agent import BaseAgent
from typing import Dict, Any, List
from ..data.database import SessionLocal
from ..data.models import Product
from ..schemas.io_models import Citation
from sqlalchemy import or_
import json

class ProductInfoAgent(BaseAgent):
    name = "product_info"

    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: List[Dict[str, Any]] = None, memory_context: Dict[str, Any] = None) -> Dict[str, Any]:
        print(f"[WORKFLOW] Executing ProductInfoAgent...")
        
        # NEW: Use memory context for enhanced understanding
        if memory_context:
            print(f"[MEMORY] Using memory context: {len(memory_context.get('important_features', []))} features")
            if memory_context.get('summary'):
                print(f"[MEMORY] Summary: {memory_context['summary']}")
        
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
            
            # NEW: Use LLM to enhance entity extraction with memory context
            if memory_context:
                enhanced_entities = self._enhance_entities_with_llm(query, entities, memory_context)
                entities.update(enhanced_entities)
                print(f"[LLM] Enhanced entities: {enhanced_entities}")
            
            price_min = entities.get("price_min")
            price_max = entities.get("price_max")
            requested_time = entities.get("time")

            # Build database query (STRICT: DB is source of truth)
            db_query = db.query(Product)

            # Search query against name and description only; prefer exact DB matches
            if q:
                search_term = f"%{q}%"
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

            # No matches -> strict handling: do NOT invent items. Offer closest in-DB alternatives.
            # Try a loose similarity on token(s) in the query to find suggestions
            suggestions: List[Product] = []
            try:
                tokens = [t for t in q.lower().split() if len(t) > 2]
                if tokens:
                    token_filters = [Product.name.ilike(f"%{t}%") for t in tokens]
                    token_desc_filters = [Product.description.ilike(f"%{t}%") for t in tokens]
                    suggestions = (
                        db.query(Product)
                        .filter(or_(*token_filters, *token_desc_filters))
                        .limit(5)
                        .all()
                    )
            except Exception:
                suggestions = []

            if suggestions:
                facts["suggested_items"] = [
                    {"name": s.name, "price": s.price, "category": s.category, "in_stock": s.quantity_in_stock > 0}
                    for s in suggestions
                ]

            # Signal unavailability and request clarification anchored to DB
            facts.update({
                "unavailable": True,
                "strict_db_only": True
            })
            return self._clarify(
                intent="product_info",
                question="We don't have that exact item. Would you like one of the suggested items, or tell me a specific item from our menu?"
            )
        finally:
            db.close()
    
    def _enhance_entities_with_llm(self, query: str, entities: Dict[str, Any], memory_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to enhance entity extraction with memory context."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            prompt = f"""
            You are analyzing a user query about bakery products to extract enhanced entity information.
            
            User Query: "{query}"
            
            Current Entities: {entities}
            
            Memory Context: {memory_context if memory_context else "None"}
            
            Extract additional product-related information in JSON format:
            {{
                "product_name": "specific product mentioned",
                "category": "product category (cakes, breads, pastries, etc.)",
                "price_min": "minimum price if mentioned",
                "price_max": "maximum price if mentioned",
                "preferences": ["user preferences from memory context"],
                "quantity": "quantity if mentioned",
                "special_requirements": "dietary restrictions or special needs"
            }}
            
            Guidelines:
            - Use memory context to understand user preferences
            - Extract implicit information (e.g., "something sweet" = desserts)
            - Consider previous interactions and preferences
            - Return valid JSON only
            """
            
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {}
                
        except Exception as e:
            print(f"LLM entity enhancement failed: {e}")
            return {}
