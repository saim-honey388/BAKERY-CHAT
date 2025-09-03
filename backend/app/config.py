#!/usr/bin/env python3
"""
Configuration management for the bakery chatbot backend.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the application."""
    
    # Groq API Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    ENHANCED_GROQ_API_KEY = os.getenv("ENHANCED_GROQ_API_KEY")
    GROQ_LLM_MODEL = "llama-3.1-8b-instant"

    # Provider Switches (groq|gemini)
    ENHANCED_PROVIDER = os.getenv("ENHANCED_PROVIDER", "gemini").lower()
    PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "gemini").lower()

    # Gemini (Google) API Configuration for Enhanced client
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Default to Gemini 2.0 Flash with fallback to Flash-Lite
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite")

    @classmethod
    def debug_print(cls):
        print(f"[CONFIG] ENHANCED_PROVIDER={cls.ENHANCED_PROVIDER}")
        print(f"[CONFIG] PRIMARY_PROVIDER={cls.PRIMARY_PROVIDER}")
        print(f"[CONFIG] GEMINI_MODEL={cls.GEMINI_MODEL} fallback={cls.GEMINI_FALLBACK_MODEL} set={bool(cls.GEMINI_API_KEY)}")
        print(f"[CONFIG] GROQ_MODEL={cls.GROQ_LLM_MODEL} set={bool(cls.GROQ_API_KEY)}")
    
    # Redis Configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    
    # Application Configuration
    CHUNK_SIZE = 250
    CHUNK_OVERLAP = 50
    MAX_CONTEXT_DOCS = 5
    MAX_CONVERSATION_TURNS = 14
    
    # FAISS Configuration
    FAISS_INDEX_PATH = "data/processed/faiss_index.bin"
    CHUNKS_FILE_PATH = "data/processed/chunks.json"
    
    # Cross-Encoder Configuration
    CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Whoosh Configuration
    WHOOSH_INDEX_PATH = "data/processed/whoosh_index"
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        missing = []
        
        # Allow a 'test' sentinel value to skip enforcing external API keys during local tests
        if not cls.GROQ_API_KEY or cls.GROQ_API_KEY in ("test", "dev"):
            # Do not require GROQ_API_KEY for test/dev runs
            pass
        else:
            if not cls.GROQ_API_KEY:
                missing.append("GROQ_API_KEY")
            if not cls.REDIS_HOST:
                missing.append("REDIS_HOST")
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True

# Validate configuration on import
Config.validate()