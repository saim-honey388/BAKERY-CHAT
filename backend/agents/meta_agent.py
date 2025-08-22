"""Meta Agent: handles meta/system queries."""
from .base_agent import BaseAgent
from typing import List, Dict, Any

class MetaAgent(BaseAgent):
    name = "meta"
    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: List[Dict[str, str]] = []) -> Any:
        print(f"[WORKFLOW] Executing MetaAgent...")
        q = query.lower()
        if "who are you" in q:
            return self._ok(intent="meta", facts={"about": "Bakery-Chat assistant for Sunrise Bakery."})
        return self._ok(intent="meta", facts={"note": "meta question"})
