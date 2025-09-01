#!/usr/bin/env python3
"""
Complete Order Agent Workflow Test
==================================

This script demonstrates the entire Order Agent workflow from start to finish,
showing how LLM makes decisions and how the database is used throughout the process.

The workflow includes:
1. Initial query processing
2. LLM-driven order analysis
3. Database queries for products and validation
4. Cart management
5. Fulfillment type detection
6. Missing details collection
7. Order confirmation
8. Final order processing
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.agents.order_agent import OrderAgent
from backend.data.database import SessionLocal
from backend.data.models import Product, Customer, Order, OrderItem
from backend.schemas.io_models import AgentResult

def test_complete_workflow():
    """Test the complete Order Agent workflow with detailed debugging."""
    
    print("🧪 COMPLETE ORDER AGENT WORKFLOW TEST")
    print("=" * 80)
    
    # Initialize the Order Agent
    print("\n1️⃣ INITIALIZING ORDER AGENT...")
    agent = OrderAgent()
    print("✅ Order Agent initialized successfully")
    
    # Create a test session ID
    session_id = "test_session_123"
    print(f"📝 Test session ID: {session_id}")
    
    # Test queries that demonstrate the complete workflow
    test_queries = [
        "I want 2 chocolate cakes for pickup",
        "My name is John Smith",
        "I'll pick up at 3 PM",
        "I'll pay with cash",
        "Yes, confirm my order"
    ]
    
    print(f"\n2️⃣ TESTING COMPLETE WORKFLOW WITH {len(test_queries)} QUERIES...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"🔍 QUERY {i}: '{query}'")
        print(f"{'='*60}")
        
        # Create memory context (simulating what the Enhanced API would provide)
        memory_context = {
            "summary": "User is ordering chocolate cakes for pickup",
            "last_10_messages": test_queries[:i],
            "cart_state": {
                "items": ["chocolate cake"] if i > 1 else [],
                "total": "0",
                "status": "building" if i > 1 else "empty",
                "customer_info": "John Smith" if i > 2 else "no customer info available",
                "fulfillment_info": "pickup" if i > 1 else "not specified"
            },
            "important_features": [
                "user prefers chocolate desserts",
                "user orders for pickup",
                "user provides complete order details"
            ]
        }
        
        print(f"\n📚 MEMORY CONTEXT:")
        print(f"   Summary: {memory_context['summary']}")
        print(f"   Cart items: {memory_context['cart_state']['items']}")
        print(f"   Important features: {len(memory_context['important_features'])} features")
        
        # Process the query
        try:
            print(f"\n🚀 PROCESSING QUERY {i}...")
            result = agent.handle(session_id, query, [], memory_context)
            
            print(f"\n✅ QUERY {i} RESULT:")
            print(f"   Intent: {result.intent}")
            print(f"   Message: {result.facts.get('note', 'No message')}")
            print(f"   Facts: {result.facts}")
            
            if result.clarification_question:
                print(f"   Clarification needed: {result.clarification_question}")
                
        except Exception as e:
            print(f"\n❌ ERROR PROCESSING QUERY {i}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("🎯 WORKFLOW TEST COMPLETED!")
    print("=" * 80)
    
    # Show final cart state
    cart = agent.carts.get(session_id)
    if cart:
        print(f"\n🛒 FINAL CART STATE:")
        print(f"   Items: {len(cart.items)}")
        print(f"   Customer: {cart.customer_info}")
        print(f"   Fulfillment: {cart.fulfillment_type}")
        print(f"   Branch: {cart.branch_name}")
        print(f"   Payment: {cart.payment_method}")
        print(f"   Awaiting: fulfillment={cart.awaiting_fulfillment}, details={cart.awaiting_details}, confirmation={cart.awaiting_confirmation}")
    else:
        print("\n❌ No cart found for session")

def test_database_operations():
    """Test database operations to ensure proper connectivity."""
    
    print("\n🗄️ TESTING DATABASE OPERATIONS...")
    
    try:
        db = SessionLocal()
        
        # Test product queries
        print("   📊 Querying products...")
        products = db.query(Product).all()
        print(f"   ✅ Found {len(products)} products")
        
        for product in products:
            print(f"      - {product.name}: ${product.price:.2f} (Stock: {product.quantity_in_stock})")
        
        # Test customer queries
        print("   👥 Querying customers...")
        customers = db.query(Customer).all()
        print(f"   ✅ Found {len(customers)} customers")
        
        # Test order queries
        print("   📋 Querying orders...")
        orders = db.query(Order).all()
        print(f"   ✅ Found {len(orders)} orders")
        
        db.close()
        print("   ✅ Database operations completed successfully")
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        import traceback
        traceback.print_exc()

def test_llm_integration():
    """Test LLM integration methods."""
    
    print("\n🧠 TESTING LLM INTEGRATION...")
    
    try:
        agent = OrderAgent()
        
        # Test fulfillment detection
        print("   🔍 Testing fulfillment detection...")
        test_queries = [
            "I want delivery to 123 Main St",
            "I'll pick up my order",
            "Can you deliver this to my office?",
            "I prefer pickup at 2 PM"
        ]
        
        for query in test_queries:
            result = agent._detect_fulfillment(query)
            print(f"      Query: '{query}' -> Result: {result}")
        
        print("   ✅ LLM integration tests completed")
        
    except Exception as e:
        print(f"   ❌ LLM integration error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Complete Order Agent Workflow Test...")
    
    # Test database operations first
    test_database_operations()
    
    # Test LLM integration
    test_llm_integration()
    
    # Test complete workflow
    test_complete_workflow()
    
    print("\n🎉 All tests completed! Check the console output for detailed workflow information.")
