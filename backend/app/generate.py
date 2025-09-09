#!/usr/bin/env python3
"""
Generation module for the bakery chatbot.

This module handles answer generation using the Gemini LLM API.
"""

import requests
from typing import Dict, Any
from .config import Config

class GenerationClient:
    """Client for generating answers using Gemini LLM API."""
    
    def __init__(self):
        """Initialize the generation client."""
        self.api_key = Config.GEMINI_API_KEY
        self.llm_model = Config.GEMINI_MODEL
        self.api_base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm_model}:generateContent"
        
        if not self.api_key:
            raise ValueError("Gemini API key is required")
    
    def generate_answer(self, prompt: str) -> str:
        """
        Generate an answer using the Gemini LLM.
        
        Args:
            prompt: Formatted prompt for the LLM
            
        Returns:
            Generated answer text
        """
        print(f"DEBUG: Generating answer with Gemini LLM, prompt length: {len(prompt)}", flush=True)
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 500,
                "stopSequences": ["\nUser:"]
            }
        }
        
        try:
            print(f"DEBUG: Sending request to Gemini API", flush=True)
            print(f"DEBUG: Model: {self.llm_model}", flush=True)
            print(f"DEBUG: API Key: {self.api_key[:10]}...", flush=True)
            print(f"DEBUG: Payload: {payload}", flush=True)
            
            response = requests.post(
                f"{self.api_base_url}?key={self.api_key}",
                json=payload,
                timeout=60
            )
            
            print(f"DEBUG: Received response from Gemini API, status: {response.status_code}", flush=True)
            
            if response.status_code != 200:
                print(f"DEBUG: Error response body: {response.text}", flush=True)
                response.raise_for_status()
                
            data = response.json()
            print(f"DEBUG: Parsed response JSON", flush=True)
            print(f"DEBUG: Full response structure: {data}", flush=True)
            
            # Extract answer from Gemini response
            if "candidates" in data and len(data["candidates"]) > 0:
                answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"DEBUG: Unexpected response structure: {data}", flush=True)
                raise KeyError("No candidates found in response")
            print(f"[WORKFLOW] 6a. LLM Raw Response:\n{answer}")
            print(f"DEBUG: Extracted answer, length: {len(answer)}", flush=True)
            return answer
            
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Error generating answer: {str(e)}", flush=True)
            if hasattr(e, 'response') and e.response is not None:
                print(f"DEBUG: Response status: {e.response.status_code}", flush=True)
                print(f"DEBUG: Response body: {e.response.text}", flush=True)
            raise Exception(f"Error generating answer: {str(e)}")
        except (KeyError, IndexError) as e:
            print(f"DEBUG: Error parsing generation response: {str(e)}", flush=True)
            raise Exception(f"Error parsing generation response: {str(e)}")

def main():
    """Main function for testing the generation client."""
    try:
        # Initialize generation client
        gen_client = GenerationClient()
        print("Generation client initialized successfully")
        
        # Test prompt
        test_prompt = """You are Sunrise Bakery's assistant. Your role is to help customers with information about our bakery.

Context:
Document 1 (Source: hours_info.txt):
Sunrise Bakery is open Monday through Friday from 8am to 8pm. Weekend hours are 9am to 6pm.

Conversation so far:
user: Hi there!
assistant: Hello! Welcome to Sunrise Bakery. How can I help you today?

User: What are your hours?
Assistant:"""
        
        print("\nGenerating answer...")
        answer = gen_client.generate_answer(test_prompt)
        
        print("\nGenerated answer:")
        print("-" * 40)
        print(answer)
        print("-" * 40)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()