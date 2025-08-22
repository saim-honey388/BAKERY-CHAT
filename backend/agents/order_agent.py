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

    def _finalize_order(self, db: Session, cart: ShoppingCart, session_id: str) -> Dict[str, Any]:
        """Single gateway for order finalization - called from one place only."""
        if not cart.items:
            return {"order_placed": False, "note": "Your cart is empty. Please add some items before confirming."}
        
        # Final stock check
        for item in cart.items:
            product = item['product']
            if product.quantity_in_stock < item['quantity']:
                return {
                    "order_placed": False, 
                    "note": f"Sorry, we only have {product.quantity_in_stock} {product.name} in stock. Would you like to adjust your order?"
                }
        
        # Create customer
        customer = self._find_or_create_customer(
            db, session_id, 
            cart.customer_info.get('name'), 
            cart.customer_info.get('phone_number')
        )
        
        # Create order
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.PENDING,
            pickup_or_delivery=FulfillmentType.PICKUP if cart.fulfillment_type == 'pickup' else FulfillmentType.DELIVERY,
            total_amount=cart.get_total()
        )
        db.add(order)
        db.flush()
        
        # Create order items and update inventory
        for item in cart.items:
            product = item['product']
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item['quantity'],
                unit_price=product.price
            )
            db.add(order_item)
            
            # Update inventory
            product.quantity_in_stock -= item['quantity']
        
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
        
        # Store receipt for this session
        self.last_receipt_by_session[session_id] = receipt_text
        
        # Clear cart
        cart.clear()
        
        # Console DB snapshot
        self._print_db_status(db)
        
        return {
            "order_placed": True,
            "order_id": order.id,
            "receipt_text": receipt_text,
            "note": "Your order has been placed successfully!"
        }

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

    def handle(self, session_id: str, query: str, session: List[Dict[str, str]] = []) -> "AgentResult":
        print(f"[WORKFLOW] Executing OrderAgent...")
        db = SessionLocal()
        try:
            print("try block entered.......")
            # ensure a cart for this session
            cart = self.carts.get(session_id)
            if cart is None:
                cart = OrderAgent.ShoppingCart()
                self.carts[session_id] = cart
            
            # Preprocess: lowercased text and early entity extraction to update cart state
            ql = query.lower().strip()
            ent_early = self.entity_extractor.extract(query)
            if ent_early.get("name"):
                cart.customer_info["name"] = ent_early["name"]
            if ent_early.get("phone_number"):
                cart.customer_info["phone_number"] = ent_early["phone_number"]
            if ent_early.get("payment_method"):
                cart.payment_method = ent_early["payment_method"]
            if ent_early.get("location"):
                # map simple keywords to branch names (best-effort)
                loc = ent_early["location"]
                if loc == 'downtown':
                    cart.branch_name = "Downtown Location"
                elif loc == 'westside':
                    cart.branch_name = "Westside Location"
                elif loc == 'mall':
                    cart.branch_name = "Mall Location"
            # If fulfillment already chosen, map time into the right field
            if ent_early.get("time"):
                if cart.fulfillment_type == 'pickup':
                    cart.pickup_info["pickup_time"] = ent_early["time"]
                elif cart.fulfillment_type == 'delivery':
                    cart.delivery_info["delivery_time"] = ent_early["time"]
            # Early address detection
            addr_match_early = re.search(r"(\d{1,5}\s+[A-Za-z0-9\.,\-\s]+\s+(Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Drive|Dr\.?))", query, flags=re.IGNORECASE)
            if addr_match_early:
                cart.delivery_info["address"] = addr_match_early.group(1).strip()
            
            # Check if this is a confirmation
            if 'clear cart' in query.lower() or 'remove everything' in query.lower():
                cart.clear()
                # Print DB snapshot to console (not to user)
                print("\n=== DB Snapshot After Order ===")
                print("[Products]")
                for p in db.query(Product).all():
                    print(f"- {p.name}: {p.quantity_in_stock} in stock")
                print("\n[Orders]")
                for o in db.query(Order).all():
                    print(f"- Order #{o.id}: Customer {o.customer_id}, Status: {o.status.value}, Fulfillment: {o.pickup_or_delivery.value}")
                print("\n[Order Items]")
                for oi in db.query(OrderItem).all():
                    print(f"- Order #{oi.order_id}: {oi.quantity} x {oi.product.name}")
                print("==============================\n")
                return self._ok("clear_cart", "Your cart has been cleared.", {"cart_cleared": True})
                
            # Handle checkout flow
            if any(k in query.lower() for k in ['checkout', 'place order', 'final order', 'finalize order']):
                if not cart.items:
                    return self._ok("checkout", "Your cart is empty. Please add some items before checking out.", {"needs_items": True})
                
                # If we don't have fulfillment type, ask for it
                if not cart.fulfillment_type:
                    cart.awaiting_fulfillment = True
                    return self._ok(
                        "checkout_fulfillment",
                        "Would you like delivery or pickup?",
                        {"needs_fulfillment_type": True, "cart_summary": cart.get_summary()}
                    )
                
                # If delivery, check for address
                if cart.fulfillment_type == 'delivery' and not cart.delivery_info.get('address'):
                    return self._ok(
                        "checkout_delivery_address",
                        "What's the delivery address? Please include street, city, and zip code.",
                        {"needs_address": True, "fulfillment": "delivery"}
                    )
                
                # If pickup, check for pickup time
                if cart.fulfillment_type == 'pickup' and not cart.pickup_info.get('pickup_time'):
                    return self._ok(
                        "checkout_pickup_time",
                        "When would you like to pick up your order? We're open from 8 AM to 6 PM.",
                        {"needs_pickup_time": True, "fulfillment": "pickup"}
                    )

                # Ask for required details
                missing_details = self._get_missing_details(cart)

                if missing_details:
                    cart.awaiting_details = True
                    return self._ask_for_missing_details(cart, missing_details)
                
                # If we have all info, confirm the order
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
            
            # Ongoing checkout flow handling
            ql = query.lower().strip()
            # Cart review requests
            if any(kw in ql for kw in ["review my cart", "show cart", "view cart", "cart summary", "what's in my cart", "whats in my cart"]):
                return self._ok(
                    "cart_summary",
                    "Here is your cart summary.",
                    {"cart_summary": cart.get_summary(), "cart_items": len(cart.items)}
                )
            if cart.awaiting_fulfillment:
                if re.search(r"\bpick\s*up\b|\bpick it up\b|\bpick\b", ql):
                    cart.fulfillment_type = 'pickup'
                    cart.awaiting_fulfillment = False
                elif re.search(r"\bdeliver(y)?\b|\bsend\b|\baddress\b", ql):
                    cart.fulfillment_type = 'delivery'
                    cart.awaiting_fulfillment = False
                if cart.awaiting_fulfillment:
                    return self._ok("checkout_fulfillment", "Would you like delivery or pickup?", {"needs_fulfillment_type": True})
                # after setting fulfillment, move to missing details if any
                missing_details = self._get_missing_details(cart)
                if missing_details:
                    cart.awaiting_details = True
                    return self._ask_for_missing_details(cart, missing_details)
                cart.awaiting_confirmation = True
                return self._ok("confirm_order", "Please confirm your order.", {"ready_to_confirm": True, "cart_summary": cart.get_summary(), "fulfillment": cart.fulfillment_type})

            if cart.awaiting_details:
                # entities are already extracted above; check if all required details are present now
                missing_details = self._get_missing_details(cart)
                
                if missing_details:
                    # Still missing details, ask for them using helper method
                    return self._ask_for_missing_details(cart, missing_details)
                
                # All details are complete. Show a full receipt-style preview and ask for confirmation.
                cart.awaiting_details = False
                cart.awaiting_confirmation = True
                preview_text = cart.build_receipt()
                return self._ok(
                    "confirm_order",
                    "Please review your order below and confirm if everything looks good.",
                    {
                        "ready_to_confirm": True,
                        "preview_receipt_text": preview_text,
                        "in_order_context": True,
                    }
                )

            # Receipt requests (common spellings)
            if any(w in ql for w in ["receipt", "reciept", "recipt", "repiet", "recipeet", "order receipt", "my receipt"]):
                if session_id in self.last_receipt_by_session:
                    return self._ok("order_receipt", "Here is your latest order receipt:", {"receipt_text": self.last_receipt_by_session[session_id]})
                return self._ok("order_receipt", "I don't see a recent order receipt yet. Would you like me to review your cart or place a new order?", {"receipt_available": False, "in_order_context": True})

            # Handle order confirmation - SINGLE GATEWAY
            if cart.awaiting_confirmation and self._is_strong_confirmation(query):
                cart.last_prompt = "confirm_order"
                return self._finalize_order(db, cart, session_id)
            
            # 1. Extract entities from current message
            ent = self.entity_extractor.extract(query)
            print(f"DEBUG: Entities extracted: {ent}")

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
            addr_match = re.search(r"(\d{1,5}\s+[A-Za-z0-9\.,\-\s]+\s+(Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Drive|Dr\.?))", query, flags=re.IGNORECASE)
            if addr_match:
                cart.delivery_info["address"] = addr_match.group(1).strip()
            
            # Get product name from entities or from context
            product_name = ent.get("product") or ent.get("product_name")
            
            # If no product in current message, check previous messages for context
            if not product_name:
                for msg in reversed(session):
                    if 'chocolate' in msg.get('content', '').lower():
                        product_name = 'chocolate fudge cake'
                        break
                
            print(f"DEBUG: Product name: {product_name}")
            
            # Determine if it's pickup or delivery
            is_pickup = any(term in query.lower() for term in ["pickup", "pick up", "come get", "come pick up"]) or ent.get("fulfillment") == "pickup"
            is_delivery = any(term in query.lower() for term in ["deliver", "delivery", "send to"]) or ent.get("fulfillment") == "delivery"
            print(f"DEBUG: Is pickup: {is_pickup}")
            
            # Set fulfillment type (do not default silently)
            try:
                if is_pickup:
                    cart.fulfillment_type = 'pickup'
                    fulfillment = FulfillmentType.pickup
                elif is_delivery:
                    cart.fulfillment_type = 'delivery'
                    fulfillment = FulfillmentType.delivery
                else:
                    fulfillment = None
                print(f"DEBUG: Fulfillment type set to: {fulfillment}")
            except Exception as e:
                print(f"ERROR: Failed to set fulfillment type: {e}")
                return self._ok("order", "I'm having trouble with the order type. Please specify if this is for pickup or delivery.", {"order_placed": False, "reason": "fulfillment_type_error"})
            
            # --- Multi-item parsing ---
            ql_full = query.lower()
            db_products = db.query(Product).all()
            found_items = []  # list of tuples (Product, quantity)

            for p in db_products:
                pname = p.name.lower()
                if pname in ql_full:
                    # quantity immediately preceding the product name (e.g., '3 chocolate fudge cake')
                    qty = 1
                    qty_match = re.search(r"(\d{1,3})\s+[a-z\s]*" + re.escape(pname), ql_full)
                    if qty_match:
                        try:
                            qty = int(qty_match.group(1))
                        except Exception:
                            qty = 1
                    found_items.append((p, qty))

            # Fallback to single-entity product if nothing detected via scan
            if not found_items and product_name:
                product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
                if product:
                    try:
                        quantity = int(ent.get("quantity", 1))
                    except (ValueError, TypeError):
                        quantity = 1
                    found_items.append((product, quantity))

            if not found_items:
                print("DEBUG: No products detected in query; asking user to specify.")
                return self._clarify("order", "What item would you like to order?")

            # Stock check for all items first
            for product, qty in found_items:
                print(f"DEBUG: Checking stock for {product.name}. Available: {product.quantity_in_stock}, Needed: {qty}")
                if product.quantity_in_stock < qty:
                    alternatives = db.query(Product).filter(Product.quantity_in_stock > 0, Product.category == product.category).limit(3).all()
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

            # Add all items to cart
            for product, qty in found_items:
                cart.add_item(product, qty)

            # Build upsell suggestions (exclude already added products)
            added_ids = {p.id for p, _ in found_items}
            suggestions = db.query(Product).filter(Product.quantity_in_stock > 0).filter(~Product.id.in_(list(added_ids))).limit(2).all()
            upsell_names = [s.name for s in suggestions]

            # If fulfillment not yet chosen, ask for it now along with confirmation of added items
            if not cart.fulfillment_type:
                cart.awaiting_fulfillment = True
                added_summary = ", ".join([f"{qty}x {p.name}" for p, qty in found_items])
                return self._ok(
                    "checkout_fulfillment",
                    f"Added {added_summary} to your cart. Would you like delivery or pickup?",
                    {"needs_fulfillment_type": True, "cart_items": len(cart.items), "cart_summary": cart.get_summary(), "upsell_suggestions": upsell_names}
                )

            # If branch not selected yet, ask for it now (for both pickup and delivery)
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
            missing_details = self._get_missing_details(cart)
            if missing_details:
                cart.awaiting_details = True
                ask = self._ask_for_missing_details(cart, missing_details)
                ask.facts["upsell_suggestions"] = upsell_names
                return ask

            # All details present, ask for confirmation with receipt preview and include upsell
            cart.awaiting_confirmation = True
            preview_text = cart.build_receipt()
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
            db.rollback()
            print("except block entered.......")
            print(f"Error in OrderAgent: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
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
            db.close()

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
        missing_details = []
        if not cart.customer_info.get('name'):
            missing_details.append('name')
        if not cart.branch_name:
            missing_details.append('branch')
        if cart.fulfillment_type == 'pickup' and not cart.customer_info.get('phone_number'):
            missing_details.append('phone_number')
        if cart.fulfillment_type == 'pickup' and not cart.pickup_info.get('pickup_time'):
            missing_details.append('pickup_time')
        if cart.fulfillment_type == 'delivery' and not cart.delivery_info.get('address'):
            missing_details.append('address')
        if cart.fulfillment_type == 'delivery' and not cart.delivery_info.get('delivery_time'):
            missing_details.append('delivery_time')
        if not cart.payment_method:
            missing_details.append('payment_method')
        return missing_details

    def _ask_for_missing_details(self, cart, missing_details: List[str]) -> AgentResult:
        """Helper method to ask for missing details."""
        if 'name' in missing_details:
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
