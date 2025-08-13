# Embedding Module

## Overview

The `embed.py` module handles text embedding generation using the Groq API. It converts text into numerical vectors that capture semantic meaning for similarity search.

## Key Features

- **Groq API Integration**: Connects to Groq's embedding service
- **Single Text Embedding**: Generate embedding for individual text strings
- **Batch Embedding**: Generate embeddings for multiple texts efficiently
- **Error Handling**: Robust error handling for API communication

## Components

### EmbeddingClient Class
Main class for generating text embeddings using Groq API.

#### Supported Models
- `groq-embed-1`: Default embedding model for text similarity

## Usage

```python
from backend.app.embed import EmbeddingClient

# Initialize embedding client
embed_client = EmbeddingClient()

# Generate embedding for single text
embedding = embed_client.generate_embedding("Hello, world!")

# Generate embeddings for multiple texts
texts = ["First text", "Second text", "Third text"]
embeddings = embed_client.generate_embeddings_batch(texts)
```

## Methods

### `generate_embedding(text)`
Generates an embedding vector for a single text string.

Parameters:
- `text`: Text string to embed

Returns:
- List of float values representing the embedding vector

### `generate_embeddings_batch(texts)`
Generates embedding vectors for a batch of text strings.

Parameters:
- `texts`: List of text strings to embed

Returns:
- List of embedding vectors

## API Integration

The module communicates with the Groq API at:
`https://api.groq.com/openai/v1/embeddings`

Request format:
```json
{
  "model": "groq-embed-1",
  "input": "Text to embed"
}
```

Response format:
```json
{
  "data": [
    {
      "embedding": [0.123, -0.456, 0.789, ...]
    }
  ]
}
```

## Dependencies

- `requests`: HTTP client for API communication
- `numpy`: Numerical computing (for vector operations)