#!/usr/bin/env python3
"""
Complete application test script to verify the entire order flow works correctly.
Tests the API endpoints and complete order workflow.
"""

import requests
import json
import time
import uuid

# Configuration
BASE_URL = "http://localhost:8000"
SESSION_ID = f"test_session_{uuid.uuid4().hex[:8]}"

def test_api_health():
    """Test if the API is running and healthy."""
    print("Testing API health...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("[SUCCESS] API is running and accessible")
            return True
        else:
            print(f"[ERROR] API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to API. Make sure the server is running on port 8000")
        return False
    except Exception as e:
        print(f"[ERROR] Error testing API health: {e}")
        return False

def make_query(query, session_id=SESSION_ID):
    """Make a query to the chat API."""
    print(f"\nUser: {query}")
    
    payload = {
        "session_id": session_id,
        "query": query
    }
    
    try:
        response = requests.post(f"{BASE_URL}/query", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"Assistant: {data.get('response', 'No response')}")
            print(f"Intents: {data.get('intents', [])}")
            if data.get('citations'):
                print(f"Citations: {len(data['citations'])} sources")
            return data
        else:
            print(f"[ERROR] API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Error making query: {e}")
        return None

def test_complete_order_flow():
    """Test the complete order flow from start to finish."""
    print("\n" + "="*60)
    print("TESTING COMPLETE ORDER FLOW")
    print("="*60)
    
    # Step 1: Greet and ask about menu
    print("\n--- Step 1: Initial Greeting ---")
    response1 = make_query("Hello! What cakes do you have?")
    if not response1:
        return False
    
    # Step 2: Place an order
    print("\n--- Step 2: Place Order ---")
    response2 = make_query("I want to order 2 chocolate fudge cakes for pickup")
    if not response2:
        return False
    
    # Step 3: Provide fulfillment details
    print("\n--- Step 3: Fulfillment Details ---")
    response3 = make_query("pickup")
    if not response3:
        return False
    
    # Step 4: Provide customer name
    print("\n--- Step 4: Customer Name ---")
    response4 = make_query("My name is John Smith")
    if not response4:
        return False
    
    # Step 5: Provide branch
    print("\n--- Step 5: Branch Selection ---")
    response5 = make_query("Downtown")
    if not response5:
        return False
    
    # Step 6: Provide phone number
    print("\n--- Step 6: Phone Number ---")
    response6 = make_query("555-123-4567")
    if not response6:
        return False
    
    # Step 7: Provide pickup time
    print("\n--- Step 7: Pickup Time ---")
    response7 = make_query("2:00 PM today")
    if not response7:
        return False
    
    # Step 8: Provide payment method
    print("\n--- Step 8: Payment Method ---")
    response8 = make_query("cash")
    if not response8:
        return False
    
    # Step 9: Confirm the order
    print("\n--- Step 9: Order Confirmation ---")
    response9 = make_query("Yes, confirm the order")
    if not response9:
        return False
    
    # Check if order was successfully placed
    if "order has been placed" in response9.get('response', '').lower() or "thank you" in response9.get('response', '').lower():
        print("[SUCCESS] Order successfully placed!")
        return True
    else:
        print("[ERROR] Order confirmation failed")
        return False

def test_product_queries():
    """Test product information queries."""
    print("\n" + "="*60)
    print("TESTING PRODUCT QUERIES")
    print("="*60)
    
    queries = [
        "What pastries do you have?",
        "Show me cakes under $20",
        "Do you have gluten-free options?",
        "What's the price of cheesecake?"
    ]
    
    success_count = 0
    for query in queries:
        response = make_query(query)
        if response and response.get('response'):
            success_count += 1
        time.sleep(1)  # Small delay between requests
    
    print(f"\nProduct queries: {success_count}/{len(queries)} successful")
    return success_count == len(queries)

def test_general_info_queries():
    """Test general information queries."""
    print("\n" + "="*60)
    print("TESTING GENERAL INFO QUERIES")
    print("="*60)
    
    queries = [
        "What are your hours?",
        "Where are you located?",
        "Do you deliver?",
        "What's your phone number?"
    ]
    
    success_count = 0
    for query in queries:
        response = make_query(query)
        if response and response.get('response'):
            success_count += 1
        time.sleep(1)
    
    print(f"\nGeneral info queries: {success_count}/{len(queries)} successful")
    return success_count == len(queries)

def test_cart_operations():
    """Test cart operations."""
    print("\n" + "="*60)
    print("TESTING CART OPERATIONS")
    print("="*60)
    
    # Start a new session for cart testing
    cart_session = f"cart_test_{uuid.uuid4().hex[:8]}"
    
    # Add items to cart
    print("\n--- Adding Items to Cart ---")
    response1 = make_query("Add 1 cheesecake to my cart", cart_session)
    response2 = make_query("Also add 2 croissants", cart_session)
    
    # View cart
    print("\n--- Viewing Cart ---")
    response3 = make_query("Show me my cart", cart_session)
    
    # Clear cart
    print("\n--- Clearing Cart ---")
    response4 = make_query("Clear my cart", cart_session)
    
    success = all([response1, response2, response3, response4])
    print(f"\nCart operations: {'[SUCCESS]' if success else '[FAILED]'}")
    return success

def run_all_tests():
    """Run all tests and provide summary."""
    print("STARTING COMPLETE APPLICATION TESTS")
    print("="*80)
    
    # Test API health first
    if not test_api_health():
        print("\n❌ API health check failed. Cannot proceed with tests.")
        return False
    
    # Run all test suites
    results = {
        "API Health": True,  # Already passed
        "Complete Order Flow": test_complete_order_flow(),
        "Product Queries": test_product_queries(),
        "General Info Queries": test_general_info_queries(),
        "Cart Operations": test_cart_operations()
    }
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "[PASSED]" if result else "[FAILED]"
        print(f"{test_name:<25}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] ALL TESTS PASSED! The application is working correctly.")
        return True
    else:
        print("[WARNING] Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)