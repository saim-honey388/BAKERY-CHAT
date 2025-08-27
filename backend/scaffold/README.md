
# BAKERY-CHAT Backend: In-Depth Structure & Workflow (v1.2+)

This backend powers a production-grade bakery chatbot using a modular, agent-based, retrieval-augmented generation (RAG) pipeline. The structure below reflects the **actual codebase** (not just the scaffold), with detailed comments and workflow analysis.

---

## Directory Structure (Key Folders & Files)

```text
backend/
  agents/           # Modular intent agents (see below)
  app/              # Core app logic, orchestration, API
  data/             # Data models, DB, ingestion, raw/processed data
  nlu/              # NLU: intent/entity extraction, routing
  schemas/          # Pydantic models for API & agent contracts
  utils/            # Logging, analytics, security
  scripts/          # Data ingestion, test scripts
```

### agents/
- `base_agent.py`         : Abstract base class for all agents (enforces interface)
- `general_info_agent.py` : Answers FAQs, hours, locations (RAG + rules)
- `product_info_agent.py` : Handles menu lookups, prices, recommendations (DB-backed)
- `order_agent.py`        : Manages order flow, cart, slot filling, upsells, business logic, DB
- `meta_agent.py`         : Handles meta/system queries ("who are you?")

### app/
- `main.py`         : FastAPI app, API endpoints, CORS, static file serving
- `controller.py`   : Orchestrates NLU, agent routing, session, LLM prompt building
- `config.py`       : Centralized config (env vars, model names, paths)
- `session.py`      : Session/context management (Redis or in-memory fallback)
- `preprocess.py`   : Text normalization, intent detection, spell correction
- `embed.py`        : Embedding client (sentence-transformers)
- `retrieval.py`    : Hybrid retrieval (FAISS dense + Whoosh BM25 sparse)
- `rerank.py`       : Cross-encoder reranking of retrieved docs
- `prompt_builder.py`: Builds LLM prompts with context, history, agent rules
- `generate.py`     : LLM client (Groq API)
- `postprocess.py`  : Cleans, formats, and adds citations to LLM output

### data/
- `database.py`     : SQLAlchemy DB setup (SQLite), session, table creation
- `models.py`       : SQLAlchemy models (Product, Customer, Order, OrderItem, enums)
- `menu_store.py`   : Loads menu from CSV, provides search/fuzzy matching
- `populate_db.py`  : Populates DB from menu CSV
- `bakery.db`       : SQLite DB file
- `orders.csv`      : Example order data
  raw/              : Source data (FAQs, menu, locations, general info)
   - `faq.json`, `general_info.txt`, `locations.json`, `menu.csv`
  processed/        : Precomputed indices for retrieval
   - `chunks.json`, `faiss_index.bin`, `whoosh_index/`

### nlu/
- `entity_extractor.py` : Rule-based entity extraction (product, time, quantity, etc.)
- `intent_model.py`     : Rule-based intent classifier
- `llm_router.py`       : LLM-based fallback router for ambiguous queries
- `rules.py`            : Rule-based intent routing utilities

### schemas/
- `io_models.py`    : AgentResult, Citation, QueryRequest/Response
- `order_models.py` : Order creation/response models, enums

### utils/
- `logger.py`       : Logging setup
- `analytics.py`    : Event tracking (stub)
- `security.py`     : PII masking

### scripts/
- `ingest_data.py`, `test_agents.py`: Data processing and agent testing

---

## In-Depth Workflow (Query to Response)

1. **Frontend** sends a query to `/query` endpoint (`main.py`).
2. **Session Management**: `session.py` ensures a session exists (Redis or in-memory).
3. **Preprocessing**: `preprocess.py` normalizes, spell-corrects, and detects intent.
4. **NLU**:
  - **Intent Detection**: `nlu/rules.py` and `nlu/intent_model.py` use rules/keywords.
  - **Entity Extraction**: `nlu/entity_extractor.py` extracts products, quantities, times, etc.
  - **LLM Router**: If rules are ambiguous, `llm_router.py` uses LLM to suggest intent.
