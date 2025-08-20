import csv
import os
from .database import SessionLocal, create_tables
from .models import Product

MENU_CSV_PATH = os.path.join(os.path.dirname(__file__), "raw", "menu.csv")

def populate_products():
    """Read menu.csv and populate the products table."""
    # Ensure tables are created
    create_tables()
    
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("Products table is not empty. Skipping population.")
            return

        with open(MENU_CSV_PATH, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                product = Product(
                    name=row['item'],
                    description=row['description'],
                    price=float(row['price'].replace('$', '')),
                    category=row['category'],
                    quantity_in_stock=100  # Default stock
                )
                db.add(product)
        
        db.commit()
        print("Successfully populated the products table.")
    except Exception as e:
        db.rollback()
        print(f"Error populating products table: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    populate_products()
