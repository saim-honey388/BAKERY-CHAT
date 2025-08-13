#!/usr/bin/env python3
"""
Postprocessing module for the bakery chatbot.

This module handles response formatting and citation generation.
"""

import re
from typing import Dict, Any, List

class Postprocessor:
    """Postprocesses LLM responses for the bakery chatbot."""
    
    def __init__(self):
        """Initialize the postprocessor."""
        pass
    
    def format_response(self, response: str) -> str:
        """
        Format the LLM response for display.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Formatted response
        """
        # Clean up extra whitespace
        response = re.sub(r'\s+', ' ', response).strip()
        
        # Ensure proper sentence spacing
        response = re.sub(r'([.!?])\s*', r'\1 ', response)
        
        # Remove extra spaces before punctuation
        response = re.sub(r'\s+([,.!?;:])', r'\1', response)
        
        return response
    
    def add_citations(self, response: str, citations: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Add citations to the response.
        
        Args:
            response: Formatted response
            citations: List of citation dictionaries
            
        Returns:
            Dictionary with response and citations
        """
        return {
            "response": response,
            "citations": citations
        }
    
    def process_response(self, response: str, citations: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Process the complete response with formatting and citations.
        
        Args:
            response: Raw LLM response
            citations: List of citation dictionaries
            
        Returns:
            Dictionary with processed response and citations
        """
        print(f"DEBUG: Processing response, length: {len(response)}", flush=True)
        # Format response
        formatted_response = self.format_response(response)
        print(f"DEBUG: Formatted response, length: {len(formatted_response)}", flush=True)
        
        # Add citations
        result = self.add_citations(formatted_response, citations)
        print(f"DEBUG: Added {len(citations)} citations", flush=True)
        
        print(f"DEBUG: Postprocessing complete", flush=True)
        return result

def main():
    """Main function for testing the postprocessor."""
    # Initialize postprocessor
    postprocessor = Postprocessor()
    print("Postprocessor initialized successfully")
    
    # Test data
    raw_response = "We are open Monday through Friday from 8am to 8pm. Weekend hours are 9am to 6pm.  "
    test_citations = [
        {
            "text": "Sunrise Bakery is open Monday through Friday from 8am to 8pm...",
            "source": "hours_info.txt#page_1"
        }
    ]
    
    # Process response
    result = postprocessor.process_response(raw_response, test_citations)
    
    print("\nProcessed response:")
    print(f"Response: {result['response']}")
    print("Citations:")
    for i, citation in enumerate(result['citations'], 1):
        print(f"  {i}. {citation['text']}")
        print(f"     Source: {citation['source']}")

if __name__ == "__main__":
    main()