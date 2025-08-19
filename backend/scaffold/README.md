# Backend Scaffold for BAKERY-CHAT

This folder contains the scaffold for the backend of the BAKERY-CHAT project. Below is the directory structure and purpose of each file:

## Directory Structure

```
/backend
  /app
    main.py                    # FastAPI app & routes
    config.py                  # Environment variables, model names
    session.py                 # SQLite session management
    controller.py              # Orchestrator: intent classification + multi-agent coordination
  /nlu
    intent_model.py            # Multi-label intent classification
    entity_extractor.py        # Entity extraction (products, time, quantity, branch)
  /agents
    __init__.py
    general_info_agent.py      # Handles hours, locations, FAQs
    product_info_agent.py      # Handles menu queries, prices, recommendations
    order_agent.py             # Handles order placement (slot filling + DB insert)
    meta_agent.py              # (Optional: system/meta queries like "who are you?")
  /rag_pipeline
    preprocess.py              # Clean & normalize input
    embed.py                   # Embedding client
    retrieval.py               # Hybrid retrieval (FAISS + Whoosh)
    rerank.py                  # Cross-encoder reranker
    prompt_factory.py          # Prompt builder for different agents
    generate.py                # LLM call for response generation
    postprocess.py             # Format, clean, add citations
  /data
    /raw                       # Raw input (FAQs, menu, policies)
    /processed                 # FAISS/Whoosh indices
    menu.csv                   # Menu items & prices
    orders.db                  # SQLite order storage
  /schemas
    io_models.py               # Pydantic models for API I/O
    order_models.py            # Pydantic models for orders
  /utils
    logger.py                  # Logging utilities
    security.py                # PII masking, safe logging
    analytics.py               # Track usage, agent success/failure
```

## Purpose of Each File

### `/app`
- **`main.py`**: Entry point for the FastAPI application. Defines routes and initializes components.
- **`config.py`**: Stores environment variables, model names, and paths.
- **`session.py`**: Manages session data using SQLite.
- **`controller.py`**: Orchestrates intent classification and multi-agent coordination.

### `/nlu`
- **`intent_model.py`**: Implements multi-label intent classification.
- **`entity_extractor.py`**: Extracts entities like products, time, quantity, and branch.

### `/agents`
- **`general_info_agent.py`**: Handles general queries like hours, locations, and FAQs.
- **`product_info_agent.py`**: Handles menu-related queries, prices, and recommendations.
- **`order_agent.py`**: Manages order placement, slot filling, and database insertion.
- **`meta_agent.py`**: (Optional) Handles system/meta queries like "who are you?".

### `/rag_pipeline`
- **`preprocess.py`**: Cleans and normalizes input queries.
- **`embed.py`**: Generates embeddings for queries and documents.
- **`retrieval.py`**: Performs hybrid retrieval using FAISS and Whoosh.
- **`rerank.py`**: Reranks retrieved documents using a cross-encoder.
- **`prompt_factory.py`**: Builds prompts for different agents.
- **`generate.py`**: Calls the LLM (e.g., Groq or OpenAI) for response generation.
- **`postprocess.py`**: Cleans, formats, and adds citations to responses.

### `/data`
- **`/raw`**: Stores raw input data like FAQs, menu, and policies.
- **`/processed`**: Stores processed data like FAISS and Whoosh indices.
- **`menu.csv`**: Contains menu items and prices.
- **`orders.db`**: SQLite database for storing orders.

### `/schemas`
- **`io_models.py`**: Defines Pydantic models for API input/output.
- **`order_models.py`**: Defines Pydantic models for order-related data.

### `/utils`
- **`logger.py`**: Provides logging utilities.
- **`security.py`**: Handles PII masking and safe logging.
- **`analytics.py`**: Tracks usage, agent success/failure, and other analytics.

## Next Steps
- Implement the file placeholders with minimal code templates.
- Add docstrings to describe the purpose and usage of each function.
- Gradually build out the functionality for each component.
