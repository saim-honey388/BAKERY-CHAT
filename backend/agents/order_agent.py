"""Order Agent: handles order creation and persistence using the database.

Enhanced to maintain a per-session cart, offer upsells, require explicit
confirmation, and collect missing details for pickup or delivery.
"""
from .base_agent import BaseAgent
from ..schemas.io_models import AgentResult
from typing import List, Dict, Any
from ..data.database import SessionLocal
from ..data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
from ..nlu.entity_extractor import EntityExtractor
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import re
import datetime
import json

class OrderAgent(BaseAgent):
    name = "order"
    
    class ShoppingCart:
        def __init__(self):
            self.items = []  # List of dicts: {'product': Product, 'quantity': int}
            self.customer_info = {}
            self.delivery_info = {}
            self.pickup_info = {}
            self.fulfillment_type = None  # 'delivery' or 'pickup'
            self.payment_method = None  # 'cash'|'card'|'upi'
            self.awaiting_fulfillment = False
            self.awaiting_details = False
            self.awaiting_confirmation = False
            self.last_prompt = None  # Track the last prompt type for confirmation logic
            self.last_suggested_items = []  # Track suggested items for "that one" references
            self.branch_name = None  # Selected branch for pickup/delivery
            self.expected_field = None  # When awaiting_details, which specific field is expected next
            
        def add_item(self, product, quantity):
            """Add an item to the cart or update quantity if it already exists."""
            for item in self.items:
                if item['product'].id == product.id:
                    item['quantity'] += quantity
                    return
            self.items.append({'product': product, 'quantity': quantity})
            
        def remove_item(self, product_id):
            """Remove an item from the cart."""
            self.items = [item for item in self.items if item['product'].id != product_id]
            
        def clear(self):
            """Clear the entire cart."""
            self.items = []
            self.customer_info = {}
            self.delivery_info = {}
            self.pickup_info = {}
            self.fulfillment_type = None
            self.payment_method = None
            self.awaiting_fulfillment = False
            self.awaiting_details = False
            self.awaiting_confirmation = False
            self.last_prompt = None
            self.last_suggested_items = []
            self.expected_field = None
            
        def get_total(self):
            """Calculate the total price of items in the cart."""
            return sum(item['product'].price * item['quantity'] for item in self.items)
            
        def get_summary(self):
            """Generate a summary of the cart contents."""
            summary = []
            for item in self.items:
                product = item['product']
                summary.append(f"- {item['quantity']}x {product.name}: ${product.price * item['quantity']:.2f}")
            summary.append(f"\nTotal: ${self.get_total():.2f}")
            return "\n".join(summary)

        def build_receipt(self, order_id: int = None, tax_rate: float = 0.0825) -> str:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            lines = []
            lines.append("Sunrise Bakery — Order Receipt")
            lines.append(now + (f"  •  Order #{order_id}" if order_id else ""))
            lines.append("")
            lines.append("Items:")
            subtotal = 0.0
            for item in self.items:
                unit = float(item['product'].price)
                qty = int(item['quantity'])
                line_total = unit * qty
                subtotal += line_total
                lines.append(f"- {qty} x {item['product'].name} — ${unit:.2f} ea  = ${line_total:.2f}")
            tax = subtotal * tax_rate
            total = subtotal + tax
            lines.append("")
            lines.append(f"Subtotal: ${subtotal:.2f}")
            lines.append(f"Tax (8.25%): ${tax:.2f}")
            lines.append(f"Total: ${total:.2f}")
            lines.append("")
            if self.fulfillment_type == 'pickup':
                lines.append("Fulfillment: Pickup")
                if self.pickup_info.get('pickup_time'):
                    lines.append(f"Pickup Time: {self.pickup_info['pickup_time']}")
            elif self.fulfillment_type == 'delivery':
                lines.append("Fulfillment: Delivery")
                if self.delivery_info.get('address'):
                    lines.append(f"Address: {self.delivery_info['address']}")
                if self.delivery_info.get('delivery_time'):
                    lines.append(f"Delivery Time: {self.delivery_info['delivery_time']}")
            if self.customer_info.get('name'):
                lines.append(f"Customer: {self.customer_info['name']}")
            if self.customer_info.get('phone_number'):
                lines.append(f"Phone: {self.customer_info['phone_number']}")
            if self.payment_method:
                lines.append(f"Payment: {self.payment_method.capitalize()}")
            return "\n".join(lines)

    # --- New: business hour validation ---
    @staticmethod
    def _parse_hour_str_to_time(hour_str: str):
        from datetime import time
        import re
        s = (hour_str or "").strip()
        if not s:
            return None
        # 12-hour format: 1, 1:30 am/pm
        m12 = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", s, re.IGNORECASE)
        if m12:
            hh = int(m12.group(1)) % 12
            mm = int(m12.group(2) or 0)
            if m12.group(3).lower() == 'pm':
                hh += 12
            return time(hh, mm)
        # 24-hour format: 0-23 or 00:00-23:59
        m24 = re.match(r"^(\d{1,2})(?::(\d{2}))$", s)
        if m24:
            hh = int(m24.group(1))
            mm = int(m24.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return time(hh, mm)
        m24h = re.match(r"^(\d{1,2})$", s)
        if m24h:
            hh = int(m24h.group(1))
            if 0 <= hh <= 23:
                return time(hh, 0)
        return None

    @staticmethod
    def _format_time_12h(t) -> str:
        # Format datetime.time to 'H am/pm' or 'H:MM am/pm'
        if t is None:
            return None
        h = t.hour
        m = t.minute
        ampm = 'am' if h < 12 else 'pm'
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        if m == 0:
            return f"{h12} {ampm}"
        return f"{h12}:{m:02d} {ampm}"

    @staticmethod
    def _load_locations():
        import json, os
        path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "locations.json")
        path = os.path.abspath(path)
        with open(path, 'r') as f:
            return json.load(f)

    @classmethod
    def _get_branch_hours_for_datetime(cls, branch_name: str, dt) -> tuple:
        """Return (open_time, close_time) for the given branch and datetime.date().
        Falls back to (time(8,0), time(18,0)) if parsing fails.
        """
        from datetime import time
        import re
        try:
            locations = cls._load_locations()
            branch = next((b for b in locations if b.get('name', '').lower().startswith(branch_name.lower())), None)
            if not branch:
                return time(8, 0), time(18, 0)
            hours_str = branch.get('hours', '')
            weekday = dt.weekday()  # 0=Mon ... 6=Sun
            # crude rules: check blocks separated by commas
            blocks = [blk.strip() for blk in hours_str.split(',')]
            day_label = {0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday'}[weekday]
            # pick block that mentions today or a range covering today
            chosen = None
            for blk in blocks:
                low = blk.lower()
                if 'monday-sunday' in low:
                    chosen = blk
                    break
                if 'monday-friday' in low and weekday <= 4:
                    chosen = blk
                if 'saturday' in low and weekday == 5:
                    chosen = blk
                if 'sunday' in low and weekday == 6:
                    chosen = blk
                if day_label in low:
                    chosen = blk
            if not chosen:
                return time(8, 0), time(18, 0)
            # extract times like 6am-8pm
            m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))", chosen, re.IGNORECASE)
            if not m:
                return time(8, 0), time(18, 0)
            open_t = cls._parse_hour_str_to_time(m.group(1)) or time(8, 0)
            close_t = cls._parse_hour_str_to_time(m.group(2)) or time(18, 0)
            return open_t, close_t
        except Exception:
            return time(8, 0), time(18, 0)

    @classmethod
    def _is_time_within_business_hours(cls, iso_timestamp: str, branch_name: str = None) -> bool:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso_timestamp)
            if branch_name:
                open_t, close_t = cls._get_branch_hours_for_datetime(branch_name, dt)
            else:
                from datetime import time
                open_t, close_t = time(8, 0), time(18, 0)
            return open_t <= dt.time() <= close_t
        except Exception:
            return False

    def __init__(self):
        self.carts: Dict[str, OrderAgent.ShoppingCart] = {}  # session_id -> ShoppingCart
        self.last_receipt_by_session: Dict[str, str] = {}  # Store last receipt per session
        self.entity_extractor = EntityExtractor()

    @staticmethod
    def _is_branch_name(value: str) -> bool:
        """Return True if the provided value matches a known branch name/prefix."""
        try:
            if not value:
                return False
            val = str(value).strip().lower()
            locations = OrderAgent._load_locations()
            for b in locations:
                name = (b.get('name') or '').strip().lower()
                if not name:
                    continue
                if val == name or val.startswith(name) or name.startswith(val):
                    return True
            return False
        except Exception:
            return False

    def get_cart_state(self, session_id: str) -> Dict[str, Any]:
        cart = self.carts.get(session_id)
        if not cart:
            return {"has_cart": False}
        return {
            "has_cart": bool(cart.items),
            "awaiting_fulfillment": cart.awaiting_fulfillment,
            "awaiting_details": cart.awaiting_details,
            "awaiting_confirmation": cart.awaiting_confirmation,
            "cart_items": len(cart.items),
        }

    def _is_strong_confirmation(self, query: str) -> bool:
        """Tightened confirmation logic - only strong confirmations when awaiting confirmation."""
        ql = query.lower().strip()
        
        # Strong confirmation phrases
        strong_confirmations = [
            "yes", "confirm", "place order", "place the order", "place my order",
            "that's correct", "that is correct", "sounds good", "looks good",
            "proceed", "go ahead", "finalize", "complete order", "submit order",
            "yes please", "yes that's right", "yes that is right", "yes place it",
            "place it", "order it", "buy it", "purchase", "checkout", "finalize order"
        ]
        
        # Negation guard - reject if contains these
        negation_words = ["not", "wait", "hold on", "change", "add more", "no", "cancel", "stop"]
        
        # Check for negation first
        if any(word in ql for word in negation_words):
            return False
            
        # Check for strong confirmation
        return any(phrase in ql for phrase in strong_confirmations)

    # --- New: robust fulfillment detection (handles typos/variants) ---
    @staticmethod
    def _detect_fulfillment(text: str):
        """Return 'pickup', 'delivery', or None based on robust keyword/typo detection.

        This avoids relying on the LLM wording and catches common misspellings:
        - pickup variants: 'pickup', 'pick up', 'pick-up', 'pic up', 'picup', 'pik up', 'pick it up'
        - delivery variants: 'deliver', 'delivery', 'deliver it', 'send', 'send to', 'ship to'
        """
        ql = (text or "").lower().strip()
        # normalize repeated spaces and simple punctuation
        ql_norm = re.sub(r"[^a-z0-9\s]", " ", ql)
        ql_norm = re.sub(r"\s+", " ", ql_norm)

        pickup_patterns = [
            r"\bpick\s*up\b",
            r"\bpick\-up\b",
            r"\bpickup\b",
            r"\bpic\s*up\b",
            r"\bpicup\b",
            r"\bpik\s*up\b",
            r"\bpick\s*it\s*up\b",
            r"\bcome\s*(get|pick)\s*(it)?\b",
        ]
        delivery_patterns = [
            r"\bdeliver(y)?\b",
            r"\bdeliver\s*it\b",
            r"\bsend\b",
            r"\bsend\s*to\b",
            r"\bship\s*to\b",
            r"\baddress\b",
        ]

        for pat in pickup_patterns:
            if re.search(pat, ql_norm):
                return 'pickup'
        for pat in delivery_patterns:
            if re.search(pat, ql_norm):
                return 'delivery'
        return None
    
    def _detect_fulfillment_with_llm(self, query: str, memory_context: Dict[str, Any] = None) -> str:
        """Use LLM to detect fulfillment type instead of hardcoded patterns."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Create prompt for LLM-based fulfillment detection
            prompt = f"""
            You are analyzing a user query to determine their fulfillment preference for a bakery order.
            
            User Query: "{query}"
            
            Memory Context: {memory_context if memory_context else "None"}
            
            Determine if the user wants:
            1. "pickup" - if they want to collect the order themselves
            2. "delivery" - if they want the order delivered to them
            3. "none" - if it's unclear or not mentioned
            
            Consider:
            - Keywords like "pickup", "delivery", "collect", "bring", "send"
            - Context from memory (previous preferences, location mentions)
            - Implicit preferences (e.g., "I'll come get it" = pickup)
            
            Respond with ONLY: pickup, delivery, or none
            """
            
            # Use Primary API for this decision
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse response
            response_lower = response.lower().strip()
            if 'pickup' in response_lower:
                return 'pickup'
            elif 'delivery' in response_lower:
                return 'delivery'
            else:
                return None
                
        except Exception as e:
            print(f"LLM fulfillment detection failed: {e}")
            # Fallback to basic pattern matching
            return self._detect_fulfillment_fallback(query)
    
    def _detect_fulfillment_fallback(self, query: str) -> str:
        """Fallback fulfillment detection when LLM fails."""
        return self._detect_fulfillment(query)
    
    def _extract_entities_with_llm(self, query: str, memory_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to extract all entities from complex query instead of hardcoded patterns."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Create prompt for comprehensive entity extraction
            prompt = f"""
            You are analyzing a complex user query for a bakery order system.
            
            User Query: "{query}"
            
            Memory Context: {memory_context if memory_context else "None"}
            
            Extract ALL relevant information in JSON format:
            {{
                "name": "customer name if mentioned",
                "phone_number": "phone number if mentioned",
                "payment_method": "payment method if mentioned (cash/card/upi)",
                "location": "branch/location if mentioned (downtown/westside/mall)",
                "time": "time if mentioned (pickup/delivery time)",
                "address": "delivery address if mentioned",
                "items": ["items mentioned in query"],
                "quantities": ["quantities for items"],
                "fulfillment_preference": "pickup/delivery preference if mentioned"
            }}
            
            Guidelines:
            - Extract ALL mentioned information, even if implicit
            - Handle typos and variations (e.g., "pic up" = pickup)
            - Consider context from memory (previous preferences)
            - Be comprehensive in extraction
            - Return valid JSON only
            """
            
            # Use Enhanced API for entity extraction
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {}
                
        except Exception as e:
            print(f"LLM entity extraction failed: {e}")
            # Fallback to basic entity extractor
            return self.entity_extractor.extract(query) if self.entity_extractor else {}
    
    def _build_llm_context(self, session: List[Dict[str, str]], cart: "OrderAgent.ShoppingCart", memory_context: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Build a single authoritative context object for LLM decisions."""
        try:
            from ..app.prompt_builder import PromptBuilder
        except Exception:
            PromptBuilder = None  # Optional; fail-soft

        # Last 10 messages (user/assistant) with clear role distinction and sequence
        last_10_messages = []
        try:
            for i, m in enumerate((session or [])[-10:], 1):
                if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                    role = m.get("role")
                    message = m.get("message", "")
                    
                    # Add context markers to prevent confusion
                    if role == "user":
                        # User messages - these are actual requests/intents
                        last_10_messages.append({
                            "sequence": i,
                            "role": "USER_REQUEST", 
                            "message": message,
                            "type": "user_intent",
                            "note": "This is what the USER asked for - treat as actual request"
                        })
                    elif role == "assistant":
                        # Bot responses - these are suggestions/clarifications, NOT user requests
                        last_10_messages.append({
                            "sequence": i,
                            "role": "BOT_RESPONSE", 
                            "message": message,
                            "type": "bot_suggestion",
                            "note": "This is what the BOT suggested/asked - do NOT treat as user request"
                        })
        except Exception:
            last_10_messages = []

        # Cart snapshot
        cart_snapshot = {
            "items": [
                {"name": it['product'].name, "quantity": it['quantity'], "price": float(it['product'].price)}
                for it in (cart.items or [])
            ],
            "customer_info": dict(cart.customer_info or {}),
            "fulfillment_type": cart.fulfillment_type,
            "payment_method": cart.payment_method,
            "branch": cart.branch_name,
            "awaiting": {
                "fulfillment": bool(cart.awaiting_fulfillment),
                "details": bool(cart.awaiting_details),
                "confirmation": bool(cart.awaiting_confirmation),
            },
        }

        # Known/missing details
        try:
            missing = self._get_missing_details(cart)
        except Exception:
            missing = []
        known = {
            "name": cart.customer_info.get("name") if isinstance(cart.customer_info, dict) else None,
            "phone": cart.customer_info.get("phone_number") if isinstance(cart.customer_info, dict) else None,
            "fulfillment": cart.fulfillment_type,
            "branch": cart.branch_name,
            "payment": cart.payment_method,
        }

        # Prompt rules (common + order)
        rules = {}
        if PromptBuilder is not None:
            try:
                pb = PromptBuilder()
                rules["common"] = pb.common_prompt
                rules["order"] = pb.agent_prompts.get("order")
            except Exception:
                rules = {}

        # DB catalog summary (names only) to prevent hallucination
        try:
            products = db.query(Product).all()
            catalog = [p.name for p in products]
        except Exception:
            catalog = []

        # Locations data (branches + hours) for LLM reasoning
        try:
            locations = self._load_locations()
        except Exception:
            locations = []

        unified = {
            "summary": memory_context.get("summary") if isinstance(memory_context, dict) else None,
            "last_10_messages": last_10_messages,
            "cart": cart_snapshot,
            "known_details": known,
            "missing_details": missing,
            "rules": rules,
            "db_catalog": catalog,
            "locations": locations,
            "weights": {
                "cart_state": 1.0,
                "last_10_messages": 0.8,
                "important_features": 0.6,
                "summary": 0.4,
            },
        }

        # Debug: confirm summary presence and show conversation context
        try:
            has_summary = bool(unified.get("summary"))
            print(f"[LLM CTX] Summary present: {has_summary}")
            print(f"[LLM CTX] Last {len(unified.get('last_10_messages', []))} messages:")
            for msg in unified.get('last_10_messages', [])[-3:]:  # Show last 3
                seq = msg.get('sequence', '?')
                role = msg.get('role', '?')
                message = msg.get('message', '')[:50]
                print(f"  {seq}. {role}: {message}...")
        except Exception:
            pass

        return unified

    def _build_preview_receipt(self, cart: ShoppingCart) -> str:
        """Build a preview receipt for user confirmation before placing order."""
        lines = []
        lines.append("=" * 50)
        lines.append("ORDER PREVIEW - Please Review Before Confirmation")
        lines.append("=" * 50)
        lines.append("")
        
        # Items
        lines.append("ITEMS:")
        subtotal = 0.0
        for item in cart.items:
            product = item['product']
            quantity = item['quantity']
            unit_price = float(product.price)
            line_total = unit_price * quantity
            subtotal += line_total
            lines.append(f"  {quantity}x {product.name} @ ${unit_price:.2f} = ${line_total:.2f}")
        
        lines.append("")
        lines.append(f"Subtotal: ${subtotal:.2f}")
        tax = subtotal * 0.0825  # 8.25% tax
        total = subtotal + tax
        lines.append(f"Tax (8.25%): ${tax:.2f}")
        lines.append(f"TOTAL: ${total:.2f}")
        lines.append("")
        
        # Customer details
        lines.append("CUSTOMER DETAILS:")
        if cart.customer_info.get('name'):
            lines.append(f"  Name: {cart.customer_info['name']}")
        if cart.customer_info.get('phone_number'):
            lines.append(f"  Phone: {cart.customer_info['phone_number']}")
        
        # Fulfillment details
        lines.append("")
        lines.append("FULFILLMENT:")
        if cart.fulfillment_type == 'pickup':
            lines.append(f"  Type: Pickup")
            if cart.pickup_info.get('pickup_time'):
                lines.append(f"  Time: {cart.pickup_info['pickup_time']}")
            if cart.branch_name:
                lines.append(f"  Branch: {cart.branch_name}")
        elif cart.fulfillment_type == 'delivery':
            lines.append(f"  Type: Delivery")
            if cart.delivery_info.get('address'):
                lines.append(f"  Address: {cart.delivery_info['address']}")
            if cart.delivery_info.get('delivery_time'):
                lines.append(f"  Time: {cart.delivery_info['delivery_time']}")
        
        # Payment
        if cart.payment_method:
            lines.append(f"  Payment: {cart.payment_method.capitalize()}")
        
        lines.append("")
        lines.append("IMPORTANT:")
        lines.append("- You can modify any details before confirming")
        lines.append("- Say 'confirm' to place this order")
        lines.append("- Say 'cancel' to clear the cart")
        lines.append("- Say 'modify' to change any details")
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)

    def _create_product_embeddings(self, db: Session) -> Dict[str, List[float]]:
        """Create embeddings for all products to enable better similarity search."""
        try:
            from ..app.embed import EmbeddingClient
            
            # Get all products
            products = db.query(Product).all()
            embeddings = {}
            
            # Initialize embedding client
            embed_gen = EmbeddingClient()
            
            for product in products:
                # Create rich product description for embedding
                desc = f"{product.name}"
                if hasattr(product, 'category') and product.category:
                    desc += f" {product.category}"
                if hasattr(product, 'description') and product.description:
                    desc += f" {product.description}"
                
                # Generate embedding
                try:
                    embedding = embed_gen.generate_embedding(desc)
                    if embedding:
                        embeddings[product.name] = embedding
                        print(f"[EMBEDDINGS] Created embedding for {product.name}")
                except Exception as e:
                    print(f"[EMBEDDINGS] Failed to create embedding for {product.name}: {e}")
                    continue
            
            print(f"[EMBEDDINGS] Successfully created {len(embeddings)} product embeddings")
            return embeddings
            
        except ImportError:
            print("[EMBEDDINGS] EmbeddingGenerator not available")
            return {}
        except Exception as e:
            print(f"[EMBEDDINGS] Error creating product embeddings: {e}")
            return {}

    def _handle_order_with_llm(self, query: str, cart: ShoppingCart, memory_context: Dict[str, Any], db: Session, session: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Use LLM to handle COMPLETE order management - no hardcoded logic."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Get database info for LLM context
            products = db.query(Product).all()
            product_info = {p.name.lower(): {"id": p.id, "price": p.price, "stock": p.quantity_in_stock} for p in products}
            
            # Unified authoritative context for LLM
            unified_context = self._build_llm_context(session=session or [], cart=cart, memory_context=memory_context or {}, db=db)
            prompt = f"""
            You are an AI managing a complete bakery order system.

            User Query: "{query}"

            CONTEXT (authoritative): {json.dumps(unified_context)}

            Available Products (DB): {product_info}

            Output STRICT JSON with this structure:
            {{
                "cart_updates": [
                    {{
                        "type": "add_item/remove_item/update_customer_info/set_fulfillment/modify_item",
                        "product": "product_name",
                        "quantity": 1,
                        "info": {{"field": "value"}},
                        "fulfillment_type": "pickup/delivery"
                    }}
                ],
                "cart_state": {{
                    "awaiting_details": true/false,
                    "awaiting_confirmation": true/false,
                    "awaiting_fulfillment": true/false
                }},
                "response_type": "ask_details/confirm_order/show_receipt/upsell/modify_cart",
                "message": "what to say to user",
                "inventory_suggestions": ["similar products if requested item not available"]
            }}

            CRITICAL RULES:
            - Treat SERVER CART as ground truth; never remove items or change quantities unless the USER explicitly asks in THIS turn.
            - Do NOT suggest "clear_cart" or remove items unless the USER explicitly asks.
            - Only add items if the USER explicitly asked for them in THIS turn.
            - NEVER set fulfillment_type to anything other than exactly "pickup" or "delivery". 
            - If user mentions payment method but fulfillment is unclear, ask "Would you like pickup or delivery?"
            - Only set customer fields that the USER provided in THIS turn.
            - NEVER invent items not in db_catalog. If unclear, ask a short, DB-anchored clarification.
            - For quantity changes: If user says "I want 3 cheesecakes" and cart has 1, use modify_item to set quantity to 3 (not add 3).
            - Always validate fulfillment_type is exactly "pickup" or "delivery" before proceeding.
            - When user mentions a specific quantity for an existing item, use modify_item type, not add_item.
            - TIME/BRANCH FLOW: For pickup orders, you MUST ask for pickup time first, then branch name. When user provides branch name, validate the previously provided time against that branch's hours. If time is outside hours, ask user to choose a time within the branch's open-close window.
            - TIME VALIDATION: Use context.locations to validate pickup/delivery times against the selected branch hours; if time is outside hours, do NOT set it. Ask the user to choose a time within that branch's open-close window.
            - NAME PROTECTION: Never set customer name to generic/command/location terms: ["modify","change","edit","update","confirm","confirmation","yes","ok","okay","pickup","pick up","delivery","downtown","branch","location"].
            - CART AUTHORITY: Treat the provided cart snapshot as authoritative; do not clear or reset it. Propose explicit cart_updates only.
            
            CONVERSATION CONTEXT RULES (CRITICAL):
            - USER_REQUEST messages contain actual user intents - treat these as real requests
            - BOT_RESPONSE messages are bot suggestions/clarifications - NEVER treat these as user requests
            - Example: If bot asked "Would you like delivery or pickup?" and user said "delivery", only "delivery" is the user request
            - Example: If bot suggested "We also have croissants" - this is NOT a user request to add croissants
            - Only act on USER_REQUEST content, ignore BOT_RESPONSE content for user intent
            - Sequence numbers show conversation order - higher numbers are more recent
            - Current user query is the LATEST USER_REQUEST in the sequence
            
            - TIME VALIDATION: Use context.locations to validate any provided pickup/delivery time against the selected branch hours; if out-of-hours, do NOT set the time and ask the user to choose a time within the branch window.
            - NAME PROTECTION: Never set name to generic/command/location terms: ["modify","change","edit","update","confirm","confirmation","yes","ok","okay","pickup","pick up","delivery","downtown","branch","location"].
            - CART AUTHORITY: Treat the provided cart snapshot as authoritative; do not clear/reset it from memory. Propose explicit cart_updates only.
            - MODIFY BEHAVIOR: If user says "modify" without specifics, return response_type: "modify_cart" and a short clarification question; when specifics are provided, update only that field and then propose confirmation.
            
            ORDER FLOW REQUIREMENTS:
            1. For pickup orders: Ask for pickup time first, then branch name
            2. When branch is provided: Validate the pickup time against branch hours
            3. If time is invalid: Ask user to choose a time within branch hours
            4. Only proceed to confirmation when all details are complete
            5. When user says "confirm" after seeing preview: Finalize the order
            
            - Think step-by-step privately. Then respond with ONLY valid JSON (no comments, no prose).
            - Return valid JSON only.
            """
            
            # Use Enhanced API for complete order management
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                # Validate LLM decisions before returning
                result = self._validate_llm_decisions(result, cart)
                return result
            else:
                return {}
                
        except Exception as e:
            print(f"LLM order management failed: {e}")
            # Fallback to basic logic
            return {
                "cart_updates": [],
                "cart_state": {"awaiting_details": False, "awaiting_confirmation": False, "awaiting_fulfillment": True},
                "response_type": "fallback",
                "message": "I need more details for your order."
            }
    
    def _add_item_to_cart(self, cart: ShoppingCart, product_name: str, quantity: int, db: Session):
        """Add item to cart with database validation."""
        try:
            # Find product in database
            product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
            if product and product.quantity_in_stock >= quantity:
                # Add to cart
                cart.add_item(product, quantity)
                print(f"DEBUG: Added {quantity}x {product.name} to cart")
                return {"success": True, "product": product, "message": f"Added {quantity}x {product.name} to cart"}
            else:
                # Find similar products for suggestions using enhanced embedding-based similarity
                suggestions = self._find_similar_products_enhanced(product_name, db)
                if not product:
                    print(f"DEBUG: Product {product_name} not found")
                    return {"success": False, "message": f"Sorry, we don't have {product_name}.", "suggestions": suggestions}
                else:
                    print(f"DEBUG: Insufficient stock for {product_name}. Available: {product.quantity_in_stock}, Requested: {quantity}")
                    return {"success": False, "message": f"Sorry, we only have {product.quantity_in_stock} {product.name} in stock.", "suggestions": suggestions}
        except Exception as e:
            print(f"DEBUG: Error adding item to cart: {e}")
            return {"success": False, "message": f"Error adding item: {str(e)}"}
    
    def _find_similar_products_enhanced(self, product_name: str, db: Session) -> List[str]:
        """Find similar products using embedding-based cosine similarity for better suggestions."""
        try:
            # Try to use the existing retrieval system for embeddings
            try:
                from ..app.retrieval import HybridRetriever
                retriever = HybridRetriever()
                
                # Get product descriptions and names for similarity search
                all_products = db.query(Product).filter(Product.quantity_in_stock > 0).all()
                
                # Create product descriptions for embedding
                product_descriptions = []
                for product in all_products:
                    # Combine name, category, and description for better context
                    desc = f"{product.name} {product.category if hasattr(product, 'category') else ''}"
                    if hasattr(product, 'description') and product.description:
                        desc += f" {product.description}"
                    product_descriptions.append({
                        'product': product,
                        'description': desc
                    })
                
                # Use the retriever to find similar products
                similar_products = retriever.hybrid_search(product_name, k=10)
                
                # Extract product names from similar results
                suggestions = []
                for result in similar_products:
                    # Try to find the product in our database
                    for prod_desc in product_descriptions:
                        if prod_desc['description'].lower() in result.get('text', '').lower():
                            suggestions.append(prod_desc['product'].name)
                            break
                
                # Fallback to basic text matching if embedding search fails
                if not suggestions:
                    print("[SIMILARITY] Embedding search failed, using fallback text matching")
                    return self._find_similar_products_fallback(product_name, db)
                
                # Remove duplicates and limit results
                unique_suggestions = list(dict.fromkeys(suggestions))[:5]
                print(f"[SIMILARITY] Found {len(unique_suggestions)} similar products using embeddings")
                return unique_suggestions
                
            except ImportError:
                print("[SIMILARITY] HybridRetriever not available, using fallback")
                return self._find_similar_products_fallback(product_name, db)
            except Exception as e:
                print(f"[SIMILARITY] Embedding search error: {e}, using fallback")
                return self._find_similar_products_fallback(product_name, db)
                
        except Exception as e:
            print(f"[SIMILARITY] Enhanced similarity search failed: {e}")
            return self._find_similar_products_fallback(product_name, db)
    
    def _find_similar_products_fallback(self, product_name: str, db: Session) -> List[str]:
        """Fallback method using basic text matching when embeddings are not available."""
        try:
            # Convert product name to searchable terms
            search_terms = product_name.lower().split()
            
            # Get all products
            all_products = db.query(Product).filter(Product.quantity_in_stock > 0).all()
            suggestions = []
            
            for product in all_products:
                product_lower = product.name.lower()
                # Check if any search term matches
                if any(term in product_lower for term in search_terms):
                    suggestions.append(product.name)
                # Check category-based suggestions
                elif any(term in product_lower for term in ['bread', 'cake', 'pastry', 'cookie']):
                    suggestions.append(product.name)
            
            # Limit suggestions and remove duplicates
            unique_suggestions = list(set(suggestions))[:5]
            return unique_suggestions
            
        except Exception as e:
            print(f"[SIMILARITY] Fallback similarity search failed: {e}")
            return []
    
    def _find_similar_products(self, product_name: str, db: Session) -> List[str]:
        """Find similar products when the requested product is not available."""
        try:
            # Convert product name to searchable terms
            search_terms = product_name.lower().split()
            
            # Get all products
            all_products = db.query(Product).filter(Product.quantity_in_stock > 0).all()
            suggestions = []
            
            for product in all_products:
                product_lower = product.name.lower()
                # Check if any search term matches
                if any(term in product_lower for term in search_terms):
                    suggestions.append(product.name)
                # Check category-based suggestions
                elif any(term in product_lower for term in ['bread', 'cake', 'pastry', 'cookie']):
                    suggestions.append(product.name)
            
            # Limit suggestions and remove duplicates
            unique_suggestions = list(set(suggestions))[:5]
            return unique_suggestions
            
        except Exception as e:
            print(f"DEBUG: Error finding similar products: {e}")
            return []
    
    def _remove_item_from_cart(self, cart: ShoppingCart, product_name: str):
        """Remove item from cart."""
        try:
            cart.remove_item(product_name)
            print(f"DEBUG: Removed {product_name} from cart")
        except Exception as e:
            print(f"DEBUG: Error removing item from cart: {e}")
    
    def _analyze_order_flow_with_llm(self, query: str, cart: ShoppingCart, memory_context: Dict[str, Any], db: Session, session: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Use LLM to analyze the order flow and decide what action to take."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Get database info for LLM context
            products = db.query(Product).all()
            product_info = {p.name.lower(): {"id": p.id, "price": p.price, "stock": p.quantity_in_stock} for p in products}
            
            unified_context = self._build_llm_context(session=session, cart=cart, memory_context=memory_context or {}, db=db)
            prompt = f"""
            You are analyzing a user query to determine the appropriate next order action.

            User Query: "{query}"

            CONTEXT (authoritative): {json.dumps(unified_context)}

            Available Products (DB): {product_info}

            Return STRICT JSON:
            {{
                "action": "clear_cart/checkout/show_cart/set_fulfillment/collect_details/confirm_order/show_receipt/modify_cart",
                "fulfillment_type": "pickup/delivery if setting fulfillment",
                "missing_details": ["list of missing details if collecting details"],
                "reasoning": "why you chose this action",
                "items_to_add": [
                    {{"product": "product_name", "quantity": 1}}
                ],
                "modifications": {{
                    "type": "change_fulfillment/change_customer_info/change_items/change_payment/unspecified",
                    "details": "what to change"
                }}
            }}

            CRITICAL RULES:
            - Do NOT clear, remove, or change SERVER CART unless the USER explicitly asked in THIS turn.
            - Only propose add_item if the USER asked for it in THIS turn; otherwise leave items_to_add empty.
            - Never set fulfillment to anything other than "pickup" or "delivery".
            - Only set customer fields that the USER provided in THIS turn.
            - NEVER invent items not in db_catalog. If unclear, ask a short, DB-anchored clarification.
            - TIME HANDLING: If the user provides a time and fulfillment is pickup, treat it as pickup_time, NOT a change_fulfillment. Do not modify fulfillment_type from time input.
            - MODIFICATION HANDLING: If user says "modify", "change", "edit", "update" without specifying what, return action: "modify_cart" with modifications.type: "unspecified"
            - NAME PROTECTION: Never set customer name to generic words like "modify", "change", "edit", "update" - these are commands, not names
            - CUSTOMER NAME RULE: Only set customer name if user explicitly provides a real name (not commands, not generic words)
            
            CONVERSATION CONTEXT RULES (CRITICAL):
            - USER_REQUEST messages contain actual user intents - treat these as real requests
            - BOT_RESPONSE messages are bot suggestions/clarifications - NEVER treat these as user requests
            - Example: If bot asked "Would you like delivery or pickup?" and user said "delivery", only "delivery" is the user request
            - Example: If bot suggested "We also have croissants" - this is NOT a user request to add croissants
            - Only act on USER_REQUEST content, ignore BOT_RESPONSE content for user intent
            - Sequence numbers show conversation order - higher numbers are more recent
            - Current user query is the LATEST USER_REQUEST in the sequence
            
            - TIME VALIDATION: Use context.locations to validate any provided pickup/delivery time against the selected branch hours; if out-of-hours, do NOT set the time and ask the user to choose a time within the branch window.
            - NAME PROTECTION: Never set name to generic/command/location terms: ["modify","change","edit","update","confirm","confirmation","yes","ok","okay","pickup","pick up","delivery","downtown","branch","location"].
            - CART AUTHORITY: Treat the provided cart snapshot as authoritative; do not clear/reset it from memory. Propose explicit cart_updates only.
            - MODIFY BEHAVIOR: If user says "modify", "change", "edit", "update" without specifying what, return action: "modify_cart" with modifications.type: "unspecified"
            
            ORDER FLOW REQUIREMENTS:
            1. For pickup orders: Ask for pickup time first, then branch name
            2. When branch is provided: Validate the pickup time against branch hours
            3. If time is invalid: Ask user to choose a time within branch hours
            4. Only proceed to confirmation when all details are complete
            5. When user says "confirm" after seeing preview: Finalize the order
            
            - Think step-by-step privately. Then respond with ONLY valid JSON (no comments, no prose).
            - Return valid JSON only.
            """
            
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                # Do not mutate cart here to avoid double-adds; main flow will handle updates explicitly
                return parsed
            else:
                return {}
                
        except Exception as e:
            print(f"LLM order flow analysis failed: {e}")
            return {}

    def _llm_clarify_next_step(self, query: str, cart: ShoppingCart, memory_context: Dict[str, Any], db: Session) -> "AgentResult":
        """Ask LLM for a single short next-step clarification. No item additions here."""
        try:
            from ..app.dual_api_system import DualAPISystem
            cart_items_text = ", ".join([f"{it['quantity']}x {it['product'].name}" for it in cart.items]) or "(empty)"
            # Determine the first missing field if available
            try:
                missing = self._get_missing_details(cart)
            except Exception:
                missing = []
            expected_field = cart.expected_field or (missing[0] if missing else None)
            allowed_fields = [
                'items','name','phone_number','pickup_time','address','delivery_time','payment_method','branch','fulfillment'
            ]
            prompt = f"""
            You are assisting a bakery order flow.
            Tone & Style:
            - Warm, natural, and concise (use our bakery assistant voice from system rules).
            - At most two short sentences: an optional friendly acknowledgement, then one clear question.
            - Second person ("you"), never third person.
            - If the user asked for an item, you may briefly acknowledge it in a tasty, human way (one short clause), then ask the question.
            - Do NOT add items or assume details.
            Clarification Rules:
            - Ask ONLY for the FIRST missing required field, if any.
            - Allowed fields: {allowed_fields}.
            - If an expected field is provided, ask ONLY for that field.
            - If fulfillment is not set, ask: pickup or delivery?
            - Do not ask for email.
            Context:
            - Cart: {cart_items_text}
            - Awaiting: fulfillment={cart.awaiting_fulfillment}, details={cart.awaiting_details}, confirmation={cart.awaiting_confirmation}
            - Customer: {cart.customer_info}
            - Fulfillment: {cart.fulfillment_type}
            - Branch: {cart.branch_name}
            - Payment: {cart.payment_method}
            - Expected field: {expected_field}
            - Missing details: {missing}
            - Memory: {memory_context if memory_context else 'None'}
            - User: {query}
            Respond with at most two to three short sentences: an optional friendly acknowledgement and then ONE direct question for the expected/missing field using "you".If any detail is missing, you must ask for it in the second sentence. If the user has already provided the detail, you should thank them and ask for the next detail.
            """
            dual_api = DualAPISystem()
            msg = (dual_api.generate_response_with_primary_api(prompt) or "Could you clarify what you'd like to do with your order?").strip()
            return self._ok("order", msg, {"in_order_context": bool(cart.items)})
        except Exception as e:
            print(f"LLM clarification failed: {e}")
            # Delegate even on failure with a neutral clarification
            return self._ok("order", "Could you clarify what you'd like to do with your order?", {"in_order_context": bool(cart.items)})

    def _finalize_order(self, db: Session, cart: ShoppingCart, session_id: str, memory_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Single gateway for order finalization - called from one place only."""
        print("DEBUG: Entering _finalize_order method.")
        print(f"DEBUG: Cart state before finalization: {cart.__dict__}")

        if not cart.items:
            print("DEBUG: Cart is empty. Cannot finalize order.")
            return self._llm_clarify_next_step("Your cart is empty; please specify items to add.", cart, memory_context, db)

        # Final stock check
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Checking stock for product {product.name}. Available: {product.quantity_in_stock}, Needed: {item['quantity']}")
            if product.quantity_in_stock < item['quantity']:
                print(f"DEBUG: Insufficient stock for product {product.name}.")
                qty = item['quantity']
                return self._llm_clarify_next_step(
                    f"Only {product.quantity_in_stock} {product.name} available; need {qty}.",
                    cart,
                    memory_context,
                    db,
                )

        print("DEBUG: Stock check passed. Proceeding to create customer and order.")

        # Create customer
        customer = self._find_or_create_customer(
            db, session_id, 
            cart.customer_info.get('name'), 
            cart.customer_info.get('phone_number')
        )
        print(f"DEBUG: Customer created or found. Customer ID: {customer.id}")

        # Create order (start as pending)
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.pending,
            pickup_or_delivery=FulfillmentType.pickup if cart.fulfillment_type == 'pickup' else FulfillmentType.delivery,
            total_amount=cart.get_total()
        )
        db.add(order)
        db.flush()
        print(f"DEBUG: Order created. Order ID: {order.id}")

        # Create order items and update inventory
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Before decrement - {product.name}: {product.quantity_in_stock} in stock")
            
            # Get the product from the current session to ensure SQLAlchemy tracks changes
            print(f"DEBUG: Before query - Product object dirty: {product in db.dirty}")
            print(f"DEBUG: Before query - Product object in session: {product in db}")
            print(f"DEBUG: Before query - Product ID: {product.id}")
            
            # Query the product from the current session instead of merging
            product = db.query(Product).filter(Product.id == product.id).first()
            print(f"DEBUG: After query - Product object dirty: {product in db.dirty}")
            print(f"DEBUG: After query - Product object in session: {product in db}")
            print(f"DEBUG: After query - Product ID: {product.id}")
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item['quantity'],
                price_at_time_of_order=product.price
            )
            db.add(order_item)
            
            # Decrement stock
            old_stock = product.quantity_in_stock
            product.quantity_in_stock -= item['quantity']
            print(f"DEBUG: Stock decrement - {product.name}: {old_stock} -> {product.quantity_in_stock}")
            print(f"DEBUG: After decrement - Product object dirty: {product in db.dirty}")
            print(f"DEBUG: After decrement - Product object in session: {product in db}")
            
            print(f"DEBUG: Order item created for product {product.name}. Remaining stock: {product.quantity_in_stock}")

        # Mark order as confirmed only at this confirmation step
        order.status = OrderStatus.confirmed
        db.flush()

        # Build receipt
        receipt_cart = OrderAgent.ShoppingCart()
        receipt_cart.items = list(cart.items)
        receipt_cart.fulfillment_type = cart.fulfillment_type
        receipt_cart.customer_info = dict(cart.customer_info)
        receipt_cart.payment_method = cart.payment_method

        if cart.fulfillment_type == 'pickup':
            receipt_cart.pickup_info = dict(cart.pickup_info)
        else:
            receipt_cart.delivery_info = dict(cart.delivery_info)

        receipt_text = receipt_cart.build_receipt(order_id=order.id) + "\n\nThank you! Your order has been placed successfully. We hope you enjoy your treats!"
        print("DEBUG: Receipt built.")

        # Store receipt for this session
        self.last_receipt_by_session[session_id] = receipt_text
        print(f"DEBUG: Receipt stored for session {session_id}.")

        # Store product references before clearing cart
        products_to_refresh = [item['product'] for item in cart.items]

        print("DEBUG: About to start commit process...")

        # Commit all changes to the database
        print(f"DEBUG: About to commit changes. Stock before commit:")
        for product in products_to_refresh:
            print(f"  - {product.name}: {product.quantity_in_stock}")
        
        try:
            print("DEBUG: Attempting commit...")
            db.commit()
            print("DEBUG: Commit completed successfully")
        except Exception as commit_error:
            print(f"DEBUG: Commit failed with error: {commit_error}")
            print(f"DEBUG: Error type: {type(commit_error).__name__}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return self._ok(
                "order",
                "Sorry, there was an error processing your order. Please try again.",
                {
                    "order_placed": False,
                    "error": "commit_failed",
                    "note": f"Database commit failed: {str(commit_error)}"
                }
            )
        
        print("DEBUG: Commit verification starting...")
        
        # Verify the commit worked by checking the database directly
        print(f"DEBUG: Verifying commit by querying database directly:")
        try:
            for product in products_to_refresh:
                fresh_product = db.query(Product).filter(Product.id == product.id).first()
                print(f"  - {fresh_product.name}: {fresh_product.quantity_in_stock} (from DB)")
        except Exception as verify_error:
            print(f"DEBUG: Verification failed: {verify_error}")
        
        # Force a flush to ensure changes are written to disk
        try:
            print("DEBUG: Attempting flush...")
            db.flush()
            print("DEBUG: Flush completed successfully")
        except Exception as flush_error:
            print(f"DEBUG: Flush failed: {flush_error}")
        
        print("DEBUG: Commit process completed successfully")

        # Clear cart
        cart.clear()
        print("DEBUG: Cart cleared after order finalization.")

        # Console DB snapshot - refresh objects to show updated values
        db.refresh(order)  # Refresh the order object to get updated status
        for product in products_to_refresh:
            db.refresh(product)  # Refresh product objects to get updated stock
        
        # Print updated status using refreshed objects
        print("\n--- Database Status (After Order Confirmation) ---")
        print("\n[Products - Updated Stock]")
        for product in products_to_refresh:
            print(f"- {product.name}: {product.quantity_in_stock} in stock")
        
        print(f"\n[Order #{order.id} - Confirmed]")
        print(f"- Customer ID: {order.customer_id}")
        print(f"- Status: {order.status.value}")
        print(f"- Fulfillment: {order.pickup_or_delivery.value}")
        print(f"- Total: ${order.total_amount}")
        
        print("\n[Order Items - Just Created]")
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for oi in order_items:
            print(f"- {oi.quantity}x {oi.product.name} @ ${oi.price_at_time_of_order}")
        print("-----------------------")

        print("DEBUG: Order finalized successfully.")
        return self._ok(
            "order_confirmed",
            f"Order #{order.id} confirmed successfully!",
            {
            "order_placed": True,
            "order_id": order.id,
            "receipt_text": receipt_text,
                "note": f"Order #{order.id} confirmed successfully!"
        }
        )

    @staticmethod
    def _normalize_branch_name(value: str) -> str:
        """Return the canonical branch name from locations.json matching the input, or empty string if none."""
        try:
            if not value:
                return ""
            val = str(value).strip().lower()
            locations = OrderAgent._load_locations()
            # Exact or prefix match
            for b in locations:
                name = (b.get('name') or '').strip()
                if not name:
                    continue
                low = name.lower()
                if val == low or val.startswith(low) or low.startswith(val):
                    return name
            return ""
        except Exception:
            return ""

    @classmethod
    def _is_time_str_within_branch_hours(cls, time_str: str, branch_name: str) -> bool:
        """Validate a time like '3 pm' or '11:30 am' against today's hours for the branch."""
        from datetime import datetime
        try:
            # Parse 12h time
            t = cls._parse_hour_str_to_time(time_str)
            if not t:
                return False
            # Compare to today's hours for branch
            now = datetime.now()
            open_t, close_t = cls._get_branch_hours_for_datetime(branch_name or "", now)
            return open_t <= t <= close_t
        except Exception:
            return False

    @classmethod
    def _get_branch_hours_for_datetime(cls, branch_name: str, dt) -> tuple:
        """Return (open_time, close_time) for the given branch and datetime.date().
        Falls back to (time(8,0), time(18,0)) if parsing fails.
        """
        from datetime import time
        import re
        try:
            locations = cls._load_locations()
            branch = next((b for b in locations if b.get('name', '').lower().startswith(branch_name.lower())), None)
            if not branch:
                return time(8, 0), time(18, 0)
            hours_str = branch.get('hours', '')
            weekday = dt.weekday()  # 0=Mon ... 6=Sun
            # crude rules: check blocks separated by commas
            blocks = [blk.strip() for blk in hours_str.split(',')]
            day_label = {0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday'}[weekday]
            # pick block that mentions today or a range covering today
            chosen = None
            for blk in blocks:
                low = blk.lower()
                if 'monday-sunday' in low:
                    chosen = blk
                    break
                if 'monday-friday' in low and weekday <= 4:
                    chosen = blk
                if 'saturday' in low and weekday == 5:
                    chosen = blk
                if 'sunday' in low and weekday == 6:
                    chosen = blk
                if day_label in low:
                    chosen = blk
            if not chosen:
                return time(8, 0), time(18, 0)
            # extract times like 6am-8pm
            m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))", chosen, re.IGNORECASE)
            if not m:
                return time(8, 0), time(18, 0)
            open_t = cls._parse_hour_str_to_time(m.group(1)) or time(8, 0)
            close_t = cls._parse_hour_str_to_time(m.group(2)) or time(18, 0)
            return open_t, close_t
        except Exception:
            return time(8, 0), time(18, 0)

    @classmethod
    def _is_time_within_business_hours(cls, iso_timestamp: str, branch_name: str = None) -> bool:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso_timestamp)
            if branch_name:
                open_t, close_t = cls._get_branch_hours_for_datetime(branch_name, dt)
            else:
                from datetime import time
                open_t, close_t = time(8, 0), time(18, 0)
            return open_t <= dt.time() <= close_t
        except Exception:
            return False

    def __init__(self):
        self.carts: Dict[str, OrderAgent.ShoppingCart] = {}  # session_id -> ShoppingCart
        self.last_receipt_by_session: Dict[str, str] = {}  # Store last receipt per session
        self.entity_extractor = EntityExtractor()

    def get_cart_state(self, session_id: str) -> Dict[str, Any]:
        cart = self.carts.get(session_id)
        if not cart:
            return {"has_cart": False}
        return {
            "has_cart": bool(cart.items),
            "awaiting_fulfillment": cart.awaiting_fulfillment,
            "awaiting_details": cart.awaiting_details,
            "awaiting_confirmation": cart.awaiting_confirmation,
            "cart_items": len(cart.items),
        }

    def _is_strong_confirmation(self, query: str) -> bool:
        """Tightened confirmation logic - only strong confirmations when awaiting confirmation."""
        ql = query.lower().strip()
        
        # Strong confirmation phrases
        strong_confirmations = [
            "yes", "confirm", "place order", "place the order", "place my order",
            "that's correct", "that is correct", "sounds good", "looks good",
            "proceed", "go ahead", "finalize", "complete order", "submit order",
            "yes please", "yes that's right", "yes that is right", "yes place it",
            "place it", "order it", "buy it", "purchase", "checkout", "finalize order"
        ]
        
        # Negation guard - reject if contains these
        negation_words = ["not", "wait", "hold on", "change", "add more", "no", "cancel", "stop"]
        
        # Check for negation first
        if any(word in ql for word in negation_words):
            return False
            
        # Check for strong confirmation
        return any(phrase in ql for phrase in strong_confirmations)

    def _finalize_order(self, db: Session, cart: ShoppingCart, session_id: str, memory_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Single gateway for order finalization - called from one place only."""
        print("DEBUG: Entering _finalize_order method.")
        print(f"DEBUG: Cart state before finalization: {cart.__dict__}")

        if not cart.items:
            print("DEBUG: Cart is empty. Cannot finalize order.")
            return self._llm_clarify_next_step("Your cart is empty; please specify items to add.", cart, memory_context, db)

        # Final stock check
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Checking stock for product {product.name}. Available: {product.quantity_in_stock}, Needed: {item['quantity']}")
            if product.quantity_in_stock < item['quantity']:
                print(f"DEBUG: Insufficient stock for product {product.name}.")
                qty = item['quantity']
                return self._llm_clarify_next_step(
                    f"Only {product.quantity_in_stock} {product.name} available; need {qty}.",
                    cart,
                    memory_context,
                    db,
                )

        print("DEBUG: Stock check passed. Proceeding to create customer and order.")

        # Create customer
        customer = self._find_or_create_customer(
            db, session_id, 
            cart.customer_info.get('name'), 
            cart.customer_info.get('phone_number')
        )
        print(f"DEBUG: Customer created or found. Customer ID: {customer.id}")

        # Create order
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.pending,
            pickup_or_delivery=FulfillmentType.pickup if cart.fulfillment_type == 'pickup' else FulfillmentType.delivery,
            total_amount=cart.get_total()
        )
        db.add(order)
        db.flush()
        print(f"DEBUG: Order created. Order ID: {order.id}")

        # Create order items and update inventory
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Before decrement - {product.name}: {product.quantity_in_stock} in stock")
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item['quantity'],
                price_at_time_of_order=product.price
            )
            db.add(order_item)
            
            # Decrement stock
            old_stock = product.quantity_in_stock
            product.quantity_in_stock -= item['quantity']
            print(f"DEBUG: Stock decrement - {product.name}: {old_stock} -> {product.quantity_in_stock}")
            print(f"DEBUG: Product object dirty: {product in db.dirty}")
            print(f"DEBUG: Product object in session: {product in db}")
            
            print(f"DEBUG: Order item created for product {product.name}. Remaining stock: {product.quantity_in_stock}")

        # Build receipt
        receipt_cart = OrderAgent.ShoppingCart()
        receipt_cart.items = list(cart.items)
        receipt_cart.fulfillment_type = cart.fulfillment_type
        receipt_cart.customer_info = dict(cart.customer_info)
        receipt_cart.payment_method = cart.payment_method

        if cart.fulfillment_type == 'pickup':
            receipt_cart.pickup_info = dict(cart.pickup_info)
        else:
            receipt_cart.delivery_info = dict(cart.delivery_info)

        receipt_text = receipt_cart.build_receipt(order_id=order.id) + "\n\nThank you! Your order has been placed successfully. We hope you enjoy your treats!"
        print("DEBUG: Receipt built.")

        # Store receipt for this session
        self.last_receipt_by_session[session_id] = receipt_text
        print(f"DEBUG: Receipt stored for session {session_id}.")

        # Mark order as confirmed now that stock is decremented and items recorded
        try:
            order.status = OrderStatus.confirmed
            print(f"DEBUG: Order status set to confirmed for Order ID: {order.id}")
        except Exception as e:
            print(f"DEBUG: Failed to set order status to confirmed: {e}")

        # Commit all changes to the database
        db.commit()

        # Clear cart
        cart.clear()
        print("DEBUG: Cart cleared after order finalization.")

        # Console DB snapshot
        self._print_db_status(db)

        print("DEBUG: Order finalized successfully.")
        return self._ok(
            "order_confirmed",
            f"Order #{order.id} confirmed successfully!",
            {
            "order_placed": True,
            "order_id": order.id,
            "receipt_text": receipt_text,
                "note": f"Order #{order.id} confirmed successfully!"
        }
        )

    def _print_db_status(self, db: Session):
        """Prints the current status of relevant database tables."""
        print("\n--- Database Status ---")
        
        # Print Product stock
        products = db.query(Product).all()
        print("\n[Products]")
        for p in products:
            print(f"- {p.name}: {p.quantity_in_stock} in stock")
        
        # Print Orders
        orders = db.query(Order).all()
        print("\n[Orders]")
        if not orders:
            print("No orders found.")
        else:
            for o in orders:
                try:
                    fulfillment = o.pickup_or_delivery.value if hasattr(o, 'pickup_or_delivery') and o.pickup_or_delivery else 'unknown'
                except Exception:
                    fulfillment = 'unknown'
                print(f"- Order #{o.id}: Customer {o.customer_id}, Status: {o.status.value if hasattr(o.status, 'value') else o.status}, Fulfillment: {fulfillment}")
        print("\n[Order Items]")
        order_items = db.query(OrderItem).all()
        if not order_items:
            print("No order items found.")
        else:
            for oi in order_items:
                print(f"- {oi.quantity}x {oi.product.name} (Order #{oi.order_id})")
        print("-----------------------\n")

    def _find_or_create_customer(self, db: Session, session_id: str = None, name: str = None, phone: str = None) -> Customer:
        """Finds an existing customer or creates a new one.
        
        Args:
            db: Database session
            session_id: Optional session ID to use as customer identifier
            
        Returns:
            Customer: The found or created customer
        """
        # Normalize inputs
        normalized_phone = phone.strip() if isinstance(phone, str) and phone.strip() else None
        customer_name = name or (f"customer_{session_id}" if session_id else "default_customer")

        # Prefer lookup by phone if provided, else by name
        customer = None
        if normalized_phone:
            customer = db.query(Customer).filter(Customer.phone_number == normalized_phone).first()
        if not customer:
            customer = db.query(Customer).filter(Customer.name == customer_name).first()
        
        # If customer doesn't exist, create a new one
        if not customer:
            customer = Customer(
                name=customer_name,
                phone_number=normalized_phone  # allow NULL when unknown
            )
            db.add(customer)
            try:
                db.flush()  # Get the customer ID without committing the transaction
            except IntegrityError:
                # Likely a unique constraint on phone_number; retry with NULL phone
                db.rollback()
                customer = Customer(name=customer_name, phone_number=None)
                db.add(customer)
                db.flush()
            db.refresh(customer)
            print(f"DEBUG: Created new customer with ID: {customer.id}")
        
        return customer

    def handle(self, session_id: str, query: str, session: List[Dict[str, str]] = [], memory_context: Dict[str, Any] = None) -> "AgentResult":
        print(f"\n{'='*80}")
        print(f"[WORKFLOW START] OrderAgent.handle() called")
        print(f"[WORKFLOW] Session ID: {session_id}")
        print(f"[WORKFLOW] Query: '{query}'")
        print(f"[WORKFLOW] Session length: {len(session)}")
        print(f"[WORKFLOW] Memory context: {'Yes' if memory_context else 'No'}")
        print(f"{'='*80}")
        
        # Initialize database connection
        print("[DATABASE] Opening database session...")
        db = SessionLocal()
        try:
            print("[DATABASE] Database session opened successfully")
            print(f"[DATABASE] Active database: {db.bind.url if db.bind else 'No bind'}")
            
            # Verify database connectivity
            try:
                product_count = db.query(Product).count()
                print(f"[DATABASE] Database connection verified - {product_count} products found")
            except Exception as db_test_error:
                print(f"[DATABASE ERROR] Failed to query products: {db_test_error}")
                return self._error("Database connection failed", {"error": str(db_test_error)})
            
            # NEW: Use memory context for enhanced understanding
            print("\n[MEMORY] Processing memory context...")
            if memory_context:
                print(f"[MEMORY] Memory context received with {len(memory_context.get('important_features', []))} features")
                # Use cart state from memory if available
                if memory_context.get('cart_state'):
                    print(f"[MEMORY] Cart state from memory: {memory_context['cart_state']}")
                # Use important features for better understanding
                if memory_context.get('important_features'):
                    print(f"[MEMORY] Important features: {memory_context['important_features']}")
                # Use last messages for context
                if memory_context.get('last_10_messages'):
                    print(f"[MEMORY] Last {len(memory_context['last_10_messages'])} messages available")
            else:
                print("[MEMORY] No memory context provided - using default behavior")
            
            # Cart management
            print("\n[CART] Managing shopping cart...")
            cart = self.carts.get(session_id)
            if cart is None:
                print(f"[CART] Creating new cart for session {session_id}")
                cart = OrderAgent.ShoppingCart()
                self.carts[session_id] = cart
            else:
                print(f"[CART] Using existing cart with {len(cart.items)} items")
                print(f"[CART] Cart state: awaiting_fulfillment={cart.awaiting_fulfillment}, awaiting_details={cart.awaiting_details}, awaiting_confirmation={cart.awaiting_confirmation}")
                if cart.items:
                    print(f"[CART] Items: {[(item['product'].name, item['quantity']) for item in cart.items]}")
                    print(f"[CART] Total: ${cart.get_total():.2f}")
            
            # If user utterance looks like a time and we're in pickup flow, set pickup_time directly
            try:
                if (cart.fulfillment_type == 'pickup'):
                    m_time = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", query, re.IGNORECASE)
                    if m_time:
                        # Preserve user-friendly 12-hour format for display
                        hour_str = str(int(m_time.group(1)))
                        min_str = (m_time.group(2) or '').strip()
                        ampm = m_time.group(3).lower()
                        display = f"{hour_str}:{min_str} {ampm}" if min_str else f"{hour_str} {ampm}"
                        # Validate against branch hours if branch is known
                        if cart.branch_name and not self._is_time_str_within_branch_hours(display, cart.branch_name):
                            print(f"[TIME VALIDATION] Provided pickup time outside hours for {cart.branch_name}: {display}")
                            # Let the LLM handle the clarification using locations context
                            cart.expected_field = 'pickup_time'
                        else:
                            cart.pickup_info['pickup_time'] = display
                            cart.awaiting_details = False
                            print(f"[CART] Set pickup_time from user query: {cart.pickup_info['pickup_time']}")
            except Exception:
                pass

            # NEW: Use LLM for COMPLETE order management - no hardcoded logic
            print("\n[LLM PHASE 1] Initial order analysis with Enhanced API...")
            print("[LLM] Calling _handle_order_with_llm()...")
            
            # Deterministic entity-based add-to-cart fallback before LLM (uses NLU extraction)
            try:
                if session and isinstance(session[-1], dict) and session[-1].get("role") == "nlu":
                    nlu = session[-1].get("message") or {}
                    # Items
                    prod_name = nlu.get("product")
                    qty = int(nlu.get("quantity") or 0)
                    if prod_name and qty > 0:
                        print(f"[NLU FALLBACK] Adding {qty}x {prod_name} to cart based on extracted entities")
                        self._add_item_to_cart(cart, prod_name, qty, db)
                    # Customer details
                    if nlu.get("name"):
                        # Guard: ignore generic modification/confirmation words as names
                        proposed_name = str(nlu.get("name")).strip()
                        if proposed_name.lower() in {"modify", "change", "edit", "update", "confirm", "confirmation", "yes", "ok", "okay"}:
                            print("[NLU FALLBACK] Ignoring generic modify word as customer name")
                        elif self._is_branch_name(proposed_name):
                            normalized_branch = self._normalize_branch_name(proposed_name)
                            if normalized_branch:
                                cart.branch_name = normalized_branch
                                print(f"[NLU FALLBACK] Interpreted 'name' as branch; set branch_name: {cart.branch_name}")
                        else:
                            cart.customer_info['name'] = proposed_name
                    if nlu.get("phone_number"):
                        cart.customer_info['phone_number'] = nlu.get("phone_number")
                    pm = (nlu.get("payment_method") or '').lower()
                    if pm in ('cash','card','upi'):
                        cart.payment_method = pm
                    # Fulfillment
                    fulf = (nlu.get("fulfillment") or nlu.get("fulfillment_preference") or '').lower()
                    if fulf in ('pickup','delivery'):
                        cart.fulfillment_type = fulf
                        cart.awaiting_fulfillment = False
                    # Times and addresses
                    if nlu.get("pickup_time"):
                        pick = str(nlu.get("pickup_time")).strip()
                        if cart.branch_name and not self._is_time_str_within_branch_hours(pick, cart.branch_name):
                            print(f"[NLU FALLBACK] Ignoring pickup time outside hours for {cart.branch_name}: {pick}")
                            cart.expected_field = 'pickup_time'
                        else:
                            cart.pickup_info['pickup_time'] = pick
                    if nlu.get("address"):
                        cart.delivery_info['address'] = nlu.get("address")
                    if nlu.get("delivery_time"):
                        cart.delivery_info['delivery_time'] = nlu.get("delivery_time")
                    # Branch
                    if nlu.get("branch"):
                        normalized = self._normalize_branch_name(nlu.get("branch"))
                        if normalized:
                            cart.branch_name = normalized
                            print(f"[NLU FALLBACK] Set branch_name from 'branch': {cart.branch_name}")
                    elif nlu.get("location"):  # Also check for location as branch
                        normalized = self._normalize_branch_name(nlu.get("location"))
                        if normalized:
                            cart.branch_name = normalized
                            print(f"[NLU FALLBACK] Set branch_name from 'location': {cart.branch_name}")
            except Exception as e:
                print(f"[NLU FALLBACK] Failed to apply entity-based add-to-cart: {e}")

            # Let LLM handle the entire order flow based on context
            order_action = self._handle_order_with_llm(query, cart, memory_context, db, session)
            print(f"[LLM] _handle_order_with_llm() returned: {order_action}")
            
            # Apply LLM decisions to cart state
            print("\n[CART UPDATES] Applying LLM decisions to cart...")
            if order_action.get("cart_updates"):
                print(f"[CART UPDATES] Processing {len(order_action['cart_updates'])} updates...")
                for i, update in enumerate(order_action["cart_updates"]):
                    print(f"[CART UPDATE {i+1}] Type: {update['type']}, Data: {update}")
                    if update["type"] == "add_item":
                        # Avoid double-adding: only add if this exact product/quantity not already present from NLU fallback
                        try:
                            prod = str(update.get('product') or '').strip()
                            qty = int(update.get('quantity') or 0)
                            already = any((it['product'].name.lower().find(prod.lower()) >= 0 and it['quantity'] >= qty) for it in cart.items)
                            if not already and prod and qty > 0:
                                print(f"[CART UPDATE] Adding {qty}x {prod} to cart (not duplicate)")
                                self._add_item_to_cart(cart, prod, qty, db)
                            else:
                                print(f"[CART UPDATE] Skipping add_item (duplicate or invalid)")
                        except Exception as e:
                            print(f"[CART UPDATE] add_item normalization failed: {e}")
                    elif update["type"] == "remove_item":
                        print(f"[CART UPDATE] Removing {update['product']} from cart")
                        self._remove_item_from_cart(cart, update["product"])
                    elif update["type"] == "modify_item":
                        print(f"[CART UPDATE] Modifying item: {update['product']} to quantity {update['quantity']}")
                        self._modify_item_quantity(cart, update["product"], update["quantity"], db)
                    elif update["type"] == "update_customer_info":
                        info = update.get("info") or {}
                        print(f"[CART UPDATE] Normalizing customer info: {info}")
                        # Support {field, value} shape from LLM
                        if set(info.keys()) == {"field", "value"}:
                            k = str(info.get("field") or "").strip()
                            v = info.get("value")
                            info = {k: v}
                        # Map fields to correct structures
                        if 'name' in info:
                            # Guard against generic/command/location terms being treated as a name
                            proposed_name = str(info['name']).strip()
                            forbidden_names = {"modify","change","edit","update","confirm","confirmation","yes","ok","okay","pickup","pick up","delivery","downtown","branch","location"}
                            if proposed_name.lower() in forbidden_names:
                                print("[CART UPDATE] Ignoring invalid name value from LLM: generic/command/location term")
                                return self._llm_clarify_next_step("What would you like to modify? (name, phone, items, fulfillment, payment)", cart, memory_context, db)
                            # Guard: avoid misclassifying branch names as customer names
                            if self._is_branch_name(proposed_name):
                                print("[CART UPDATE] Detected branch-like value for name; treating as branch selection instead")
                                cart.branch_name = proposed_name
                            else:
                                cart.customer_info['name'] = proposed_name
                        if 'phone' in info:
                            cart.customer_info['phone_number'] = info['phone']
                        if 'phone_number' in info:
                            cart.customer_info['phone_number'] = info['phone_number']
                        if 'payment_method' in info:
                            pm = str(info['payment_method']).lower()
                            if pm in ('cash','card','upi'):
                                cart.payment_method = pm
                        # Guard: never treat payment_method as fulfillment
                        if 'fulfillment_type' in info and str(info['fulfillment_type']).lower() in ('cash','card','upi'):
                            print("[CART UPDATE] Ignoring invalid fulfillment_type that looks like payment method")
                        # Fulfillment specific
                        if 'address' in info:
                            cart.delivery_info['address'] = info['address']
                        if 'delivery_time' in info:
                            cart.delivery_info['delivery_time'] = info['delivery_time']
                        if 'pickup_time' in info:
                            # Normalize/validate pickup time; accept 12h or 24h, store user-friendly 12h
                            raw = str(info['pickup_time']).strip()
                            parsed = self._parse_hour_str_to_time(raw)
                            if not parsed:
                                print(f"[CART UPDATE] Invalid pickup_time format: {raw}")
                                cart.expected_field = 'pickup_time'
                                return self._llm_clarify_next_step("Please provide a valid pickup time (e.g., 5 pm).", cart, memory_context, db)
                            # Validate against branch hours when branch known
                            if cart.branch_name and not self._is_time_within_business_hours(datetime.datetime.combine(datetime.date.today(), parsed).isoformat(), cart.branch_name):
                                print(f"[CART UPDATE] Pickup time outside branch hours for {cart.branch_name}: {raw}")
                                open_t, close_t = self._get_branch_hours_for_datetime(cart.branch_name, datetime.datetime.now())
                                cart.expected_field = 'pickup_time'
                                return self._llm_clarify_next_step(
                                    f"The {cart.branch_name} branch is open {open_t.strftime('%-I:%M %p')}–{close_t.strftime('%-I:%M %p')}. Please choose a time within those hours.",
                                    cart, memory_context, db)
                            cart.pickup_info['pickup_time'] = self._format_time_12h(parsed)
                            cart.awaiting_details = False
                        if 'branch' in info:
                            # Normalize branch to canonical name from locations.json
                            normalized = self._normalize_branch_name(info['branch'])
                            if normalized:
                                cart.branch_name = normalized
                                print(f"[CART UPDATE] Set branch_name: {cart.branch_name}")
                            else:
                                print(f"[CART UPDATE] Invalid branch provided: {info['branch']}")
                                return self._llm_clarify_next_step("Please choose a valid branch (Downtown, Westside, Mall)", cart, memory_context, db)
                    elif update["type"] == "set_fulfillment":
                        # Support LLM using set_fulfillment to set time/branch; normalize
                        info = update.get("info") or {}
                        if 'pickup_time' in info:
                            raw = str(info['pickup_time']).strip()
                            parsed = self._parse_hour_str_to_time(raw)
                            if not parsed:
                                print(f"[CART UPDATE] Invalid pickup_time format in set_fulfillment: {raw}")
                                cart.expected_field = 'pickup_time'
                                return self._llm_clarify_next_step("Please provide a valid pickup time (e.g., 5 pm).", cart, memory_context, db)
                            if cart.branch_name and not self._is_time_within_business_hours(datetime.datetime.combine(datetime.date.today(), parsed).isoformat(), cart.branch_name):
                                print(f"[CART UPDATE] Pickup time outside branch hours in set_fulfillment for {cart.branch_name}: {raw}")
                                open_t, close_t = self._get_branch_hours_for_datetime(cart.branch_name, datetime.datetime.now())
                                cart.expected_field = 'pickup_time'
                                return self._llm_clarify_next_step(
                                    f"The {cart.branch_name} branch is open {open_t.strftime('%-I:%M %p')}–{close_t.strftime('%-I:%M %p')}. Please choose a time within those hours.",
                                    cart, memory_context, db)
                            cart.pickup_info['pickup_time'] = self._format_time_12h(parsed)
                            cart.awaiting_details = False
                            print(f"[CART UPDATE] Set pickup_time: {cart.pickup_info['pickup_time']}")
                        if 'delivery_time' in info:
                            cart.delivery_info['delivery_time'] = info['delivery_time']
                            print(f"[CART UPDATE] Set delivery_time: {cart.delivery_info['delivery_time']}")
                        if 'branch' in info:
                            normalized = self._normalize_branch_name(info['branch'])
                            if normalized:
                                cart.branch_name = normalized
                                print(f"[CART UPDATE] Set branch: {cart.branch_name}")
                            else:
                                print(f"[CART UPDATE] Invalid branch provided in set_fulfillment: {info['branch']}")
                                return self._llm_clarify_next_step("Please choose a valid branch (Downtown, Westside, Mall)", cart, memory_context, db)
                        ft = (update.get("fulfillment_type") or '').lower()
                        if ft in ('pickup','delivery'):
                            print(f"[CART UPDATE] Setting fulfillment type: {ft}")
                            cart.fulfillment_type = ft
                            cart.awaiting_fulfillment = False
                        elif info:
                            # If only details provided (time/branch), do not force invalid fulfillment
                            print("[CART UPDATE] Fulfillment details updated without changing fulfillment type")
                        else:
                            print(f"[CART UPDATE] Ignoring invalid fulfillment type from LLM: {ft}")
            else:
                print("[CART UPDATES] No cart updates from LLM")
            
            # Set cart state based on LLM decision
            print("\n[CART STATE] Updating cart state based on LLM decision...")
            if order_action.get("cart_state"):
                print(f"[CART STATE] LLM cart state: {order_action['cart_state']}")
                cart.awaiting_details = order_action["cart_state"].get("awaiting_details", False)
                cart.awaiting_confirmation = order_action["cart_state"].get("awaiting_confirmation", False)
                cart.awaiting_fulfillment = order_action["cart_state"].get("awaiting_fulfillment", True)
                print(f"[CART STATE] Updated cart flags: awaiting_details={cart.awaiting_details}, awaiting_confirmation={cart.awaiting_confirmation}, awaiting_fulfillment={cart.awaiting_fulfillment}")
                # Server-side guard: do not allow awaiting_confirmation unless details complete
                missing_for_confirmation = self._get_missing_details(cart)
                if cart.awaiting_confirmation and (missing_for_confirmation or not cart.fulfillment_type):
                    print(f"[CART STATE GUARD] Confirmation blocked; missing details: {missing_for_confirmation} or fulfillment not set")
                    cart.awaiting_confirmation = False
                    cart.awaiting_details = True
                    if missing_for_confirmation:
                        cart.expected_field = missing_for_confirmation[0]
                    return self._llm_clarify_next_step(
                        f"Collect missing: {', '.join(missing_for_confirmation)}." if missing_for_confirmation else "Please collect fulfillment details (pickup or delivery).",
                        cart,
                        memory_context,
                        db,
                    )
                # If details are complete, always show preview receipt immediately
                if not self._get_missing_details(cart):
                    print("[CONFIRMATION] Details complete and awaiting confirmation - showing preview receipt")
                    preview_receipt = self._build_preview_receipt(cart)
                    cart.last_prompt = "preview_receipt"
                    cart.awaiting_confirmation = True
                    return self._ok(
                        "order",
                        "Here is your order summary. Please review and confirm:",
                        {
                            "in_order_context": True,
                            "preview_receipt_text": preview_receipt,
                            "awaiting_confirmation": True
                        }
                    )
            else:
                print("[CART STATE] No cart state updates from LLM")

            # Define Phase 1 outputs before trust check to avoid unbound variables
            phase1_response_type = (order_action.get("response_type") or "").lower()
            phase1_message = order_action.get("message") or ""

            # Trust the LLM's response - only use missing details logic as fallback
            # If LLM provided a good response, use it instead of overriding with generic messages
            if phase1_message and phase1_message.strip() and not phase1_message.startswith("Collect missing"):
                print("[LLM TRUST] Using LLM's response instead of missing details logic")
                return self._ok("order", phase1_message, {"in_order_context": True})
            
            # Only use missing details logic if LLM didn't provide a good response
            try:
                pending_missing = self._get_missing_details(cart)
            except Exception:
                pending_missing = []
            if pending_missing:
                cart.awaiting_details = True
                cart.expected_field = pending_missing[0]
                # If we specifically need pickup_time and branch is known, include branch hours
                if 'pickup_time' in pending_missing and cart.branch_name:
                    open_t, close_t = self._get_branch_hours_for_datetime(cart.branch_name, datetime.datetime.now())
                    return self._llm_clarify_next_step(
                        f"The {cart.branch_name} branch is open {open_t.strftime('%-I:%M %p')}–{close_t.strftime('%-I:%M %p')}. Please choose a time within those hours.",
                        cart,
                        memory_context,
                        db,
                    )
                # Generic missing details clarification
                return self._llm_clarify_next_step(
                    f"Collect missing: {', '.join(pending_missing)}.",
                    cart,
                    memory_context,
                    db,
                )

            # Handle confirmation when awaiting confirmation
            if cart.awaiting_confirmation and self._is_strong_confirmation(query):
                print("[CONFIRMATION] User confirmed while awaiting confirmation - finalizing order")
                cart.awaiting_confirmation = False
                return self._finalize_order(db, cart, session_id, memory_context)

            # Phase 1 short-circuit: if Phase 1 produced actionable output, use it and skip Phase 2
            phase1_response_type = (order_action.get("response_type") or "").lower()
            phase1_message = order_action.get("message") or ""
            actionable_types = {"ask_details", "confirm_order", "modify_cart", "show_receipt", "upsell"}
            has_updates = bool(order_action.get("cart_updates"))
            has_actionable = has_updates or (phase1_response_type in actionable_types)
            if has_actionable:
                print(f"[SHORT-CIRCUIT] Using Phase 1 output response_type={phase1_response_type}, has_updates={has_updates}")
                facts = {"in_order_context": True}
                if phase1_response_type == "confirm_order" and not self._get_missing_details(cart):
                    preview_receipt = self._build_preview_receipt(cart)
                    cart.awaiting_confirmation = True
                    facts.update({"preview_receipt_text": preview_receipt, "awaiting_confirmation": True})
                # Trust the LLM's message completely - don't override it
                return self._ok("order", phase1_message, facts)

            # NEW: Let LLM handle ALL order flow decisions instead of hardcoded patterns
            print("\n[LLM PHASE 2] Order flow analysis with Enhanced API...")
            print("[LLM] Calling _analyze_order_flow_with_llm()...")
            
            # Let LLM analyze the query and decide what to do
            order_flow_decision = self._analyze_order_flow_with_llm(query, cart, memory_context, db, session)
            print(f"[LLM] _analyze_order_flow_with_llm() returned: {order_flow_decision}")
            
            # Apply LLM decisions
            print("\n[LLM DECISIONS] Processing LLM flow decisions...")
            if order_flow_decision.get("action") == "clear_cart":
                print("[LLM DECISION] Action: clear_cart - IGNORED (requires explicit user command)")
                return self._llm_clarify_next_step("Do you want to clear your cart?", cart, memory_context, db)
                
            elif order_flow_decision.get("action") == "checkout":
                print("[LLM DECISION] Action: checkout - Processing checkout flow...")
                # LLM has already added items if needed
                if not cart.items:
                    print("[CHECKOUT] Cart is empty - delegating to LLM for items")
                    return self._llm_clarify_next_step("Your cart is empty; please specify items to add.", cart, memory_context, db)
                
                # If fulfillment not set, ask LLM to collect it
                if not cart.fulfillment_type:
                    print("[CHECKOUT] Fulfillment not set - delegating to LLM for clarification")
                    cart.awaiting_fulfillment = True
                    return self._llm_clarify_next_step("Please collect fulfillment details (pickup or delivery).", cart, memory_context, db)

                # Check what's missing based on LLM analysis
                print("[CHECKOUT] Checking for missing details...")
                missing_details = self._get_missing_details(cart)
                if missing_details:
                    print(f"[CHECKOUT] Missing details found: {missing_details}")
                    cart.awaiting_details = True
                    cart.expected_field = missing_details[0]
                    return self._llm_clarify_next_step(f"Collect missing: {', '.join(missing_details)}.", cart, memory_context, db)
                
                # Ready for confirmation -> show preview receipt first
                print("[CHECKOUT] All details complete - showing preview receipt")
                cart.awaiting_confirmation = True
                preview_receipt = self._build_preview_receipt(cart)
                return self._ok(
                    "order",
                    "Perfect! Here's your order summary. Please review and confirm:",
                    {
                        "in_order_context": True,
                        "preview_receipt_text": preview_receipt,
                        "awaiting_confirmation": True
                    }
                )
            
            elif order_flow_decision.get("action") == "show_cart":
                print("[LLM DECISION] Action: show_cart - Displaying cart summary...")
                return self._ok(
                    "cart_summary",
                    "Here is your cart summary.",
                    {"cart_summary": cart.get_summary(), "cart_items": len(cart.items)}
                )
            
            elif order_flow_decision.get("action") == "set_fulfillment":
                print(f"[LLM DECISION] Action: set_fulfillment - Setting fulfillment type: {order_flow_decision.get('fulfillment_type')}")
                cart.fulfillment_type = order_flow_decision.get("fulfillment_type")
                cart.awaiting_fulfillment = False
                print(f"[CART] Fulfillment type set to: {cart.fulfillment_type}")

                # Move to next step
                print("[FULFILLMENT] Checking for missing details...")
                missing_details = self._get_missing_details(cart)
                if missing_details:
                    print(f"[FULFILLMENT] Missing details found: {missing_details}")
                    cart.awaiting_details = True
                    cart.expected_field = missing_details[0]
                    return self._llm_clarify_next_step(f"Collect missing: {', '.join(missing_details)}.", cart, memory_context, db)
                print("[FULFILLMENT] All details complete - showing preview receipt")
                cart.awaiting_confirmation = True
                preview_receipt = self._build_preview_receipt(cart)
                return self._ok(
                    "order",
                    "Great! Here's your order summary. Please review and confirm:",
                    {
                        "in_order_context": True,
                        "preview_receipt_text": preview_receipt,
                        "awaiting_confirmation": True
                    }
                )

            elif order_flow_decision.get("action") == "collect_details":
                print(f"[LLM DECISION] Action: collect_details - Collecting missing details: {order_flow_decision.get('missing_details', [])}")
                cart.awaiting_details = True
                missing_details = order_flow_decision.get("missing_details", [])
                if missing_details:
                    cart.expected_field = missing_details[0]
                return self._llm_clarify_next_step(
                    f"Collect missing: {', '.join(missing_details)}." if missing_details else "Please provide the missing details.",
                    cart,
                    memory_context,
                    db,
                )
            
            elif order_flow_decision.get("action") == "confirm_order":
                print("[LLM DECISION] Action: confirm_order - Processing order confirmation...")
                # Server-side guard: ensure all required details are present before finalization
                guard_missing = self._get_missing_details(cart)
                if guard_missing or not cart.fulfillment_type:
                    print(f"[CONFIRMATION GUARD] Missing details before confirmation: {guard_missing}, fulfillment={cart.fulfillment_type}")
                    cart.awaiting_confirmation = False
                    cart.awaiting_details = True
                    if guard_missing:
                        cart.expected_field = guard_missing[0]
                    return self._llm_clarify_next_step(
                        f"Collect missing: {', '.join(guard_missing)}." if guard_missing else "Please collect fulfillment details (pickup or delivery).",
                        cart,
                        memory_context,
                        db,
                    )
                # If user gave strong confirmation and details are complete, finalize immediately
                if self._is_strong_confirmation(query):
                    print("[CONFIRMATION] Strong confirmation detected (no preview required on this turn) - finalizing order")
                    cart.last_prompt = "confirm_order"
                    return self._finalize_order(db, cart, session_id, memory_context)
                # Otherwise, show preview receipt and set awaiting_confirmation for next turn
                print("[CONFIRMATION] Showing preview receipt and setting awaiting_confirmation for explicit confirm")
                preview_receipt = self._build_preview_receipt(cart)
                cart.awaiting_confirmation = True
                return self._ok(
                    "order",
                    "Here is your order summary. Please say 'confirm' to place the order:",
                    {
                        "in_order_context": True,
                        "preview_receipt_text": preview_receipt,
                        "awaiting_confirmation": True
                    }
                )
            
            elif order_flow_decision.get("action") == "show_receipt":
                print("[LLM DECISION] Action: show_receipt - Displaying order receipt...")
                if session_id in self.last_receipt_by_session:
                    print(f"[RECEIPT] Found receipt for session {session_id}")
                    return self._ok("order_receipt", self.last_receipt_by_session[session_id], {"receipt_text": self.last_receipt_by_session[session_id]})
                print("[RECEIPT] No receipt found for this session")
                return self._llm_clarify_next_step("No receipt yet; offer to review cart or start new order.", cart, memory_context, db)
            
            elif order_flow_decision.get("action") == "modify_cart":
                print("[LLM DECISION] Action: modify_cart - Handling cart modifications...")
                modifications = order_flow_decision.get("modifications", {})
                mod_type = modifications.get("type")
                
                if mod_type == "unspecified":
                    # User said "modify" without specifying what - ask for clarification
                    return self._llm_clarify_next_step("What would you like to modify? (items, fulfillment, customer info, payment)", cart, memory_context, db)
                elif mod_type == "change_fulfillment":
                    cart.awaiting_fulfillment = True
                    return self._llm_clarify_next_step("What would you like to change about fulfillment? (pickup/delivery, time, address, etc.)", cart, memory_context, db)
                elif mod_type == "change_customer_info":
                    cart.awaiting_details = True
                    # Ask which specific field to modify to avoid overwriting with generic words
                    return self._llm_clarify_next_step("Which customer info should I update? (name, phone)", cart, memory_context, db)
                elif mod_type == "change_items":
                    cart.awaiting_details = True
                    return self._llm_clarify_next_step("What items would you like to change? (add, remove, modify quantities)", cart, memory_context, db)
                elif mod_type == "change_payment":
                    cart.awaiting_details = True
                    return self._llm_clarify_next_step("What payment method would you like to use? (cash, card, upi)", cart, memory_context, db)
                else:
                    # Generic 'modify' command: ask what exactly to change
                    return self._llm_clarify_next_step("What would you like to modify? (items, fulfillment, customer info, payment)", cart, memory_context, db)
            
            # If LLM didn't provide a clear action, delegate clarification to LLM
            print("[LLM] No clear action from LLM; delegating clarification to LLM")
            return self._llm_clarify_next_step(query, cart, memory_context, db)
           
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"[ERROR] Exception occurred in OrderAgent.handle()")
            print(f"[ERROR] Error message: {str(e)}")
            print(f"[ERROR] Error type: {type(e).__name__}")
            print(f"[ERROR] Session ID: {session_id}")
            print(f"[ERROR] Query: {query}")
            print(f"{'='*80}")
            
            print("[DATABASE] Rolling back transaction...")
            db.rollback()
            
            print("[ERROR] Printing full traceback...")
            import traceback
            traceback.print_exc()
            
            print("[DATABASE] Printing database status...")
            self._print_db_status(db)  # Print status on error
            
            return self._ok(
                "order", 
                "I'm sorry, I couldn't complete your order. Please try again or contact support if the issue persists.", 
                {
                    "error": "order_processing_error",
                    "error_type": type(e).__name__,
                    "message": str(e)
                }
            )
        finally:
            print("[DATABASE] Closing database session...")
            db.close()
            print(f"[WORKFLOW END] OrderAgent.handle() completed")
            print(f"{'='*80}\n")

    def _ok(self, intent: str, message: str, facts: Dict = {}) -> AgentResult:
        print(f"[OK] {message}")
        merged_facts = dict(facts)
        merged_facts.setdefault("note", message)
        return AgentResult(
            agent=self.name,
            intent=intent,
            facts=merged_facts
        )

    def _clarify(self, intent: str, question: str) -> AgentResult:
        print(f"[CLARIFY] for intent '{intent}': {question}")
        return AgentResult(
            agent=self.name,
            intent=intent,
            facts={"needs_clarification": True},
            clarification_question=question
        )

    def _modify_item_quantity(self, cart: ShoppingCart, product_name: str, new_quantity: int, db: Session):
        """Modify the quantity of an existing item in the cart."""
        try:
            # Find the product in the cart
            for i, item in enumerate(cart.items):
                if item['product'].name.lower() == product_name.lower():
                    # Validate new quantity
                    if new_quantity <= 0:
                        print(f"[MODIFY ITEM] Removing {product_name} (quantity set to {new_quantity})")
                        cart.remove_item(item['product'])
                    else:
                        # Check stock availability
                        product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
                        if product and product.quantity_in_stock >= new_quantity:
                            print(f"[MODIFY ITEM] Updating {product_name} quantity from {item['quantity']} to {new_quantity}")
                            cart.items[i]['quantity'] = new_quantity
                            cart.calculate_total()
                        else:
                            print(f"[MODIFY ITEM] Insufficient stock for {product_name}. Available: {product.quantity_in_stock if product else 0}, Requested: {new_quantity}")
                    return
            print(f"[MODIFY ITEM] Product {product_name} not found in cart")
        except Exception as e:
            print(f"[MODIFY ITEM] Error modifying item quantity: {e}")

    def _validate_llm_decisions(self, llm_result: Dict, cart: ShoppingCart) -> Dict:
        """Validate and sanitize LLM decisions before applying to cart."""
        print(f"[LLM VALIDATION] Validating LLM decisions...")
        
        # Validate fulfillment_type
        if 'cart_updates' in llm_result:
            for update in llm_result['cart_updates']:
                if update.get('type') == 'set_fulfillment':
                    fulfillment_type = update.get('fulfillment_type', '')
                    if fulfillment_type not in ['pickup', 'delivery']:
                        print(f"[LLM VALIDATION] Invalid fulfillment_type: {fulfillment_type}, removing update")
                        llm_result['cart_updates'].remove(update)
                        # Set response to ask for clarification
                        llm_result['response_type'] = 'ask_details'
                        llm_result['message'] = 'Would you like pickup or delivery?'
        
        # Validate cart_state
        if 'cart_state' in llm_result:
            cart_state = llm_result['cart_state']
            # Ensure boolean values
            for key in ['awaiting_details', 'awaiting_confirmation', 'awaiting_fulfillment']:
                if key in cart_state:
                    cart_state[key] = bool(cart_state[key])
        
        print(f"[LLM VALIDATION] Validation complete")
        return llm_result

    def _get_missing_details(self, cart) -> List[str]:
        """Helper method to get list of missing required details."""
        print(f"\n[MISSING DETAILS CHECK] Analyzing cart for missing information...")
        print(f"[MISSING DETAILS CHECK] Cart items: {len(cart.items)}")
        print(f"[MISSING DETAILS CHECK] Fulfillment type: {cart.fulfillment_type}")
        print(f"[MISSING DETAILS CHECK] Customer info: {cart.customer_info}")
        print(f"[MISSING DETAILS CHECK] Branch name: {cart.branch_name}")
        
        missing_details = []
        
        # First check if there are items in the cart
        if not cart.items:
            print("[MISSING DETAILS CHECK] No items in cart - adding 'items' to missing")
            missing_details.append('items')
            return missing_details  # If no items, don't check other details
            
        # PRIORITY 1: Essential customer information
        if not cart.customer_info.get('name'):
            print("[MISSING DETAILS CHECK] Missing customer name")
            missing_details.append('name')
            
        # PRIORITY 1.5: Phone number (required for all orders)
        if not cart.customer_info.get('phone_number'):
            print("[MISSING DETAILS CHECK] Missing phone number")
            missing_details.append('phone_number')
            
        # PRIORITY 2: Fulfillment type (must be set before other fulfillment details)
        if not cart.fulfillment_type or cart.fulfillment_type not in ['pickup', 'delivery']:
            print("[MISSING DETAILS CHECK] Missing or invalid fulfillment type")
            missing_details.append('fulfillment_type')
            return missing_details  # Don't check other details until fulfillment is set
            
        # PRIORITY 3: Fulfillment-specific details
        if cart.fulfillment_type == 'pickup':
            # Ask for branch before time; if branch not set, defer pickup_time
            if not cart.branch_name:
                print("[MISSING DETAILS CHECK] Branch not set, deferring pickup_time until branch chosen")
                # Don't add pickup_time to missing if branch is not set yet
            else:
                if not cart.pickup_info.get('pickup_time'):
                    print("[MISSING DETAILS CHECK] Missing pickup time (post-branch)")
                    missing_details.append('pickup_time')
        elif cart.fulfillment_type == 'delivery':
            if not cart.delivery_info.get('address'):
                print("[MISSING DETAILS CHECK] Missing delivery address")
                missing_details.append('address')
            if not cart.delivery_info.get('delivery_time'):
                print("[MISSING DETAILS CHECK] Missing delivery time")
                missing_details.append('delivery_time')
                
        # PRIORITY 3: Payment method
        if not cart.payment_method:
            print("[MISSING DETAILS CHECK] Missing payment method")
            missing_details.append('payment_method')
            
        # PRIORITY 4: Branch selection (for pickup orders, ask for branch before validating time)
        if cart.fulfillment_type == 'pickup':
            if not cart.branch_name:
                print("[MISSING DETAILS CHECK] Missing branch selection for pickup")
                missing_details.append('branch')
            else:
                print("[MISSING DETAILS CHECK] Branch selected, can validate pickup time")
        elif cart.fulfillment_type == 'delivery':
            # For delivery, branch is not required
            print("[MISSING DETAILS CHECK] Delivery order - no branch selection needed")
        
        print(f"[MISSING DETAILS CHECK] Final missing details: {missing_details}")
        return missing_details

    def _ask_for_missing_details(self, cart, missing_details: List[str]) -> AgentResult:
        """Helper method to ask for missing details."""
        if 'items' in missing_details:
            cart.awaiting_details = True
            cart.expected_field = 'items'
            return self._llm_clarify_next_step("Your cart is empty; please specify items to add.", cart, {}, None)
        elif 'name' in missing_details:
            cart.awaiting_details = True
            cart.expected_field = 'name'
            return self._llm_clarify_next_step("Collect missing: name.", cart, {}, None)
        elif 'branch' in missing_details:
            return self._llm_clarify_next_step("Ask for branch selection (Downtown/Westside/Mall).", cart, {}, None)
        elif 'phone_number' in missing_details and cart.fulfillment_type == 'pickup':
            cart.awaiting_details = True
            cart.expected_field = 'phone_number'
            return self._llm_clarify_next_step("Collect missing: phone_number.", cart, {}, None)
        elif 'pickup_time' in missing_details and cart.fulfillment_type == 'pickup':
            cart.awaiting_details = True
            cart.expected_field = 'pickup_time'
            return self._llm_clarify_next_step("Collect missing: pickup_time.", cart, {}, None)
        elif 'address' in missing_details and cart.fulfillment_type == 'delivery':
            cart.awaiting_details = True
            cart.expected_field = 'address'
            return self._llm_clarify_next_step("Collect missing: address.", cart, {}, None)
        elif 'delivery_time' in missing_details and cart.fulfillment_type == 'delivery':
            cart.awaiting_details = True
            cart.expected_field = 'delivery_time'
            return self._llm_clarify_next_step("Collect missing: delivery_time.", cart, {}, None)
        elif 'payment_method' in missing_details:
            cart.awaiting_details = True
            cart.expected_field = 'payment_method'
            return self._llm_clarify_next_step("Collect missing: payment_method.", cart, {}, None)
        else:
            cart.awaiting_details = True
            if missing_details:
                cart.expected_field = missing_details[0]
            return self._llm_clarify_next_step(
                f"Collect missing: {', '.join(missing_details)}." if missing_details else "Please provide the missing details.",
                cart,
                {},
                None,
            )

    def _print_db_status(self, db):
        """Print current database status for debugging"""
        print("\n--- Database Status ---\n")
        print("[Products]")
        products = db.query(Product).all()
        for p in products:
            print(f"- {p.name}: {p.quantity_in_stock} in stock")
        print("\n[Orders]")
        orders = db.query(Order).all()
        if not orders:
            print("No orders found.")
        else:
            for o in orders:
                try:
                    fulfillment = o.pickup_or_delivery.value if hasattr(o, 'pickup_or_delivery') and o.pickup_or_delivery else 'unknown'
                except Exception:
                    fulfillment = 'unknown'
                print(f"- Order #{o.id}: Customer {o.customer_id}, Status: {o.status.value if hasattr(o.status, 'value') else o.status}, Fulfillment: {fulfillment}")
        print("\n[Order Items]")
        order_items = db.query(OrderItem).all()
        if not order_items:
            print("No order items found.")
        else:
            for oi in order_items:
                print(f"- {oi.quantity}x {oi.product.name} (Order #{oi.order_id})")
        print("-----------------------")
