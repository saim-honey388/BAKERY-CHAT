#!/usr/bin/env python3
"""
Retrieval module for the bakery chatbot.

This module handles hybrid retrieval using FAISS (dense) and BM25 (sparse) search.
"""

import json
import os
import numpy as np
from typing import List, Dict, Any, Tuple
import faiss
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import QueryParser
from .config import Config
from .embed import EmbeddingClient

class HybridRetriever:
    """Hybrid retriever combining FAISS and BM25 retrieval."""
    
    def __init__(self):
        """Initialize the hybrid retriever."""
        self.embed_client = EmbeddingClient()
        self.faiss_index = None
        self.whoosh_index = None
        self.chunks = []
        
        # Load data and indexes
        self._load_data()
        self._load_faiss_index()
        self._load_whoosh_index()
    
    def _load_data(self):
        """Load document chunks from file."""
        if os.path.exists(Config.CHUNKS_FILE_PATH):
            with open(Config.CHUNKS_FILE_PATH, 'r') as f:
                self.chunks = json.load(f)
            print(f"Loaded {len(self.chunks)} document chunks")
        else:
            print("No chunks file found")
            self.chunks = []
    
    def _load_faiss_index(self):
        """Load FAISS index from file."""
        if os.path.exists(Config.FAISS_INDEX_PATH):
            self.faiss_index = faiss.read_index(Config.FAISS_INDEX_PATH)
            print(f"Loaded FAISS index with {self.faiss_index.ntotal} vectors")
        else:
            print("No FAISS index found")
            self.faiss_index = None
    
    def _load_whoosh_index(self):
        """Load Whoosh index from directory."""
        if os.path.exists(Config.WHOOSH_INDEX_PATH):
            self.whoosh_index = open_dir(Config.WHOOSH_INDEX_PATH)
            print("Loaded Whoosh index")
        else:
            print("No Whoosh index found")
            self.whoosh_index = None
    
    def _faiss_search(self, query_embedding: List[float], k: int = 10) -> List[Tuple[int, float]]:
        """
        Search FAISS index for similar documents.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of (index, distance) tuples
        """
        if self.faiss_index is None:
            return []
        
        # Convert to numpy array and reshape
        query_vector = np.array(query_embedding).astype('float32').reshape(1, -1)
        
        # Search index
        distances, indices = self.faiss_index.search(query_vector, k)
        
        # Return results as list of tuples
        results = []
        for i in range(len(indices[0])):
            if indices[0][i] != -1:  # -1 means no result
                results.append((int(indices[0][i]), float(distances[0][i])))
        
        return results
    
    def _bm25_search(self, query_text: str, k: int = 10) -> List[Tuple[int, float]]:
        """
        Search Whoosh index using BM25.
        
        Args:
            query_text: Query text
            k: Number of results to return
            
        Returns:
            List of (index, score) tuples
        """
        if self.whoosh_index is None:
            return []
        
        results = []
        
        with self.whoosh_index.searcher() as searcher:
            query = QueryParser("content", self.whoosh_index.schema).parse(query_text)
            hits = searcher.search(query, limit=k)
            
            for hit in hits:
                # Get document index from stored field
                doc_id = hit["id"]
                score = hit.score
                
                # Find chunk index
                for i, chunk in enumerate(self.chunks):
                    if chunk["id"] == doc_id:
                        results.append((i, score))
                        break
        
        return results
    
    def hybrid_search(self, query_text: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using both FAISS and BM25.
        
        Args:
            query_text: Query text
            k: Number of results to return
            
        Returns:
            List of retrieved documents with scores
        """
        print(f"DEBUG: Hybrid search for query: {query_text}", flush=True)
        # Generate query embedding
        query_embedding = self.embed_client.generate_embedding(query_text)
        print(f"DEBUG: Generated query embedding with {len(query_embedding)} dimensions", flush=True)
        
        # Perform both searches
        faiss_results = self._faiss_search(query_embedding, k * 2)  # Get more results for merging
        print(f"DEBUG: FAISS search returned {len(faiss_results)} results", flush=True)
        bm25_results = self._bm25_search(query_text, k * 2)
        print(f"DEBUG: BM25 search returned {len(bm25_results)} results", flush=True)
        
        # Combine results with weights
        combined_scores = {}
        
        # Add FAISS results (convert distance to similarity score)
        for idx, distance in faiss_results:
            similarity = 1 / (1 + distance)  # Convert distance to similarity
            combined_scores[idx] = combined_scores.get(idx, 0) + 0.5 * similarity
        
        # Add BM25 results
        for idx, score in bm25_results:
            combined_scores[idx] = combined_scores.get(idx, 0) + 0.5 * score
        
        # Sort by combined score
        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        print(f"DEBUG: Combined and sorted {len(sorted_results)} results", flush=True)
        
        # Get top k results
        top_results = sorted_results[:k]
        print(f"DEBUG: Selected top {len(top_results)} results", flush=True)
        
        # Format results with document content
        retrieved_docs = []
        for idx, score in top_results:
            if idx < len(self.chunks):
                doc = self.chunks[idx].copy()
                doc["retrieval_score"] = score
                retrieved_docs.append(doc)
        
        print(f"DEBUG: Hybrid search complete, returning {len(retrieved_docs)} documents", flush=True)
        return retrieved_docs

def create_faiss_index(chunks_file: str, index_file: str):
    """
    Create FAISS index from document chunks.
    
    Args:
        chunks_file: Path to chunks JSON file
        index_file: Path to save FAISS index
    """
    print("Creating FAISS index...")
    
    # Load chunks
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)
    
    if not chunks:
        print("No chunks found, skipping FAISS index creation")
        return
    
    # Initialize embedding client
    embed_client = EmbeddingClient()
    
    # Generate embeddings for all chunks
    texts = [chunk["text"] for chunk in chunks]
    print(f"Generating embeddings for {len(texts)} chunks...")
    
    embeddings = embed_client.generate_embeddings_batch(texts)
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings).astype('float32')
    
    # Create FAISS index
    dimension = len(embeddings[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_array)
    
    # Save index
    faiss.write_index(index, index_file)
    print(f"FAISS index created with {index.ntotal} vectors")

def create_whoosh_index(chunks_file: str, index_dir: str):
    """
    Create Whoosh index from document chunks.
    
    Args:
        chunks_file: Path to chunks JSON file
        index_dir: Directory to save Whoosh index
    """
    print("Creating Whoosh index...")
    
    # Load chunks
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)
    
    if not chunks:
        print("No chunks found, skipping Whoosh index creation")
        return
    
    # Create index directory
    os.makedirs(index_dir, exist_ok=True)
    
    # Define schema
    schema = Schema(
        id=ID(stored=True),
        content=TEXT(stored=True),
        branch=STORED(),
        category=STORED(),
        source=STORED()
    )
    
    # Create index
    index = create_in(index_dir, schema)
    
    # Add documents to index
    writer = index.writer()
    
    for chunk in chunks:
        writer.add_document(
            id=chunk["id"],
            content=chunk["text"],
            branch=chunk["branch"],
            category=chunk["category"],
            source=chunk["source"]
        )
    
    writer.commit()
    print(f"Whoosh index created with {len(chunks)} documents")

def main():
    """Main function for testing the hybrid retriever."""
    try:
        # Create indexes if they don't exist
        if not os.path.exists(Config.FAISS_INDEX_PATH):
            print("FAISS index not found, creating...")
            create_faiss_index(Config.CHUNKS_FILE_PATH, Config.FAISS_INDEX_PATH)
        
        if not os.path.exists(Config.WHOOSH_INDEX_PATH):
            print("Whoosh index not found, creating...")
            create_whoosh_index(Config.CHUNKS_FILE_PATH, Config.WHOOSH_INDEX_PATH)
        
        # Initialize retriever
        retriever = HybridRetriever()
        print("Hybrid retriever initialized successfully")
        
        # Test query
        query = "What are your business hours?"
        print(f"\nSearching for: {query}")
        
        results = retriever.hybrid_search(query, k=5)
        
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results):
            print(f"{i+1}. Score: {result['retrieval_score']:.4f}")
            print(f"   Text: {result['text'][:100]}...")
            print(f"   Source: {result['source']}")
            print()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()