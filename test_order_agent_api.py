#!/usr/bin/env python3
"""
API Integration Test for OrderAgent

PURPOSE:
    This script starts the FastAPI server and makes real API calls
    to test OrderAgent functionality and verify database updates.

CREATED:
    January 2025
    Author: AI Assistant
"""

import sys
import os
import time
import requests
import json
import subprocess
import threading
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from check_database import check_database_state

def start_server():
    """Start the FastAPI server in a separate process."""
    print("🚀 Starting FastAPI server...")
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "app.main:app", 
        "--host", "0.0.0.0", "--port", "8000", "--reload"
    ], cwd="backend")
    return process

def wait_for_server():
    """Wait for the server to be ready."""
    print("⏳ Waiting for server to start...")
    for i in range(30):  # Wait up to 30 seconds
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
        print(f"   Attempt {i+1}/30...")
    
    print("❌ Server failed to start")
    return False

def make_api_call(endpoint, data=None, method="GET"):
    """Make an API call to the server."""
    url = f"http://localhost:8000{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response
    except requests.exceptions.RequestException as e:
        print(f"❌ API call failed: {e}")
        return None

def test_order_flow():
    """Test a complete order flow through the API."""
    print("\n" + "="*80)
    print("TESTING COMPLETE ORDER FLOW")
    print("="*80)
    
    # Step 1: Create a session
    print("\n1️⃣ Creating session...")
    session_response = make_api_call("/session", method="POST")
    if not session_response or session_response.status_code != 200:
        print("❌ Failed to create session")
        return False
    
    session_data = session_response.json()
    session_id = session_data.get("session_id")
    print(f"✅ Session created: {session_id}")
    
    # Step 2: Add items to cart
    print("\n2️⃣ Adding items to cart...")
    queries = [
        "I want 2 chocolate fudge cakes",
        "Also add 1 cheesecake",
        "And 3 croissants"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"   Query {i}: {query}")
        response = make_api_call("/query", {
            "session_id": session_id,
            "query": query
        }, method="POST")
        
        if response and response.status_code == 200:
            result = response.json()
            print(f"   ✅ Response: {result.get('response', 'No response')}")
        else:
            print(f"   ❌ Failed to process query")
    
    # Step 3: Checkout and select fulfillment
    print("\n3️⃣ Selecting fulfillment type...")
    response = make_api_call("/query", {
        "session_id": session_id,
        "query": "pickup"
    }, method="POST")
    
    if response and response.status_code == 200:
        result = response.json()
        print(f"✅ Fulfillment selected: {result.get('response', 'No response')}")
    
    # Step 4: Provide customer details
    print("\n4️⃣ Providing customer details...")
    details_queries = [
        "My name is John Doe",
        "My phone number is 555-1234",
        "I'll pick up at 2:30 PM",
        "I'll pay with card"
    ]
    
    for i, query in enumerate(details_queries, 1):
        print(f"   Detail {i}: {query}")
        response = make_api_call("/query", {
            "session_id": session_id,
            "query": query
        }, method="POST")
        
        if response and response.status_code == 200:
            result = response.json()
            print(f"   ✅ Response: {result.get('response', 'No response')}")
        else:
            print(f"   ❌ Failed to process detail")
    
    # Step 5: Confirm order
    print("\n5️⃣ Confirming order...")
    response = make_api_call("/query", {
        "session_id": session_id,
        "query": "yes, confirm the order"
    }, method="POST")
    
    if response and response.status_code == 200:
        result = response.json()
        print(f"✅ Order confirmation: {result.get('response', 'No response')}")
        
        # Check if order was placed
        if "order placed" in result.get('response', '').lower():
            print("🎉 Order successfully placed!")
            return True
        else:
            print("❌ Order was not placed")
            return False
    else:
        print("❌ Failed to confirm order")
        return False

def main():
    """Main test function."""
    print("🧪 ORDER AGENT API INTEGRATION TEST")
    print("="*80)
    print("Purpose: Test OrderAgent through real API calls")
    print("Created: January 2025")
    print("="*80)
    
    # Check initial database state
    print("\n📊 INITIAL DATABASE STATE:")
    check_database_state()
    
    # Start server
    server_process = start_server()
    
    try:
        # Wait for server to be ready
        if not wait_for_server():
            return False
        
        # Test the order flow
        success = test_order_flow()
        
        # Wait a moment for database updates
        print("\n⏳ Waiting for database updates...")
        time.sleep(2)
        
        # Check final database state
        print("\n📊 FINAL DATABASE STATE:")
        check_database_state()
        
        if success:
            print("\n🎉 TEST COMPLETED SUCCESSFULLY!")
            print("✅ OrderAgent is working correctly")
            print("✅ Database is being updated properly")
        else:
            print("\n❌ TEST FAILED!")
            print("❌ OrderAgent has issues")
        
        return success
        
    finally:
        # Stop server
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server stopped")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
