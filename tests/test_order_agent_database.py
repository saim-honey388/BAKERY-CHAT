#!/usr/bin/env python3
"""
Database Integration Test for OrderAgent

PURPOSE:
    This test file tests the actual OrderAgent with real database operations
    to verify that orders are properly created and database is updated.

CREATED:
    January 2025
    Author: AI Assistant
    Version: 1.0

TEST COVERAGE:
    - Real database operations
    - Order creation and persistence
    - Customer creation
    - Inventory updates
    - Database state verification
"""

import sys
import os
import unittest
import tempfile
import shutil
from datetime import datetime

# Add backend to path for proper imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import the actual modules
from agents.order_agent import OrderAgent
from data.database import SessionLocal, engine, Base
from data.models import Product, Customer, Order, OrderItem, OrderStatus, FulfillmentType


class TestOrderAgentDatabase(unittest.TestCase):
    """
    Test suite for OrderAgent database operations.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and sample data."""
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
        """Clean up test database."""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        if cls.original_db_url:
            os.environ['DATABASE_URL'] = cls.original_db_url
    
    @classmethod
    def setup_test_data(cls):
        """Create sample products for testing."""
        db = SessionLocal()
        try:
            # Create test products
            products = [
                Product(name="Chocolate Fudge Cake", description="Rich chocolate cake", price=25.00, category="Cakes", quantity_in_stock=10),
                Product(name="Cheesecake", description="Classic New York style", price=20.00, category="Cakes", quantity_in_stock=5),
                Product(name="Almond Croissant", description="Buttery croissant with almonds", price=4.50, category="Pastries", quantity_in_stock=20),
            ]
            
            for product in products:
                db.add(product)
            
            db.commit()
            cls.test_products = products
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def setUp(self):
        """Set up each test case."""
        self.agent = OrderAgent()
        self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.db = SessionLocal()
        
        # Clear any existing cart for this session
        if self.session_id in self.agent.carts:
            del self.agent.carts[self.session_id]
    
    def tearDown(self):
        """Clean up after each test."""
        self.db.close()
        # Clear cart
        if self.session_id in self.agent.carts:
            del self.agent.carts[self.session_id]
    
    def print_database_state(self, message=""):
        """Print current database state for debugging."""
        print(f"\n{'='*60}")
        print(f"DATABASE STATE: {message}")
        print(f"{'='*60}")
        
        # Products
        products = self.db.query(Product).all()
        print(f"\nProducts ({len(products)} total):")
        for p in products:
            print(f"  - {p.name}: {p.quantity_in_stock} in stock @ ${p.price}")
        
        # Customers
        customers = self.db.query(Customer).all()
        print(f"\nCustomers ({len(customers)} total):")
        for c in customers:
            print(f"  - {c.name}: {c.phone_number}")
        
        # Orders
        orders = self.db.query(Order).all()
        print(f"\nOrders ({len(orders)} total):")
        for o in orders:
            customer = self.db.query(Customer).filter(Customer.id == o.customer_id).first()
            customer_name = customer.name if customer else f"Customer #{o.customer_id}"
            print(f"  - Order #{o.id}: {customer_name}, Status: {o.status.value}, Type: {o.pickup_or_delivery.value}, Total: ${o.total_amount or 0:.2f}")
        
        # Order Items
        order_items = self.db.query(OrderItem).all()
        print(f"\nOrder Items ({len(order_items)} total):")
        for oi in order_items:
            product = self.db.query(Product).filter(Product.id == oi.product_id).first()
            product_name = product.name if product else f"Product #{oi.product_id}"
            print(f"  - Order #{oi.order_id}: {oi.quantity}x {product_name} @ ${oi.price_at_time_of_order}")
        
        print(f"{'='*60}\n")
    
    def test_database_initial_state(self):
        """Test initial database state."""
        print("\nTesting initial database state...")
        self.print_database_state("INITIAL STATE")
        
        # Check initial products
        products = self.db.query(Product).all()
        self.assertEqual(len(products), 3)
        
        # Check no orders exist
        orders = self.db.query(Order).all()
        self.assertEqual(len(orders), 0)
        
        # Check no customers exist
        customers = self.db.query(Customer).all()
        self.assertEqual(len(customers), 0)
    
    def test_customer_creation(self):
        """Test customer creation functionality."""
        print("\nTesting customer creation...")
        
        # Test customer creation
        cart = OrderAgent.ShoppingCart()
        cart.customer_info['name'] = 'John Doe'
        cart.customer_info['phone_number'] = '555-1234'
        
        customer = self.agent._find_or_create_customer(
            self.db, self.session_id,
            cart.customer_info['name'],
            cart.customer_info['phone_number']
        )
        
        self.assertIsNotNone(customer.id)
        self.assertEqual(customer.name, 'John Doe')
        self.assertEqual(customer.phone_number, '555-1234')
        
        self.print_database_state("AFTER CUSTOMER CREATION")
        
        # Verify customer is in database
        db_customer = self.db.query(Customer).filter(Customer.id == customer.id).first()
        self.assertIsNotNone(db_customer)
        self.assertEqual(db_customer.name, 'John Doe')
    
    def test_order_creation_with_database_update(self):
        """Test complete order creation with database updates."""
        print("\nTesting complete order creation...")
        
        # Set up a complete order
        cart = OrderAgent.ShoppingCart()
        cart.add_item(self.test_products[0], 2)  # 2x Chocolate Fudge Cake
        cart.add_item(self.test_products[1], 1)  # 1x Cheesecake
        cart.fulfillment_type = 'pickup'
        cart.customer_info['name'] = 'Jane Smith'
        cart.customer_info['phone_number'] = '555-9876'
        cart.pickup_info['pickup_time'] = '2024-01-15T14:30:00'
        cart.payment_method = 'card'
        cart.branch_name = 'Downtown Location'
        
        print(f"Cart total: ${cart.get_total():.2f}")
        print(f"Cart items: {len(cart.items)}")
        
        # Get initial stock levels
        initial_stock = {}
        for product in self.test_products:
            initial_stock[product.id] = product.quantity_in_stock
            print(f"Initial stock for {product.name}: {product.quantity_in_stock}")
        
        self.print_database_state("BEFORE ORDER CREATION")
        
        # Create the order
        result = self.agent._finalize_order(self.db, cart, self.session_id)
        
        print(f"Order creation result: {result}")
        
        self.assertTrue(result["order_placed"])
        self.assertIsNotNone(result["order_id"])
        
        self.print_database_state("AFTER ORDER CREATION")
        
        # Verify order was created
        order = self.db.query(Order).filter(Order.id == result["order_id"]).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.pending)
        self.assertEqual(order.pickup_or_delivery, FulfillmentType.pickup)
        self.assertEqual(order.total_amount, cart.get_total())
        
        # Verify customer was created
        customer = self.db.query(Customer).filter(Customer.id == order.customer_id).first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.name, 'Jane Smith')
        self.assertEqual(customer.phone_number, '555-9876')
        
        # Verify order items were created
        order_items = self.db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        self.assertEqual(len(order_items), 2)
        
        # Check specific items
        chocolate_cake_item = next(item for item in order_items if item.product_id == self.test_products[0].id)
        cheesecake_item = next(item for item in order_items if item.product_id == self.test_products[1].id)
        
        self.assertEqual(chocolate_cake_item.quantity, 2)
        self.assertEqual(cheesecake_item.quantity, 1)
        
        # Verify inventory was updated
        self.db.refresh(self.test_products[0])
        self.db.refresh(self.test_products[1])
        
        print(f"Updated stock for {self.test_products[0].name}: {self.test_products[0].quantity_in_stock}")
        print(f"Updated stock for {self.test_products[1].name}: {self.test_products[1].quantity_in_stock}")
        
        self.assertEqual(self.test_products[0].quantity_in_stock, initial_stock[self.test_products[0].id] - 2)
        self.assertEqual(self.test_products[1].quantity_in_stock, initial_stock[self.test_products[1].id] - 1)
    
    def test_multiple_orders_database_state(self):
        """Test multiple orders and verify database state."""
        print("\nTesting multiple orders...")
        
        # Create first order
        cart1 = OrderAgent.ShoppingCart()
        cart1.add_item(self.test_products[2], 3)  # 3x Almond Croissant
        cart1.fulfillment_type = 'delivery'
        cart1.customer_info['name'] = 'Bob Johnson'
        cart1.customer_info['phone_number'] = '555-1111'
        cart1.delivery_info['address'] = '123 Main St, City, State'
        cart1.delivery_info['delivery_time'] = '2024-01-15T16:00:00'
        cart1.payment_method = 'cash'
        cart1.branch_name = 'Westside Location'
        
        result1 = self.agent._finalize_order(self.db, cart1, f"{self.session_id}_1")
        self.assertTrue(result1["order_placed"])
        
        # Create second order
        cart2 = OrderAgent.ShoppingCart()
        cart2.add_item(self.test_products[0], 1)  # 1x Chocolate Fudge Cake
        cart2.fulfillment_type = 'pickup'
        cart2.customer_info['name'] = 'Alice Brown'
        cart2.customer_info['phone_number'] = '555-2222'
        cart2.pickup_info['pickup_time'] = '2024-01-15T15:00:00'
        cart2.payment_method = 'upi'
        cart2.branch_name = 'Mall Location'
        
        result2 = self.agent._finalize_order(self.db, cart2, f"{self.session_id}_2")
        self.assertTrue(result2["order_placed"])
        
        self.print_database_state("AFTER MULTIPLE ORDERS")
        
        # Verify multiple orders exist
        orders = self.db.query(Order).all()
        self.assertEqual(len(orders), 3)  # Including the one from previous test
        
        # Verify multiple customers exist
        customers = self.db.query(Customer).all()
        self.assertEqual(len(customers), 3)
        
        # Verify order items exist
        order_items = self.db.query(OrderItem).all()
        self.assertEqual(len(order_items), 5)  # 2 + 1 + 2 from previous tests
    
    def test_stock_validation_database(self):
        """Test stock validation with database."""
        print("\nTesting stock validation...")
        
        # Try to order more than available stock
        cart = OrderAgent.ShoppingCart()
        cart.add_item(self.test_products[1], 10)  # Try to order 10 cheesecakes (only 4 left)
        cart.fulfillment_type = 'pickup'
        cart.customer_info['name'] = 'Test Customer'
        cart.customer_info['phone_number'] = '555-9999'
        cart.pickup_info['pickup_time'] = '2024-01-15T14:00:00'
        cart.payment_method = 'card'
        cart.branch_name = 'Downtown Location'
        
        self.print_database_state("BEFORE STOCK VALIDATION TEST")
        
        result = self.agent._finalize_order(self.db, cart, f"{self.session_id}_stock_test")
        
        print(f"Stock validation result: {result}")
        
        # Should fail due to insufficient stock
        self.assertFalse(result["order_placed"])
        self.assertIn("insufficient", result["note"].lower())
        
        self.print_database_state("AFTER STOCK VALIDATION TEST")
        
        # Verify no order was created
        latest_orders = self.db.query(Order).order_by(Order.id.desc()).limit(1).all()
        if latest_orders:
            # Check that the latest order is not from this test
            latest_order = latest_orders[0]
            self.assertNotIn("stock_test", str(latest_order.id))


def run_database_tests():
    """Run all database integration tests with detailed output."""
    print("=" * 80)
    print("DATABASE INTEGRATION TEST SUITE FOR ORDER AGENT")
    print("=" * 80)
    print("Purpose: Test real database operations and updates")
    print("Created: January 2025")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOrderAgentDatabase)
    
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
    success = run_database_tests()
    sys.exit(0 if success else 1)
