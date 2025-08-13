# Retrieval Module

## Overview

The `retrieval.py` module implements hybrid document retrieval combining FAISS (dense) and BM25 (sparse) search algorithms. It finds relevant documents based on semantic similarity and keyword matching.

## Key Features

- **Hybrid Search**: Combines FAISS and BM25 retrieval
- **FAISS Integration**: Fast similarity search with vector embeddings
- **BM25 Integration**: Keyword-based search with Whoosh
- **Result Merging**: Combines results from both retrieval methods
- **Index Management**: Creates and loads search indexes

## Components

### HybridRetriever Class
Main class for performing hybrid document retrieval.

#### FAISS Retrieval
- Converts text to embeddings using Groq API
- Performs similarity search in FAISS index
- Returns documents with highest cosine similarity

#### BM25 Retrieval
- Performs keyword-based search with Whoosh
- Uses TF-IDF based scoring
- Returns documents with highest BM25 scores

#### Result Merging
- Combines scores from both retrieval methods
- Applies equal weighting (50% FAISS, 50% BM25)
- Sorts by combined relevance score

## Usage

```python
from backend.app.retrieval import HybridRetriever

# Initialize retriever
retriever = HybridRetriever()

# Search for relevant documents
query = "What are your business hours?"
results = retriever.hybrid_search(query, k=5)

# Results contain document text, source, and retrieval scores
for result in results:
    print(f"Text: {result['text']}")
    print(f"Source: {result['source']}")
    print(f"Score: {result['retrieval_score']}")
```

## Methods

### `hybrid_search(query_text, k=10)`
Performs hybrid search using both FAISS and BM25.

Parameters:
- `query_text`: Search query text
- `k`: Number of results to return

Returns:
- List of retrieved documents with scores

### `create_faiss_index(chunks_file, index_file)`
Creates FAISS index from document chunks.

### `create_whoosh_index(chunks_file, index_dir)`
Creates Whoosh index from document chunks.

## Index Structure

### Document Chunks
```json
{
  "id": "uuid",
  "branch": "Downtown",
  "category": "general_info",
  "text": "Sunrise Bakery is open Monday through Friday...",
  "source": "hours_info.txt#page_1",
  "timestamp": "2023-01-01T10:00:00"
}
```

## Dependencies

- `faiss`: Facebook AI Similarity Search library
- `whoosh`: Pure Python search engine
- `numpy`: Numerical computing
- `requests`: HTTP client for API communication