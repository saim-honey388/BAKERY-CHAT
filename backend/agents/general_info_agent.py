"""General Info Agent: uses RAG pipeline to answer FAQs and location/hours questions.

This is a minimal implementation returning canned replies for common queries.
"""
from .base_agent import BaseAgent
from typing import Dict, Any
from ..schemas.io_models import Citation
import json
import os
import csv

class GeneralInfoAgent(BaseAgent):
    name = "general_info"

    def __init__(self):
        pass

    def handle(self, session_id: str, query: str, session: Dict[str, Any] = None, memory_context: Dict[str, Any] = None):
        print(f"[WORKFLOW] Executing GeneralInfoAgent...")
        
        # NEW: Use memory context for enhanced understanding
        if memory_context:
            print(f"[MEMORY] Using memory context: {len(memory_context.get('important_features', []))} features")
            if memory_context.get('summary'):
                print(f"[MEMORY] Summary: {memory_context['summary']}")
        
        # NEW: Use proper RAG retrieval from data files instead of hardcoded info
        try:
            from ..app.retrieval import HybridRetriever
            from ..app.dual_api_system import DualAPISystem
            
            print("[RAG] Retrieving information from data files...")
            
            # Use the existing retrieval system to get relevant information
            retriever = HybridRetriever()
            retrieved_docs = retriever.hybrid_search(query, k=5)
            
            if retrieved_docs:
                print(f"[RAG] Retrieved {len(retrieved_docs)} relevant documents")
                
                # Use prompt_builder.py rules for general_info agent
                from ..app.prompt_builder import PromptBuilder
                prompt_builder = PromptBuilder()
                
                # Build prompt using prompt_builder with general_info rules
                context_docs = [{"text": doc['text'], "source": doc.get('source', 'data_file')} for doc in retrieved_docs]
                conversation_history = f"Memory Context: {memory_context if memory_context else 'None'}"
                
                prompt = prompt_builder.build_prompt(
                    query=query,
                    context_docs=context_docs,
                    conversation_history=conversation_history,
                    intents=["general_info"]
                )
                
                # Add JSON response format instruction
                prompt += "\n\nReturn JSON with:\n{\n    \"facts\": {\n        \"query_type\": \"what user is asking about\",\n        \"relevant_info\": \"key information from documents\",\n        \"personalized_note\": \"using memory context if available\"\n    },\n    \"citations\": [\n        {\n            \"source\": \"document source\",\n            \"snippet\": \"relevant text snippet\"\n        }\n    ],\n    \"response\": \"natural, helpful response to user\"\n}"
                
                dual_api = DualAPISystem()
                response = dual_api.generate_response_with_primary_api(prompt)
                
                # Parse LLM response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    facts = parsed.get("facts", {"note": "RAG-enhanced response"})
                    
                    # Create citations from retrieved documents
                    citations = []
                    for doc in retrieved_docs:
                        citations.append(Citation(
                            source=doc.get('source', 'data_file'),
                            snippet=doc.get('text', '')[:200] + "..." if len(doc.get('text', '')) > 200 else doc.get('text', '')
                        ))
                    
                    return self._ok(intent="general_info", facts=facts, context_docs=retrieved_docs, citations=citations)
            
            else:
                print("[RAG] No relevant documents found, using fallback")
                
        except Exception as e:
            print(f"RAG retrieval failed: {e}")
        
        # Fallback: Use basic information from data files
        try:
            # Read data files directly as fallback
            data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
            
            # Check what the user is asking about
            q = query.lower()
            
            if "menu" in q or "price" in q or "prices" in q:
                # Return the entire menu from menu.csv
                menu_file = os.path.join(data_path, 'menu.csv')
                if os.path.exists(menu_file):
                    items = []
                    try:
                        with open(menu_file, 'r', newline='') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                # Normalize common columns
                                name = row.get('name') or row.get('item') or row.get('Item') or row.get('product')
                                description = row.get('description') or row.get('Description') or row.get('details')
                                price = row.get('price') or row.get('Price') or row.get('cost')
                                category = row.get('category') or row.get('Category')
                                item = {k: v for k, v in {
                                    'name': name,
                                    'description': description,
                                    'price': price,
                                    'category': category,
                                }.items() if v}
                                if item:
                                    items.append(item)
                    except Exception as e:
                        print(f"[RAG FALLBACK] Failed reading menu.csv: {e}")
                    facts = {"menu_items": items, "note": "Complete menu from data/raw/menu.csv"}
                    cites = [Citation(source="menu.csv", snippet="Full menu loaded from data/raw/menu.csv")]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
            
            if "hours" in q or "open" in q or "close" in q or "timing" in q or "time" in q:
                # Read hours from general_info.txt
                info_file = os.path.join(data_path, 'general_info.txt')
                if os.path.exists(info_file):
                    with open(info_file, 'r') as f:
                        content = f.read()
                    facts = {"hours": content}
                    cites = [Citation(source="general_info.txt", snippet=content[:200] + ("..." if len(content) > 200 else ""))]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
            
            elif "location" in q or "where" in q or "branch" in q:
                # Read locations from locations.json
                locations_file = os.path.join(data_path, 'locations.json')
                if os.path.exists(locations_file):
                    with open(locations_file, 'r') as f:
                        locations = json.load(f)
                    facts = {"locations": locations}
                    cites = [Citation(source="locations.json", snippet="Loaded branch locations from data/raw/locations.json")]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
            
            elif "delivery" in q or "deliver" in q:
                # Read delivery info from general_info.txt
                info_file = os.path.join(data_path, 'general_info.txt')
                if os.path.exists(info_file):
                    with open(info_file, 'r') as f:
                        content = f.read()
                    facts = {"delivery": content}
                    cites = [Citation(source="general_info.txt", snippet=content[:200] + ("..." if len(content) > 200 else ""))]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
                    
        except Exception as e:
            print(f"Fallback data reading failed: {e}")
        
        # Ultimate fallback
        return self._ok(intent="general_info", facts={"note": "Unable to retrieve information; please try rephrasing your question"}, context_docs=[], citations=[])
