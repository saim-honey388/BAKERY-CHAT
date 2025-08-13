# Configuration Management Module

## Overview

The `config.py` module manages all configuration settings for the bakery chatbot backend. It loads environment variables, validates required settings, and provides a centralized configuration interface.

## Key Features

- **Environment Variable Loading**: Uses `python-dotenv` to load settings from `.env` file
- **Validation**: Ensures required configuration values are present
- **Centralized Access**: All configuration values accessible through the `Config` class

## Configuration Settings

### Groq API Configuration
- `GROQ_API_KEY`: API key for Groq services
- `GROQ_EMBEDDING_MODEL`: Model name for text embeddings (`groq-embed-1`)
- `GROQ_LLM_MODEL`: Model name for text generation (`groq-llama-3.1`)

### Redis Configuration
- `REDIS_HOST`: Redis server hostname (default: `localhost`)
- `REDIS_PORT`: Redis server port (default: `6379`)
- `REDIS_DB`: Redis database number (default: `0`)

### Application Configuration
- `CHUNK_SIZE`: Target size for document chunks (250 tokens)
- `CHUNK_OVERLAP`: Overlap between document chunks (50 tokens)
- `MAX_CONTEXT_DOCS`: Maximum documents to include in context (5)
- `MAX_CONVERSATION_TURNS`: Maximum conversation history to retain (10)

### Index Configuration
- `FAISS_INDEX_PATH`: Path to FAISS index file
- `CHUNKS_FILE_PATH`: Path to processed document chunks
- `WHOOSH_INDEX_PATH`: Path to Whoosh index directory

## Usage

```python
from backend.app.config import Config

# Access configuration values
api_key = Config.GROQ_API_KEY
redis_host = Config.REDIS_HOST
```

## Environment Variables

Create a `.env` file in the project root with the following:

```env
GROQ_API_KEY=your_groq_api_key_here
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## Dependencies

- `python-dotenv`: For loading environment variables