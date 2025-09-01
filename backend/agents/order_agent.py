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
        m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", hour_str.strip(), re.IGNORECASE)
        if not m:
            return None
        hh = int(m.group(1)) % 12
        mm = int(m.group(2) or 0)
        if m.group(3).lower() == 'pm':
            hh += 12
        return time(hh, mm)

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
    
    def _handle_order_with_llm(self, query: str, cart: ShoppingCart, memory_context: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Use LLM to handle COMPLETE order management - no hardcoded logic."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Get database info for LLM context
            products = db.query(Product).all()
            product_info = {p.name.lower(): {"id": p.id, "price": p.price, "stock": p.quantity_in_stock} for p in products}
            
            # Create comprehensive prompt for complete order management
            prompt = f"""
            You are an AI managing a complete bakery order system.
            
            User Query: "{query}"
            
            Current Cart State:
            - Items: {cart.items}
            - Customer Info: {cart.customer_info}
            - Fulfillment Type: {cart.fulfillment_type}
            - Awaiting: Fulfillment={cart.awaiting_fulfillment}, Details={cart.awaiting_details}, Confirmation={cart.awaiting_confirmation}
            
            Memory Context: {memory_context if memory_context else "None"}
            
            Available Products: {product_info}
            
            Your task is to understand the user's intent and manage the order accordingly.
            
            Return JSON with this structure:
            {{
                "cart_updates": [
                    {{
                        "type": "add_item/remove_item/update_customer_info/set_fulfillment",
                        "product": "product_name",
                        "quantity": 1,
                        "info": {{"name": "value"}},
                        "fulfillment_type": "pickup/delivery"
                    }}
                ],
                "cart_state": {{
                    "awaiting_details": true/false,
                    "awaiting_confirmation": true/false,
                    "awaiting_fulfillment": true/false
                }},
                "response_type": "ask_details/confirm_order/show_receipt/upsell",
                "message": "what to say to user"
            }}
            
            Guidelines:
            - Understand implicit requests (e.g., "I want chocolate cake" = add item)
            - Handle variations and typos (e.g., "pic up" = pickup)
            - Consider memory context for user preferences
            - Make decisions based on current cart state
            - Return valid JSON only
            """
            
            # Use Enhanced API for complete order management
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
            else:
                print(f"DEBUG: Product {product_name} not found or insufficient stock")
        except Exception as e:
            print(f"DEBUG: Error adding item to cart: {e}")
    
    def _remove_item_from_cart(self, cart: ShoppingCart, product_name: str):
        """Remove item from cart."""
        try:
            cart.remove_item(product_name)
            print(f"DEBUG: Removed {product_name} from cart")
        except Exception as e:
            print(f"DEBUG: Error removing item from cart: {e}")
    
    def _analyze_order_flow_with_llm(self, query: str, cart: ShoppingCart, memory_context: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Use LLM to analyze the order flow and decide what action to take."""
        try:
            from ..app.dual_api_system import DualAPISystem
            
            # Get database info for LLM context
            products = db.query(Product).all()
            product_info = {p.name.lower(): {"id": p.id, "price": p.price, "stock": p.quantity_in_stock} for p in products}
            
            prompt = f"""
            You are analyzing a user query to determine the appropriate order flow action.
            
            User Query: "{query}"
            
            Current Cart State:
            - Items: {cart.items}
            - Customer Info: {cart.customer_info}
            - Fulfillment Type: {cart.fulfillment_type}
            - Awaiting: Fulfillment={cart.awaiting_fulfillment}, Details={cart.awaiting_details}, Confirmation={cart.awaiting_confirmation}
            
            Memory Context: {memory_context if memory_context else "None"}
            
            Available Products: {product_info}
            
            Determine what action the system should take. Return JSON with:
            {{
                "action": "clear_cart/checkout/show_cart/set_fulfillment/collect_details/confirm_order/show_receipt",
                "fulfillment_type": "pickup/delivery if setting fulfillment",
                "missing_details": ["list of missing details if collecting details"],
                "reasoning": "why you chose this action",
                "items_to_add": [
                    {{"product": "product_name", "quantity": 1}}
                ]
            }}
            
            Guidelines:
            - Understand implicit requests (e.g., "I want chocolate cake" = add item)
            - Handle variations and typos (e.g., "pic up" = pickup)
            - Consider memory context for user preferences
            - Make decisions based on current cart state
            - Return valid JSON only
            """
            
            dual_api = DualAPISystem()
            response = dual_api.generate_response_with_primary_api(prompt)
            
            # Parse response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                
                # Add items if specified
                if parsed.get("items_to_add"):
                    for item in parsed["items_to_add"]:
                        self._add_item_to_cart(cart, item["product"], item["quantity"], db)
                
                return parsed
            else:
                return {}
                
        except Exception as e:
            print(f"LLM order flow analysis failed: {e}")
            return {}

    def _finalize_order(self, db: Session, cart: ShoppingCart, session_id: str) -> Dict[str, Any]:
        """Single gateway for order finalization - called from one place only."""
        print("DEBUG: Entering _finalize_order method.")
        print(f"DEBUG: Cart state before finalization: {cart.__dict__}")

        if not cart.items:
            print("DEBUG: Cart is empty. Cannot finalize order.")
            return self._ok(
                "order",
                "I notice your cart is empty! Please add some items to your order first. You can say something like 'Add 2 chocolate cakes' or 'I'd like 1 bread and 3 cookies'.",
                {
                    "order_placed": False, 
                    "cart_empty": True,
                    "needs_items": True,
                    "note": "Your cart is empty. Please add some items before confirming."
                }
            )

        # Final stock check
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Checking stock for product {product.name}. Available: {product.quantity_in_stock}, Needed: {item['quantity']}")
            if product.quantity_in_stock < item['quantity']:
                print(f"DEBUG: Insufficient stock for product {product.name}.")
                return {
                    "order_placed": False, 
                    "note": f"Sorry, we only have {product.quantity_in_stock} {product.name} in stock. Would you like to adjust your order?"
                }

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

    # --- New: business hour validation ---
    @staticmethod
    def _parse_hour_str_to_time(hour_str: str):
        from datetime import time
        import re
        m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", hour_str.strip(), re.IGNORECASE)
        if not m:
            return None
        hh = int(m.group(1)) % 12
        mm = int(m.group(2) or 0)
        if m.group(3).lower() == 'pm':
            hh += 12
        return time(hh, mm)

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

    def _finalize_order(self, db: Session, cart: ShoppingCart, session_id: str) -> Dict[str, Any]:
        """Single gateway for order finalization - called from one place only."""
        print("DEBUG: Entering _finalize_order method.")
        print(f"DEBUG: Cart state before finalization: {cart.__dict__}")

        if not cart.items:
            print("DEBUG: Cart is empty. Cannot finalize order.")
            return {"order_placed": False, "note": "Your cart is empty. Please add some items before confirming."}

        # Final stock check
        for item in cart.items:
            product = item['product']
            print(f"DEBUG: Checking stock for product {product.name}. Available: {product.quantity_in_stock}, Needed: {item['quantity']}")
            if product.quantity_in_stock < item['quantity']:
                print(f"DEBUG: Insufficient stock for product {product.name}.")
                return {
                    "order_placed": False, 
                    "note": f"Sorry, we only have {product.quantity_in_stock} {product.name} in stock. Would you like to adjust your order?"
                }

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
                print(f"- Order #{o.id}: Customer {o.customer_id}, Status: {o.status.value}, Fulfillment: {o.pickup_or_delivery.value}")

        # Print Order Items
        order_items = db.query(OrderItem).all()
        print("\n[Order Items]")
        if not order_items:
            print("No order items found.")
        else:
            for oi in order_items:
                print(f"- Item: {oi.product.name}, Quantity: {oi.quantity}, Order ID: {oi.order_id}")
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
            
            # NEW: Use LLM for COMPLETE order management - no hardcoded logic
            print("\n[LLM PHASE 1] Initial order analysis with Enhanced API...")
            print("[LLM] Calling _handle_order_with_llm()...")
            
            # Let LLM handle the entire order flow based on context
            order_action = self._handle_order_with_llm(query, cart, memory_context, db)
            print(f"[LLM] _handle_order_with_llm() returned: {order_action}")
            
            # Apply LLM decisions to cart state
            print("\n[CART UPDATES] Applying LLM decisions to cart...")
            if order_action.get("cart_updates"):
                print(f"[CART UPDATES] Processing {len(order_action['cart_updates'])} updates...")
                for i, update in enumerate(order_action["cart_updates"]):
                    print(f"[CART UPDATE {i+1}] Type: {update['type']}, Data: {update}")
                    if update["type"] == "add_item":
                        print(f"[CART UPDATE] Adding {update['quantity']}x {update['product']} to cart")
                        self._add_item_to_cart(cart, update["product"], update["quantity"], db)
                    elif update["type"] == "remove_item":
                        print(f"[CART UPDATE] Removing {update['product']} from cart")
                        self._remove_item_from_cart(cart, update["product"])
                    elif update["type"] == "update_customer_info":
                        print(f"[CART UPDATE] Updating customer info: {update['info']}")
                        cart.customer_info.update(update["info"])
                    elif update["type"] == "set_fulfillment":
                        print(f"[CART UPDATE] Setting fulfillment type: {update['fulfillment_type']}")
                        cart.fulfillment_type = update["fulfillment_type"]
                        cart.awaiting_fulfillment = False
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
            else:
                print("[CART STATE] No cart state updates from LLM")

            # NEW: Let LLM handle ALL order flow decisions instead of hardcoded patterns
            print("\n[LLM PHASE 2] Order flow analysis with Enhanced API...")
            print("[LLM] Calling _analyze_order_flow_with_llm()...")
            
            # Let LLM analyze the query and decide what to do
            order_flow_decision = self._analyze_order_flow_with_llm(query, cart, memory_context, db)
            print(f"[LLM] _analyze_order_flow_with_llm() returned: {order_flow_decision}")
            
            # Apply LLM decisions
            print("\n[LLM DECISIONS] Processing LLM flow decisions...")
            if order_flow_decision.get("action") == "clear_cart":
                print("[LLM DECISION] Action: clear_cart - Clearing cart...")
                cart.clear()
                print("[CART] Cart cleared successfully")
                return self._ok("clear_cart", "Your cart has been cleared.", {"cart_cleared": True})
            
            elif order_flow_decision.get("action") == "checkout":
                print("[LLM DECISION] Action: checkout - Processing checkout flow...")
                # LLM has already added items if needed
                if not cart.items:
                    print("[CHECKOUT] Cart is empty - asking for items")
                    return self._ok("checkout", "Your cart is empty. Please add some items before checking out.", {"needs_items": True})
                
                # Check what's missing based on LLM analysis
                print("[CHECKOUT] Checking for missing details...")
                missing_details = self._get_missing_details(cart)
                if missing_details:
                    print(f"[CHECKOUT] Missing details found: {missing_details}")
                    cart.awaiting_details = True
                    return self._ask_for_missing_details(cart, missing_details)
                
                # Ready for confirmation
                print("[CHECKOUT] All details complete - ready for confirmation")
                cart.awaiting_confirmation = True
                return self._ok(
                    "confirm_order",
                    "Please confirm your order.",
                    {
                        "ready_to_confirm": True,
                        "cart_summary": cart.get_summary(),
                        "fulfillment": cart.fulfillment_type,
                        "customer": cart.customer_info,
                        "delivery": cart.delivery_info,
                        "pickup": cart.pickup_info,
                        "payment_method": cart.payment_method,
                        "total": cart.get_total(),
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
                    return self._ask_for_missing_details(cart, missing_details)
                print("[FULFILLMENT] All details complete - moving to confirmation")
                cart.awaiting_confirmation = True
                return self._ok("confirm_order", "Please confirm your order.", {"ready_to_confirm": True, "cart_summary": cart.get_summary(), "fulfillment": cart.fulfillment_type})
            
            elif order_flow_decision.get("action") == "collect_details":
                print(f"[LLM DECISION] Action: collect_details - Collecting missing details: {order_flow_decision.get('missing_details', [])}")
                cart.awaiting_details = True
                return self._ask_for_missing_details(cart, order_flow_decision.get("missing_details", []))
            
            elif order_flow_decision.get("action") == "confirm_order":
                print("[LLM DECISION] Action: confirm_order - Processing order confirmation...")
                if cart.awaiting_confirmation:
                    print("[CONFIRMATION] Order awaiting confirmation - finalizing...")
                    cart.last_prompt = "confirm_order"
                    return self._finalize_order(db, cart, session_id)
                else:
                    print("[CONFIRMATION] No order awaiting confirmation")
                    return self._ok(
                        "confirm_order",
                        "I don't see an order awaiting confirmation. Would you like me to start a new order or review your cart?",
                        {"in_order_context": bool(cart.items), "cart_items": len(cart.items)}
                    )
            
            elif order_flow_decision.get("action") == "show_receipt":
                print("[LLM DECISION] Action: show_receipt - Displaying order receipt...")
                if session_id in self.last_receipt_by_session:
                    print(f"[RECEIPT] Found receipt for session {session_id}")
                    return self._ok("order_receipt", "Here is your latest order receipt:", {"receipt_text": self.last_receipt_by_session[session_id]})
                print("[RECEIPT] No receipt found for this session")
                return self._ok("order_receipt", "I don't see a recent order receipt yet. Would you like me to review your cart or place a new order?", {"receipt_available": False, "in_order_context": True})
            
            # If LLM didn't provide a clear action, use fallback
            print("[LLM] No clear action from LLM, using fallback logic")
            
            # Handle ongoing checkout flow states
            print("\n[FALLBACK] Processing ongoing checkout flow states...")
            if cart.awaiting_details:
                print("[FALLBACK] Cart is awaiting details - checking what's missing...")
                # Check if all required details are present now
                missing_details = self._get_missing_details(cart)
                
                if missing_details:
                    # Still missing details, ask for them using helper method
                    print(f"[FALLBACK] Still missing details: {missing_details}")
                    return self._ask_for_missing_details(cart, missing_details)
                
                # All details are complete. Show a full receipt-style preview and ask for confirmation.
                print("[FALLBACK] All details complete - building receipt preview...")
                cart.awaiting_details = False
                cart.awaiting_confirmation = True
                preview_text = cart.build_receipt()
                print("[FALLBACK] Receipt preview built - asking for confirmation")
                return self._ok(
                    "confirm_order",
                    "Please review your order below and confirm if everything looks good.",
                    {
                        "ready_to_confirm": True,
                        "preview_receipt_text": preview_text,
                        "in_order_context": True,
                    }
                )
            
            # Handle order confirmation - SINGLE GATEWAY
            if cart.awaiting_confirmation and self._is_strong_confirmation(query):
                print("[FALLBACK] Order confirmation detected - finalizing order...")
                cart.last_prompt = "confirm_order"
                return self._finalize_order(db, cart, session_id)
            
            # 1. Extract entities from current message
            print("\n[ENTITY EXTRACTION] Starting entity extraction...")
            ent = self.entity_extractor.extract(query)
            print(f"[ENTITY EXTRACTION] Entities extracted: {ent}")

            # Update cart with any provided details (name/phone/time/address)
            if ent.get("name"):
                # Avoid setting name to a product name (e.g., "Almond Croissant")
                try:
                    known_product_names = {row[0].lower() for row in db.query(Product.name).all()}
                except Exception:
                    known_product_names = set()
                proposed_name = ent["name"].strip()
                if proposed_name.lower() not in known_product_names and "croissant" not in proposed_name.lower():
                    cart.customer_info["name"] = proposed_name
            if ent.get("phone_number"):
                cart.customer_info["phone_number"] = ent["phone_number"]
            else:
                # Fallback: capture bare phone numbers (7-15 digits) in free text
                phone_match = re.search(r"(?<!\d)(\+?\d[\d\s\-]{6,14}\d)(?!\d)", query)
                if phone_match and not cart.customer_info.get("phone_number"):
                    cart.customer_info["phone_number"] = re.sub(r"[^\d\+]", "", phone_match.group(1))
            if ent.get("time"):
                if cart.fulfillment_type == 'pickup':
                    # validate time window 8:00–18:00
                    if self._is_time_within_business_hours(ent["time"], cart.branch_name):
                        cart.pickup_info["pickup_time"] = ent["time"]
                    else:
                        return self._ok("checkout_missing_details", "Our pickup window is 8 AM–6 PM. What pickup time works for you within that window?", {"asking_for": "pickup_time", "in_order_context": True})
                elif cart.fulfillment_type == 'delivery':
                    if self._is_time_within_business_hours(ent["time"], cart.branch_name):
                        cart.delivery_info["delivery_time"] = ent["time"]
                    else:
                        return self._ok("checkout_missing_details", "Our delivery window is 8 AM–6 PM. What time should we deliver within that window?", {"asking_for": "delivery_time", "in_order_context": True})
            if ent.get("payment_method"):
                cart.payment_method = ent["payment_method"]

            # Naive address extraction (number + street + type)
            print("\n[ADDRESS EXTRACTION] Checking for delivery address...")
            addr_match = re.search(r"(\d{1,5}\s+[A-Za-z0-9\.,\-\s]+\s+(Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Drive|Dr\.?))", query, flags=re.IGNORECASE)
            if addr_match:
                extracted_address = addr_match.group(1).strip()
                cart.delivery_info["address"] = extracted_address
                print(f"[ADDRESS] Delivery address extracted: {extracted_address}")
            else:
                print("[ADDRESS] No delivery address found in query")
            
            # Branch selection detection
            print("\n[BRANCH DETECTION] Checking for branch selection...")
            branch_keywords = {
                'downtown': 'Downtown Location',
                'westside': 'Westside Location', 
                'mall': 'Mall Location'
            }
            
            query_lower = query.lower()
            for keyword, branch_name in branch_keywords.items():
                if keyword in query_lower:
                    cart.branch_name = branch_name
                    print(f"[BRANCH] Branch selected: {branch_name}")
                    break
            else:
                print("[BRANCH] No branch selection detected in query")
            
            # Get product name from entities or from context
            print("\n[PRODUCT DETECTION] Determining product from entities and context...")
            product_name = ent.get("product") or ent.get("product_name")
            print(f"[PRODUCT] Product from entities: {product_name}")
            
            # If no product in current message, check previous messages for context
            if not product_name:
                print("[PRODUCT] No product in current message - checking session history...")
                for i, msg in enumerate(reversed(session)):
                    try:
                        raw = msg.get('message') if isinstance(msg, dict) else ''
                        if raw is None:
                            continue
                        if not isinstance(raw, str):
                            raw = str(raw)
                        msg_content = raw.lower()
                        print(f"[PRODUCT] Checking message {len(session)-i}: {msg_content[:50]}...")
                    except Exception as e:
                        print(f"[PRODUCT ERROR] Failed to process message: {e}")
                        msg_content = ''
                    if 'cheesecake' in msg_content or 'cheese cake' in msg_content:
                        product_name = 'cheesecake'
                        print(f"[PRODUCT] Found 'cheesecake' in message {len(session)-i}")
                        break
                    elif 'chocolate' in msg_content:
                        product_name = 'chocolate fudge cake'
                        print(f"[PRODUCT] Found 'chocolate' in message {len(session)-i}")
                        break
                    elif 'croissant' in msg_content:
                        product_name = 'croissant'
                        print(f"[PRODUCT] Found 'croissant' in message {len(session)-i}")
                        break
            else:
                print(f"[PRODUCT] Product already determined: {product_name}")
                
            print(f"[PRODUCT] Final product name: {product_name}")
            
            # Determine if it's pickup or delivery
            # Prefer robust detector; fall back to simple heuristics and extracted entity
            ful_det = self._detect_fulfillment(query)
            is_pickup = (ful_det == 'pickup') or any(term in query.lower() for term in ["pickup", "pick up", "pick-up", "pic up", "come get", "come pick up"]) or ent.get("fulfillment") == "pickup"
            is_delivery = (ful_det == 'delivery') or any(term in query.lower() for term in ["deliver", "delivery", "deliver it", "send to"]) or ent.get("fulfillment") == "delivery"
            print(f"DEBUG: Is pickup: {is_pickup}")
            
            # Set fulfillment type (do not default silently)
            try:
                if is_pickup:
                    cart.fulfillment_type = 'pickup'
                    fulfillment = FulfillmentType.pickup
                    print("DEBUG: Fulfillment decided as pickup (detector/heuristics)")
                elif is_delivery:
                    cart.fulfillment_type = 'delivery'
                    fulfillment = FulfillmentType.delivery
                    print("DEBUG: Fulfillment decided as delivery (detector/heuristics)")
                else:
                    fulfillment = None
                print(f"DEBUG: Fulfillment type set to: {fulfillment}")
            except Exception as e:
                print(f"ERROR: Failed to set fulfillment type: {e}")
                return self._ok("order", "I'm having trouble with the order type. Please specify if this is for pickup or delivery.", {"order_placed": False, "reason": "fulfillment_type_error"})
            
            # --- Multi-item parsing ---
            print("\n[MULTI-ITEM PARSING] Searching for products in query...")
            ql_full = query.lower()
            print(f"[MULTI-ITEM] Query (lowercase): {ql_full}")
            
            print("[DATABASE] Querying all products for name matching...")
            db_products = db.query(Product).all()
            print(f"[DATABASE] Found {len(db_products)} products in database")
            
            found_items = []  # list of tuples (Product, quantity)

            for p in db_products:
                pname = p.name.lower()
                print(f"[MULTI-ITEM] Checking product: {pname}")
                if pname in ql_full:
                    print(f"[MULTI-ITEM] Product '{pname}' found in query!")
                    # quantity immediately preceding the product name (e.g., '3 chocolate fudge cake')
                    qty = 1
                    qty_match = re.search(r"(\d{1,3})\s+[a-z\s]*" + re.escape(pname), ql_full)
                    if qty_match:
                        try:
                            qty = int(qty_match.group(1))
                            print(f"[MULTI-ITEM] Quantity extracted: {qty}")
                        except Exception as e:
                            print(f"[MULTI-ITEM] Failed to parse quantity, using default: 1 (error: {e})")
                            qty = 1
                    else:
                        print(f"[MULTI-ITEM] No quantity specified, using default: 1")
                    found_items.append((p, qty))
                    print(f"[MULTI-ITEM] Added to found_items: {p.name} x {qty}")
                else:
                    print(f"[MULTIITEM] Product '{pname}' not found in query")
            
            print(f"[MULTI-ITEM] Total items found: {len(found_items)}")
            for p, qty in found_items:
                print(f"[MULTI-ITEM] - {p.name} x {qty}")

            # Fallback to single-entity product if nothing detected via scan
            print("\n[FALLBACK] Checking for single-entity product fallback...")
            if not found_items and product_name:
                print(f"[FALLBACK] No items found via scan, trying product_name: {product_name}")
                print("[DATABASE] Querying product by name pattern...")
                product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
                if product:
                    print(f"[FALLBACK] Found product: {product.name}")
                    try:
                        quantity = int(ent.get("quantity", 1))
                        print(f"[FALLBACK] Quantity from entities: {quantity}")
                    except (ValueError, TypeError) as e:
                        print(f"[FALLBACK] Failed to parse quantity, using default: 1 (error: {e})")
                        quantity = 1
                    found_items.append((product, quantity))
                    print(f"[FALLBACK] Added fallback item: {product.name} x {quantity}")
                else:
                    print(f"[FALLBACK] No product found matching pattern: {product_name}")
            else:
                print(f"[FALLBACK] Fallback not needed - found_items: {len(found_items)}, product_name: {product_name}")

            if not found_items:
                print("[NO ITEMS] No products detected in query...")
                # Check if we're in an ongoing order context - don't ask for clarification
                if cart.items or cart.awaiting_fulfillment or cart.awaiting_details or cart.awaiting_confirmation:
                    # We're in order context but no new products found - continue with existing cart
                    print("[NO ITEMS] In order context, no new products found, continuing with existing cart.")
                else:
                    print("[NO ITEMS] No products detected in query; asking user to specify.")
                    return self._clarify("order", "What item would you like to order?")

            # Stock check for all items first
            print("\n[STOCK CHECK] Verifying product availability...")
            for product, qty in found_items:
                print(f"[STOCK CHECK] Checking stock for {product.name}. Available: {product.quantity_in_stock}, Needed: {qty}")
                if product.quantity_in_stock < qty:
                    print(f"[STOCK CHECK] Insufficient stock for {product.name}")
                    print("[DATABASE] Querying alternatives in same category...")
                    alternatives = db.query(Product).filter(Product.quantity_in_stock > 0, Product.category == product.category).limit(3).all()
                    print(f"[STOCK CHECK] Found {len(alternatives)} alternatives: {[a.name for a in alternatives]}")
                    return self._ok(
                        "order",
                        f"We only have {product.quantity_in_stock} {product.name}(s) available.",
                        {
                            "order_placed": False,
                            "reason": "insufficient_stock",
                            "available_quantity": product.quantity_in_stock,
                            "product_name": product.name,
                            "alternatives": [a.name for a in alternatives]
                        }
                    )
                else:
                    print(f"[STOCK CHECK] Sufficient stock for {product.name}: {product.quantity_in_stock} >= {qty}")

            # Add all items to cart
            print("\n[CART ADDITION] Adding items to shopping cart...")
            for product, qty in found_items:
                print(f"[CART ADDITION] Adding {qty}x {product.name} to cart...")
                cart.add_item(product, qty)
                print(f"[CART ADDITION] Added successfully. Cart now has {len(cart.items)} items")

            # Build upsell suggestions (exclude already added products)
            print("\n[UPSELL] Building upsell suggestions...")
            added_ids = {p.id for p, _ in found_items}
            print(f"[UPSELL] Added product IDs: {added_ids}")
            print("[DATABASE] Querying for upsell suggestions...")
            suggestions = db.query(Product).filter(Product.quantity_in_stock > 0).filter(~Product.id.in_(list(added_ids))).limit(2).all()
            upsell_names = [s.name for s in suggestions]
            print(f"[UPSELL] Found {len(suggestions)} suggestions: {upsell_names}")

            # If fulfillment not yet chosen, ask for it now along with confirmation of added items
            print("\n[FULFILLMENT CHECK] Checking if fulfillment type is set...")
            if not cart.fulfillment_type:
                print("[FULFILLMENT CHECK] No fulfillment type set - asking user...")
                cart.awaiting_fulfillment = True
                added_summary = ", ".join([f"{qty}x {p.name}" for p, qty in found_items])
                print(f"[FULFILLMENT CHECK] Added summary: {added_summary}")
                print(f"[FULFILLMENT CHECK] Cart now has {len(cart.items)} items")
                return self._ok(
                    "checkout_fulfillment",
                    f"Added {added_summary} to your cart. Would you like delivery or pickup?",
                    {"needs_fulfillment_type": True, "cart_items": len(cart.items), "cart_summary": cart.get_summary(), "upsell_suggestions": upsell_names}
                )
            else:
                print(f"[FULFILLMENT CHECK] Fulfillment type already set: {cart.fulfillment_type}")

            # If branch not selected yet, ask for it now (for both pickup and delivery)
            print("\n[BRANCH CHECK] Checking if branch is selected...")
            if not cart.branch_name:
                try:
                    locations = self._load_locations()
                    branches = [loc["name"] for loc in locations]
                except Exception:
                    branches = ["Downtown Location", "Westside Location", "Mall Location"]
                return self._ok(
                    "checkout_missing_details",
                    "Which branch should we use for your order? (Downtown, Westside, or Mall)",
                    {"asking_for": "branch", "branches": branches, "in_order_context": True}
                )

            # If fulfillment chosen, proceed with missing details
            print("\n[MISSING DETAILS] Checking for missing required details...")
            missing_details = self._get_missing_details(cart)
            if missing_details:
                print(f"[MISSING DETAILS] Found missing details: {missing_details}")
                cart.awaiting_details = True
                print("[MISSING DETAILS] Setting cart to await details...")
                ask = self._ask_for_missing_details(cart, missing_details)
                ask.facts["upsell_suggestions"] = upsell_names
                print(f"[MISSING DETAILS] Returning request for details with upsell suggestions: {upsell_names}")
                return ask
            else:
                print("[MISSING DETAILS] All required details are present!")

            # All details present, ask for confirmation with receipt preview and include upsell
            print("\n[CONFIRMATION] All details complete - preparing order confirmation...")
            cart.awaiting_confirmation = True
            print("[CONFIRMATION] Building receipt preview...")
            preview_text = cart.build_receipt()
            print(f"[CONFIRMATION] Receipt preview built ({len(preview_text)} characters)")
            print(f"[CONFIRMATION] Upsell suggestions: {upsell_names}")
            return self._ok(
                "confirm_order",
                "Please review your order below and confirm if everything looks good.",
                {
                    "ready_to_confirm": True,
                    "preview_receipt_text": preview_text,
                    "in_order_context": True,
                    "upsell_suggestions": upsell_names
                }
            )
           
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
            
        # PRIORITY 2: Fulfillment-specific details
        if cart.fulfillment_type == 'pickup':
            if not cart.customer_info.get('phone_number'):
                print("[MISSING DETAILS CHECK] Missing phone number for pickup")
                missing_details.append('phone_number')
            if not cart.pickup_info.get('pickup_time'):
                print("[MISSING DETAILS CHECK] Missing pickup time")
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
            
        # PRIORITY 4: Branch selection (only if other details are complete)
        # Only ask for branch if we have all other essential details
        if (cart.customer_info.get('name') and 
            cart.payment_method and
            ((cart.fulfillment_type == 'pickup' and cart.customer_info.get('phone_number') and cart.pickup_info.get('pickup_time')) or
             (cart.fulfillment_type == 'delivery' and cart.delivery_info.get('address') and cart.delivery_info.get('delivery_time')))):
            
            if not cart.branch_name:
                print("[MISSING DETAILS CHECK] Missing branch selection (all other details complete)")
                missing_details.append('branch')
            else:
                print("[MISSING DETAILS CHECK] Branch already selected, all details complete!")
        else:
            print("[MISSING DETAILS CHECK] Branch selection deferred - other essential details missing")
        
        print(f"[MISSING DETAILS CHECK] Final missing details: {missing_details}")
        return missing_details

    def _ask_for_missing_details(self, cart, missing_details: List[str]) -> AgentResult:
        """Helper method to ask for missing details."""
        if 'items' in missing_details:
            return self._ok(
                "checkout_missing_details", 
                "I notice your cart is empty! Please add some items to your order first. You can say something like 'Add 2 chocolate cakes' or 'I'd like 1 bread and 3 cookies'.",
                {
                    "missing_details": missing_details, 
                    "asking_for": "items", 
                    "cart_empty": True,
                    "in_order_context": True
                }
            )
        elif 'name' in missing_details:
            return self._ok("checkout_missing_details", "Got it! What's the name for the order?", {"missing_details": missing_details, "asking_for": "name", "in_order_context": True})
        elif 'branch' in missing_details:
            try:
                locations = self._load_locations()
                branches = [loc["name"] for loc in locations]
            except Exception:
                branches = ["Downtown Location", "Westside Location", "Mall Location"]
            return self._ok("checkout_missing_details", "Which branch should we use for your order? (Downtown, Westside, or Mall)", {"missing_details": missing_details, "asking_for": "branch", "branches": branches, "in_order_context": True})
        elif 'phone_number' in missing_details and cart.fulfillment_type == 'pickup':
            return self._ok("checkout_missing_details", f"Thanks {cart.customer_info.get('name', '')}! For pickup, what's the best phone number to reach you?", {"missing_details": missing_details, "asking_for": "phone_number", "in_order_context": True})
        elif 'pickup_time' in missing_details and cart.fulfillment_type == 'pickup':
            # include branch hours hint
            try:
                from datetime import datetime
                open_t, close_t = self._get_branch_hours_for_datetime(cart.branch_name or '', datetime.now())
                window = f"{open_t.strftime('%-I:%M %p')}–{close_t.strftime('%-I:%M %p')}" if hasattr(open_t, 'strftime') else "business hours"
            except Exception:
                window = "business hours"
            return self._ok("checkout_missing_details", f"Perfect! What pickup time works for you, {cart.customer_info.get('name', '')}? Our {cart.branch_name or 'branch'} window is {window}.", {"missing_details": missing_details, "asking_for": "pickup_time", "in_order_context": True})
        elif 'address' in missing_details and cart.fulfillment_type == 'delivery':
            return self._ok("checkout_missing_details", f"Thanks {cart.customer_info.get('name', '')}! What's the full delivery address?", {"missing_details": missing_details, "asking_for": "address", "in_order_context": True})
        elif 'delivery_time' in missing_details and cart.fulfillment_type == 'delivery':
            return self._ok("checkout_missing_details", f"Great! What delivery time works for you, {cart.customer_info.get('name', '')}?", {"missing_details": missing_details, "asking_for": "delivery_time", "in_order_context": True})
        elif 'payment_method' in missing_details:
            return self._ok("checkout_missing_details", f"Almost done, {cart.customer_info.get('name', '')}! How would you like to pay? (cash, card, or UPI)", {"missing_details": missing_details, "asking_for": "payment_method", "in_order_context": True})
        else:
            return self._ok("checkout_missing_details", "I need a few more details to place your order.", {"missing_details": missing_details, "in_order_context": True})

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
