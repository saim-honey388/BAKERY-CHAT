"""
BAKERY-CHAT — Complete System Documentation (Deep Dive)
======================================================

This module-style README documents the full architecture, components, data
flows, and operational practices of the BAKERY-CHAT application. It mirrors
the live codebase and can be imported to programmatically inspect metadata
or printed for human consumption.

How to use this file
--------------------
- View in an editor for structured reading.
- Run `python README.py` to print a concise outline.
- Import `README` in tools or scripts to surface sections.

Table of Contents
-----------------
1. System Overview
2. Architecture
3. Backend Components
4. Data & Persistence
5. NLU & Agent Routing
6. Order Flow (Phase 1-first policy)
7. RAG Pipeline
8. Frontend
9. Configuration & Environment
10. Data Lifecycle
11. Testing Strategy
12. Security & PII Handling
13. Observability
14. Deployment & Branching
15. Troubleshooting

"""

from __future__ import annotations

import textwrap


def section(title: str, body: str) -> str:
    return f"\n{title}\n{'-' * len(title)}\n{body.strip()}\n"


SYSTEM_OVERVIEW = section(
    "1. System Overview",
    """
    BAKERY-CHAT is a modular, production-grade chatbot for a bakery business.
    It supports general info, product lookup, and a robust ordering experience
    with cart management and database persistence. The app employs a
    Retrieval-Augmented Generation (RAG) pipeline and an agent-based backend.
    """,
)


ARCHITECTURE = section(
    "2. Architecture",
    """
    - Frontend: Minimal chat UI (static pages) that talks to FastAPI backend.
    - Backend: FastAPI app exposing `/query`, orchestrating NLU + agents.
    - Agents: `general_info`, `product_info`, `order`, `meta`.
    - Data: SQLite database (`bakery.db`) and retrieval indices (FAISS + Whoosh).
    - LLM/RAG: Enhanced context extraction, prompt building, generation, reranking.
    """,
)


BACKEND_COMPONENTS = section(
    "3. Backend Components",
    """
    app/
      - main.py: FastAPI app setup, routes, CORS.
      - controller.py: Intent routing, session handling, prompting, response wiring.
      - config.py: Env-driven configuration (keys, URLs, models).
      - preprocess.py/postprocess.py: Input cleaning and output formatting.
      - generate.py: LLM client; see `dual_api_system.py` (Gemini‑first).
      - retrieval.py/rerank.py/embed.py: RAG stack.

    agents/
      - base_agent.py: Interface/contract for agents.
      - general_info_agent.py: FAQs, hours, locations (RAG + heuristics).
      - product_info_agent.py: Menu, pricing, availability (DB-backed).
      - order_agent.py: Cart, slot filling, modify/confirm/cancel, stock decrement.
      - meta_agent.py: System/meta answers.

    data/
      - models.py/database.py: SQLAlchemy models and session management.
      - menu_store.py: CSV loader + fuzzy search convenience.
      - populate_db.py: Ingest menu into DB.
      - processed/: FAISS + Whoosh indices; chunks.json.
    """,
)


DATA_AND_PERSISTENCE = section(
    "4. Data & Persistence",
    """
    - DB: SQLite via SQLAlchemy; entities: Product, Customer, Order, OrderItem.
    - Stock updates: Applied on order finalization; product instances are re-queried
      into the active session before decrement and committed.
    - Retrieval: Processed indices live under `backend/data/processed/`.
    """,
)


NLU_AND_ROUTING = section(
    "5. NLU & Agent Routing",
    """
    - Rules: `nlu/rules.py` + `intent_model.py` for deterministic intents.
    - LLM Router: Fallback for ambiguous inputs.
    - Controller: Chooses agent; preserves order context for in-progress carts.
    """,
)


