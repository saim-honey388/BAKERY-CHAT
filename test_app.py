#!/usr/bin/env python3
"""
Test script to verify the bakery chat application fixes.
"""

import sys
import os
import requests
import json
import time
from subprocess import Popen, PIPE

def test_session_manager():
    """Test the session manager directly."""
    print("Testing Session Manager...")
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
        from backend.app.session import SessionManager
        
        # Test session manager
        sm = SessionManager()
        print("✓ Session Manager initialized successfully")
        
        # Test session creation
        session_id = "test_session_123"
        created = sm.create_session(session_id)
        print(f"✓ Session created: {created}")
        
        # Test adding messages
        sm.add_message(session_id, "user", "What are your hours?")
        sm.add_message(session_id, "assistant", "We are open 8am-8pm Monday through Friday.")
        print("✓ Messages added successfully")
        
        # Test getting conversation context
        context = sm.get_conversation_context(session_id)
        print(f"✓ Conversation context retrieved: {len(context)} messages")
        print(f"  Context format: {type(context)}")
        if context:
            print(f"  First message: {context[0]}")
        
        return True
    except Exception as e:
        print(f"✗ Session Manager test failed: {e}")
        return False

def test_controller():
    """Test the controller directly."""
    print("\nTesting Controller...")
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
        from backend.app.controller import Controller
        
        controller = Controller()
        print("✓ Controller initialized successfully")
        
        # Test query handling
        result = controller.handle_query("test_session_456", "What are your hours?", skip_llm=True)
        print(f"✓ Query handled successfully")
        print(f"  Response type: {type(result)}")
        print(f"  Response keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        if isinstance(result, dict) and 'response' in result:
            print(f"  Response preview: {result['response'][:100]}...")
        
        return True
    except Exception as e:
        print(f"✗ Controller test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_server():
    """Start the FastAPI server."""
    print("\nStarting FastAPI server...")
    try:
        # Change to the project directory
        os.chdir('/home/saim/bakery-chat')
        
        # Start the server
        process = Popen([
            'python', '-m', 'backend.app.main'
        ], stdout=PIPE, stderr=PIPE, env=os.environ.copy())
        
        # Wait a bit for server to start
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            print("✓ Server started successfully")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"✗ Server failed to start")
            print(f"  stdout: {stdout.decode()}")
            print(f"  stderr: {stderr.decode()}")
            return None
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return None

def test_api_endpoints(server_process):
    """Test the API endpoints."""
    print("\nTesting API endpoints...")
    
    try:
        # Test session creation
        print("Testing session creation...")
        response = requests.post(
            'http://localhost:8000/session',
            json={'session_id': 'test_api_session'},
            timeout=10
        )
        print(f"  Session creation status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Session response: {response.json()}")
            print("✓ Session creation successful")
        else:
            print(f"✗ Session creation failed: {response.text}")
            return False
        
        # Test query endpoint
        print("Testing query endpoint...")
        response = requests.post(
            'http://localhost:8000/query',
            json={
                'session_id': 'test_api_session',
                'query': 'What are your hours?'
            },
            timeout=30
        )
        print(f"  Query status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Query response keys: {result.keys()}")
            print(f"  Response preview: {result.get('response', '')[:100]}...")
            print("✓ Query endpoint successful")
        else:
            print(f"✗ Query endpoint failed: {response.text}")
            return False
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ API test failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error in API test: {e}")
        return False

def main():
    """Main test function."""
    print("=== Bakery Chat Application Test ===\n")
    
    # Test 1: Session Manager
    session_test = test_session_manager()
    
    # Test 2: Controller
    controller_test = test_controller()
    
    # Test 3: Full API
    server_process = start_server()
    api_test = False
    
    if server_process:
        try:
            api_test = test_api_endpoints(server_process)
        finally:
            # Clean up server process
            print("\nStopping server...")
            server_process.terminate()
            server_process.wait()
            print("✓ Server stopped")
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"Session Manager: {'✓ PASS' if session_test else '✗ FAIL'}")
    print(f"Controller: {'✓ PASS' if controller_test else '✗ FAIL'}")
    print(f"API Endpoints: {'✓ PASS' if api_test else '✗ FAIL'}")
    
    if all([session_test, controller_test, api_test]):
        print("\n🎉 All tests passed! The application should work correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
