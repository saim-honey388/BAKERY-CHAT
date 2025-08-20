"""BaseAgent interface for all agents."""
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..schemas.io_models import AgentResult

class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    def handle(self, query: str, session: Dict[str, Any]) -> AgentResult:
        """Return structured facts; no tone or final prose here."""
        ...

    def _ok(self, intent: str, facts: Dict[str, Any], **extras) -> AgentResult:
        return AgentResult(agent=self.name, intent=intent, facts=facts, **extras)

    def _clarify(self, intent: str, question: str) -> AgentResult:
        print(f"[CLARIFY] for intent '{intent}': {question}")
        return AgentResult(
            agent=self.name,
            status="clarify",
            intent=intent,
            clarification=question,
            facts={}
        )
