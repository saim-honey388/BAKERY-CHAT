#!/usr/bin/env python3
"""
Reranking module for the bakery chatbot.

This module uses a Cross-Encoder model to rerank retrieved documents.
"""

from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from .config import Config

class Reranker:
    """Reranker using Cross-Encoder model."""
    
    def __init__(self):
        """Initialize the reranker with Cross-Encoder model."""
        self.model = CrossEncoder(Config.CROSS_ENCODER_MODEL)
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
        """
        Rerank documents using Cross-Encoder.
        
        Args:
            query: Query text
            documents: List of documents to rerank
            k: Number of top documents to return
            
        Returns:
            List of reranked documents
        """
        print(f"DEBUG: Reranking {len(documents)} documents for query: {query}", flush=True)
        if not documents:
            print("DEBUG: No documents to rerank", flush=True)
            return []
        
        # Prepare pairs for Cross-Encoder
        pairs = [[query, doc["text"]] for doc in documents]
        print(f"DEBUG: Prepared {len(pairs)} query-document pairs", flush=True)
        
        # Get similarity scores
        scores = self.model.predict(pairs)
        print(f"DEBUG: Generated {len(scores)} similarity scores", flush=True)
        
        # Add scores to documents
        for i, doc in enumerate(documents):
            doc["rerank_score"] = float(scores[i])
        
        # Sort by rerank score
        reranked_docs = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
        print(f"DEBUG: Sorted documents by rerank score", flush=True)
        
        # Return top k documents
        result = reranked_docs[:k]
        print(f"DEBUG: Reranking complete, returning {len(result)} documents", flush=True)
        return result

def main():
    """Main function for testing the reranker."""
    try:
        # Initialize reranker
        reranker = Reranker()
        print("Reranker initialized successfully")
        
        # Test query and documents
        query = "What are your business hours?"
        test_docs = [
            {
                "text": "Sunrise Bakery is open Monday through Friday from 8am to 8pm. Weekend hours are 9am to 6pm.",
                "source": "hours_info.txt"
            },
            {
                "text": "We offer fresh croissants, baguettes, and sourdough bread daily. All our pastries are made fresh each morning.",
                "source": "menu_info.txt"
            },
            {
                "text": "Our Downtown branch is located at 123 Main Street. We also have locations in Uptown and the Mall.",
                "source": "location_info.txt"
            }
        ]
        
        print(f"\nReranking {len(test_docs)} documents for query: {query}")
        
        reranked_docs = reranker.rerank(query, test_docs, k=3)
        
        print("\nReranked results:")
        for i, doc in enumerate(reranked_docs):
            print(f"{i+1}. Score: {doc['rerank_score']:.4f}")
            print(f"   Text: {doc['text']}")
            print(f"   Source: {doc['source']}")
            print()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()