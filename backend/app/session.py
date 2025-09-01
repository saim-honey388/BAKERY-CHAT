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
        """Initialize the session manager with Redis connection or fallback to in-memory."""
        self.use_redis = True
        self.memory_sessions = {}  # Fallback in-memory storage
        
        # Enhanced memory tracking
        self.memory_features = {}  # Track important features per session
        self.memory_weights = {
            "cart_state": 100,      # Highest priority
            "last_10_messages": 80, # High priority
            "important_features": 60, # Medium priority
            "summary": 40           # Lower priority
        }
        
        try:
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True
            )
            # Test Redis connection
            self.redis_client.ping()
            print("DEBUG: Using Redis for session storage", flush=True)
        except (redis.ConnectionError, Exception) as e:
            print(f"DEBUG: Redis not available ({e}), using in-memory session storage", flush=True)
            self.use_redis = False
            self.redis_client = None
    
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
        if self.use_redis:
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
        else:
            # In-memory fallback
            if session_id in self.memory_sessions:
                return False
            
            self.memory_sessions[session_id] = {
                "messages": [],
                "summary": "",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            return True
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session data or None if not found
        """
        if self.use_redis:
            session_key = self._get_session_key(session_id)
            session_data = self.redis_client.get(session_key)
            if session_data:
                return json.loads(session_data)
            return None
        else:
            # In-memory fallback
            return self.memory_sessions.get(session_id)
    
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
        # Get current session data
        session_data = self.get_session(session_id)
        if not session_data:
            # Auto-create session if it doesn't exist
            self.create_session(session_id)
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
        
        # Update session
        if self.use_redis:
            session_key = self._get_session_key(session_id)
            self.redis_client.set(session_key, json.dumps(session_data))
        else:
            # In-memory: session_data is already a reference to the stored data
            pass
        
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
    
    def get_conversation_context(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation context as a list of message dictionaries.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of message dictionaries with 'role' and 'message' keys
        """
        print(f"DEBUG: Getting conversation context for session {session_id}", flush=True)
        messages = self.get_recent_messages(session_id, Config.MAX_CONVERSATION_TURNS)
        print(f"DEBUG: Retrieved {len(messages)} recent messages", flush=True)
        
        if not messages:
            print("DEBUG: No messages found, returning empty list", flush=True)
            return []
        
        # Convert to the format expected by agents
        context = []
        for message in messages:
            context.append({
                "role": message["role"],
                "message": message["text"]
            })
        
        print(f"DEBUG: Formatted conversation context, length: {len(context)}", flush=True)
        return context
    
    def update_summary(self, session_id: str, summary: str) -> bool:
        """
        Update the session summary.
        
        Args:
            session_id: Unique session identifier
            summary: New session summary
            
        Returns:
            True if successful, False otherwise
        """
        # Get current session data
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        session_data["summary"] = summary
        session_data["last_updated"] = datetime.now().isoformat()
        
        # Update session
        if self.use_redis:
            session_key = self._get_session_key(session_id)
            self.redis_client.set(session_key, json.dumps(session_data))
        else:
            # In-memory: session_data is already a reference to the stored data
            pass
        
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
        if self.use_redis:
            session_key = self._get_session_key(session_id)
            return bool(self.redis_client.delete(session_key))
        else:
            # In-memory fallback
            if session_id in self.memory_sessions:
                del self.memory_sessions[session_id]
                return True
            return False
    
    def extract_memory_context(self, session_id: str, current_query: str) -> Dict[str, Any]:
        """
        Extract comprehensive memory context using LLM for smart understanding.
        
        Args:
            session_id: Unique session identifier
            current_query: User's current query
            
        Returns:
            Structured memory context with extracted information
        """
        try:
            # Get conversation context
            conversation = self.get_conversation_context(session_id)
            
            # Get cart state from order agent (if available)
            cart_state = self._get_cart_state(session_id)
            
            # Use LLM to extract context (Enhanced API approach)
            context = self._extract_context_with_llm(conversation, cart_state, current_query)
            
            # Cache the extracted context
            self._cache_memory_context(session_id, context)
            
            return context
            
        except Exception as e:
            print(f"Memory context extraction failed: {e}")
            # Fallback to basic context
            return self._fallback_context_extraction(session_id, current_query)
    
    def _extract_context_with_llm(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> Dict[str, Any]:
        """Extract context using Enhanced API for smart understanding."""
        from .dual_api_system import DualAPISystem
        
        try:
            # Use Enhanced API to understand complex user query
            dual_api = DualAPISystem()
            
            # Extract meaning, features, and cart info from complex query
            context = dual_api.extract_context_with_enhanced_api(conversation, cart_state, current_query)
            
            # Calculate memory weights
            weights = dual_api.calculate_memory_weights(context)
            print(f"[MEMORY] Calculated weights: {weights}")
            
            # IMPORTANT: This context will be used by your existing prompt_builder.py
            # We're NOT replacing your system, just enhancing it with memory context
            return context
            
        except Exception as e:
            print(f"Enhanced API context extraction failed: {e}")
            return self._fallback_context_extraction_simple(conversation, cart_state, current_query)
    
    def _build_context_extraction_prompt(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> str:
        """Build prompt for context extraction."""
        return f"""
        Analyze this conversation and extract structured information for a bakery chatbot memory system.
        
        Conversation History:
        {self._format_conversation_for_prompt(conversation)}
        
        Current Cart State:
        {cart_state}
        
        Current Query:
        {current_query}
        
        Extract the following information in JSON format:
        {{
            "summary": "Brief summary of conversation (key points, user preferences, habits)",
            "last_10_messages": ["message1", "message2", ...],
            "cart_state": {{
                "items": ["item1", "item2"],
                "total": "total_amount",
                "status": "cart_status",
                "customer_info": "customer_details",
                "fulfillment_info": "pickup_delivery_details"
            }},
            "important_features": [
                "feature1 (e.g., prefers chocolate desserts)",
                "feature2 (e.g., orders pickup frequently)",
                "feature3 (e.g., likes breakfast items)"
            ],
            "rule_base": [
                "rule1 (e.g., business_hours_validation)",
                "rule2 (e.g., stock_validation)",
                "rule3 (e.g., order_confirmation)"
            ]
        }}
        
        Guidelines:
        - Summary should capture user preferences, habits, and key conversation points
        - Important features should focus on user behavior patterns and preferences
        - Rule base should identify business logic and validation rules needed
        - Cart state should reflect current order status and details
        - Be concise but comprehensive in feature extraction
        """
    
    def _format_conversation_for_prompt(self, conversation: List[Dict]) -> str:
        """Format conversation for the prompt."""
        formatted = []
        for msg in conversation[-10:]:  # Last 10 messages
            role = msg.get('role', 'unknown')
            message = msg.get('message', '')
            formatted.append(f"{role}: {message}")
        return "\n".join(formatted)
    
    def _parse_context_response(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response to extract context."""
        import json
        import re
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Fallback parsing
        return {
            "summary": "Context extraction completed",
            "last_10_messages": [],
            "cart_state": {},
            "important_features": [],
            "rule_base": []
        }
    
    def _get_cart_state(self, session_id: str) -> Dict[str, Any]:
        """Get cart state from order agent if available."""
        try:
            from ..agents.order_agent import OrderAgent
            order_agent = OrderAgent()
            cart = order_agent.carts.get(session_id) if hasattr(order_agent, 'carts') else None
            
            if cart:
                return {
                    "items": [f"{item['quantity']}x {item['product'].name}" for item in cart.items] if cart.items else [],
                    "total": cart.get_total(),
                    "status": "active" if cart.items else "empty",
                    "customer_info": cart.customer_info,
                    "fulfillment_info": {
                        "type": cart.fulfillment_type,
                        "branch": cart.branch_name,
                        "payment_method": cart.payment_method
                    }
                }
        except:
            pass
        
        return {"items": [], "total": 0, "status": "no_cart"}
    
    def _fallback_context_extraction(self, session_id: str, current_query: str) -> Dict[str, Any]:
        """Fallback context extraction when LLM fails."""
        conversation = self.get_conversation_context(session_id)
        cart_state = self._get_cart_state(session_id)
        return self._fallback_context_extraction_simple(conversation, cart_state, current_query)
    
    def _fallback_context_extraction_simple(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> Dict[str, Any]:
        """Fallback context extraction when Enhanced API fails."""
        # Even in fallback, try to use LLM for basic understanding
        try:
            from .generate import GenerationClient
            llm_client = GenerationClient()
            
            # Simple prompt for fallback
            fallback_prompt = f"""
            Analyze this conversation briefly and extract basic context:
            Conversation: {conversation[-5:]}  # Last 5 messages
            Query: {current_query}
            
            Provide a simple JSON with: summary, important_features, rule_base
            """
            
            response = llm_client.generate_answer(fallback_prompt)
            
            # Try to parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "summary": parsed.get("summary", "Fallback context"),
                    "last_10_messages": [msg.get("message", "") for msg in conversation[-10:]],
                    "cart_state": cart_state,
                    "important_features": parsed.get("important_features", []),
                    "rule_base": parsed.get("rule_base", ["business_hours_validation"])
                }
        except:
            pass
        
        # Ultimate fallback - minimal context
        return {
            "summary": "Minimal fallback context",
            "last_10_messages": [msg.get("message", "") for msg in conversation[-10:]],
            "cart_state": cart_state,
            "important_features": [],
            "rule_base": ["business_hours_validation"]
        }
    
    def _cache_memory_context(self, session_id: str, context: Dict[str, Any]):
        """Cache memory context for performance."""
        if session_id not in self.memory_features:
            self.memory_features[session_id] = {}
        
        self.memory_features[session_id] = context
    
    def get_memory_context(self, session_id: str) -> Dict[str, Any]:
        """Get cached memory context if available."""
        return self.memory_features.get(session_id, {})
    
    def calculate_memory_weights(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Calculate memory weights based on importance."""
        weights = {}
        
        for key, base_weight in self.memory_weights.items():
            if key in context:
                # Adjust weight based on content richness
                content = context[key]
                if isinstance(content, list):
                    richness_factor = min(len(content) / 5, 1.0)  # Normalize to 0-1
                elif isinstance(content, dict):
                    richness_factor = min(len(content) / 3, 1.0)
                else:
                    richness_factor = 0.5
                
                weights[key] = base_weight * richness_factor
        
        return weights

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
