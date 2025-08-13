# Session Management Module

## Overview

The `session.py` module manages conversation context and session data using Redis. It maintains conversation history, handles session creation, and provides context for the RAG pipeline.

## Key Features

- **Session Creation**: Initialize new chat sessions with unique IDs
- **Message Storage**: Store conversation history in Redis
- **Context Retrieval**: Retrieve recent conversation context
- **Session Persistence**: Maintain sessions across API calls

## Components

### SessionManager Class
Main class for managing user sessions with Redis backend.

#### Session Data Structure
```json
{
  "messages": [
    {"role": "user", "text": "Hello", "timestamp": "2023-01-01T10:00:00"},
    {"role": "assistant", "text": "Hi there!", "timestamp": "2023-01-01T10:00:05"}
  ],
  "summary": "Conversation about bakery hours",
  "created_at": "2023-01-01T10:00:00",
  "last_updated": "2023-01-01T10:00:05"
}
```

## Usage

```python
from backend.app.session import SessionManager

session_manager = SessionManager()

# Create a new session
session_id = "session_123"
session_manager.create_session(session_id)

# Add messages to session
session_manager.add_message(session_id, "user", "What are your hours?")
session_manager.add_message(session_id, "assistant", "We are open 8am-8pm M-F")

# Retrieve conversation context
context = session_manager.get_conversation_context(session_id)
```

## Methods

### `create_session(session_id)`
Creates a new session with the given ID.

### `get_session(session_id)`
Retrieves all session data for a session ID.

### `add_message(session_id, role, text)`
Adds a new message to the conversation history.

### `get_recent_messages(session_id, max_messages)`
Retrieves recent messages from the conversation history.

### `get_conversation_context(session_id)`
Formats recent conversation history for prompt context.

### `update_summary(session_id, summary)`
Updates the session summary.

### `get_summary(session_id)`
Retrieves the session summary.

### `clear_session(session_id)`
Deletes all session data.

## Redis Storage

Sessions are stored in Redis with keys in the format: `session:{session_id}`

## Dependencies

- `redis`: Redis client for Python
- `json`: JSON serialization
- `datetime`: Timestamp generation