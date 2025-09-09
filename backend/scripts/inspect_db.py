#!/usr/bin/env python3
"""
Inspect the bakery database: print all rows from core tables and show relationships.

Usage:
  python backend/scripts/inspect_db.py

Notes:
- Uses the existing SQLAlchemy session and models.
- Safe read‑only inspection; makes no writes.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

# Allow running from repo root or from backend/
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.data.database import SessionLocal
from backend.data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType


def line(ch: str = "-", width: int = 60) -> str:
    return ch * width


def print_products(session):
    print(line("="))
    print("Products")
    print(line("="))
    products = session.query(Product).order_by(Product.id).all()
    print(f"Total products: {len(products)}")
    for p in products:
        print(
            f"- #{p.id} {p.name} | price=${p.price:.2f} | stock={p.quantity_in_stock} | category={getattr(p, 'category', None)}"
        )
    print()


def print_customers(session):
    print(line("="))
    print("Customers")
    print(line("="))
    customers = session.query(Customer).order_by(Customer.id).all()
    print(f"Total customers: {len(customers)}")
    for c in customers:
        phone = getattr(c, 'phone_number', None)
        print(f"- #{c.id} {c.name or '(no name)'} | phone={phone or '(none)'}")
    print()


def print_orders(session):
    print(line("="))
    print("Orders (with items and connectivity)")
    print(line("="))
    orders = session.query(Order).order_by(Order.id).all()
    print(f"Total orders: {len(orders)}")
    for o in orders:
        status = o.status.name if isinstance(o.status, OrderStatus) else str(o.status)
        fulfill = (
            o.pickup_or_delivery.name if isinstance(o.pickup_or_delivery, FulfillmentType) else str(o.pickup_or_delivery)
        )
        # Format time fields
        pickup_delivery_time_str = "N/A"
        if o.pickup_delivery_time:
            pickup_delivery_time_str = o.pickup_delivery_time.strftime("%Y-%m-%d %I:%M %p")
        
        confirmed_at_str = "N/A"
        if o.confirmed_at:
            confirmed_at_str = o.confirmed_at.strftime("%Y-%m-%d %I:%M %p")
        
        print(
            f"\nOrder #{o.id} | customer_id={o.customer_id} | status={status} | fulfillment={fulfill} | total=${float(o.total_amount or 0):.2f}"
        )
        print(f"  Pickup/Delivery Time: {pickup_delivery_time_str}")
        print(f"  Confirmed At: {confirmed_at_str}")

        # Join to customer for connectivity
        customer = session.query(Customer).get(o.customer_id)
        if customer:
            phone = getattr(customer, 'phone_number', None)
            print(f"  Customer → #{customer.id} {customer.name or '(no name)'} | phone={phone or '(none)'}")
        else:
            print("  Customer → (missing)")

        # Items
        items = session.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        print(f"  Items: {len(items)}")
        for it in items:
            # Join to product for connectivity
            product = session.query(Product).get(it.product_id)
            pname = product.name if product else "(missing product)"
            print(
                f"    - {it.quantity} x {pname} (product_id={it.product_id}) @ ${float(it.price_at_time_of_order or 0):.2f}"
            )
    print()


def main():
    session = SessionLocal()
    try:
        print(f"DB Inspection — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print_products(session)
        print_customers(session)
        print_orders(session)
        print(line("="))
        print("End of database inspection")
        print(line("="))
    finally:
        session.close()


if __name__ == "__main__":
    main()


