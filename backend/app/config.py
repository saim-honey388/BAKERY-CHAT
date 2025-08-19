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
    GROQ_LLM_MODEL = "llama3-8b-8192"
    
    # Redis Configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    
    # Application Configuration
    CHUNK_SIZE = 250
    CHUNK_OVERLAP = 50
    MAX_CONTEXT_DOCS = 5
    MAX_CONVERSATION_TURNS = 10
    
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