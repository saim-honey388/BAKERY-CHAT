#!/usr/bin/env python3
"""
Preprocessing module for the bakery chatbot.

This module handles text normalization, intent detection, and spell correction.
"""

import re
from typing import Dict, Any, Tuple

class Preprocessor:
    """Preprocessor for bakery chatbot queries."""
    
    def __init__(self):
        """Initialize the preprocessor."""
        # Define intent keywords for classification
        self.intent_keywords = {
            "general_info": [
                "hours", "location", "address", "branch", "about", 
                "information", "contact", "phone", "email", "history",
                "story", "founded", "established", "services"
            ],
            "menu": [
                "menu", "item", "product", "food", "drink", "price",
                "cost", "availability", "special", "today", "recommend",
                "bread", "cake", "pastry", "cookie", "muffin", "donut"
            ],
            "order": [
                "order", "place", "buy", "purchase", "delivery", 
                "pickup", "status", "track", "cancel", "change", "when"
            ]
        }
        
        # Common bakery product names for spell correction
        self.bakery_products = {
            "baguette", "croissant", "muffin", "sourdough", "bread",
            "cake", "pastry", "cookie", "donut", "danish",
            "scone", "bagel", "roll", "bun", "loaf", "sandwich",
            "pie", "tart", "brownie", "cupcake", "pretzel"
        }
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize user input text.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove non-informative characters but keep punctuation for intent
        # This removes special characters that don't add meaning
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        return text
    
    def detect_intent(self, text: str) -> str:
        """
        Detect the intent category of a query.
        
        Args:
            text: Normalized query text
            
        Returns:
            Intent category (general_info, menu, order, or unknown)
        """
        # Count matches for each intent category
        intent_scores = {}
        
        for intent, keywords in self.intent_keywords.items():
            score = 0
            for keyword in keywords:
                # Simple keyword matching - in a real implementation, 
                # you might use more sophisticated NLP techniques
                if keyword in text:
                    score += 1
            intent_scores[intent] = score
        
        # Return the intent with the highest score, or "general_info" if all are 0
        if max(intent_scores.values()) > 0:
            return max(intent_scores, key=intent_scores.get)
        else:
            return "general_info"  # Default to general info
    
    def spell_correct_products(self, text: str) -> str:
        """
        Correct spelling of common bakery product names.
        
        Args:
            text: Text to correct
            
        Returns:
            Text with corrected product names
        """
        # Simple spell correction based on edit distance
        # In a real implementation, you might use SymSpell or similar
        corrected_text = text
        
        for product in self.bakery_products:
            # Simple fuzzy matching - replace common misspellings
            # This is a simplified version - a real implementation would be more robust
            patterns = [
                product,  # Correct spelling
                product[:-1] if len(product) > 3 else product,  # Missing last letter
                product + product[-1] if len(product) > 2 else product,  # Double last letter
            ]
            
            for pattern in patterns:
                corrected_text = re.sub(
                    r'\b' + pattern + r'\b', 
                    product, 
                    corrected_text,
                    flags=re.IGNORECASE
                )
        
        return corrected_text
    
    def preprocess_query(self, query: str) -> Dict[str, Any]:
        """
        Preprocess a user query.
        
        Args:
            query: Raw user query
            
        Returns:
            Dictionary with preprocessed query and metadata
        """
        print(f"DEBUG: Preprocessing query: {query}", flush=True)
        # Normalize text
        normalized = self.normalize_text(query)
        print(f"DEBUG: Normalized text: {normalized}", flush=True)
        
        # Detect intent
        intent = self.detect_intent(normalized)
        print(f"DEBUG: Detected intent: {intent}", flush=True)
        
        # Spell correct product names
        corrected = self.spell_correct_products(normalized)
        print(f"DEBUG: Corrected text: {corrected}", flush=True)
        
        result = {
            "original": query,
            "normalized": normalized,
            "corrected": corrected,
            "intent": intent,
            "preprocessed": corrected  # Final preprocessed version
        }
        print(f"DEBUG: Preprocessing complete: {result}", flush=True)
        return result

def main():
    """Main function for testing the preprocessor."""
    preprocessor = Preprocessor()
    
    # Test queries
    test_queries = [
        "What are your hours?",
        "Do you have croissants?",
        "I want to place an order",
        "Where are you located?",
        "How much is a baguette?",
        "Tell me about your bakery"
    ]
    
    print("Testing Preprocessor:")
    print("-" * 40)
    
    for query in test_queries:
        result = preprocessor.preprocess_query(query)
        print(f"Query: {query}")
        print(f"  Normalized: {result['normalized']}")
        print(f"  Intent: {result['intent']}")
        print(f"  Corrected: {result['corrected']}")
        print()

if __name__ == "__main__":
    main()