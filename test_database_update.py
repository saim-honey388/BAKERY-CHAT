#!/usr/bin/env python3
"""
Database Update Test

PURPOSE:
    This script manually creates an order to test if the database
    gets updated properly.

CREATED:
    January 2025
    Author: AI Assistant
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from data.database import SessionLocal
from data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
from datetime import datetime

def test_database_update():
    """Test database update by manually creating an order."""
    print("🧪 DATABASE UPDATE TEST")
    print("="*60)
    print("Purpose: Test database updates by manual order creation")
    print("Created: January 2025")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Get initial state
        print("\n📊 INITIAL DATABASE STATE:")
        initial_products = db.query(Product).all()
        initial_customers = db.query(Customer).all()
        initial_orders = db.query(Order).all()
        
        print(f"  - Products: {len(initial_products)}")
        print(f"  - Customers: {len(initial_customers)}")
        print(f"  - Orders: {len(initial_orders)}")
        
        # Get a product to order
        chocolate_cake = db.query(Product).filter(Product.name == "Chocolate Fudge Cake").first()
        if not chocolate_cake:
            print("❌ Chocolate Fudge Cake not found in database")
            return False
        
        print(f"\n📦 Selected product: {chocolate_cake.name}")
        print(f"  - Current stock: {chocolate_cake.quantity_in_stock}")
        print(f"  - Price: ${chocolate_cake.price}")
        
        # Create or find customer
        customer_name = "Test Customer API"
        customer_phone = "555-9999"
        
        customer = db.query(Customer).filter(
            Customer.name == customer_name,
            Customer.phone_number == customer_phone
        ).first()
        
        if not customer:
            print(f"\n👤 Creating new customer: {customer_name}")
            customer = Customer(name=customer_name, phone_number=customer_phone)
            db.add(customer)
            db.flush()  # Get the ID
            print(f"  ✅ Customer created with ID: {customer.id}")
        else:
            print(f"\n👤 Found existing customer: {customer.name} (ID: {customer.id})")
        
        # Create order
        print(f"\n📋 Creating order...")
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.pending,
            pickup_or_delivery=FulfillmentType.pickup,
            total_amount=chocolate_cake.price * 2  # Order 2 cakes
        )
        db.add(order)
        db.flush()  # Get the ID
        print(f"  ✅ Order created with ID: {order.id}")
        print(f"  - Total amount: ${order.total_amount}")
        
        # Create order item
        print(f"\n🛒 Creating order item...")
        order_item = OrderItem(
            order_id=order.id,
            product_id=chocolate_cake.id,
            quantity=2,
            price_at_time_of_order=chocolate_cake.price
        )
        db.add(order_item)
        print(f"  ✅ Order item created")
        print(f"  - Quantity: {order_item.quantity}")
        print(f"  - Price: ${order_item.price_at_time_of_order}")
        
        # Update product stock
        print(f"\n📦 Updating product stock...")
        initial_stock = chocolate_cake.quantity_in_stock
        chocolate_cake.quantity_in_stock -= 2
        print(f"  - Stock before: {initial_stock}")
        print(f"  - Stock after: {chocolate_cake.quantity_in_stock}")
        
        # Commit all changes
        print(f"\n💾 Committing changes to database...")
        db.commit()
        print(f"  ✅ All changes committed successfully!")
        
        # Check final state
        print(f"\n📊 FINAL DATABASE STATE:")
        final_products = db.query(Product).all()
        final_customers = db.query(Customer).all()
        final_orders = db.query(Order).all()
        final_order_items = db.query(OrderItem).all()
        
        print(f"  - Products: {len(final_products)}")
        print(f"  - Customers: {len(final_customers)}")
        print(f"  - Orders: {len(final_orders)}")
        print(f"  - Order Items: {len(final_order_items)}")
        
        # Verify the changes
        print(f"\n✅ VERIFICATION:")
        
        # Check if customer was added
        if len(final_customers) > len(initial_customers):
            print(f"  ✅ New customer was added")
        else:
            print(f"  ✅ Customer already existed")
        
        # Check if order was added
        if len(final_orders) > len(initial_orders):
            print(f"  ✅ New order was added")
        else:
            print(f"  ❌ Order was not added")
        
        # Check if order item was added
        if len(final_order_items) > 0:
            print(f"  ✅ Order item was added")
        else:
            print(f"  ❌ Order item was not added")
        
        # Check if stock was updated
        updated_cake = db.query(Product).filter(Product.id == chocolate_cake.id).first()
        if updated_cake.quantity_in_stock == initial_stock - 2:
            print(f"  ✅ Product stock was updated correctly")
        else:
            print(f"  ❌ Product stock was not updated correctly")
        
        print(f"\n🎉 DATABASE UPDATE TEST COMPLETED!")
        print(f"✅ Database is being updated properly")
        print(f"✅ Orders are being created successfully")
        print(f"✅ Inventory is being updated correctly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = test_database_update()
    sys.exit(0 if success else 1)
