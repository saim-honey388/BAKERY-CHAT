#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from backend.agents.order_agent import OrderAgent


class TestNoReaskDetails(unittest.TestCase):
    def setUp(self):
        self.agent = OrderAgent()
        self.session_id = "session_no_reask"

    def test_name_not_reasked_once_set(self):
        # Add an item to enter order flow
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        # Choose fulfillment so we move to details
        self.agent.handle(self.session_id, "pickup")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.fulfillment_type, 'pickup')

        # Provide name once
        self.agent.handle(self.session_id, "My name is Saim")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.customer_info.get('name'), 'Saim')

        # Provide payment and ensure name stays and not re-asked
        self.agent.handle(self.session_id, "I'll pay with card")
        cart = self.agent.carts[self.session_id]
        self.assertEqual(cart.customer_info.get('name'), 'Saim')
        # Name should not appear in missing details now
        missing = self.agent._get_missing_details(cart)
        self.assertNotIn('name', missing)


if __name__ == '__main__':
    unittest.main()


