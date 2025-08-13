# Postprocessing Module

## Overview

The `postprocess.py` module handles response formatting and citation generation. It ensures generated responses are properly formatted and include source information.

## Key Features

- **Response Formatting**: Cleans and formats LLM responses
- **Citation Generation**: Attaches source information to responses
- **Whitespace Management**: Removes extra spaces and formatting issues
- **Structured Output**: Returns responses with citations in consistent format

## Components

### Postprocessor Class
Main class for postprocessing LLM responses and adding citations.

## Usage

```python
from backend.app.postprocess import Postprocessor

# Initialize postprocessor
postprocessor = Postprocessor()

# Process response with citations
raw_response = "We are open Monday through Friday from 8am to 8pm.  "
citations = [
    {"text": "Hours: 8am-8pm Mon-Fri", "source": "hours_info.txt#page_1"}
]

# Process response
result = postprocessor.process_response(raw_response, citations)

# Result contains formatted response and citations
print(result["response"])
print(result["citations"])
```

## Methods

### `format_response(response)`
Formats the LLM response for display.

Parameters:
- `response`: Raw LLM response text

Returns:
- Formatted response text

### `add_citations(response, citations)`
Adds citations to the response.

Parameters:
- `response`: Formatted response text
- `citations`: List of citation dictionaries

Returns:
- Dictionary with response and citations

### `process_response(response, citations)`
Complete postprocessing pipeline.

Parameters:
- `response`: Raw LLM response text
- `citations`: List of citation dictionaries

Returns:
- Dictionary with formatted response and citations

## Output Format

The module returns responses in a structured format:

```json
{
  "response": "We are open Monday through Friday from 8am to 8pm.",
  "citations": [
    {
      "text": "Hours: 8am-8pm Mon-Fri",
      "source": "hours_info.txt#page_1"
    }
  ]
}
```

## Dependencies

- `re`: Regular expressions for text formatting