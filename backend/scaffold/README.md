
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

#### Agent Deep Dive

1) base_agent.py
- Purpose: Establish a consistent interface for all agents and shared utilities.
- Key API:
  - `handle(session_id, query, session, memory_context) -> AgentResult`: required entrypoint.
  - Shared helpers for standardized success/error responses and message formatting.
- Inputs: normalized user query, session turns, optional memory context snapshot.
- Outputs: `AgentResult` containing message text, optional facts (e.g., receipt), and flags.

2) general_info_agent.py
- Purpose: Fast, reliable answers to general bakery questions (hours, branches, policies).
- Logic:
  - Rule checks for common intents (e.g., open hours, address) to answer instantly.
  - Falls back to RAG (Whoosh/FAISS + rerank) when the answer requires longer text.
- Inputs: user query + retrieval context.
- Outputs: concise factual answer with optional citations.
- Edge cases: ambiguous branch names → prompts user to choose; off-hours queries → returns correct schedule.

3) product_info_agent.py
- Purpose: Product discovery — names, prices, availability, categories, recommendations.
- Data Sources: SQLAlchemy Product model (populated from CSV), `menu_store.py` fuzzy search.
- Logic:
  - Extract product/quantity terms; match against DB with case-insensitive and fuzzy strategies.
  - Respond with price, category, and availability; propose similar items if not found.
- Inputs: user query with possible item names; optional filters (price, category).
- Outputs: structured message about items; can return a list or single product details.
- Edge cases: typo-heavy names → uses fuzzy match; multiple candidates → asks a clarifying question.

4) order_agent.py
- Purpose: End-to-end order management with a server-side cart, validations, and persistence.
- Core Responsibilities:
  - Maintain per-session cart (items, fulfillment, customer info, payment).
  - Validate stock, branch hours, and required fields before confirm.
  - Implement Phase 1-first modify policy: ask what to change, apply specific change, then preview.
  - Finalize orders: create Order/OrderItem rows; decrement product stock atomically.
- Dual API (Gemini-first):
  - Enhanced/context phase builds an authoritative memory snapshot (summary, last turns, cart_state).
  - Primary/decision phase returns: `response_type` (ask_details | modify_cart | confirm_order | show_receipt), `message`, `cart_updates`, and `cart_state`.
- Important Flags in cart_state:
  - `awaiting_details`: collecting missing info
  - `awaiting_confirmation`: user needs to explicitly confirm
  - `awaiting_fulfillment`: waiting for pickup/delivery specifics
- Modify Flow (Phase 1-first):
  1. User: "modify" → agent returns a short prompt: what to change (items, time, branch, name/phone, payment).
  2. User specifies field → agent applies targeted update and recalculates totals.
  3. Agent shows a preview receipt and sets `awaiting_confirmation = True`.
  4. Loop until user confirms or cancels.
- Confirm Flow (Preview-first):
  - Only finalize on explicit confirm. On finalize:
    - Re-query products into the active SQLAlchemy session.
    - Decrement `quantity_in_stock`, insert `OrderItem` rows, commit, set status to confirmed.
    - Cache receipt text by session for retrieval.
- Cancel Flow:
  - If awaiting confirmation and user cancels: clear cart safely (no stock changes) and exit.
- Edge cases & Guards:
  - Invalid pickup time relative to branch hours → ask for a valid time window.
  - Product stock insufficiency → return a concise message with available quantity.

5) meta_agent.py
- Purpose: Handles system/meta queries (about the assistant, capabilities, version).
- Behavior: Returns brief, friendly answers without touching cart or DB.

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
- `generate.py`     : LLM client (Gemini‑first via Dual API System)
- `postprocess.py`  : Cleans, formats, and adds citations to LLM output

#### App Deep Dive

1) main.py
- FastAPI factory, CORS, and route registration (e.g., POST `/query`).
- Serves minimal frontend assets for local testing.

2) controller.py
- Entry coordinator: pulls session history, calls preprocessing + NLU, chooses agent.
- Packages memory context (summary, last messages, authoritative cart) for the Dual API.
- Returns a unified JSON to frontend (message, facts like receipt, flags).

3) config.py
- Reads environment variables (GEMINI_API_KEY, providers, models). Defaults are safe.
- Provides a `.validate()` guard for critical settings.

4) preprocess.py / postprocess.py
- Preprocess: lowercasing, trimming, simple replacements, and intent cues.
- Postprocess: normalize formatting and attach citations (if any) to answers.

5) retrieval.py / rerank.py / embed.py
- retrieval.py: orchestrates hybrid search (FAISS dense + Whoosh BM25).
- rerank.py: cross-encoder reranking to improve top-k relevance.
- embed.py: embedding generation for documents/queries (model configurable).

6) prompt_builder.py
- Builds LLM prompts with: session context, cart facts, validation rules, and constraints.
- Produces separate prompts for Enhanced (context) and Primary (decision) stages.

