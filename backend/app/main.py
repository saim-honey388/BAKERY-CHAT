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
    Process a chat query using the RAG pipeline.
    
    Args:
        request: Query request with session ID and query text
        
    Returns:
        Query response with answer and citations
    """
    try:
        # Preprocess query
        print(f"DEBUG: Processing query for session {request.session_id}: {request.query}", flush=True)
        preprocessed = preprocessor.preprocess_query(request.query)
        print(f"DEBUG: Preprocessed query: {preprocessed}", flush=True)
        
        # Add user message to session
        session_manager.add_message(request.session_id, "user", request.query)
        print(f"DEBUG: Added user message to session {request.session_id}", flush=True)
        
        # Retrieve context documents
        print(f"DEBUG: Retrieving context documents for: {preprocessed['preprocessed']}", flush=True)
        retrieved_docs = retriever.hybrid_search(preprocessed["preprocessed"], k=10)
        print(f"DEBUG: Retrieved {len(retrieved_docs)} documents", flush=True)
        
        # Rerank documents
        print(f"DEBUG: Reranking {len(retrieved_docs)} documents", flush=True)
        reranked_docs = reranker.rerank(preprocessed["preprocessed"], retrieved_docs, k=5)
        print(f"DEBUG: Reranked to {len(reranked_docs)} documents", flush=True)
        
        # Get conversation context
        conversation_context = session_manager.get_conversation_context(request.session_id)
        print(f"DEBUG: Conversation context length: {len(conversation_context)}", flush=True)
        
        # Build prompt
        print(f"DEBUG: Building prompt with {len(reranked_docs)} documents", flush=True)
        prompt = prompt_builder.build_prompt(
            preprocessed["preprocessed"],
            reranked_docs,
            conversation_context
        )
        print(f"DEBUG: Prompt built, length: {len(prompt)}", flush=True)
        
        # Generate answer
        print(f"DEBUG: Generating answer with LLM", flush=True)
        answer = gen_client.generate_answer(prompt)
        print(f"DEBUG: Generated answer, length: {len(answer)}", flush=True)
        
        # Format citations
        citations = prompt_builder.format_citations(reranked_docs)
        print(f"DEBUG: Formatted {len(citations)} citations", flush=True)
        
        # Postprocess response
        result = postprocessor.process_response(answer, citations)
        print(f"DEBUG: Postprocessed response", flush=True)
        
        # Add assistant message to session
        session_manager.add_message(request.session_id, "assistant", result["response"])
        print(f"DEBUG: Added assistant message to session {request.session_id}", flush=True)
        
        # Return response
        print(f"DEBUG: Returning response for session {request.session_id}", flush=True)
        return QueryResponse(
            session_id=request.session_id,
            response=result["response"],
            citations=result["citations"]
        )
        
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