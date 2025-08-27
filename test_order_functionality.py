#!/usr/bin/env python3
"""
Test script to verify that the order functionality works after fixing the database schema.
"""

from backend.data.database import SessionLocal
from backend.data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
from backend.agents.order_agent import OrderAgent

def test_order_creation():
    """Test creating a new order to verify the fix works."""
    print("Testing order creation functionality...")
    
    db = SessionLocal()
    try:
        # Create a test order agent
        order_agent = OrderAgent()
        session_id = "test_session_123"
        
        # Simulate adding items to cart
        cart = order_agent.carts.get(session_id)
        if not cart:
            cart = OrderAgent.ShoppingCart()
            order_agent.carts[session_id] = cart
        
        # Get a product from the database
        product = db.query(Product).first()
        if not product:
            print("No products found in database!")
            return False
        
        print(f"Adding product: {product.name} (${product.price})")
        cart.add_item(product, 2)
        
        # Set required order details
        cart.fulfillment_type = 'pickup'
        cart.customer_info = {'name': 'Test Customer', 'phone_number': '555-0123'}
        cart.pickup_info = {'pickup_time': '2025-08-28T14:00:00'}
        cart.payment_method = 'cash'
        cart.branch_name = 'Downtown Location'
        
        print("Cart setup complete. Testing order finalization...")
        
        # Test the finalize_order method directly
        result = order_agent._finalize_order(db, cart, session_id)
        
        if result.get("order_placed"):
            print(f"[SUCCESS] Order created successfully! Order ID: {result.get('order_id')}")
            print(f"Receipt preview:\n{result.get('receipt_text', 'No receipt')[:200]}...")
            return True
        else:
            print(f"[FAILED] Order creation failed: {result.get('note', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error during order creation test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def verify_database_state():
    """Verify the current state of the database."""
    print("\nVerifying database state...")
    
    db = SessionLocal()
    try:
        # Check orders
        orders = db.query(Order).all()
        print(f"Total orders in database: {len(orders)}")
        
        for order in orders:
            if order.total_amount is not None:
                total_str = f"${order.total_amount:.2f}"
            else:
                total_str = "NULL"
            print(f"  Order #{order.id}: Customer {order.customer_id}, "
                  f"Status: {order.status.value}, "
                  f"Total: {total_str}")
        
        # Check order items
        order_items = db.query(OrderItem).all()
        print(f"Total order items: {len(order_items)}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error verifying database state: {e}")
        return False
    finally:
        db.close()

def main():
    """Main test function."""
    print("Testing Order Functionality After Database Schema Fix")
    print("=" * 60)
    
    # Verify current database state
    if not verify_database_state():
        return
    
    # Test order creation
    success = test_order_creation()
    
    # Verify final state
    verify_database_state()
    
    if success:
        print("\n[SUCCESS] All tests passed! The order functionality is working correctly.")
    else:
        print("\n[FAILED] Tests failed. There may still be issues with the order functionality.")

if __name__ == "__main__":
    main()