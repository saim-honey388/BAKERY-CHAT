#!/usr/bin/env python3
"""
Embedding module for the bakery chatbot.

This module handles text embedding using sentence-transformers.
"""

import json
import numpy as np
from typing import List, Dict, Any, Union
from sentence_transformers import SentenceTransformer
from .config import Config

class EmbeddingClient:
    """Client for generating text embeddings using sentence-transformers."""
    
    def __init__(self):
        """Initialize the embedding client."""
        # Use all-MiniLM-L6-v2 model for embeddings
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as a list of floats
        """
        # Generate embedding
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of text strings.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Generate embeddings for all texts
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

def main():
    """Main function for testing the embedding client."""
    try:
        # Initialize embedding client
        embed_client = EmbeddingClient()
        print("Embedding client initialized successfully")
        
        # Test texts
        test_texts = [
            "Sunrise Bakery is open from 8am to 8pm Monday through Friday.",
            "Our Downtown branch is located at 123 Main Street.",
            "We offer fresh croissants, baguettes, and sourdough bread daily."
        ]
        
        print("\nGenerating embeddings...")
        embeddings = embed_client.generate_embeddings_batch(test_texts)
        
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Embedding dimension: {len(embeddings[0])}")
        
        # Show sample of first embedding
        print(f"First embedding (first 5 values): {embeddings[0][:5]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()