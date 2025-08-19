"""LLM-based router fallback (stub).

This file provides a simple llm_route function that calls the existing generation
client and expects a JSON-style response. It's a safe fallback for ambiguous queries.
"""
import json
from typing import Dict
from ..app.generate import GenerationClient

ROUTER_PROMPT = '''You are a strict intent router for a bakery assistant.
Return a JSON object with keys:
- intents: array subset of ["general_info","product_info","order","meta"]
- confidence: number between 0 and 1 (rough estimate)
Respond with ONLY JSON.

User query: "{query}"
'''


def llm_route(query: str) -> Dict:
    try:
        gen = GenerationClient()
        msg = ROUTER_PROMPT.format(query=query)
        out = gen.generate_answer(msg)
        parsed = json.loads(out)
        intents = [i for i in parsed.get("intents", []) if i in {"general_info","product_info","order","meta"}]
        conf = float(parsed.get("confidence", 0.5))
        return {"intents": intents or ["general_info"], "confidence": conf}
    except Exception:
        return {"intents": ["general_info"], "confidence": 0.5}
