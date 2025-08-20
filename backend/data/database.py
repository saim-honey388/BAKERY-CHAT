import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Define the database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "bakery.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for our models
Base = declarative_base()

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all tables in the database."""
    # Import all models here before calling create_all
    # This ensures they are registered with the Base metadata
    from .models import Product, Customer, Order, OrderItem
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    create_tables()
