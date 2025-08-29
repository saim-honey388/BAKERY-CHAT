#!/usr/bin/env python3
"""
Simple Test Suite for OrderAgent Logic

PURPOSE:
    This test file provides simple testing for OrderAgent logic without
    requiring complex imports. It tests the core business logic directly.

CREATED:
    January 2025
    Author: AI Assistant
    Version: 1.0

TEST COVERAGE:
    - Shopping cart logic
    - Business hours validation
    - Confirmation detection
    - Missing details detection
"""

import unittest
import re
from datetime import datetime, time


class ShoppingCart:
    """Simplified ShoppingCart class for testing."""
    
    def __init__(self):
        self.items = []  # List of dicts: {'product': Product, 'quantity': int}
        self.customer_info = {}
        self.delivery_info = {}
        self.pickup_info = {}
        self.fulfillment_type = None  # 'delivery' or 'pickup'
        self.payment_method = None  # 'cash'|'card'|'upi'
        self.awaiting_fulfillment = False
        self.awaiting_details = False
        self.awaiting_confirmation = False
        self.branch_name = None
        
    def add_item(self, product, quantity):
        """Add an item to the cart or update quantity if it already exists."""
        for item in self.items:
            if item['product'].id == product.id:
                item['quantity'] += quantity
                return
        self.items.append({'product': product, 'quantity': quantity})
        
    def remove_item(self, product_id):
        """Remove an item from the cart."""
        self.items = [item for item in self.items if item['product'].id != product_id]
        
    def clear(self):
        """Clear the entire cart."""
        self.items = []
        self.customer_info = {}
        self.delivery_info = {}
        self.pickup_info = {}
        self.fulfillment_type = None
        self.payment_method = None
        self.awaiting_fulfillment = False
        self.awaiting_details = False
        self.awaiting_confirmation = False
        
    def get_total(self):
        """Calculate the total price of items in the cart."""
        return sum(item['product'].price * item['quantity'] for item in self.items)
        
    def get_summary(self):
        """Generate a summary of the cart contents."""
        summary = []
        for item in self.items:
            product = item['product']
            summary.append(f"- {item['quantity']}x {product.name}: ${product.price * item['quantity']:.2f}")
        summary.append(f"\nTotal: ${self.get_total():.2f}")
        return "\n".join(summary)


class MockProduct:
    """Mock Product class for testing."""
    
    def __init__(self, id, name, price, quantity_in_stock=10):
        self.id = id
        self.name = name
        self.price = price
        self.quantity_in_stock = quantity_in_stock


