"""Pydantic models for API I/O and agent contracts.

This replaces the minimal models with richer AgentResult/Citation types used by the
controller/agents/prompt builder.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class Citation(BaseModel):
    source: str
    snippet: str

class AgentResult(BaseModel):
    agent: str
    intent: str
    facts: Dict[str, Any]
    context_docs: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None

class QueryRequest(BaseModel):
    session_id: str
    query: str

class QueryResponse(BaseModel):
    session_id: str
    response: str
    citations: List[Citation] = Field(default_factory=list)
