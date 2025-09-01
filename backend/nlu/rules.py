"""Rule-based router utilities with tiny fuzzy matching."""
import re
from difflib import SequenceMatcher
from typing import List

GENERAL = ["hours", "timings", "timmings", "open", "close", "location",
           "branch", "branches", "operate", "serve", "deliver", "delivery", "policy", "policies"]
PRODUCT = ["menu", "pastry", "bread", "cupcake", "brownie",
           "chocolate", "flavor", "price", "prices", "recommend", "suggest", "best", "list", "available"]
ORDER   = ["order", "buy", "book", "reserve", "pickup", "pick up", "deliver", "delivery", "place an order",
           "add", "cart", "want", "get", "take", "cake", "cakes", "cheesecake", "croissant"]
META    = ["who are you", "tell me about yourself", "what are you", "about you", "yourself", "meta", "system"]


def _contains_any(q: str, vocab: List[str]) -> bool:
    ql = q.lower()
    
    # First check for exact multi-word phrases
    for phrase in vocab:
        if phrase in ql:
            return True
    
    # Then check for single word matches
    tokens = re.findall(r"[a-zA-Z]+", ql)
    for t in tokens:
        for w in vocab:
            if SequenceMatcher(None, t, w).ratio() >= 0.84:
                return True
    return False


def rule_based_intents(query: str) -> List[str]:
    intents = []
    if _contains_any(query, GENERAL): intents.append("general_info")
    if _contains_any(query, PRODUCT): intents.append("product_info")
    if _contains_any(query, ORDER):   intents.append("order")
    if _contains_any(query, META):    intents.append("meta")
    return intents
