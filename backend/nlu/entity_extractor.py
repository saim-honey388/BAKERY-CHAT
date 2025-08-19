"""Very small rule-based entity extractor for the bakery domain."""
import re
from typing import Dict, Any
from datetime import datetime, timedelta

# try to import dateparser for better datetime parsing (optional)
try:
    import dateparser
except Exception:
    dateparser = None

# add import for menu store
from ..data.menu_store import get_menu_store

class EntityExtractor:
    def __init__(self):
        self.menu = get_menu_store()

    def extract(self, text: str) -> Dict[str, Any]:
        t = text.lower()
        entities = {}
        # price ranges (support 'under $20', '$10-$20', '10 to 20')
        m = re.search(r"under\s*\$?([0-9]+)", t)
        if m:
            entities["price_max"] = int(m.group(1))
        else:
            m = re.search(r"\$?([0-9]+)\s*(?:-|to)\s*\$?([0-9]+)", t)
            if m:
                entities["price_min"] = int(m.group(1))
                entities["price_max"] = int(m.group(2))
            else:
                # phrases like 'around $5' or 'about 5 dollars'
                m3 = re.search(r"(?:around|about)\s*\$?([0-9]+)", t)
                if m3:
                    val = int(m3.group(1))
                    entities["price_min"] = max(0, val - 2)
                    entities["price_max"] = val + 2
        # quantity
        m2 = re.search(r"(\d+)\s+(?:pieces|pcs|items|croissants|muffins|cakes|cake|bread|loaves|bagels)?", t)
        if m2:
            entities["quantity"] = int(m2.group(1))

        # time parsing: prefer dateparser if available, else use conservative regex
        if dateparser:
            dt = dateparser.parse(t, settings={"PREFER_DATES_FROM": "future"})
            if dt:
                entities["time"] = dt.isoformat()
        else:
            # require am/pm or explicit 'at' to avoid capturing lone numbers
            # match patterns like 'at 5pm', '5:30 am', 'tomorrow at 10am'
            m4 = re.search(r"(?:(tomorrow|today)\s*)?(?:at\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm))", t)
            if m4:
                day = m4.group(1)
                timestr = m4.group(2)
                try:
                    dt = datetime.strptime(timestr, "%I:%M %p") if ":" in timestr else datetime.strptime(timestr, "%I %p")
                    now = datetime.now()
                    if day == "tomorrow":
                        dt = dt.replace(year=now.year, month=now.month, day=now.day) + timedelta(days=1)
                    else:
                        dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    entities["time"] = dt.isoformat()
                except Exception:
                    entities["time"] = timestr

        # simple location words
        locs = ["downtown", "uptown", "midtown", "central", "south", "north"]
        for loc in locs:
            if loc in t:
                entities.setdefault("location", loc)
                break

        # product matching using menu store
        # attempt exact token match
        for item in self.menu.list_all_items():
            name = item["item"].lower()
            if name in t:
                entities.setdefault("product", name)
                break
        # fuzzy match
        if "product" not in entities:
            best, score, idx = self.menu.find_best_match(t)
            if best and score >= 0.6:
                entities.setdefault("product", best.lower())
        return entities
