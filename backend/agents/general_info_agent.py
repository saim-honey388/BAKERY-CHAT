"""General Info Agent: uses RAG pipeline to answer FAQs and location/hours questions.

This is a minimal implementation returning canned replies for common queries.
"""
from .base_agent import BaseAgent
from typing import Dict, Any
from ..schemas.io_models import Citation
import json

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
                
                # Use LLM to analyze the query and retrieved information
                prompt = f"""
                You are a bakery information assistant. Analyze the user's query and provide a comprehensive answer using the retrieved information.
                
                User Query: "{query}"
                
                Memory Context: {memory_context if memory_context else "None"}
                
                Retrieved Information:
                {chr(10).join([f"Document {i+1}: {doc['text']}" for i, doc in enumerate(retrieved_docs)])}
                
                Your task is to:
                1. Understand what the user is asking about (hours, location, delivery, services, etc.)
                2. Provide accurate information from the retrieved documents
                3. Use memory context to personalize the response
                4. Format the response naturally and helpfully
                
                Return JSON with:
                {{
                    "facts": {{
                        "query_type": "what user is asking about",
                        "relevant_info": "key information from documents",
                        "personalized_note": "using memory context if available"
                    }},
                    "citations": [
                        {{
                            "source": "document source",
                            "snippet": "relevant text snippet"
                        }}
                    ],
                    "response": "natural, helpful response to user"
                }}
                """
                
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
            import os
            data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
            
            # Check what the user is asking about
            q = query.lower()
            
            if "hours" in q or "open" in q or "close" in q:
                # Read hours from general_info.txt
                info_file = os.path.join(data_path, 'general_info.txt')
                if os.path.exists(info_file):
                    with open(info_file, 'r') as f:
                        content = f.read()
                    facts = {"hours": "Retrieved from data files", "content": content}
                    cites = [Citation(source="general_info.txt", snippet="Hours information from data files")]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
            
            elif "location" in q or "where" in q or "branch" in q:
                # Read locations from locations.json
                locations_file = os.path.join(data_path, 'locations.json')
                if os.path.exists(locations_file):
                    with open(locations_file, 'r') as f:
                        locations = json.load(f)
                    facts = {"locations": locations}
                    cites = [Citation(source="locations.json", snippet="Location information from data files")]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
            
            elif "delivery" in q or "deliver" in q:
                # Read delivery info from general_info.txt
                info_file = os.path.join(data_path, 'general_info.txt')
                if os.path.exists(info_file):
                    with open(info_file, 'r') as f:
                        content = f.read()
                    facts = {"delivery": "Retrieved from data files", "content": content}
                    cites = [Citation(source="general_info.txt", snippet="Delivery information from data files")]
                    return self._ok(intent="general_info", facts=facts, context_docs=[], citations=cites)
                    
        except Exception as e:
            print(f"Fallback data reading failed: {e}")
        
        # Ultimate fallback
        return self._ok(intent="general_info", facts={"note": "Unable to retrieve information; please try rephrasing your question"}, context_docs=[], citations=[])
