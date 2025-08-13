# Prompt Building Module

## Overview

The `prompt_builder.py` module constructs prompts for the LLM by combining retrieved context, conversation history, and user queries. It ensures the LLM has all necessary information to generate accurate responses.

## Key Features

- **Prompt Template**: Structured prompt with system instructions
- **Context Integration**: Incorporates retrieved documents
- **Conversation History**: Maintains dialogue context
- **Citation Formatting**: Prepares source information for responses

## Components

### PromptBuilder Class
Main class for constructing LLM prompts with context and conversation history.

#### Prompt Structure
```
You are Sunrise Bakery's assistant. Your role is to help customers...

Context:
{retrieved_document_context}

Conversation so far:
{conversation_history}

User: {latest_user_query}
Assistant:
```

## Usage

```python
from backend.app.prompt_builder import PromptBuilder

# Initialize prompt builder
prompt_builder = PromptBuilder()

# Build prompt with context and conversation history
query = "What are your hours?"
context_docs = [{"text": "We are open 8am-8pm M-F", "source": "hours.txt"}]
conversation_history = "user: Hi there!\nassistant: Hello! How can I help?"

prompt = prompt_builder.build_prompt(query, context_docs, conversation_history)
```

## Methods

### `build_prompt(query, context_docs, conversation_history="")`
Builds a complete prompt for the LLM.

Parameters:
- `query`: Latest user query
- `context_docs`: Retrieved documents with context
- `conversation_history`: Recent conversation history

Returns:
- Formatted prompt string for LLM

### `format_citations(context_docs)`
Formats citations from retrieved documents.

Parameters:
- `context_docs`: Retrieved documents

Returns:
- List of formatted citations

## Prompt Template

The system uses a structured prompt template:

```
You are Sunrise Bakery's assistant. Your role is to help customers with information about our bakery, including hours, locations, menu items, and services.

Instructions:
- Use only the provided context to answer questions
- If you don't have enough information to answer accurately, say "I'm not sure, but I can check with our staff."
- Be friendly and helpful in your responses
- Provide concise but complete answers
- Include relevant details like hours, prices, or locations when applicable

Context:
{context}

{conversation_history}

User: {query}
Assistant:
```

## Dependencies

- Built-in Python string formatting