ORDER_FLOW = section(
    "6. Order Flow (Phase 1-first modify policy)",
    """
    - Phase 1 handles: ask details, modify_cart, confirm_order, show_receipt.
    - Modify flow:
        1) User says "modify" → show LLM prompt asking what to change.
        2) User specifies field → apply targeted update.
        3) Show preview receipt (updated cart), set awaiting_confirmation.
        4) Loop until confirm/cancel.
    - Confirm flow: Preview-first policy; finalize only on explicit confirm.
    - Cancel flow: When awaiting confirmation, clear cart and end order.
    - Guards: Business hours validation, stock checks, required fields gating.
    """,
)


RAG_PIPELINE = section(
    "7. RAG Pipeline",
    """
    - Retrieval: Hybrid dense/sparse (FAISS + Whoosh) over curated documents.
    - Reranking: Cross-encoder reranks results.
    - Prompt building: Includes session context, cart facts, and citations.
    - Generation: Gemini (preferred). Dual API system separates context extraction
      and response generation, preferring Gemini and falling back only if needed.
    - Postprocess: Cleanup and citation formatting.
    """,
)


FRONTEND = section(
    "8. Frontend",
    """
    - Minimal static UI under `frontend/public/` for testing and demos.
    - Can integrate with a modern SPA as needed.
    """,
)


CONFIG_ENV = section(
    "9. Configuration & Environment",
    """
    - `.env` compatible; keys: GROQ_API_KEY, DB_URL, LOG_LEVEL, REDIS_URL.
    - Sensible defaults defined in `config.py`.
    """,
)


DATA_LIFECYCLE = section(
    "10. Data Lifecycle",
    """
    - Update raw data in `backend/data/raw/`, then re-run ingestion.
    - Rebuild retrieval indices after content updates.
    - Run DB migrations if schema changes (alembic integration ready).
    """,
)


TESTING = section(
    "11. Testing Strategy",
    """
    - Pytest-based unit/integration tests in `/tests` and at repo root.
    - `backend/scripts/test_agents.py` for ad-hoc exercises.
    - E2E flows target: confirm, modify, cancel, and stock decrement.
    """,
)


SECURITY = section(
    "12. Security & PII Handling",
    """
    - `utils/security.py`: PII masking; avoid logging phone numbers in full.
    - API: CORS configured; sanitize user inputs in preprocessing.
    - Keys: Loaded from env; do not commit secrets.
    """,
)


OBSERVABILITY = section(
    "13. Observability",
    """
    - Structured logs via `utils/logger.py` and informative debug prints.
    - Database snapshot printing in critical order paths aids debugging.
    """,
)


DEPLOYMENT = section(
    "14. Deployment & Branching",
    """
    - Run locally via `uvicorn backend.app.main:app --reload`.
    - Version branches: `Added_general_info_agent_product_info_agent_order_agent_vX.Y_pipeline`.
    - PRs via GitHub; CI can run tests and lint.
    """,
)


TROUBLESHOOTING = section(
    "15. Troubleshooting",
    """
    - IndentationError: Check recent blocks with multi-line returns and `elif`.
    - Inventory not decrementing: Ensure product instances are session-bound and committed.
    - Modify shows preview instead of question: Verify Phase 1 respects `modify_cart` logic.
    - 500 on confirm: Inspect `_finalize_order` stock checks and receipt build.
    """,
)


def as_text() -> str:
    return "\n".join(
        [
            SYSTEM_OVERVIEW,
            ARCHITECTURE,
            BACKEND_COMPONENTS,
            DATA_AND_PERSISTENCE,
            NLU_AND_ROUTING,
            ORDER_FLOW,
            RAG_PIPELINE,
            FRONTEND,
            CONFIG_ENV,
            DATA_LIFECYCLE,
            TESTING,
            SECURITY,
            OBSERVABILITY,
            DEPLOYMENT,
            TROUBLESHOOTING,
        ]
    )


def main() -> None:
    print(textwrap.dedent(as_text()))


if __name__ == "__main__":
    main()


