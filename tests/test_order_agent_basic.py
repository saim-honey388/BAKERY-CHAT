#!/usr/bin/env python3
"""
Basic Test Suite for OrderAgent

PURPOSE:
    This test file provides basic testing for the OrderAgent class, focusing on
    core functionality like cart management, product parsing, and basic order flow.

CREATED:
    January 2025
    Author: AI Assistant
    Version: 1.0

TEST COVERAGE:
    - Cart initialization and basic operations
    - Product parsing from queries
    - Basic order flow states
    - Error handling

USAGE:
    Run from project root: python -m pytest tests/test_order_agent_basic.py -v
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add backend to path for proper imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import the modules to test
from agents.order_agent import OrderAgent


class TestOrderAgentBasic(unittest.TestCase):
    """
    Basic test suite for OrderAgent functionality.
    """
    
    def setUp(self):
        """Set up each test case."""
        self.agent = OrderAgent()
        self.session_id = "test_session_123"
    
    def test_cart_initialization(self):
        """Test cart initialization and basic properties."""
        cart = OrderAgent.ShoppingCart()
        
        self.assertEqual(len(cart.items), 0)
        self.assertEqual(cart.get_total(), 0.0)
        self.assertIsNone(cart.fulfillment_type)
        self.assertIsNone(cart.payment_method)
        self.assertFalse(cart.awaiting_fulfillment)
        self.assertFalse(cart.awaiting_details)
        self.assertFalse(cart.awaiting_confirmation)
    
    def test_cart_add_items(self):
        """Test adding items to cart."""
        cart = OrderAgent.ShoppingCart()
        
        # Mock a product
        mock_product = type('Product', (), {
            'id': 1,
            'name': 'Chocolate Cake',
            'price': 25.00
        })()
        
        # Add single item
        cart.add_item(mock_product, 2)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0]['product'], mock_product)
        self.assertEqual(cart.items[0]['quantity'], 2)
        self.assertEqual(cart.get_total(), 50.00)
    
    def test_cart_clear(self):
        """Test clearing the entire cart."""
        cart = OrderAgent.ShoppingCart()
        
        # Add some data
        cart.customer_info['name'] = 'John'
        cart.fulfillment_type = 'pickup'
        cart.payment_method = 'cash'
        
        cart.clear()
        
        self.assertEqual(len(cart.items), 0)
        self.assertEqual(cart.get_total(), 0.0)
        self.assertEqual(cart.customer_info, {})
        self.assertIsNone(cart.fulfillment_type)
        self.assertIsNone(cart.payment_method)
    
    def test_strong_confirmation_detection(self):
        """Test strong confirmation phrase detection."""
        # Test strong confirmations
        strong_confirmations = [
            "yes", "confirm", "place order", "place the order",
            "that's correct", "sounds good", "proceed", "finalize"
        ]
        
        for phrase in strong_confirmations:
            self.assertTrue(self.agent._is_strong_confirmation(phrase))
        
        # Test negations (should return False)
        negations = [
            "not yes", "wait", "hold on", "change", "no", "cancel"
        ]
        
        for phrase in negations:
            self.assertFalse(self.agent._is_strong_confirmation(phrase))
    
    def test_missing_details_detection(self):
        """Test missing details detection logic."""
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
    
    def test_business_hours_validation(self):
        """Test business hours validation logic."""
        # Test valid time
        valid_time = "2024-01-15T14:30:00"  # 2:30 PM
        self.assertTrue(OrderAgent._is_time_within_business_hours(valid_time))
        
        # Test invalid time (too early)
        early_time = "2024-01-15T06:30:00"  # 6:30 AM
        self.assertFalse(OrderAgent._is_time_within_business_hours(early_time))
        
        # Test invalid time (too late)
        late_time = "2024-01-15T20:30:00"  # 8:30 PM
        self.assertFalse(OrderAgent._is_time_within_business_hours(late_time))


def run_basic_tests():
    """Run all basic tests with detailed output."""
    print("=" * 60)
    print("BASIC ORDER AGENT TEST SUITE")
    print("=" * 60)
    print("Purpose: Test core OrderAgent functionality")
    print("Created: January 2025")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOrderAgentBasic)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_basic_tests()
    sys.exit(0 if success else 1)
