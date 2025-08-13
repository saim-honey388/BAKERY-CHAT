# Generation Module

## Overview

The `generate.py` module handles response generation using the Groq LLM API. It sends formatted prompts to the LLM and returns generated responses.

## Key Features

- **Groq API Integration**: Connects to Groq's LLM service
- **Response Generation**: Generates natural language responses
- **Parameter Control**: Manages generation parameters for consistency
- **Error Handling**: Robust error handling for API communication

## Components

### GenerationClient Class
Main class for generating responses using Groq LLM API.

#### Supported Models
- `groq-llama-3.1`: Default LLM for text generation

#### Generation Parameters
- `temperature`: 0.2 (low temperature for consistent responses)
- `max_tokens`: 500 (maximum response length)
- `stop`: ["\nUser:"] (stop sequence to prevent extra conversation)

## Usage

```python
from backend.app.generate import GenerationClient

# Initialize generation client
gen_client = GenerationClient()

# Generate response from prompt
prompt = """
You are Sunrise Bakery's assistant...
Context:
Document 1: We are open 8am-8pm Monday through Friday.
User: What are your hours?
Assistant:
"""

response = gen_client.generate_answer(prompt)
```

## Methods

### `generate_answer(prompt)`
Generates a response using the LLM.

Parameters:
- `prompt`: Formatted prompt for the LLM

Returns:
- Generated response text

## API Integration

The module communicates with the Groq API at:
`https://api.groq.com/openai/v1/chat/completions`

Request format:
```json
{
  "model": "groq-llama-3.1",
  "messages": [
    {
      "role": "user",
      "content": "Formatted prompt..."
    }
  ],
  "temperature": 0.2,
  "max_tokens": 500,
  "stop": ["\nUser:"]
}
```

Response format:
```json
{
  "choices": [
    {
      "message": {
        "content": "We are open Monday through Friday from 8am to 8pm."
      }
    }
  ]
}
```

## Dependencies

- `requests`: HTTP client for API communication