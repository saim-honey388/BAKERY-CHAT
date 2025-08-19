"""Menu helpers: load menu.csv and provide search / lookup utilities.

This module avoids heavy dependencies and uses Python stdlib difflib for fuzzy
matching. If you later want higher-quality fuzzy matching, swap to `rapidfuzz`.
"""
from typing import List, Dict, Optional, Tuple
import os
import csv
import difflib

# try rapidfuzz for better matching
try:
    from rapidfuzz import fuzz, process
except Exception:
    process = None

MENU_PATH = os.path.join(os.path.dirname(__file__), "raw", "menu.csv")


class MenuStore:
    def __init__(self, menu_path: Optional[str] = None):
        self.menu_path = menu_path or MENU_PATH
        self.items: List[Dict[str, str]] = []
        self.item_names: List[str] = []
        self._load()

    def _load(self):
        try:
            with open(self.menu_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # normalize price to float (strip $ and commas)
                    price_raw = row.get("price", "")
                    price = None
                    if price_raw:
                        price = float(price_raw.replace("$", "").replace(",", ""))
                    item = {
                        "category": row.get("category", "").strip(),
                        "item": row.get("item", "").strip(),
                        "price": price,
                        "description": row.get("description", "").strip(),
                    }
                    self.items.append(item)
            self.item_names = [i["item"] for i in self.items if i.get("item")]
        except FileNotFoundError:
            self.items = []
            self.item_names = []

    def list_all_items(self) -> List[Dict]:
        return list(self.items)

    def get_items_by_category(self, category: str) -> List[Dict]:
        c = category.lower()
        return [i for i in self.items if c in i.get("category", "").lower()]

    def get_price(self, item_name: str) -> Optional[float]:
        match, score, idx = self.find_best_match(item_name)
        if match and idx is not None:
            return self.items[idx]["price"]
        return None

    def find_best_match(self, query: str, cutoff: float = 0.6) -> Tuple[Optional[str], float, Optional[int]]:
        """Return (best_match_name, score (0..1), index_in_items) or (None,0,None)."""
        if not query or not self.item_names:
            return (None, 0.0, None)
        q = query.lower().strip()
        # quick substring match
        for i, name in enumerate(self.item_names):
            if q in name.lower():
                return (name, 1.0, i)
        # rapidfuzz fuzzy
        if process:
            result = process.extractOne(q, self.item_names, score_cutoff=cutoff*100)
            if result:
                best, score, idx = result[0], result[1], self.item_names.index(result[0])
                return (best, score/100.0, idx)
        # difflib fuzzy fallback
        matches = difflib.get_close_matches(q, self.item_names, n=1, cutoff=cutoff)
        if matches:
            best = matches[0]
            idx = self.item_names.index(best)
            # derive a similarity score via SequenceMatcher
            score = difflib.SequenceMatcher(None, q, best.lower()).ratio()
            return (best, score, idx)
        # no good match
        return (None, 0.0, None)

    def search_items(self, query: str) -> List[Dict]:
        """Return items whose names or descriptions contain all tokens in query."""
        if not query:
            return []
        tokens = [t for t in query.lower().split() if len(t) > 1]
        results = []
        for item in self.items:
            text = (item.get("item", "") + " " + item.get("description", "")).lower()
            if all(tok in text for tok in tokens):
                results.append(item)
        return results


# Provide a module-level singleton for convenience
_store: Optional[MenuStore] = None


def get_menu_store() -> MenuStore:
    global _store
    if _store is None:
        _store = MenuStore()
    return _store
