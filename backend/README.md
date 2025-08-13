# Bakery Chatbot Backend

This directory contains the backend implementation of the bakery chatbot RAG pipeline.

## Directory Structure

```
backend/
├── app/                 # Main application modules
├── data/                # Data storage
│   ├── raw/             # Raw data files
│   └── processed/       # Processed data chunks
├── scripts/             # Utility scripts
└── requirements.txt     # Python dependencies
```

## Modules

Each module in the `app/` directory serves a specific function in the RAG pipeline:

1. **config.py** - Configuration management
2. **preprocess.py** - Text preprocessing and intent detection
3. **session.py** - Conversation session management with Redis
4. **embed.py** - Text embedding generation with Groq API
5. **retrieval.py** - Hybrid document retrieval (FAISS + BM25)
6. **rerank.py** - Document relevance reranking
7. **prompt_builder.py** - LLM prompt construction
8. **generate.py** - Response generation with Groq LLM
9. **postprocess.py** - Response formatting and citation management
10. **main.py** - FastAPI application orchestration

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`:
   ```bash
   GROQ_API_KEY=your_groq_api_key
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

3. Process data:
   ```bash
   python scripts/ingest_data.py
   ```

4. Run the application:
   ```bash
   uvicorn backend.app.main:app --reload