7) generate.py (Gemini-first via Dual API)
- Handles LLM calls in a provider-agnostic way; Dual API decides which provider to use.
- Enhanced: concise memory snapshot (summary, last turns, cart state, features).
- Primary: returns `response_type`, `message`, `cart_updates`, `cart_state`.

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
  - **LLM Generation (Dual API, Gemini-first)**:
    - Enhanced phase: Gemini builds a memory snapshot (summary, last messages, cart_state, features).
    - Primary phase: Gemini returns action and message: `response_type` (ask_details | modify_cart | confirm_order | show_receipt), `message`, optional `cart_updates`, and `cart_state` flags.
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

---

## Plain‑English Summary (for non‑technical readers)

BAKERY‑CHAT is a helpful assistant for a bakery. You can chat with it to ask about store hours, locations, and products, and you can place an order. When you order, the assistant keeps track of your cart (what you want to buy), your name and phone, where and when you’ll pick it up (or get it delivered), and how you want to pay.

Before confirming, it always shows you a clear preview of your order (items, prices, tax, total, pickup time, and branch). If you say “modify,” it will ask what you want to change (like time, branch, items, or payment) and then show the updated preview. When you say “confirm,” it safely saves the order and reduces product stock in the store’s system. If you say “cancel,” it clears the cart without changing stock.

Behind the scenes, the assistant uses a smart language model (Gemini) to understand your messages and a small database to store products and orders. It also checks simple rules like “is the pickup time inside the branch’s open hours?” and “is there enough stock?” to make sure your order is realistic. All this happens quickly so you can order with confidence.

User preferences and likes are also stored to provide warm, personalized responses and suggest relevant items.

In short: ask questions, build a cart, preview, modify as needed, and confirm—exactly like talking to a helpful clerk, but online.

---

## Future Work (Roadmap)

- Multi‑item edits in one turn: allow “change cheesecake to 2 and pickup to 6 pm” in a single message with safe validation.
- Delivery address validation and maps: verify addresses and estimate delivery windows.
- Promotions and discounts: coupon codes, time‑based promos, and bundle pricing.
- Real‑time stock: live updates when multiple customers order the same item.
- Payment integrations: card/UPI flows with secure tokens and receipts by email/SMS.
- User accounts and order history: repeat orders, favorites, and loyalty points.
- Better recommendations: “people also buy” suggestions powered by browsing and purchase patterns.
- Admin dashboard: view orders, edit inventory, and adjust hours from a web UI.
- Observability: dashboards for errors, latency, and popular items/queries.
- Internationalization: support multiple languages, currencies, and tax rules.

---

## Quickstart (Backend)

1. Create and activate venv
   - Linux/macOS:
     - `python3 -m venv venv`
     - `source venv/bin/activate`
   - Windows (PowerShell):
     - `py -3 -m venv venv`
     - `venv\\Scripts\\Activate.ps1`

2. Install dependencies
   - `pip install -r backend/requirements.txt`

3. Prepare data and DB
   - `python backend/scripts/ingest_data.py` (build indices, load menu)
   - Or run: `python backend/data/populate_db.py`

4. Start API server (FastAPI + Uvicorn)
   - `uvicorn backend.app.main:app --reload`
   - API docs: http://127.0.0.1:8000/docs

5. Try endpoints
   - POST `/query` with JSON body `{ "session_id": "<uuid>", "message": "hi" }`

---

## Environment Configuration

Supported (optional) environment variables:
- `GEMINI_API_KEY`          – LLM generation provider key
- `EMBED_MODEL`           – embedding model name (defaults in `config.py`)
- `DB_URL`                – database URL (defaults to SQLite in `backend/data/bakery.db`)
- `LOG_LEVEL`             – logging level (INFO/DEBUG)
- `REDIS_URL`             – for session persistence (optional)

Set via shell or a `.env` file at project root. `config.py` reads these with safe fallbacks.

---

## Data & Index Lifecycle

- Update raw data in `backend/data/raw/`
- Rebuild indices: `python backend/scripts/ingest_data.py`
- Regenerate DB if schema/menu changes: `python backend/data/populate_db.py`

Processed artifacts:
- `backend/data/processed/chunks.json`
- `backend/data/processed/faiss_index.bin`
- `backend/data/processed/whoosh_index/`

---

## Testing & Diagnostics

- Run unit/e2e tests:
  - `pytest -q` or `python tests/run_tests.py`
- Ad‑hoc agent tests:
  - `python backend/scripts/test_agents.py`
- DB sanity:
  - `python check_database.py`

Troubleshooting tips:
- Inventory not decrementing after confirm → ensure commit happens in `OrderAgent._finalize_order` and product instances are session-managed.
- “modify” shows preview instead of asking → verify Phase 1 short‑circuit respects `response_type == "modify_cart"` flow.
- Indentation errors → check recent edits around return blocks and conditional nesting.

---

## Frontend (Minimal)

A simple chat UI exists under `frontend/`. To serve locally:
- `cd frontend && npm install && npm start` (if a dev server is configured), or open `frontend/public/chat.html` directly for a basic UI.

---

## Versioning & Branching

Feature/version branches follow the pattern:
`Added_general_info_agent_product_info_agent_order_agent_vX.Y_pipeline`

Create and push:
```
git checkout -b <branch>
git commit -m "<message>"
git push -u origin <branch>
```

Open a PR using the link printed by `git push` (GitHub).

