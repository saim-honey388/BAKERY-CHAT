#!/usr/bin/env python3
"""
True Dual-API System for Enhanced Memory Management.

This implements the exact strategy from plan/01_25_am_aug_30_readme.md:
- API Key 1 (Enhanced): Context extraction, feature analysis, rule-based analysis
- API Key 2 (Primary): Response generation with memory context
"""

import json
import requests
from typing import Dict, List, Any, Optional
from .config import Config
import time

class EnhancedAPIClient:
    """Enhanced API Client for context extraction and memory analysis."""
    
    def __init__(self, api_key: str = None):
        """Initialize Enhanced API client.

        Supports providers:
        - groq (default): uses OpenAI-compatible chat completions
        - gemini: uses Google Generative Language API (Gemini)
        """
        provider = Config.ENHANCED_PROVIDER
        self.provider = provider
        if provider == "gemini":
            # Prefer Gemini if configured, else fall back to Groq transparently
            self.api_key = api_key or Config.GEMINI_API_KEY
            if not self.api_key:
                print("Enhanced API init: Gemini API key missing. Falling back to Groq Enhanced API.")
                self.provider = "groq"
                self.api_key = Config.ENHANCED_GROQ_API_KEY or Config.GROQ_API_KEY
                self.model = "llama-3.1-8b-instant"
                self.api_base_url = "https://api.groq.com/openai/v1/chat/completions"
            else:
                self.model = Config.GEMINI_MODEL
                self.api_base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            print(f"[ENHANCED_PROVIDER] {self.provider} model={self.model}")
        else:
            self.api_key = api_key or Config.ENHANCED_GROQ_API_KEY or Config.GROQ_API_KEY
            self.model = "llama-3.1-8b-instant"
            self.api_base_url = "https://api.groq.com/openai/v1/chat/completions"
            print(f"[ENHANCED_PROVIDER] groq model={self.model}")
        
        if not self.api_key:
            raise ValueError("Enhanced API key is required")
    
    def extract_memory_context(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> Dict[str, Any]:
        """
        Extract comprehensive memory context using Enhanced API.
        
        Args:
            conversation: List of conversation messages
            cart_state: Current cart state information
            current_query: User's current query
            
        Returns:
            Structured memory context with extracted information
        """
        prompt = self._build_enhanced_prompt(conversation, cart_state, current_query)
        
        try:
            response = self._call_enhanced_api(prompt)
            print(f"DEBUG: Raw Enhanced API response: {response}")
            parsed = self._parse_enhanced_response(response)
            print(f"DEBUG: Parsed response: {parsed}")
            return parsed
        except Exception as e:
            print(f"Enhanced API context extraction failed: {e}")
            # Fallback to basic extraction
            return self._fallback_extraction(conversation, cart_state, current_query)
    
    def _build_enhanced_prompt(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> str:
        """Build enhanced prompt for context extraction."""
        return f"""
        You are an advanced AI analyzing a bakery chatbot conversation for memory context extraction.
        
        Conversation History (Last 10 messages):
        {self._format_conversation(conversation)}
        
        Current Cart State:
        {json.dumps(cart_state, indent=2)}
        
        Current User Query:
        {current_query}
        
        Your task is to extract structured information for the chatbot's memory system.
        
        CRITICAL: You MUST respond with ONLY valid JSON. No other text, no comments.
        
        Analyze the conversation and provide this exact JSON structure:
        {{
            "summary": "Brief summary capturing user preferences, habits, and key conversation points",
            "last_10_messages": ["message1", "message2", ...],
            "cart_state": {{
                "items": ["item1", "item2"],
                "total": "total_amount",
                "status": "cart_status",
                "customer_info": "customer_details",
                "fulfillment_info": "pickup_delivery_details"
            }},
            "important_features": [
                "feature1 (e.g., user prefers chocolate desserts)",
                "feature2 (e.g., user orders pickup frequently)",
                "feature3 (e.g., user likes coffee with desserts)",
                "feature4 (e.g., user prefers downtown branch)",
                "feature5 (e.g., user orders for multiple people)"
            ]
        }}
        
        Guidelines:
        - Extract user preferences, habits, and behavioral patterns
        - Capture cart state accurately
        - Focus on features that help with future interactions
        - Be comprehensive but concise
        - RESPOND WITH ONLY THE JSON, NO OTHER TEXT, NO COMMENTS
        """
    
    def _format_conversation(self, conversation: List[Dict]) -> str:
        """Format conversation for the prompt."""
        formatted = []
        for msg in conversation[-10:]:  # Last 10 messages
            role = msg.get('role', 'unknown')
            message = msg.get('message', '')
            formatted.append(f"{role}: {message}")
        return "\n".join(formatted)
    
    def _call_enhanced_api(self, prompt: str) -> str:
        """Call Enhanced API for context extraction for the active provider."""
        if self.provider == "gemini":
            # Gemini generateContent API
            params = {"key": self.api_key}
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {"parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1000
                }
            }
            try:
                print("DEBUG: Calling Gemini API for context extraction...")
                resp = requests.post(self.api_base_url, params=params, headers=headers, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                # Extract text from candidates
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return text
            except Exception as e:
                print(f"Enhanced API (Gemini) call failed: {e}. Attempting Groq fallback...")
                # Fallback to Groq if available
                groq_key = Config.ENHANCED_GROQ_API_KEY or Config.GROQ_API_KEY
                if groq_key:
                    try:
                        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                        payload = {
                            "model": "llama-3.1-8b-instant",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "max_tokens": 1000,
                            "stop": ["\nUser:", "\n\n"]
                        }
                        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                        resp.raise_for_status()
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
                    except Exception as e2:
                        print(f"Enhanced API Groq fallback failed: {e2}")
                        raise e
                else:
                    raise e
        else:
            # Groq-compatible
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1000,
                "stop": ["\nUser:", "\n\n"]
            }
            try:
                print("DEBUG: Calling Enhanced API for context extraction (Groq)...")
                response = requests.post(self.api_base_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Enhanced API (Groq) call failed: {e}")
                raise e
    
    def _parse_enhanced_response(self, response: str) -> Dict[str, Any]:
        """Parse Enhanced API response."""
        import re
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                print(f"DEBUG: Parsed JSON response: {parsed}")
                return parsed
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            print(f"Raw response: {response}")
        
        # Fallback parsing
        return {
            "summary": "Enhanced context extraction completed",
            "last_10_messages": [],
            "cart_state": {},
            "important_features": [],
            "rule_base": []
        }
    
    def _fallback_extraction(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> Dict[str, Any]:
        """Fallback extraction when Enhanced API fails."""
        return {
            "summary": "Fallback context extraction",
            "last_10_messages": [msg.get("message", "") for msg in conversation[-10:]],
            "cart_state": cart_state,
            "important_features": [],
            "rule_base": ["business_hours_validation", "stock_validation"]
        }

class PrimaryAPIClient:
    """Primary API Client for response generation."""
    
    def __init__(self, api_key: str = None):
        """Initialize Primary API client."""
        self.api_key = api_key or Config.GROQ_API_KEY
        # Use configured Groq model to avoid 400 model_not_found
        self.model = Config.GROQ_LLM_MODEL
        self.api_base_url = "https://api.groq.com/openai/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("Primary API key is required")
    
    def generate_response(self, prompt: str) -> str:
        """Generate response using Primary API."""
        try:
            response = self._call_primary_api(prompt)
            return response
        except Exception as e:
            print(f"Primary API response generation failed: {e}")
            return self._fallback_response(prompt)
    
    def _call_primary_api(self, prompt: str) -> str:
        """Call Primary API for response generation."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,  # Higher temperature for creative responses
            "max_tokens": 500,
            "stop": ["\nUser:", "\n\n"]
        }
        
        # Simple retry with backoff for rate limits and transient errors
        max_retries = 3
        backoff = 2.0
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"DEBUG: Calling Primary API for response generation (attempt {attempt})...")
                response = requests.post(
                    self.api_base_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                if response.status_code == 429:
                    # Rate limited: observe Retry-After if present
                    retry_after = float(response.headers.get('Retry-After', backoff))
                    print(f"DEBUG: Rate limited. Sleeping for {retry_after}s before retry...")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                data = response.json()
                print(f"DEBUG: Primary API response received successfully")
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                print(f"Primary API call failed on attempt {attempt}: {e}")
                if attempt < max_retries:
                    sleep_s = backoff * attempt
                    print(f"DEBUG: Backing off for {sleep_s}s before retry...")
                    time.sleep(sleep_s)
                else:
                    print("DEBUG: Exhausted retries for Primary API")
        # After retries exhausted
        raise last_err if last_err else RuntimeError("Primary API call failed without exception")
    
    def _fallback_response(self, prompt: str) -> str:
        """Fallback response when Primary API fails."""
        return "I'm here to help with your bakery needs. How can I assist you today?"

class DualAPISystem:
    """Main dual-API system orchestrator."""
    
    def __init__(self, enhanced_api_key: str = None, primary_api_key: str = None):
        """Initialize dual-API system."""
        # Get API keys from environment variables
        from .config import Config
        self.enhanced_client = EnhancedAPIClient(enhanced_api_key or Config.ENHANCED_GROQ_API_KEY)
        self.primary_client = PrimaryAPIClient(primary_api_key or Config.GROQ_API_KEY)
        
        # Memory weight hierarchy as per plan
        self.memory_weights = {
            "cart_state": 100,      # Highest priority
            "last_10_messages": 80, # High priority
            "important_features": 60, # Medium priority
            "summary": 40           # Lower priority
        }
    
    def extract_context_with_enhanced_api(self, conversation: List[Dict], cart_state: Dict, current_query: str) -> Dict[str, Any]:
        """Extract context using Enhanced API."""
        return self.enhanced_client.extract_memory_context(conversation, cart_state, current_query)
    
    def generate_response_with_primary_api(self, prompt: str) -> str:
        """Generate response using Primary API."""
        return self.primary_client.generate_response(prompt)
    
    def calculate_memory_weights(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Calculate memory weights based on importance."""
        weights = {}
        
        for key, base_weight in self.memory_weights.items():
            if key in context:
                # Adjust weight based on content richness
                content = context[key]
                if isinstance(content, list):
                    richness_factor = min(len(content) / 5, 1.0)
                elif isinstance(content, dict):
                    richness_factor = min(len(content) / 3, 1.0)
                else:
                    richness_factor = 0.5
                
                weights[key] = base_weight * richness_factor
        
        return weights
    
    def route_to_appropriate_api(self, task_type: str, complexity: str) -> str:
        """Route tasks to appropriate API based on complexity."""
        if task_type == "context_extraction" or complexity == "high":
            return "enhanced"
        else:
            return "primary"

def main():
    """Test the dual-API system."""
    try:
        print("🧠 Testing Dual-API System")
        print("=" * 50)
        
        # Initialize dual-API system
        dual_api = DualAPISystem()
        print("✅ Dual-API system initialized")
        
        # Test context extraction
        test_conversation = [
            {"role": "user", "message": "I want a chocolate cake"},
            {"role": "assistant", "message": "Great choice! How many would you like?"},
            {"role": "user", "message": "2 please, and a coffee"}
        ]
        
        test_cart_state = {"items": [], "total": 0}
        test_query = "What's in my cart?"
        
        print("\n🔍 Testing Enhanced API Context Extraction...")
        context = dual_api.extract_context_with_enhanced_api(test_conversation, test_cart_state, test_query)
        print(f"Context extracted: {len(context.get('important_features', []))} features")
        
        # Test memory weights
        weights = dual_api.calculate_memory_weights(context)
        print(f"Memory weights: {weights}")
        
        # Test API routing
        route = dual_api.route_to_appropriate_api("context_extraction", "high")
        print(f"API routing: {route}")
        
        print("\n✅ Dual-API system test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()
