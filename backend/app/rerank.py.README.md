# Reranking Module

## Overview

The `rerank.py` module improves the relevance of retrieved documents using a Cross-Encoder model. It scores document-query pairs more accurately than initial retrieval methods.

## Key Features

- **Cross-Encoder Integration**: Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` model
- **Relevance Scoring**: Accurately scores document-query relevance
- **Result Reranking**: Sorts retrieved documents by relevance scores
- **Top-K Selection**: Returns the most relevant documents

## Components

### Reranker Class
Main class for reranking retrieved documents using Cross-Encoder.

#### Cross-Encoder Model
- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Purpose: Rerank search results based on relevance
- Input: Query and document text pairs
- Output: Relevance scores for each pair

## Usage

```python
from backend.app.rerank import Reranker

# Initialize reranker
reranker = Reranker()

# Rerank retrieved documents
query = "What are your business hours?"
documents = [
    {"text": "We are open Monday through Friday from 8am to 8pm.", "source": "hours.txt"},
    {"text": "Our Downtown branch is located at 123 Main Street.", "source": "locations.txt"}
]

# Get reranked results
reranked_docs = reranker.rerank(query, documents, k=5)
```

## Methods

### `rerank(query, documents, k=5)`
Reranks documents using Cross-Encoder model.

Parameters:
- `query`: Search query text
- `documents`: List of retrieved documents
- `k`: Number of top documents to return

Returns:
- List of reranked documents with relevance scores

## Model Details

### cross-encoder/ms-marco-MiniLM-L-6-v2
- **Type**: Cross-Encoder model
- **Training Data**: Microsoft's MS MARCO dataset
- **Architecture**: MiniLM with 6 layers
- **Purpose**: Efficient and accurate relevance scoring
- **Input**: Query-document text pairs
- **Output**: Relevance scores (higher = more relevant)

## Dependencies

- `sentence-transformers`: Cross-Encoder model implementation
- `torch`: Deep learning framework (required by sentence-transformers)