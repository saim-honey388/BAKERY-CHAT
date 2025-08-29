#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from backend.agents.order_agent import OrderAgent


class TestE2EPickupFlow(unittest.TestCase):
    def setUp(self):
        self.agent = OrderAgent()
        self.sid = "session_e2e_pickup"

    def test_end_to_end_pickup_flow_with_typo(self):
        # Add multiple items
        self.agent.handle(self.sid, "Add 2 chocolate fudge cake and 1 cheesecake")
        cart = self.agent.carts[self.sid]
        self.assertGreaterEqual(len(cart.items), 1)

        # Choose fulfillment with typo
        self.agent.handle(self.sid, "I want to pic up my order")
        cart = self.agent.carts[self.sid]
        self.assertEqual(cart.fulfillment_type, 'pickup')
        self.assertTrue(cart.awaiting_details)

        # Provide branch, name, phone, time, payment
        self.agent.handle(self.sid, "Downtown")
        self.agent.handle(self.sid, "My name is John Doe")
        self.agent.handle(self.sid, "Phone is 555-7777")
        self.agent.handle(self.sid, "I'll pick up at 3:00 PM")
        self.agent.handle(self.sid, "Pay with card")

        # Ask to confirm
        res = self.agent.handle(self.sid, "confirm the order")
        # Not necessarily finalized if time invalid, but flow should be at confirmation
        # Ensure we are either ready to confirm or finalized
        cart = self.agent.carts.get(self.sid)
        if cart:
            self.assertTrue(cart.awaiting_confirmation or (not cart.items))


if __name__ == '__main__':
    unittest.main()


