"""Meta Agent: handles meta/system queries."""
from .base_agent import BaseAgent
from typing import List, Dict, Any

class MetaAgent(BaseAgent):
    name = "meta"
    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: List[Dict[str, str]] = [], memory_context: Dict[str, Any] = None) -> Any:
        print(f"[WORKFLOW] Executing MetaAgent...")
        print(f"[MEMORY] MetaAgent received memory context: {memory_context}")
        q = query.lower()
        
        # Handle various meta/about queries
        if any(phrase in q for phrase in ["who are you", "tell me about yourself", "what are you", "about you"]):
            return self._ok(intent="meta", facts={
                "about": "I'm Bakery-Chat, your AI assistant for Sunrise Bakery! I can help you with ordering delicious pastries, checking our menu, finding store hours and locations, and answering any questions about our bakery. How can I assist you today?"
            })
        
        # Handle system queries
        if any(phrase in q for phrase in ["system", "meta", "help", "what can you do"]):
            return self._ok(intent="meta", facts={
                "capabilities": "I can help you order bakery items, check our menu and prices, find store locations and hours, and answer questions about our products and services."
            })
            
        return self._ok(intent="meta", facts={"note": "meta question"})
