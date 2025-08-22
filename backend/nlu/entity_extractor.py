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

        # fulfillment intent
        if any(k in t for k in ["pickup", "pick up", "collection"]):
            entities["fulfillment"] = "pickup"
        if any(k in t for k in ["deliver", "delivery", "send to", "ship to", "drop off"]):
            entities["fulfillment"] = "delivery"

        # payment method - expanded mapping
        payment_map = {
            "cash": ["cash", "pay cash", "cash on delivery", "money"],
            "card": ["card", "credit", "debit", "visa", "mastercard", "american express", "amex", "apple pay", "paypal"],
            "upi": ["upi", "paytm", "gpay", "google pay", "phonepe", "digital payment", "mobile payment"]
        }
        
        has_payment_keyword = False
        for method, keywords in payment_map.items():
            if any(k in t for k in keywords):
                entities["payment_method"] = method
                has_payment_keyword = True
                break

        # simple name extraction (e.g., "my name is John")
        mname = re.search(r"(?:i am|i'm|my name is)\s+([a-z][a-z\s]{1,30})", t)
        if mname and not has_payment_keyword:
            entities["name"] = mname.group(1).strip().title()

        # bare name fallback: single short token(s) likely to be a name
        if "name" not in entities and not has_payment_keyword:
            raw = text.strip()
            if 1 <= len(raw.split()) <= 3 and re.fullmatch(r"[A-Za-z][A-Za-z\s]{0,30}", raw):
                token = raw.lower()
                if token not in {"yes", "no", "ok", "okay", "card", "cash", "upi", "pickup", "deliver", "delivery", "and"}:
                    entities["name"] = raw.title()

        # phone number (more robust)
        # First try the existing pattern
        mph = re.search(r"(\+?\d[\d\-\s]{5,}\d)", t)
        if mph:
            entities["phone_number"] = mph.group(1).replace(" ", "")
        else:
            # Fallback: look for sequences of 6-15 digits
            phone_patterns = [
                r"(?<!\d)(\d{6,15})(?!\d)",  # standalone digits
                r"phone.*?(\d{6,15})",  # after "phone"
                r"number.*?(\d{6,15})",  # after "number"
            ]
            for pattern in phone_patterns:
                match = re.search(pattern, t, re.IGNORECASE)
                if match:
                    entities["phone_number"] = match.group(1)
                    break

        # time parsing: more conservative approach
        # Only parse if explicitly mentioned with time indicators
        time_patterns = [
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))",  # 5pm, 5:30pm
            r"at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))",  # at 5pm
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:today|tomorrow)",  # 5pm today
        ]
        for pattern in time_patterns:
            match = re.search(pattern, t, re.IGNORECASE)
            if match:
                timestr = match.group(1)
                try:
                    # Parse the time
                    if ":" in timestr:
                        dt = datetime.strptime(timestr, "%I:%M %p")
                    else:
                        dt = datetime.strptime(timestr, "%I %p")
                    # Set to today's date
                    now = datetime.now(); dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    # If time is in the past, assume tomorrow
                    if dt < now:
                        dt = dt + timedelta(days=1)
                    entities["time"] = dt.isoformat()
                    break
                except Exception:
                    continue

        # simple location words
        locs = ["downtown", "uptown", "midtown", "central", "south", "north"]
        for loc in locs:
            if loc in t:
                entities.setdefault("location", loc)
                break

        # product matching - more flexible approach
        # First try exact matches from database (most up-to-date)
        try:
            from ..data.database import SessionLocal
            from ..data.models import Product
            db = SessionLocal()
            products = db.query(Product.name).all()
            db.close()
            
            # Find the longest matching product name (most specific)
            best_match = None
            best_length = 0
            
            for product_row in products:
                product_name = product_row[0].lower()
                if product_name in t and len(product_name) > best_length:
                    best_match = product_name
                    best_length = len(product_name)
            
            if best_match:
                entities.setdefault("product", best_match)
        except Exception:
            pass
        
        # If no exact match from database, try menu store
        if "product" not in entities:
            for item in self.menu.list_all_items():
                name = item["item"].lower()
                if name in t:
                    entities.setdefault("product", name)
                    break
        
        # If no exact match, try partial matches
        if "product" not in entities:
            # Common product keywords that might be mentioned
            product_keywords = {
                "strawberry": ["strawberry", "strawberries"],
                "raspberry": ["raspberry", "raspberries"], 
                "chocolate": ["chocolate", "choc"],
                "almond": ["almond", "almonds"],
                "cream": ["cream", "creamy"],
                "danish": ["danish", "danish pastry"],
                "croissant": ["croissant", "croissants"],
                "cake": ["cake", "cakes"],
                "muffin": ["muffin", "muffins"],
                "bread": ["bread", "loaf"],
                "cookie": ["cookie", "cookies"],
            }
            
            # Find the best matching product
            best_match = None
            best_score = 0
            
            for item in self.menu.list_all_items():
                item_name = item["item"].lower()
                score = 0
                
                # Check for keyword matches
                for keyword, variants in product_keywords.items():
                    if any(variant in item_name for variant in variants):
                        if any(variant in t for variant in variants):
                            score += 1
                
                # Check for partial word matches
                words = t.split()
                for word in words:
                    if len(word) > 3 and word in item_name:
                        score += 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = item["item"]
            
            if best_match and best_score >= 0.5:
                entities.setdefault("product", best_match.lower())
        
        # Fallback: try fuzzy match from menu store
        if "product" not in entities:
            best, score, idx = self.menu.find_best_match(t)
            if best and score >= 0.6:
                entities.setdefault("product", best.lower())
        return entities
