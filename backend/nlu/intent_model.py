"""Simple rule-based multi-label intent classifier."""
from typing import List

class IntentModel:
    def __init__(self):
        # keywords mapping to intents
        self.mapping = {
            "general_info": ["where", "hours", "open", "close", "deliver", "delivery", "location", "located"],
            "product_info": ["menu", "price", "prices", "recommend", "best", "list", "cakes", "croissant", "muffin", "cake"],
            "order": ["order", "buy", "purchase", "cancel", "pickup", "pick up"],
            "meta": ["who are you", "are you human", "bot", "assistant"]
        }

    def predict(self, text: str) -> List[str]:
        t = text.lower()
        intents = set()
        for intent, kws in self.mapping.items():
            for kw in kws:
                if kw in t:
                    intents.add(intent)
                    break
        # fallback: if no intent, assume general_info
        if not intents:
            return ["general_info"]
        return list(intents)
