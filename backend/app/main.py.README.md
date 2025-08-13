# Main Application Module

## Overview

The `main.py` module orchestrates the entire RAG pipeline by connecting all components through a FastAPI web application. It exposes REST endpoints for session management and query processing.

## Key Features

- **FastAPI Integration**: REST API with automatic documentation
- **Pipeline Orchestration**: Coordinates all RAG components
- **Session Management**: Handles user sessions and conversation context
- **Error Handling**: Centralized error handling for API responses

## Components

### FastAPI Application
Main application with endpoints for session creation and query processing.

#### Request/Response Models
- `QueryRequest`: Session ID and query text
- `QueryResponse`: Response text and citations
- `SessionCreateRequest`: Optional session ID for creation
- `SessionCreateResponse`: Created session ID and status

## Endpoints

### `POST /session`
Creates a new chat session.

Request:
```json
{
  "session_id": "optional_custom_session_id"
}
```

Response:
```json
{
  "session_id": "generated_or_provided_session_id",
  "created": true
}
```

### `POST /query`
Processes a chat query through the full RAG pipeline.

Request:
```json
{
  "session_id": "session_123",
  "query": "What are your business hours?"
}
```

Response:
```json
{
  "session_id": "session_123",
  "response": "We are open Monday through Friday from 8am to 8pm.",
  "citations": [
    {
      "text": "Hours: 8am-8pm Mon-Fri",
      "source": "hours_info.txt#page_1"
    }
  ]
}
```

### `GET /health`
Health check endpoint.

Response:
```json
{
  "status": "healthy"
}
```

## Pipeline Flow

1. **Preprocessing**: Clean and analyze user query
2. **Session Management**: Store user message, retrieve conversation history
3. **Retrieval**: Find relevant documents using hybrid search
4. **Reranking**: Improve document relevance with Cross-Encoder
5. **Prompt Building**: Construct LLM prompt with context and history
6. **Generation**: Generate response using Groq LLM
7. **Postprocessing**: Format response and add citations
8. **Session Update**: Store assistant response in conversation history

## Usage

```bash
# Start the application
uvicorn backend.app.main:app --reload

# Create a session
curl -X POST http://localhost:8000/session

# Send a query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"session_id": "session_123", "query": "What are your hours?"}'
```

## Dependencies

- `fastapi`: Web framework for API
- `uvicorn`: ASGI server for FastAPI
- `pydantic`: Data validation and settings management
- All other backend modules