#!/usr/bin/env python3
"""Quick test harness to exercise Controller and agents in skip-LLM mode.

Run from the repository root:

    python3 backend/scripts/test_agents.py

This script sets a dummy GROQ_API_KEY to avoid Config.validate failing during imports,
then imports the Controller and runs a few sample queries with skip_llm=True so no
external LLM call is made.
"""
import os
import sys
import uuid
from pprint import pprint

# Ensure project root is on sys.path so we can import backend package
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set a dummy GROQ_API_KEY for local testing to avoid Config.validate() failing
os.environ.setdefault('GROQ_API_KEY', 'test')

# Import after setting env
from backend.app.controller import Controller, AGENT_MAP
from backend.agents.general_info_agent import GeneralInfoAgent
from backend.agents.product_info_agent import ProductInfoAgent
from backend.nlu.entity_extractor import EntityExtractor


def run_controller_tests():
    ctrl = Controller()
    session_id = str(uuid.uuid4())

    queries = [
        "What time do you close on Sunday?",
        "Do you deliver to Downtown?",
        "List all cakes under $24",
        "Do you have chocolate croissants?",
        "I want 2 croissants for pickup at 5 PM",
        "Are you open and do you have chocolate cake?",
        # out-of-domain tests
        "Who is Donald Trump?",
        "What is the capital of France?",
        "Tell me a joke about bakers",
        "Do you sell iPhones?",
        "How many planets are in the solar system?",
    ]

    print("== Controller (skip LLM) tests ==")
    for q in queries:
        print('\n---\nQuery:', q)
        res = ctrl.handle_query(session_id, q, skip_llm=True)
        pprint(res)
        # print which agent classes were used for the detected intents
        intents = res.get('intents', [])
        agents_used = [AGENT_MAP.get(i).__class__.__name__ if AGENT_MAP.get(i) else 'unknown' for i in intents]
        print('Intents:', intents)
        print('Agents used:', agents_used)


def run_agent_unit_tests():
    print('\n== Agent unit tests ==')
    gi = GeneralInfoAgent()
    pi = ProductInfoAgent()
    extractor = EntityExtractor()

    tests = [
        "What are your hours?",
        "Where is your main bakery located?",
        "List pastries under $4",
        "How much is a croissant?",
        "I want 3 chocolate croissants for pickup tomorrow at 10am",
        # out-of-domain checks for individual agents
        "Who is Donald Trump?",
        "What is the capital of France?",
        "Do you sell iPhones?",
    ]

    for q in tests:
        print('\n---\nQuery:', q)
        ents = extractor.extract(q)
        print('Extracted entities:')
        pprint(ents)
        print('\nGeneralInfoAgent:')
        pprint(gi.handle(q, {}))
        print('\nProductInfoAgent:')
        pprint(pi.handle(q, []))


if __name__ == '__main__':
    run_controller_tests()
    run_agent_unit_tests()
