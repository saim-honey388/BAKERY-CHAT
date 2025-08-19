#!/usr/bin/env python3
"""
Main FastAPI application for the bakery chatbot.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from fastapi.staticfiles import StaticFiles
import uuid
import os

from .config import Config
from .preprocess import Preprocessor
from .session import SessionManager
from .embed import EmbeddingClient
from .retrieval import HybridRetriever
from .rerank import Reranker
from .prompt_builder import PromptBuilder
from .generate import GenerationClient
from .postprocess import Postprocessor
from .controller import Controller

# Initialize FastAPI app
app = FastAPI(
    title="Bakery Chatbot API",
    description="RAG-based chatbot for bakery information",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
preprocessor = Preprocessor()
session_manager = SessionManager()
# embed_client = EmbeddingClient()  # Not used directly in API
retriever = HybridRetriever()
reranker = Reranker()
prompt_builder = PromptBuilder()
gen_client = GenerationClient()
postprocessor = Postprocessor()
controller = Controller()

class QueryRequest(BaseModel):
    """Request model for chat queries."""
    session_id: str
    query: str

class QueryResponse(BaseModel):
    """Response model for chat queries."""
    session_id: str
    response: str
    citations: List[Dict[str, str]]

class SessionCreateRequest(BaseModel):
    """Request model for session creation."""
    session_id: Optional[str] = None

class SessionCreateResponse(BaseModel):
    """Response model for session creation."""
    session_id: str
    created: bool

@app.get("/")
async def root():
    """Root endpoint."""
    return FileResponse(os.path.join(static_files_path, "chat.html"))

@app.post("/session", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):
    """
    Create a new chat session.
    
    Args:
        request: Session creation request
        
    Returns:
        Session creation response
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Create session
    created = session_manager.create_session(session_id)
    
    return SessionCreateResponse(session_id=session_id, created=created)

@app.post("/query", response_model=QueryResponse)
async def query_chatbot(request: QueryRequest):
    """
    Process a chat query using the Controller orchestration.
    """
    try:
        print(f"DEBUG: Controller handling query for session {request.session_id}: {request.query}", flush=True)
        # Decide whether to call the LLM: prefer explicit USE_LLM env var, else require a non-test GROQ_API_KEY
        use_llm_env = os.getenv("USE_LLM", "false").lower() in ("1", "true", "yes")
        groq_key = Config.GROQ_API_KEY
        has_real_key = bool(groq_key) and groq_key not in ("test", "dev")
        call_llm = use_llm_env or has_real_key
        result = controller.handle_query(request.session_id, request.query, skip_llm=not call_llm)

        response_text = result.get("response", "")
        citations = result.get("citations", [])

        # Add assistant message to session (controller already does this, but keep idempotent)
        try:
            session_manager.add_message(request.session_id, "assistant", response_text)
        except Exception:
            pass

        return QueryResponse(session_id=request.session_id, response=response_text, citations=citations)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Serve static files from frontend/public
static_files_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public")
if os.path.exists(static_files_path):
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)