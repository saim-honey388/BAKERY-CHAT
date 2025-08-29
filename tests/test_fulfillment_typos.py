#!/usr/bin/env python3
import os
import sys
import unittest

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from backend.agents.order_agent import OrderAgent


class TestFulfillmentTypos(unittest.TestCase):
    def setUp(self):
        self.agent = OrderAgent()
        self.session_id = "session_fulfillment_typos"

    def test_pickup_typo_pic_up_is_detected(self):
        # Add one item to trigger checkout/fulfillment flow
        self.agent.handle(self.session_id, "I want 1 chocolate fudge cake")
        cart = self.agent.carts[self.session_id]
        self.assertTrue(cart.awaiting_fulfillment)

        # Provide typo variant for pickup
        self.agent.handle(self.session_id, "I want to pic up my order")
        cart = self.agent.carts[self.session_id]

        self.assertEqual(cart.fulfillment_type, 'pickup')
        self.assertFalse(cart.awaiting_fulfillment)
        self.assertTrue(cart.awaiting_details)

    def test_pick_up_and_pickup_variants(self):
        # Variant: pick up
        sid = self.session_id + "_1"
        self.agent.handle(sid, "I want 1 cheesecake")
        self.agent.handle(sid, "pick up please")
        cart = self.agent.carts[sid]
        self.assertEqual(cart.fulfillment_type, 'pickup')

        # Variant: pickup
        sid2 = self.session_id + "_2"
        self.agent.handle(sid2, "Add 1 croissant")
        self.agent.handle(sid2, "pickup")
        cart2 = self.agent.carts[sid2]
        self.assertEqual(cart2.fulfillment_type, 'pickup')


if __name__ == "__main__":
    unittest.main()


