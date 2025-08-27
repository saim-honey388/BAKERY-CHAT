#!/usr/bin/env python3
"""
Script to fix the database schema by adding total_amount column and populating existing orders.
"""

import sqlite3
import os
from backend.data.database import SessionLocal
from backend.data.models import Order, OrderItem

def check_column_exists(db_path, table_name, column_name):
    """Check if a column exists in a table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    
    conn.close()
    return column_name in columns

def add_total_amount_column(db_path):
    """Add total_amount column if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN total_amount FLOAT")
        print("Added total_amount column to orders table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("total_amount column already exists")
        else:
            raise e
    
    conn.commit()
    conn.close()

def populate_total_amounts():
    """Calculate and populate total_amount for existing orders."""
    db = SessionLocal()
    try:
        # Get all orders that don't have total_amount set
        orders = db.query(Order).filter(Order.total_amount.is_(None)).all()
        
        print(f"Found {len(orders)} orders without total_amount")
        
        for order in orders:
            # Calculate total from order items
            total = 0.0
            for item in order.items:
                total += item.quantity * item.price_at_time_of_order
            
            # Update the order
            order.total_amount = total
            print(f"Order #{order.id}: Set total_amount to ${total:.2f}")
        
        db.commit()
        print("Successfully populated total_amount for all existing orders")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

def main():
    """Main function to fix the database schema."""
    db_path = os.path.join("backend", "data", "bakery.db")
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    print("Checking database schema...")
    
    # Check if total_amount column exists
    has_column = check_column_exists(db_path, "orders", "total_amount")
    print(f"total_amount column exists: {has_column}")
    
    if not has_column:
        print("Adding total_amount column...")
        add_total_amount_column(db_path)
    
    print("Populating total_amount values...")
    populate_total_amounts()
    
    print("Database schema fix completed!")

if __name__ == "__main__":
    main()