class TestOrderAgentLogic(unittest.TestCase):
    """
    Test suite for OrderAgent business logic.
    """
    
    def setUp(self):
        """Set up each test case."""
        self.cart = ShoppingCart()
        
        # Create mock products
        self.chocolate_cake = MockProduct(1, "Chocolate Fudge Cake", 25.00)
        self.cheesecake = MockProduct(2, "Cheesecake", 20.00)
        self.croissant = MockProduct(3, "Almond Croissant", 4.50)
    
    def test_cart_initialization(self):
        """Test cart initialization and basic properties."""
        self.assertEqual(len(self.cart.items), 0)
        self.assertEqual(self.cart.get_total(), 0.0)
        self.assertIsNone(self.cart.fulfillment_type)
        self.assertIsNone(self.cart.payment_method)
        self.assertFalse(self.cart.awaiting_fulfillment)
        self.assertFalse(self.cart.awaiting_details)
        self.assertFalse(self.cart.awaiting_confirmation)
    
    def test_cart_add_items(self):
        """Test adding items to cart."""
        # Add single item
        self.cart.add_item(self.chocolate_cake, 2)
        self.assertEqual(len(self.cart.items), 1)
        self.assertEqual(self.cart.items[0]['product'], self.chocolate_cake)
        self.assertEqual(self.cart.items[0]['quantity'], 2)
        self.assertEqual(self.cart.get_total(), 50.00)
        
        # Add same item again (should update quantity)
        self.cart.add_item(self.chocolate_cake, 1)
        self.assertEqual(len(self.cart.items), 1)
        self.assertEqual(self.cart.items[0]['quantity'], 3)
        self.assertEqual(self.cart.get_total(), 75.00)
        
        # Add different item
        self.cart.add_item(self.cheesecake, 1)
        self.assertEqual(len(self.cart.items), 2)
        self.assertEqual(self.cart.get_total(), 95.00)
    
    def test_cart_remove_items(self):
        """Test removing items from cart."""
        self.cart.add_item(self.chocolate_cake, 2)
        self.cart.add_item(self.cheesecake, 1)
        self.assertEqual(len(self.cart.items), 2)
        
        self.cart.remove_item(self.chocolate_cake.id)
        self.assertEqual(len(self.cart.items), 1)
        self.assertEqual(self.cart.items[0]['product'], self.cheesecake)
    
    def test_cart_clear(self):
        """Test clearing the entire cart."""
        self.cart.add_item(self.chocolate_cake, 2)
        self.cart.customer_info['name'] = 'John'
        self.cart.fulfillment_type = 'pickup'
        self.cart.payment_method = 'cash'
        
        self.cart.clear()
        
        self.assertEqual(len(self.cart.items), 0)
        self.assertEqual(self.cart.get_total(), 0.0)
        self.assertEqual(self.cart.customer_info, {})
        self.assertIsNone(self.cart.fulfillment_type)
        self.assertIsNone(self.cart.payment_method)
        self.assertFalse(self.cart.awaiting_fulfillment)
        self.assertFalse(self.cart.awaiting_details)
        self.assertFalse(self.cart.awaiting_confirmation)
    
    def test_cart_summary_generation(self):
        """Test cart summary generation."""
        self.cart.add_item(self.chocolate_cake, 2)
        self.cart.add_item(self.cheesecake, 1)
        
        summary = self.cart.get_summary()
        expected_lines = [
            "- 2x Chocolate Fudge Cake: $50.00",
            "- 1x Cheesecake: $20.00",
            "",
            "Total: $70.00"
        ]
        
        for line in expected_lines:
            self.assertIn(line, summary)
    
    def test_business_hours_validation(self):
        """Test business hours validation logic."""
        def is_time_within_business_hours(iso_timestamp: str) -> bool:
            """Check if time is within business hours (8 AM - 6 PM)."""
            try:
                dt = datetime.fromisoformat(iso_timestamp)
                open_time = time(8, 0)  # 8:00 AM
                close_time = time(18, 0)  # 6:00 PM
                return open_time <= dt.time() <= close_time
            except Exception:
                return False
        
        # Test valid time
        valid_time = "2024-01-15T14:30:00"  # 2:30 PM
        self.assertTrue(is_time_within_business_hours(valid_time))
        
        # Test invalid time (too early)
        early_time = "2024-01-15T06:30:00"  # 6:30 AM
        self.assertFalse(is_time_within_business_hours(early_time))
        
        # Test invalid time (too late)
        late_time = "2024-01-15T20:30:00"  # 8:30 PM
        self.assertFalse(is_time_within_business_hours(late_time))
        
        # Test edge cases
        edge_open = "2024-01-15T08:00:00"  # 8:00 AM
        self.assertTrue(is_time_within_business_hours(edge_open))
        
        edge_close = "2024-01-15T18:00:00"  # 6:00 PM
        self.assertTrue(is_time_within_business_hours(edge_close))
    
    def test_strong_confirmation_detection(self):
        """Test strong confirmation phrase detection."""
        def is_strong_confirmation(query: str) -> bool:
            """Check if query contains strong confirmation phrases."""
            ql = query.lower().strip()
            
            # Strong confirmation phrases
            strong_confirmations = [
                "yes", "confirm", "place order", "place the order", "place my order",
                "that's correct", "that is correct", "sounds good", "looks good",
                "proceed", "go ahead", "finalize", "complete order", "submit order",
                "yes please", "yes that's right", "yes that is right", "yes place it",
                "place it", "order it", "buy it", "purchase", "checkout", "finalize order"
            ]
            
            # Negation guard - reject if contains these
            negation_words = ["not", "wait", "hold on", "change", "add more", "no", "cancel", "stop"]
            
            # Check for negation first - more strict checking
            for word in negation_words:
                if word in ql:
                    return False
                
            # Check for strong confirmation
            return any(phrase in ql for phrase in strong_confirmations)
        
        # Test strong confirmations
        strong_confirmations = [
            "yes", "confirm", "place order", "place the order",
            "that's correct", "sounds good", "proceed", "finalize",
            "yes please", "place it", "order it", "checkout"
        ]
        
        for phrase in strong_confirmations:
            self.assertTrue(is_strong_confirmation(phrase))
        
        # Test negations (should return False)
        negations = [
            "not yes", "wait", "hold on", "change", "no", "cancel",
            "not confirm", "don't place order", "stop"
        ]
        
        for phrase in negations:
            self.assertFalse(is_strong_confirmation(phrase))
    
    def test_missing_details_detection(self):
        """Test missing details detection logic."""
        def get_missing_details(cart) -> list:
            """Get list of missing required details."""
            missing_details = []
            if not cart.customer_info.get('name'):
                missing_details.append('name')
            if not cart.branch_name:
                missing_details.append('branch')
            if cart.fulfillment_type == 'pickup' and not cart.customer_info.get('phone_number'):
                missing_details.append('phone_number')
            if cart.fulfillment_type == 'pickup' and not cart.pickup_info.get('pickup_time'):
                missing_details.append('pickup_time')
            if cart.fulfillment_type == 'delivery' and not cart.delivery_info.get('address'):
                missing_details.append('address')
            if cart.fulfillment_type == 'delivery' and not cart.delivery_info.get('delivery_time'):
                missing_details.append('delivery_time')
            if not cart.payment_method:
                missing_details.append('payment_method')
            return missing_details
        
        # Test with no details
        missing = get_missing_details(self.cart)
        self.assertIn('name', missing)
        self.assertIn('branch', missing)
        self.assertIn('payment_method', missing)
        
        # Test pickup scenario
        self.cart.fulfillment_type = 'pickup'
        self.cart.customer_info['name'] = 'John'
        self.cart.branch_name = 'Downtown'
        self.cart.payment_method = 'cash'
        
        missing = get_missing_details(self.cart)
        self.assertIn('phone_number', missing)
        self.assertIn('pickup_time', missing)
        self.assertNotIn('name', missing)
        self.assertNotIn('branch', missing)
        self.assertNotIn('payment_method', missing)
        
        # Test delivery scenario
        self.cart.fulfillment_type = 'delivery'
        self.cart.customer_info['phone_number'] = '555-1234'
        
        missing = get_missing_details(self.cart)
        self.assertIn('address', missing)
        self.assertIn('delivery_time', missing)
        self.assertNotIn('phone_number', missing)
        self.assertNotIn('pickup_time', missing)
    
    def test_product_parsing_logic(self):
        """Test product parsing logic from queries."""
        def parse_products_from_query(query: str, available_products: list) -> list:
            """Parse products and quantities from a query."""
            ql = query.lower()
            found_items = []
            
            for product in available_products:
                pname = product.name.lower()
                if pname in ql:
                    # quantity immediately preceding the product name
                    qty = 1
                    qty_match = re.search(r"(\d{1,3})\s+[a-z\s]*" + re.escape(pname), ql)
                    if qty_match:
                        try:
                            qty = int(qty_match.group(1))
                        except Exception:
                            qty = 1
                    found_items.append((product, qty))
            
            return found_items
        
        available_products = [self.chocolate_cake, self.cheesecake, self.croissant]
        
        # Test single product
        query = "I want 2 chocolate fudge cakes"
        found = parse_products_from_query(query, available_products)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], self.chocolate_cake)
        self.assertEqual(found[0][1], 2)
        
        # Test multiple products
        query = "I want 1 cheesecake and 3 almond croissants"
        found = parse_products_from_query(query, available_products)
        self.assertEqual(len(found), 2)
        
        # Find specific items
        cheesecake_item = next(item for item in found if item[0] == self.cheesecake)
        croissant_item = next(item for item in found if item[0] == self.croissant)
        
        self.assertEqual(cheesecake_item[1], 1)
        self.assertEqual(croissant_item[1], 3)


def run_simple_tests():
    """Run all simple tests with detailed output."""
    print("=" * 60)
    print("SIMPLE ORDER AGENT LOGIC TEST SUITE")
    print("=" * 60)
    print("Purpose: Test core OrderAgent business logic")
    print("Created: January 2025")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOrderAgentLogic)
    
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
    success = run_simple_tests()
    import sys
    sys.exit(0 if success else 1)
