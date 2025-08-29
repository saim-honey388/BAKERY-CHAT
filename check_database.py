#!/usr/bin/env python3
"""
Database State Checker

PURPOSE:
    This script checks the current state of the bakery database
    to see what products, customers, and orders exist.

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

def check_database_state():
    """Check and display the current database state."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("CURRENT DATABASE STATE")
        print("=" * 80)
        
        # Products
        products = db.query(Product).all()
        print(f"\n📦 Products ({len(products)} total):")
        for p in products:
            print(f"  - {p.name}: {p.quantity_in_stock} in stock @ ${p.price}")
        
        # Customers
        customers = db.query(Customer).all()
        print(f"\n👥 Customers ({len(customers)} total):")
        for c in customers:
            print(f"  - {c.name}: {c.phone_number}")
        
        # Orders
        orders = db.query(Order).all()
        print(f"\n📋 Orders ({len(orders)} total):")
        for o in orders:
            customer = db.query(Customer).filter(Customer.id == o.customer_id).first()
            customer_name = customer.name if customer else f"Customer #{o.customer_id}"
            print(f"  - Order #{o.id}: {customer_name}")
            print(f"    Status: {o.status.value}")
            print(f"    Type: {o.pickup_or_delivery.value}")
            print(f"    Total: ${o.total_amount or 0:.2f}")
            print(f"    Created: {o.created_at}")
        
        # Order Items
        order_items = db.query(OrderItem).all()
        print(f"\n🛒 Order Items ({len(order_items)} total):")
        for oi in order_items:
            product = db.query(Product).filter(Product.id == oi.product_id).first()
            product_name = product.name if product else f"Product #{oi.product_id}"
            print(f"  - Order #{oi.order_id}: {oi.quantity}x {product_name} @ ${oi.price_at_time_of_order}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"Error checking database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_database_state()
