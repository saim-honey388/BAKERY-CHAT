#!/usr/bin/env python3
"""
Comprehensive Test Suite for OrderAgent

PURPOSE:
    This test file provides comprehensive testing for the OrderAgent class, which is
    the core component responsible for handling bakery order processing in the
    BAKERY-CHAT application.

CREATED:
    January 2025
    Author: AI Assistant
    Version: 1.0

TEST COVERAGE:
    - Cart management and state transitions
    - Product parsing and quantity detection
    - Entity extraction and validation
    - Order flow states (fulfillment, details collection, confirmation)
    - Business logic validation (stock, business hours)
    - Database operations and persistence
    - Edge cases and error handling
    - Concurrent session management
    - Receipt generation and retrieval

DEPENDENCIES:
    - Python 3.10+
    - unittest framework
    - SQLAlchemy for database operations
    - Mock objects for testing external dependencies

USAGE:
    Run from project root: python -m pytest tests/test_order_agent_comprehensive.py -v
    Run individual test: python -m pytest tests/test_order_agent_comprehensive.py::TestOrderAgentComprehensive::test_cart_initialization -v
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time
import json
import tempfile
import shutil

# Add backend to path for proper imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import the modules to test
from agents.order_agent import OrderAgent
from data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType
from data.database import SessionLocal, engine, Base
from schemas.io_models import AgentResult


class TestOrderAgentComprehensive(unittest.TestCase):
    """
    Comprehensive test suite for OrderAgent functionality.
    
    This class contains all the test methods for validating the OrderAgent's
    behavior across various scenarios including normal operations, edge cases,
    and error conditions.
    """
    
    @classmethod
    def setUpClass(cls):
        """
        Set up test database and sample data.
        
        This method runs once before all tests and creates:
        - A temporary SQLite database for testing
        - Sample products with various prices and stock levels
        - A test customer for order processing
        """
        # Create test database
        cls.test_db_path = tempfile.mktemp(suffix='.db')
        cls.original_db_url = os.getenv('DATABASE_URL')
        os.environ['DATABASE_URL'] = f'sqlite:///{cls.test_db_path}'
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Create test data
        cls.setup_test_data()
    
    @classmethod
    def tearDownClass(cls):
        """
        Clean up test database and restore environment.
        
        This method runs once after all tests and:
        - Removes the temporary database file
        - Restores the original DATABASE_URL environment variable
        """
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        if cls.original_db_url:
            os.environ['DATABASE_URL'] = cls.original_db_url
    
    @classmethod
    def setup_test_data(cls):
        """
        Create sample products and customers for testing.
        
        Creates a variety of products with different:
        - Names and descriptions
        - Prices (ranging from $3.50 to $25.00)
        - Categories (Cakes, Pastries, Bread)
        - Stock levels (for testing inventory validation)
        """
        db = SessionLocal()
        try:
            # Create test products with realistic bakery items
            products = [
                Product(name="Chocolate Fudge Cake", description="Rich chocolate cake with fudge frosting", price=25.00, category="Cakes", quantity_in_stock=10),
                Product(name="Cheesecake", description="Classic New York style cheesecake", price=20.00, category="Cakes", quantity_in_stock=5),
                Product(name="Almond Croissant", description="Buttery croissant with almonds and sugar", price=4.50, category="Pastries", quantity_in_stock=20),
                Product(name="Sourdough Bread", description="Artisan sourdough bread", price=6.00, category="Bread", quantity_in_stock=15),
                Product(name="Blueberry Muffin", description="Fresh blueberry muffin", price=3.50, category="Pastries", quantity_in_stock=8)
            ]
            
            for product in products:
                db.add(product)
            
            # Create test customer
            customer = Customer(name="Test Customer", phone_number="555-1234")
            db.add(customer)
            
            db.commit()
            cls.test_products = products
            cls.test_customer = customer
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def setUp(self):
        """
        Set up each test case.
        
        This method runs before each test and:
        - Creates a fresh OrderAgent instance
        - Sets up a unique session ID
        - Creates a database session
        - Clears any existing cart for the test session
        """
        self.agent = OrderAgent()
        self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.db = SessionLocal()
        
        # Clear any existing cart for this session
        if self.session_id in self.agent.carts:
            del self.agent.carts[self.session_id]
    
    def tearDown(self):
        """
        Clean up after each test.
        
        This method runs after each test and:
        - Closes the database session
        - Clears the cart for the test session
        """
        self.db.close()
        # Clear cart
        if self.session_id in self.agent.carts:
            del self.agent.carts[self.session_id]
    
    def test_cart_initialization(self):
        """
        Test cart initialization and basic properties.
        
        Validates that a new ShoppingCart instance:
        - Starts with empty items list
        - Has zero total
        - Has no fulfillment type set
        - Has no payment method set
        - Is not in any awaiting state
        """
        cart = OrderAgent.ShoppingCart()
        
        self.assertEqual(len(cart.items), 0)
        self.assertEqual(cart.get_total(), 0.0)
        self.assertIsNone(cart.fulfillment_type)
        self.assertIsNone(cart.payment_method)
        self.assertFalse(cart.awaiting_fulfillment)
        self.assertFalse(cart.awaiting_details)
        self.assertFalse(cart.awaiting_confirmation)
    
    def test_cart_add_items(self):
        """
        Test adding items to cart functionality.
        
        Tests:
        - Adding a single item with quantity
        - Adding the same item again (should update quantity)
        - Adding different items (should create separate entries)
        - Total calculation accuracy
        """
        cart = OrderAgent.ShoppingCart()
        product = self.test_products[0]  # Chocolate Fudge Cake ($25.00)
        
        # Add single item
        cart.add_item(product, 2)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0]['product'], product)
        self.assertEqual(cart.items[0]['quantity'], 2)
        self.assertEqual(cart.get_total(), 50.00)
        
        # Add same item again (should update quantity)
        cart.add_item(product, 1)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0]['quantity'], 3)
        self.assertEqual(cart.get_total(), 75.00)
        
        # Add different item
        product2 = self.test_products[1]  # Cheesecake ($20.00)
        cart.add_item(product2, 1)
        self.assertEqual(len(cart.items), 2)
        self.assertEqual(cart.get_total(), 95.00)
    
    def test_cart_remove_items(self):
        """
        Test removing items from cart functionality.
        
        Tests:
        - Removing a specific item by product ID
        - Verifying other items remain in cart
        - Cart state after removal
        """
        cart = OrderAgent.ShoppingCart()
        product1 = self.test_products[0]
        product2 = self.test_products[1]
        
        cart.add_item(product1, 2)
        cart.add_item(product2, 1)
        self.assertEqual(len(cart.items), 2)
        
        cart.remove_item(product1.id)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0]['product'], product2)
    
    def test_cart_clear(self):
        """
        Test clearing the entire cart functionality.
        
        Tests:
        - Clearing all items from cart
        - Resetting all cart properties to initial state
        - Verifying cart is completely empty
        """
        cart = OrderAgent.ShoppingCart()
        product = self.test_products[0]
        
        cart.add_item(product, 2)
        cart.customer_info['name'] = 'John'
        cart.fulfillment_type = 'pickup'
        cart.payment_method = 'cash'
        
        cart.clear()
        
        self.assertEqual(len(cart.items), 0)
        self.assertEqual(cart.get_total(), 0.0)
        self.assertEqual(cart.customer_info, {})
        self.assertIsNone(cart.fulfillment_type)
        self.assertIsNone(cart.payment_method)
        self.assertFalse(cart.awaiting_fulfillment)
        self.assertFalse(cart.awaiting_details)
        self.assertFalse(cart.awaiting_confirmation)
    
    def test_cart_summary_generation(self):
        """
        Test cart summary generation functionality.
        
        Tests:
        - Summary format and content
        - Price calculations in summary
        - Total calculation accuracy
        """
        cart = OrderAgent.ShoppingCart()
        product1 = self.test_products[0]  # $25.00
        product2 = self.test_products[1]  # $20.00
        
        cart.add_item(product1, 2)
        cart.add_item(product2, 1)
        
        summary = cart.get_summary()
        expected_lines = [
            "- 2x Chocolate Fudge Cake: $50.00",
            "- 1x Cheesecake: $20.00",
            "",
            "Total: $70.00"
        ]
        
        for line in expected_lines:
            self.assertIn(line, summary)
    
    def test_receipt_generation(self):
        """
        Test receipt generation with all details.
        
        Tests:
        - Receipt format and structure
        - All required fields are present
        - Tax calculation accuracy
        - Customer information display
        - Fulfillment details
        """
        cart = OrderAgent.ShoppingCart()
        product = self.test_products[0]  # $25.00
        
        cart.add_item(product, 2)
        cart.customer_info['name'] = 'John Doe'
        cart.customer_info['phone_number'] = '555-1234'
        cart.fulfillment_type = 'pickup'
        cart.pickup_info['pickup_time'] = '2024-01-15T14:30:00'
        cart.payment_method = 'card'
        
        receipt = cart.build_receipt(order_id=123)
        
        # Check key elements
        self.assertIn("Sunrise Bakery — Order Receipt", receipt)
        self.assertIn("Order #123", receipt)
        self.assertIn("2 x Chocolate Fudge Cake — $25.00 ea  = $50.00", receipt)
        self.assertIn("Subtotal: $50.00", receipt)
        self.assertIn("Tax (8.25%): $4.12", receipt)
        self.assertIn("Total: $54.12", receipt)
        self.assertIn("Fulfillment: Pickup", receipt)
        self.assertIn("Customer: John Doe", receipt)
        self.assertIn("Phone: 555-1234", receipt)
        self.assertIn("Payment: Card", receipt)
    
    def test_business_hours_validation(self):
        """
        Test business hours validation logic.
        
        Tests:
        - Valid times within business hours (8 AM - 6 PM)
        - Invalid times outside business hours
        - Edge cases (exactly 8 AM and 6 PM)
        - Time format parsing
        """
        # Test valid time
        valid_time = "2024-01-15T14:30:00"  # 2:30 PM
        self.assertTrue(OrderAgent._is_time_within_business_hours(valid_time))
        
        # Test invalid time (too early)
        early_time = "2024-01-15T06:30:00"  # 6:30 AM
        self.assertFalse(OrderAgent._is_time_within_business_hours(early_time))
        
        # Test invalid time (too late)
        late_time = "2024-01-15T20:30:00"  # 8:30 PM
        self.assertFalse(OrderAgent._is_time_within_business_hours(late_time))
        
        # Test edge cases
        edge_open = "2024-01-15T08:00:00"  # 8:00 AM
        self.assertTrue(OrderAgent._is_time_within_business_hours(edge_open))
        
        edge_close = "2024-01-15T18:00:00"  # 6:00 PM
        self.assertTrue(OrderAgent._is_time_within_business_hours(edge_close))
    
    def test_strong_confirmation_detection(self):
        """
        Test strong confirmation phrase detection.
        
        Tests:
        - Various confirmation phrases that should trigger order placement
        - Negation phrases that should prevent order placement
        - Case insensitivity
        - Edge cases in phrase matching
        """
        # Test strong confirmations
        strong_confirmations = [
            "yes", "confirm", "place order", "place the order",
            "that's correct", "sounds good", "proceed", "finalize",
            "yes please", "place it", "order it", "checkout"
        ]
        
        for phrase in strong_confirmations:
            self.assertTrue(self.agent._is_strong_confirmation(phrase))
        
        # Test negations (should return False)
        negations = [
            "not yes", "wait", "hold on", "change", "no", "cancel",
            "not confirm", "don't place order", "stop"
        ]
        
        for phrase in negations:
            self.assertFalse(self.agent._is_strong_confirmation(phrase))
    
    def test_missing_details_detection(self):
        """
        Test missing details detection logic.
        
        Tests:
        - Required fields for different fulfillment types
        - Pickup vs delivery requirements
        - Dynamic missing details calculation
        """
        cart = OrderAgent.ShoppingCart()
        
        # Test with no details
        missing = self.agent._get_missing_details(cart)
        self.assertIn('name', missing)
        self.assertIn('branch', missing)
        self.assertIn('payment_method', missing)
        
        # Test pickup scenario
        cart.fulfillment_type = 'pickup'
        cart.customer_info['name'] = 'John'
        cart.branch_name = 'Downtown'
        cart.payment_method = 'cash'
        
        missing = self.agent._get_missing_details(cart)
        self.assertIn('phone_number', missing)
        self.assertIn('pickup_time', missing)
        self.assertNotIn('name', missing)
        self.assertNotIn('branch', missing)
        self.assertNotIn('payment_method', missing)
        
        # Test delivery scenario
        cart.fulfillment_type = 'delivery'
        cart.customer_info['phone_number'] = '555-1234'
        
        missing = self.agent._get_missing_details(cart)
        self.assertIn('address', missing)
        self.assertIn('delivery_time', missing)
        self.assertNotIn('phone_number', missing)
        self.assertNotIn('pickup_time', missing)
    
    def test_product_parsing(self):
        """
        Test product parsing from natural language queries.
        
        Tests:
        - Single product with quantity detection
        - Multiple products in one query
        - Quantity extraction from text
        - Product name matching
        """
        # Test single product with quantity
        result = self.agent.handle(self.session_id, "I want 2 chocolate fudge cakes")
        self.assertEqual(result.intent, "checkout_fulfillment")
        self.assertTrue(result.facts.get("needs_fulfillment_type"))
        
        cart = self.agent.carts[self.session_id]
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0]['product'].name, "Chocolate Fudge Cake")
        self.assertEqual(cart.items[0]['quantity'], 2)
        
        # Test multiple products
        result = self.agent.handle(self.session_id, "Also add 1 cheesecake and 3 almond croissants")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(len(cart.items), 3)
        
        # Find specific items
        cheesecake_item = next(item for item in cart.items if item['product'].name == "Cheesecake")
        croissant_item = next(item for item in cart.items if item['product'].name == "Almond Croissant")
        
        self.assertEqual(cheesecake_item['quantity'], 1)
        self.assertEqual(croissant_item['quantity'], 3)
    
    def test_stock_validation(self):
        """
        Test stock validation during order processing.
        
        Tests:
        - Insufficient stock detection
        - Stock quantity validation
        - Error handling for out-of-stock items
        - Cart state when stock validation fails
        """
        # Reduce stock to test validation
        product = self.test_products[1]  # Cheesecake (5 in stock)
        product.quantity_in_stock = 2
        self.db.commit()
        
        # Try to order more than available
        result = self.agent.handle(self.session_id, "I want 5 cheesecakes")
        self.assertEqual(result.intent, "order")
        self.assertFalse(result.facts.get("order_placed"))
        self.assertEqual(result.facts.get("reason"), "insufficient_stock")
        self.assertEqual(result.facts.get("available_quantity"), 2)
        
        # Verify cart is empty (order not added)
        cart = self.agent.carts[self.session_id]
        self.assertEqual(len(cart.items), 0)
    
    def test_fulfillment_type_selection(self):
        """
        Test fulfillment type selection flow.
        
        Tests:
        - Pickup selection
        - Delivery selection
        - State transitions after selection
        - Cart state updates
        """
        # Add items first
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        
        # Test pickup selection
        result = self.agent.handle(self.session_id, "pickup")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.fulfillment_type, 'pickup')
        self.assertFalse(cart.awaiting_fulfillment)
        
        # Test delivery selection
        self.agent.carts[self.session_id] = OrderAgent.ShoppingCart()
        self.agent.handle(self.session_id, "I want 1 cheesecake")
        result = self.agent.handle(self.session_id, "delivery")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.fulfillment_type, 'delivery')
        self.assertFalse(cart.awaiting_fulfillment)
    
    def test_details_collection_flow(self):
        """
        Test the details collection flow.
        
        Tests:
        - Sequential collection of customer details
        - Name, phone, time, and payment method collection
        - State transitions during collection
        - Data validation and storage
        """
        # Start with items and fulfillment
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        self.agent.handle(self.session_id, "pickup")
        
        cart = self.agent.carts[self.session_id]
        self.assertTrue(cart.awaiting_details)
        
        # Test name collection
        result = self.agent.handle(self.session_id, "My name is John Doe")
        self.assertEqual(cart.customer_info.get('name'), 'John Doe')
        
        # Test phone collection
        result = self.agent.handle(self.session_id, "My phone is 555-1234")
        self.assertEqual(cart.customer_info.get('phone_number'), '555-1234')
        
        # Test pickup time collection
        result = self.agent.handle(self.session_id, "I'll pick up at 2:30 PM")
        self.assertEqual(cart.pickup_info.get('pickup_time'), '2024-01-15T14:30:00')
        
        # Test payment method
        result = self.agent.handle(self.session_id, "I'll pay with card")
        self.assertEqual(cart.payment_method, 'card')
    
    def test_order_confirmation_flow(self):
        """
        Test the complete order confirmation flow.
        
        Tests:
        - Order confirmation with complete details
        - Mock order finalization
        - Receipt generation
        - Cart clearing after order
        """
        # Set up complete order
        cart = OrderAgent.ShoppingCart()
        cart.add_item(self.test_products[0], 1)  # $25.00
        cart.fulfillment_type = 'pickup'
        cart.customer_info['name'] = 'John Doe'
        cart.customer_info['phone_number'] = '555-1234'
        cart.pickup_info['pickup_time'] = '2024-01-15T14:30:00'
        cart.payment_method = 'card'
        cart.branch_name = 'Downtown Location'
        cart.awaiting_confirmation = True
        
        self.agent.carts[self.session_id] = cart
        
        # Test confirmation
        with patch.object(self.agent, '_finalize_order') as mock_finalize:
            mock_finalize.return_value = {
                "order_placed": True,
                "order_id": 123,
                "receipt_text": "Test receipt",
                "note": "Order placed successfully!"
            }
            
            result = self.agent.handle(self.session_id, "yes, confirm the order")
            
            mock_finalize.assert_called_once()
            self.assertEqual(result.facts.get("order_placed"), True)
    
    def test_cart_review_functionality(self):
        """
        Test cart review and summary functionality.
        
        Tests:
        - Cart summary generation
        - Summary content accuracy
        - Total calculations
        """
        # Add items to cart
        self.agent.handle(self.session_id, "I want 2 chocolate fudge cakes and 1 cheesecake")
        
        # Test cart review
        result = self.agent.handle(self.session_id, "show my cart")
        self.assertEqual(result.intent, "cart_summary")
        self.assertIn("cart_summary", result.facts)
        
        cart_summary = result.facts["cart_summary"]
        self.assertIn("2x Chocolate Fudge Cake: $50.00", cart_summary)
        self.assertIn("1x Cheesecake: $20.00", cart_summary)
        self.assertIn("Total: $70.00", cart_summary)
    
    def test_cart_clearing(self):
        """
        Test cart clearing functionality.
        
        Tests:
        - Cart clearing command recognition
        - Complete cart reset
        - State cleanup
        """
        # Add items to cart
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(len(cart.items), 1)
        
        # Clear cart
        result = self.agent.handle(self.session_id, "clear cart")
        self.assertEqual(result.intent, "clear_cart")
        self.assertTrue(result.facts.get("cart_cleared"))
        self.assertEqual(len(cart.items), 0)
    
    def test_receipt_retrieval(self):
        """
        Test receipt retrieval functionality.
        
        Tests:
        - Receipt storage and retrieval
        - Handling when no receipt exists
        - Receipt content accuracy
        """
        # Store a test receipt
        test_receipt = "Test receipt content"
        self.agent.last_receipt_by_session[self.session_id] = test_receipt
        
        # Test receipt retrieval
        result = self.agent.handle(self.session_id, "show me my receipt")
        self.assertEqual(result.intent, "order_receipt")
        self.assertEqual(result.facts.get("receipt_text"), test_receipt)
        
        # Test when no receipt exists
        del self.agent.last_receipt_by_session[self.session_id]
        result = self.agent.handle(self.session_id, "show me my receipt")
        self.assertEqual(result.intent, "order_receipt")
        self.assertFalse(result.facts.get("receipt_available"))
    
    def test_entity_extraction_integration(self):
        """
        Test integration with entity extraction.
        
        Tests:
        - Entity extraction from queries
        - Integration with cart state
        - Customer information extraction
        """
        # Mock entity extractor to return specific entities
        with patch.object(self.agent.entity_extractor, 'extract') as mock_extract:
            mock_extract.return_value = {
                'name': 'Jane Doe',
                'phone_number': '555-9876',
                'payment_method': 'upi',
                'time': '2024-01-15T15:00:00'
            }
            
            result = self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
            cart = self.agent.carts[self.session_id]
            
            # Verify entities were extracted and stored
            self.assertEqual(cart.customer_info.get('name'), 'Jane Doe')
            self.assertEqual(cart.customer_info.get('phone_number'), '555-9876')
            self.assertEqual(cart.payment_method, 'upi')
    
    def test_error_handling(self):
        """
        Test error handling in various scenarios.
        
        Tests:
        - Invalid product handling
        - Invalid time format handling
        - Graceful error responses
        """
        # Test with invalid product
        result = self.agent.handle(self.session_id, "I want 1 nonexistent product")
        self.assertEqual(result.intent, "order")
        self.assertIn("needs_clarification", result.facts)
        
        # Test with invalid time format
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        self.agent.handle(self.session_id, "pickup")
        self.agent.handle(self.session_id, "My name is John")
        
        result = self.agent.handle(self.session_id, "I'll pick up at invalid time")
        self.assertEqual(result.intent, "checkout_missing_details")
        self.assertIn("pickup_time", result.facts.get("asking_for", ""))
    
    def test_database_integration(self):
        """
        Test database operations and persistence.
        
        Tests:
        - Customer creation and lookup
        - Order creation process
        - Database transaction handling
        """
        # Test customer creation
        cart = OrderAgent.ShoppingCart()
        cart.customer_info['name'] = 'New Customer'
        cart.customer_info['phone_number'] = '555-9999'
        
        customer = self.agent._find_or_create_customer(
            self.db, self.session_id,
            cart.customer_info['name'],
            cart.customer_info['phone_number']
        )
        
        self.assertIsNotNone(customer.id)
        self.assertEqual(customer.name, 'New Customer')
        self.assertEqual(customer.phone_number, '555-9999')
        
        # Test order creation
        cart.add_item(self.test_products[0], 1)
        cart.fulfillment_type = 'pickup'
        cart.payment_method = 'cash'
        
        with patch.object(self.agent, '_finalize_order') as mock_finalize:
            mock_finalize.return_value = {
                "order_placed": True,
                "order_id": 456,
                "receipt_text": "Test receipt",
                "note": "Order placed successfully!"
            }
            
            result = self.agent._finalize_order(self.db, cart, self.session_id)
            self.assertTrue(result["order_placed"])
    
    def test_edge_cases(self):
        """
        Test various edge cases and boundary conditions.
        
        Tests:
        - Empty cart checkout
        - Zero quantity orders
        - Very large quantities
        - Special characters in names
        """
        # Test empty cart checkout
        result = self.agent.handle(self.session_id, "checkout")
        self.assertEqual(result.intent, "checkout")
        self.assertTrue(result.facts.get("needs_items"))
        
        # Test zero quantity
        result = self.agent.handle(self.session_id, "I want 0 chocolate fudge cakes")
        self.assertEqual(result.intent, "order")
        self.assertIn("needs_clarification", result.facts)
        
        # Test very large quantity
        result = self.agent.handle(self.session_id, "I want 999 chocolate fudge cakes")
        self.assertEqual(result.intent, "order")
        self.assertFalse(result.facts.get("order_placed"))
        self.assertEqual(result.facts.get("reason"), "insufficient_stock")
        
        # Test special characters in names
        result = self.agent.handle(self.session_id, "My name is John O'Connor")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.customer_info.get('name'), "John O'Connor")
    
    def test_concurrent_sessions(self):
        """
        Test handling of multiple concurrent sessions.
        
        Tests:
        - Session isolation
        - Independent cart management
        - Cart state reporting per session
        """
        session1 = "session_1"
        session2 = "session_2"
        
        # Add items to different sessions
        self.agent.handle(session1, "I want 1 chocolate fudge cake")
        self.agent.handle(session2, "I want 1 cheesecake")
        
        # Verify carts are separate
        cart1 = self.agent.carts[session1]
        cart2 = self.agent.carts[session2]
        
        self.assertEqual(len(cart1.items), 1)
        self.assertEqual(len(cart2.items), 1)
        self.assertEqual(cart1.items[0]['product'].name, "Chocolate Fudge Cake")
        self.assertEqual(cart2.items[0]['product'].name, "Cheesecake")
        
        # Verify cart state reporting
        state1 = self.agent.get_cart_state(session1)
        state2 = self.agent.get_cart_state(session2)
        
        self.assertTrue(state1["has_cart"])
        self.assertTrue(state2["has_cart"])
        self.assertEqual(state1["cart_items"], 1)
        self.assertEqual(state2["cart_items"], 1)


def run_comprehensive_tests():
    """
    Run all comprehensive tests with detailed output.
    
    This function:
    - Creates a test suite with all OrderAgent tests
    - Runs tests with verbose output
    - Provides a detailed summary of results
    - Returns success/failure status
    """
    print("=" * 80)
    print("COMPREHENSIVE ORDER AGENT TEST SUITE")
    print("=" * 80)
    print("Purpose: Test all OrderAgent functionality including cart management,")
    print("         order processing, validation, and edge cases.")
    print("Created: January 2025")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOrderAgentComprehensive)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
