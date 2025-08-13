#!/usr/bin/env python3
"""
Script to create FAISS and Whoosh indexes for the bakery chatbot.
"""

import sys
import os

# Add backend to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.retrieval import create_faiss_index, create_whoosh_index

def main():
    """Main function to create indexes."""
    chunks_file = "backend/data/processed/chunks.json"
    faiss_index_file = "backend/data/processed/faiss_index.bin"
    whoosh_index_dir = "backend/data/processed/whoosh_index"
    
    print("Creating FAISS index...")
    try:
        create_faiss_index(chunks_file, faiss_index_file)
        print("FAISS index created successfully")
    except Exception as e:
        print(f"Error creating FAISS index: {e}")
        return False
    
    print("\nCreating Whoosh index...")
    try:
        create_whoosh_index(chunks_file, whoosh_index_dir)
        print("Whoosh index created successfully")
    except Exception as e:
        print(f"Error creating Whoosh index: {e}")
        return False
    
    print("\nAll indexes created successfully!")
    return True

if __name__ == "__main__":
    main()