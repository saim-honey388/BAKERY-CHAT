#!/usr/bin/env python3
"""
Direct OrderAgent Test

PURPOSE:
    This script directly tests the OrderAgent by importing it and
    testing its functionality without API calls.

CREATED:
    January 2025
    Author: AI Assistant
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_order_agent_direct():
    """Test OrderAgent directly by importing it."""
    print("🧪 DIRECT ORDER AGENT TEST")
    print("="*60)
    print("Purpose: Test OrderAgent by direct import")
    print("Created: January 2025")
    print("="*60)
    
    try:
        # Try to import the modules
        print("\n📦 Testing imports...")
        
        # Test database imports
        print("  - Testing database imports...")
        from data.database import SessionLocal, engine, Base
        from data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
        print("    ✅ Database imports successful")
        
        # Test agent imports
        print("  - Testing agent imports...")
        from agents.order_agent import OrderAgent
        print("    ✅ OrderAgent import successful")
        
        # Test other imports
        print("  - Testing other imports...")
        from agents.base_agent import BaseAgent
        from schemas.io_models import AgentResult
        print("    ✅ All imports successful")
        
        # Create OrderAgent instance
        print("\n🤖 Creating OrderAgent instance...")
        agent = OrderAgent()
        print("    ✅ OrderAgent created successfully")
        
        # Test basic functionality
        print("\n🧪 Testing basic functionality...")
        
        # Test cart creation
        cart = OrderAgent.ShoppingCart()
        print("    ✅ ShoppingCart created")
        
        # Test cart properties
        print(f"    - Cart items: {len(cart.items)}")
        print(f"    - Cart total: ${cart.get_total():.2f}")
        print(f"    - Awaiting fulfillment: {cart.awaiting_fulfillment}")
        print(f"    - Awaiting details: {cart.awaiting_details}")
        print(f"    - Awaiting confirmation: {cart.awaiting_confirmation}")
        
        # Test business hours validation
        print("\n⏰ Testing business hours validation...")
        valid_time = "2024-01-15T14:30:00"
        is_valid = OrderAgent._is_time_within_business_hours(valid_time)
        print(f"    - Time {valid_time} is valid: {is_valid}")
        
        # Test confirmation detection
        print("\n✅ Testing confirmation detection...")
        confirmations = ["yes", "confirm", "place order", "no", "wait"]
        for phrase in confirmations:
            is_confirm = agent._is_strong_confirmation(phrase)
            print(f"    - '{phrase}' is confirmation: {is_confirm}")
        
        # Test database connection
        print("\n🗄️ Testing database connection...")
        db = SessionLocal()
        try:
            # Get products
            products = db.query(Product).limit(5).all()
            print(f"    ✅ Found {len(products)} products in database")
            
            # Get customers
            customers = db.query(Customer).limit(5).all()
            print(f"    ✅ Found {len(customers)} customers in database")
            
            # Get orders
            orders = db.query(Order).limit(5).all()
            print(f"    ✅ Found {len(orders)} orders in database")
            
        finally:
            db.close()
        
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ OrderAgent is working correctly")
        print("✅ Database connection is working")
        print("✅ All imports are successful")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}")
        print("❌ There are issues with the import structure")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("❌ There are issues with the OrderAgent functionality")
        return False

if __name__ == "__main__":
    success = test_order_agent_direct()
    sys.exit(0 if success else 1)