5. **Agent Routing** (`controller.py`):
  - Based on intent, dispatches to the appropriate agent (`agents/`).
  - **Order context**: If an order is in progress, always routes to `order_agent.py`.
  - Passes session context and extracted entities to agent.
6. **Agent Execution**:
  - **GeneralInfoAgent**: Answers FAQs, hours, locations (uses RAG pipeline or rules).
  - **ProductInfoAgent**: Looks up menu items, prices, recommendations (DB-backed).
  - **OrderAgent**: Manages cart, slot filling, upsells, confirmation, and DB persistence.
  - **MetaAgent**: Handles system/meta queries.
7. **Retrieval-Augmented Generation (RAG)**:
  - **Retrieval**: `retrieval.py` uses hybrid search (FAISS + Whoosh) to fetch relevant docs.
  - **Reranking**: `rerank.py` sorts retrieved docs by relevance.
  - **Prompt Building**: `prompt_builder.py` constructs a prompt with context, history, and agent facts.
  - **LLM Generation**: `generate.py` calls Groq LLM for final response.
  - **Postprocessing**: `postprocess.py` formats and adds citations.
8. **Response**: Controller returns the response and citations to the frontend, and logs the assistant message in the session.

---

## Data Flow & Storage

- **Menu and Product Data**: Loaded from `menu.csv` into DB (`populate_db.py`, `menu_store.py`).
- **Order Data**: Orders are persisted in `bakery.db` (SQLAlchemy models).
- **FAQs, Locations, General Info**: Used for RAG context and quick answers.
- **Indices**: `chunks.json`, `faiss_index.bin`, and `whoosh_index/` enable fast retrieval.

---

## Agent Design (with Comments)

- **BaseAgent**: All agents inherit from this, ensuring a consistent interface.
- **OrderAgent**: Maintains a per-session cart, handles slot filling, upsells, and order confirmation. Validates business hours, stock, and required details before finalizing.
- **ProductInfoAgent**: Handles menu queries, price filtering, and recommendations.
- **GeneralInfoAgent**: Answers FAQs, hours, delivery, and location queries.
- **MetaAgent**: Handles system/meta queries.

---

## RAG Pipeline (Retrieval-Augmented Generation)

1. **Preprocessing**: Cleans and normalizes input.
2. **Embedding**: Generates dense vectors for queries and docs.
3. **Retrieval**: Hybrid search (dense + sparse).
4. **Reranking**: Cross-encoder for best matches.
5. **Prompt Building**: Assembles all context and facts for LLM.
6. **LLM Generation**: Produces final, conversational response.
7. **Postprocessing**: Cleans up and attaches citations.

---

## Data Ingestion & Indexing

- **Scripts**: `scripts/ingest_data.py` processes raw data, builds indices, and populates the DB.
- **Raw Data**: `data/raw/faq.json`, `menu.csv`, `locations.json`, `general_info.txt` are used for both retrieval and agent logic.
- **Processed Data**: `data/processed/` contains precomputed indices for fast hybrid retrieval.

---

## Comments on Modifications vs. Original Scaffold

- The actual codebase is more modular and robust than the original scaffold.
- **OrderAgent** is much more sophisticated: cart, upsells, slot filling, business hour validation, and error handling.
- **Menu and Product Info**: Uses both DB and CSV, with fuzzy matching and category filtering.
- **NLU**: Rule-based, but with LLM fallback for ambiguous queries.
- **Session Management**: Redis-backed, with in-memory fallback.
- **RAG Pipeline**: Fully implemented with FAISS, Whoosh, and cross-encoder reranking.
- **Data**: Real menu, FAQ, and location data are present and used in both retrieval and agent logic.

---

## Best Practices & Extensibility

- **Add docstrings and comments** to all new modules and functions.
- **Test agents and data flows** using scripts in `scripts/`.
- **Extend agents** for new intents or business logic as needed.
- **Update indices** after major data changes (menu, FAQs, etc.).

---

*This README reflects the actual, deeply analyzed structure and workflow of the BAKERY-CHAT backend as of August 2025.*
