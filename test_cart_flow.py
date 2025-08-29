from backend.agents.order_agent import OrderAgent

agent = OrderAgent()

print("=== Testing empty cart confirmation ===")
sid = "test_empty_cart"
result = agent.handle(sid, "confirm my order")
print(f"Result: {result.facts}")
print(f"Message: {result.facts.get('note', 'No note')}")
print()

print("=== Testing full order flow ===")
sid2 = "test_full_flow"

# Add items
agent.handle(sid2, "Add 1 chocolate fudge cake")
agent.handle(sid2, "pickup")
agent.handle(sid2, "Downtown")
agent.handle(sid2, "My name is John")
agent.handle(sid2, "Phone 555-1234")
agent.handle(sid2, "3pm")
agent.handle(sid2, "card")

# Confirm order
result = agent.handle(sid2, "confirm my order")
print(f"Result: {result.facts}")
print(f"Message: {result.facts.get('note', 'No note')}")
