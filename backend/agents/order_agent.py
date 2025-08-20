"""Order Agent: handles order creation and persistence using the database."""
from .base_agent import BaseAgent
from ..schemas.io_models import AgentResult
from typing import List, Dict, Any
from ..data.database import SessionLocal
from ..data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
from ..nlu.entity_extractor import EntityExtractor
from sqlalchemy.orm import Session
import datetime

class OrderAgent(BaseAgent):
    name = "order"

    def __init__(self):
        pass  # No need to handle CSV files anymore

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
                print(f"- Order #{o.id}: Customer {o.customer_id}, Status: {o.status.value}, Fulfillment: {o.fulfillment.value}")

        # Print Order Items
        order_items = db.query(OrderItem).all()
        print("\n[Order Items]")
        if not order_items:
            print("No order items found.")
        else:
            for oi in order_items:
                print(f"- Item: {oi.product.name}, Quantity: {oi.quantity}, Order ID: {oi.order_id}")
        print("-----------------------\n")

    def _find_or_create_customer(self, db: Session, session_id: str = None) -> Customer:
        """Finds an existing customer or creates a new one.
        
        Args:
            db: Database session
            session_id: Optional session ID to use as customer identifier
            
        Returns:
            Customer: The found or created customer
        """
        # Use session_id if provided, otherwise use a default customer
        customer_name = f"customer_{session_id}" if session_id else "default_customer"
        
        # Try to find existing customer by name
        customer = db.query(Customer).filter(Customer.name == customer_name).first()
        
        # If customer doesn't exist, create a new one
        if not customer:
            customer = Customer(
                name=customer_name,
                phone_number="N/A"  # You might want to collect this later
            )
            db.add(customer)
            db.flush()  # Get the customer ID without committing the transaction
            db.refresh(customer)
            print(f"DEBUG: Created new customer with ID: {customer.id}")
        
        return customer

    def handle(self, query: str, session: List[Dict[str, str]] = []) -> "AgentResult":
        print(f"[WORKFLOW] Executing OrderAgent...")
        db = SessionLocal()
        try:
            print("try block entered.......")
            
            # Check if this is a confirmation
            is_confirmation = any(phrase in query.lower() 
                               for phrase in ["yes", "sure", "place order", "confirm", "proceed", "no,just place the order"])
            
            # 1. Extract entities from current message
            ent = EntityExtractor().extract(query)
            print(f"DEBUG: Entities extracted: {ent}")
            
            # Get product name from entities or from context
            product_name = ent.get("product") or ent.get("product_name")
            
            # If no product in current message but it's a confirmation, check previous messages
            if not product_name and is_confirmation:
                for msg in reversed(session):
                    if 'chocolate' in msg.get('content', '').lower():
                        product_name = 'chocolate fudge cake'
                        break
                
            print(f"DEBUG: Product name: {product_name}")
            
            # Get quantity, default to 1 if not specified
            try:
                quantity = int(ent.get("quantity", 1))
            except (ValueError, TypeError):
                quantity = 1
            print(f"DEBUG: Quantity: {quantity}")
            
            # Determine if it's pickup or delivery
            is_pickup = any(term in query.lower() for term in ["pickup", "pick up", "come get", "come pick up"])
            print(f"DEBUG: Is pickup: {is_pickup}")
            
            # If no product name and this isn't a confirmation, ask for clarification
            if not product_name and not is_confirmation:
                print("DEBUG: No product name found, clarifying.")
                return self._clarify("order", "What item would you like to order?")

            # If we still don't have a product name after checking everything, ask for it
            if not product_name:
                print("DEBUG: Still no product name after checking context.")
                return self._clarify("order", "I'm sorry, I couldn't determine what you'd like to order. Could you please tell me the name of the item?")

            # Set fulfillment type
            try:
                fulfillment = FulfillmentType.pickup if is_pickup else FulfillmentType.delivery
                print(f"DEBUG: Fulfillment type set to: {fulfillment}")
            except Exception as e:
                print(f"ERROR: Failed to set fulfillment type: {e}")
                return self._ok("order", "I'm having trouble with the order type. Please specify if this is for pickup or delivery.", {"order_placed": False, "reason": "fulfillment_type_error"})
            
            # 2. Find the product and check stock
            print(f"DEBUG: Finding product: {product_name}")
            product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
            print(f"DEBUG: Product found: {product.name if product else 'None'}")

            if not product:
                print(f"DEBUG: Product '{product_name}' not found, clarifying.")
                return self._clarify("order", f"I'm sorry, I couldn't find '{product_name}' on our menu. Would you like to try something else?")

            print(f"DEBUG: Checking stock for {product.name}. Available: {product.quantity_in_stock}, Needed: {quantity}")
            if product.quantity_in_stock < quantity:
                print(f"DEBUG: Not enough stock for {product.name}. Available: {product.quantity_in_stock}")
                return self._ok(
                    "order",
                    f"I'm sorry, we only have {product.quantity_in_stock} {product.name}(s) in stock. Would you like to order a smaller quantity?",
                    {
                        "order_placed": False,
                        "reason": "insufficient_stock",
                        "available_quantity": product.quantity_in_stock,
                        "product_name": product.name
                    }
                )

            # 3. Find or create customer
            session_id = None
            if isinstance(session, list) and session:
                for msg in reversed(session):
                    if isinstance(msg, dict) and "session_id" in msg:
                        session_id = msg["session_id"]
                        break
            
            print(f"DEBUG: Using session ID: {session_id}")
            customer = self._find_or_create_customer(db, session_id=session_id)
            if not customer:
                print("ERROR: Failed to find or create customer")
                return self._ok(
                    "order", 
                    "I'm sorry, I couldn't process your order. Please try again.", 
                    {
                        "order_placed": False, 
                        "reason": "customer_creation_failed"
                    }
                )

            # 4. Create order
            print("DEBUG: Creating order...")
            order = Order(
                customer_id=customer.id,
                status=OrderStatus.pending,  # Use lowercase to match enum definition
                pickup_or_delivery=fulfillment
            )
            db.add(order)
            db.flush()

            # 5. Create order item with price
            print("DEBUG: Creating order item...")
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                price_at_time_of_order=float(product.price)
            )
            db.add(order_item)

            # 6. Update product stock
            print("DEBUG: Updating product stock...")
            product.quantity_in_stock -= quantity

            # 7. Commit transaction
            db.commit()
            print(f"DEBUG: Order created successfully. Order ID: {order.id}")

            # 8. Calculate total price from order items
            total_price = float(product.price * quantity)
            
            # 9. Return success response
            fulfillment_text = "for pickup" if fulfillment == FulfillmentType.pickup else "for delivery"
            return self._ok(
                "order",
                f"Your order for {quantity} {product.name}(s) {fulfillment_text} has been placed! Your order ID is {order.id}.",
                {
                    "order_placed": True,
                    "order_id": order.id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "total_price": total_price,
                    "fulfillment": fulfillment.value
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
            try:
                if 'order' in locals() and order:
                    print(f"DEBUG: Order created with ID: {order.id}")
                    # Refresh the order to get the latest state
                    db.refresh(order)
                    # Print database status for debugging
                    self._print_db_status(db)
                    
                    # If we have a product, print order details
                    if 'product' in locals() and product:
                        print(f"Order Details:")
                        print(f"- {quantity}x {product.name} (Order #{order.id})")
                        print(f"- Total Price: ${product.price * quantity:.2f}")
                        print("-----------------------")
            except Exception as e:
                print(f"Error in finally block: {e}")
            finally:
                db.close()

    def _ok(self, intent: str, message: str, facts: Dict = {}) -> AgentResult:
        print(f"[OK] {message}")
        return AgentResult(
            agent=self.name,
            status="success",
            intent=intent,
            message=message,
            facts=facts
        )

    def _clarify(self, intent: str, question: str) -> AgentResult:
        print(f"[CLARIFY] for intent '{intent}': {question}")
        return AgentResult(
            agent=self.name,
            status="clarify",
            intent=intent,
            message=question,
            facts={"needs_clarification": True}
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
                print(f"- Order #{o.id}: {o.status}, Total: ${o.total_price}")
        print("\n[Order Items]")
        order_items = db.query(OrderItem).all()
        if not order_items:
            print("No order items found.")
        else:
            for oi in order_items:
                print(f"- {oi.quantity}x {oi.product.name} (Order #{oi.order_id})")
        print("-----------------------")
