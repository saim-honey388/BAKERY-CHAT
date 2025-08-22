"""General Info Agent: uses RAG pipeline to answer FAQs and location/hours questions.

This is a minimal implementation returning canned replies for common queries.
"""
from .base_agent import BaseAgent
from typing import Dict, Any
from ..schemas.io_models import Citation

class GeneralInfoAgent(BaseAgent):
    name = "general_info"

    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: Dict[str, Any]):
        print(f"[WORKFLOW] Executing GeneralInfoAgent...")
        q = query.lower()
        # simple rules for quick facts
        if "hours" in q or "open" in q or "close" in q:
            facts = {"hours": {"mon_sat": "8am-6pm", "sun": "9am-4pm"}}
            cites = [Citation(source="hours.md", snippet="Open 8am-6pm Mon-Sat; 9am-4pm Sun")]
            return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
        if "deliver" in q or "delivery" in q:
            facts = {"delivery_area_km": 5}
            cites = [Citation(source="delivery.md", snippet="Delivery within 5km of main branch")] 
            return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
        if "where" in q or "located" in q or "location" in q:
            facts = {"branches": [{"name": "Main", "address": "123 Baker Street"}]}
            cites = [Citation(source="branches.json", snippet="Main branch: 123 Baker Street")]
            return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)

        # fallback: no structured fact found
        return self._ok(intent="general_info", facts={"note": "no structured facts found; please see context"}, context_docs=[], citations=[])
