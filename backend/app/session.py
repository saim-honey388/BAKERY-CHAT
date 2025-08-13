#!/usr/bin/env python3
"""
Session management module for the bakery chatbot.

This module handles conversation context storage and retrieval using Redis.
"""

import json
import redis
from typing import Dict, List, Any, Optional
from datetime import datetime
from .config import Config

class SessionManager:
    """Manages user sessions and conversation context."""
    
    def __init__(self):
        """Initialize the session manager with Redis connection."""
        self.redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )
        
        # Test Redis connection
        try:
            self.redis_client.ping()
        except redis.ConnectionError:
            raise ConnectionError("Could not connect to Redis server")
    
    def _get_session_key(self, session_id: str) -> str:
        """
        Generate Redis key for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Redis key for the session
        """
        return f"session:{session_id}"
    
    def create_session(self, session_id: str) -> bool:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session was created, False if it already exists
        """
        session_key = self._get_session_key(session_id)
        
        # Check if session already exists
        if self.redis_client.exists(session_key):
            return False
        
        # Create empty session
        session_data = {
            "messages": [],
            "summary": "",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        self.redis_client.set(session_key, json.dumps(session_data))
        return True
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session data or None if not found
        """
        session_key = self._get_session_key(session_id)
        
        session_data = self.redis_client.get(session_key)
        if session_data:
            return json.loads(session_data)
        return None
    
    def add_message(self, session_id: str, role: str, text: str) -> bool:
        """
        Add a message to the session conversation history.
        
        Args:
            session_id: Unique session identifier
            role: Role of the message sender (user or assistant)
            text: Message text
            
        Returns:
            True if successful, False otherwise
        """
        session_key = self._get_session_key(session_id)
        
        # Get current session data
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        # Add new message
        message = {
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        
        session_data["messages"].append(message)
        session_data["last_updated"] = datetime.now().isoformat()
        
        # Update session in Redis
        self.redis_client.set(session_key, json.dumps(session_data))
        return True
    
    def get_recent_messages(self, session_id: str, max_messages: int = 5) -> List[Dict[str, str]]:
        """
        Get recent messages from the conversation history.
        
        Args:
            session_id: Unique session identifier
            max_messages: Maximum number of recent messages to return
            
        Returns:
            List of recent messages
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return []
        
        # Return the last max_messages messages
        messages = session_data.get("messages", [])
        return messages[-max_messages:] if messages else []
    
    def get_conversation_context(self, session_id: str) -> str:
        """
        Get conversation context as a formatted string.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Formatted conversation context
        """
        print(f"DEBUG: Getting conversation context for session {session_id}", flush=True)
        messages = self.get_recent_messages(session_id, Config.MAX_CONVERSATION_TURNS)
        print(f"DEBUG: Retrieved {len(messages)} recent messages", flush=True)
        
        if not messages:
            print("DEBUG: No messages found, returning empty context", flush=True)
            return ""
        
        context_lines = ["Conversation so far:"]
        for message in messages:
            role = message["role"]
            text = message["text"]
            context_lines.append(f"{role}: {text}")
        
        result = "\n".join(context_lines)
        print(f"DEBUG: Formatted conversation context, length: {len(result)}", flush=True)
        return result
    
    def update_summary(self, session_id: str, summary: str) -> bool:
        """
        Update the session summary.
        
        Args:
            session_id: Unique session identifier
            summary: New session summary
            
        Returns:
            True if successful, False otherwise
        """
        session_key = self._get_session_key(session_id)
        
        # Get current session data
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        session_data["summary"] = summary
        session_data["last_updated"] = datetime.now().isoformat()
        
        # Update session in Redis
        self.redis_client.set(session_key, json.dumps(session_data))
        return True
    
    def get_summary(self, session_id: str) -> str:
        """
        Get session summary.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session summary
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return ""
        
        return session_data.get("summary", "")
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear session data.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if successful, False otherwise
        """
        session_key = self._get_session_key(session_id)
        return bool(self.redis_client.delete(session_key))

def main():
    """Main function for testing the session manager."""
    try:
        session_manager = SessionManager()
        print("Session Manager initialized successfully")
        
        # Test session creation
        session_id = "test_session_123"
        if session_manager.create_session(session_id):
            print(f"Created session: {session_id}")
        else:
            print(f"Session {session_id} already exists")
        
        # Test adding messages
        session_manager.add_message(session_id, "user", "What are your hours?")
        session_manager.add_message(session_id, "assistant", "We are open 8am-8pm Monday through Friday.")
        session_manager.add_message(session_id, "user", "Are you open on weekends?")
        session_manager.add_message(session_id, "assistant", "Yes, we are open 9am-6pm on weekends.")
        
        # Test retrieving context
        context = session_manager.get_conversation_context(session_id)
        print("\nConversation Context:")
        print(context)
        
        # Test summary
        session_manager.update_summary(session_id, "User asked about hours and weekend availability.")
        summary = session_manager.get_summary(session_id)
        print(f"\nSession Summary: {summary}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()