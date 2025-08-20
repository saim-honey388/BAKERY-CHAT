#!/usr/bin/env python3
"""
Generation module for the bakery chatbot.

This module handles answer generation using the Groq LLM API.
"""

import requests
from typing import Dict, Any
from .config import Config

class GenerationClient:
    """Client for generating answers using Groq LLM API."""
    
    def __init__(self):
        """Initialize the generation client."""
        self.api_key = Config.GROQ_API_KEY
        self.llm_model = Config.GROQ_LLM_MODEL
        self.api_base_url = "https://api.groq.com/openai/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("Groq API key is required")
    
    def generate_answer(self, prompt: str) -> str:
        """
        Generate an answer using the LLM.
        
        Args:
            prompt: Formatted prompt for the LLM
            
        Returns:
            Generated answer text
        """
        print(f"DEBUG: Generating answer with LLM, prompt length: {len(prompt)}", flush=True)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 500,
            "stop": ["\nUser:"]
        }
        
        try:
            print(f"DEBUG: Sending request to Groq API", flush=True)
            response = requests.post(
                self.api_base_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            print(f"DEBUG: Received response from Groq API, status: {response.status_code}", flush=True)
            response.raise_for_status()
            data = response.json()
            print(f"DEBUG: Parsed response JSON", flush=True)
            
            # Extract answer from response
            answer = data["choices"][0]["message"]["content"].strip()
            print(f"[WORKFLOW] 6a. LLM Raw Response:\n{answer}")
            print(f"DEBUG: Extracted answer, length: {len(answer)}", flush=True)
            return answer
            
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Error generating answer: {str(e)}", flush=True)
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