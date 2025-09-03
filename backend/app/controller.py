"""Controller / Orchestrator to route queries to agents and manage NLU.

This is an initial implementation that uses rule-based NLU and agents stubs.
"""
import json
from typing import Dict, Any, List
from ..nlu.rules import rule_based_intents
from ..nlu.llm_router import llm_route
from ..nlu.entity_extractor import EntityExtractor
from ..agents.general_info_agent import GeneralInfoAgent
from ..agents.product_info_agent import ProductInfoAgent
from ..agents.order_agent import OrderAgent
from ..agents.meta_agent import MetaAgent
from .session import SessionManager
from ..schemas.io_models import AgentResult
from .prompt_builder import PromptBuilder

AGENT_MAP = {
    "general_info": GeneralInfoAgent(),
    "product_info": ProductInfoAgent(),
    "order": OrderAgent(),
    "meta": MetaAgent(),
}

class Controller:
    def __init__(self):
        self.intent_model = None
        # instantiate a small rule-based extractor for test/production routing
        self.entity_extractor = EntityExtractor()
        self.session_manager = SessionManager()
        self.builder = PromptBuilder()

    def _format_facts_text(self, results: List[AgentResult]) -> str:
        """Create a simple readable text representation of agent facts for test mode."""
        blocks = []
        for r in results:
            blocks.append(f"[{r.agent}] {r.facts}")
        return "\n\n".join(blocks)

    def handle_query(self, session_id: str, query: str, skip_llm: bool = False) -> Dict[str, Any]:
        print("\n" + "="*50)
        print(f"[WORKFLOW] 1. Controller received query: '{query}'")
        # save user message
        self.session_manager.add_message(session_id, "user", query)

        # NEW: Extract memory context using Enhanced API for complex query understanding
        print("[WORKFLOW] 1a. Extracting memory context from complex query...")
        memory_context = self.session_manager.extract_memory_context(session_id, query)
        print(f"[WORKFLOW] 1b. Memory context extracted: {len(memory_context.get('important_features', []))} features")
        print(f"[WORKFLOW] 1c. Cart info extracted: {memory_context.get('cart_state', {})}")

        # routing: rules first
        print("[WORKFLOW] 2. Detecting intent...")
        intents = rule_based_intents(query)
        print(f"[WORKFLOW] 2a. Rule-based intents detected: {intents}")
        if not intents:
            print("[WORKFLOW] 2b. No rule-based intent found, trying LLM router...")
            routed = llm_route(query)
            intents = routed.get("intents", ["general_info"]) if isinstance(routed, dict) else ["general_info"]
            print(f"[WORKFLOW] 2c. LLM router intents: {intents}")
        # Bias routing to order agent if an order flow is in progress OR if user is making ordering requests
        try:
            order_agent: OrderAgent = AGENT_MAP.get("order")  # type: ignore
            cart_state = order_agent.get_cart_state(session_id) if hasattr(order_agent, "get_cart_state") else {"has_cart": False}
            
            # Check if we're in an active order flow
            in_order_flow = (cart_state.get("awaiting_fulfillment") or
                           cart_state.get("awaiting_details") or
                           cart_state.get("awaiting_confirmation") or
                           cart_state.get("has_cart"))
            
            # Check if this looks like an ordering query
            ordering_keywords = ["want", "order", "get", "take", "add", "cart", "pickup", "delivery", "2", "two"]
            looks_like_order = any(keyword in query.lower() for keyword in ordering_keywords)
            
            # Route to order agent if in order flow OR if it looks like an ordering request
            if in_order_flow or looks_like_order:
                if "order" not in intents:
                    intents = ["order"] + [i for i in intents if i != "order"]
                    print(f"[WORKFLOW] 2d. Biased routing to order agent. In order flow: {in_order_flow}, Looks like order: {looks_like_order}")
        except Exception:
            pass
        print(f"[WORKFLOW] 2b. Intent(s) detected: {intents}")

        # extract entities once and pass them into agents via the conversation list
        print("[WORKFLOW] 3. Extracting entities...")
        extracted = self.entity_extractor.extract(query) if self.entity_extractor else {}
        print(f"[WORKFLOW] 3a. Entities extracted: {extracted}")

        # NEW: Distribute memory context to agents based on intent
        print("[WORKFLOW] 3b. Distributing memory context to agents...")
        agent_memory = self._distribute_memory_to_agents(memory_context, intents)

        # call agents
        print("[WORKFLOW] 4. Dispatching to agent(s)...")
        results: List[AgentResult] = []
        # If we're in an active order flow, only dispatch the order agent for this turn
        if 'order' in intents and any([
            cart_state.get('awaiting_fulfillment'),
            cart_state.get('awaiting_details'),
            cart_state.get('awaiting_confirmation'),
            cart_state.get('has_cart')
        ]):
            intents = ['order']

        for intent in intents:
            agent = AGENT_MAP.get(intent)
            if not agent:
                print(f"[ERROR] Agent '{intent}' not found in AGENT_MAP: {list(AGENT_MAP.keys())}")
                continue
            # obtain conversation context and append an 'nlu' message containing extracted entities
            session_ctx = list(self.session_manager.get_conversation_context(session_id))
            # append a non-persistent local marker so agents can read entities from the last message
            session_with_entities = session_ctx + [{"role": "nlu", "message": extracted}]
            
            # NEW: Pass memory context to agent
            agent_memory_context = agent_memory.get(intent, {})
            print(f"[WORKFLOW] 4a. Calling agent: '{agent.name}' for intent '{intent}' with memory context")
            res = agent.handle(session_id, query, session=session_with_entities, memory_context=agent_memory_context)
            results.append(res)
            print(f"[WORKFLOW] 4b. Agent '{agent.name}' returned facts: {res.facts}")

        if not results:
            results = [AGENT_MAP["general_info"].handle(session_id, query, session=self.session_manager.get_conversation_context(session_id))]

        # If any agent returned a receipt_text, prefer returning it directly (bypass LLM prose)
        for r in results:
            rt = r.facts.get("receipt_text") if isinstance(r.facts, dict) else None
            if rt:
                self.session_manager.add_message(session_id, "assistant", rt)
                citations = []
                for rr in results:
                    for c in getattr(rr, "citations", []):
                        citations.append({"source": c.source, "snippet": c.snippet})
                
                # Print order details and database status
                self._print_order_status_and_db(session_id, results)
                
                return {"response": rt, "citations": citations, "intents": intents}

        # If we're in order context (collecting details), return agent response directly
        for r in results:
            if isinstance(r.facts, dict) and r.facts.get("in_order_context"):
                # Get the note/message from the agent result
                response_text = r.facts.get("note", "I need more details for your order.")
                # If there is a receipt preview, append it below the note
                if r.facts.get("preview_receipt_text"):
                    response_text = f"{response_text}\n\n{r.facts.get('preview_receipt_text')}"
                self.session_manager.add_message(session_id, "assistant", response_text)
                citations = []
                for rr in results:
                    for c in getattr(rr, "citations", []):
                        citations.append({"source": c.source, "snippet": c.snippet})
                
                # Print order details and database status
                self._print_order_status_and_db(session_id, results)
                
                return {"response": response_text, "citations": citations, "intents": intents}

        # If skip_llm/test mode: return merged facts and citations without calling the LLM
        if skip_llm:
            # build readable facts block and collect citations
            facts_text = self._format_facts_text(results)
            citations = []
            for r in results:
                for c in getattr(r, "citations", []):
                    citations.append({"source": c.source, "snippet": c.snippet})

            # save assistant message as the facts text for record
            self.session_manager.add_message(session_id, "assistant", facts_text)

            # Print order details and database status
            self._print_order_status_and_db(session_id, results)

            return {"response": facts_text, "citations": citations, "intents": intents}

        # regular flow: merge facts into FACTS blocks and call LLM
        facts_blocks = []
        merged_context_docs = []
        for r in results:
            facts_blocks.append(f"[{r.agent}] {r.facts}")
            merged_context_docs.extend(getattr(r, "context_docs", []))
        
        # NEW: Use your existing prompt_builder.py with enhanced memory context
        print("[WORKFLOW] 5. Building prompt with existing prompt_builder.py + memory context...")
        from .prompt_builder import PromptBuilder
        prompt_builder = PromptBuilder()
        
        # Build prompt using your existing system + memory context
        prompt = prompt_builder.build_prompt(
            query=query,
            context_docs=merged_context_docs,
            conversation_history=self._format_conversation_for_prompt(session_id),
            intents=intents
        )
        
        # ENHANCE the prompt with memory context (don't replace, enhance!)
        enhanced_prompt = self._enhance_prompt_with_memory(prompt, memory_context, facts_blocks)

        conversation_history = "\n".join([f"{m['role']}: {m['message']}" for m in self.session_manager.get_conversation_context(session_id)])

        print("[WORKFLOW] 5. Building prompt...")
        # Build enhanced conversation history with FACTS, KNOWN_DETAILS and MISSING_DETAILS
        # Extract KNOWN/MISSING details if order agent is active
        known_details_text = ""
        missing_details_text = ""
        cart_info_text = ""
        try:
            order_agent: OrderAgent = AGENT_MAP.get("order")  # type: ignore
            cart = order_agent.carts.get(session_id) if order_agent else None
            if cart:
                # Include detailed cart information
                cart_items_text = ""
                if cart.items:
                    cart_items = []
                    for item in cart.items:
                        cart_items.append(f"{item['quantity']}x {item['product'].name} @ ${item['product'].price}")
                    cart_items_text = "\n".join(cart_items)
                else:
                    cart_items_text = "No items in cart"
                
                # Include all cart state information
                cart_info_text = f"\nCART_STATE:\nItems: {cart_items_text}\nTotal: ${cart.get_total():.2f}\nCart Items Count: {len(cart.items)}"
                
                # Include detailed customer and order information
                customer_info = {
                    "name": cart.customer_info.get("name"),
                    "phone": cart.customer_info.get("phone_number"),
                }
                
                fulfillment_info = {
                    "type": cart.fulfillment_type,
                    "branch": cart.branch_name,
                    "payment_method": cart.payment_method,
                }
                
                # Include pickup/delivery specific details
                if cart.fulfillment_type == 'pickup':
                    fulfillment_info["pickup_time"] = cart.pickup_info.get("pickup_time")
                elif cart.fulfillment_type == 'delivery':
                    fulfillment_info["delivery_address"] = cart.delivery_info.get("address")
                    fulfillment_info["delivery_time"] = cart.delivery_info.get("delivery_time")
                
                # Include order state
                order_state = {
                    "awaiting_fulfillment": cart.awaiting_fulfillment,
                    "awaiting_details": cart.awaiting_details,
                    "awaiting_confirmation": cart.awaiting_confirmation,
                }
                
                cart_info_text += f"\nCUSTOMER_INFO: {customer_info}"
                cart_info_text += f"\nFULFILLMENT_INFO: {fulfillment_info}"
                cart_info_text += f"\nORDER_STATE: {order_state}"
                
                known_details = {
                    "name": cart.customer_info.get("name"),
                    "phone": cart.customer_info.get("phone_number"),
                    "fulfillment": cart.fulfillment_type,
                    "branch": cart.branch_name,
                    "payment": cart.payment_method,
                }
                missing = order_agent._get_missing_details(cart) if hasattr(order_agent, '_get_missing_details') else []
                known_details_text = "\nKNOWN_DETAILS: " + str(known_details)
                missing_details_text = "\nMISSING_DETAILS: " + ", ".join(missing)
        except Exception:
            pass

        conv_with_facts = conversation_history + "\n\nFACTS:\n" + "\n".join(facts_blocks) + cart_info_text + known_details_text + missing_details_text

        # Debug: Show what cart information is being included
        print(f"DEBUG: Cart info being included in LLM context:")
        print(f"  Cart info text: {cart_info_text}")
        print(f"  Known details: {known_details_text}")
        print(f"  Missing details: {missing_details_text}")

        prompt = self.builder.build_prompt(
            query=query,
            context_docs=merged_context_docs,
            conversation_history=conv_with_facts,
            intents=intents,
        )

        print("[WORKFLOW] 6. Generating final response with LLM...")
        try:
            final_text = self.builder.llm_generate(prompt)
            print(f"[WORKFLOW] 6a. LLM generation successful: {type(final_text)}")
        except Exception as e:
            print(f"[ERROR] LLM generation failed: {e}")
            final_text = "Sorry, I'm having trouble generating a response right now."

        # save assistant response
        # Ensure we save the final text, not the whole object, to history
        response_text = final_text
        if isinstance(final_text, dict) and 'response' in final_text:
            response_text = final_text['response']
        elif not isinstance(final_text, str):
            response_text = str(final_text) # Fallback
        
        try:
            self.session_manager.add_message(session_id, "assistant", response_text)
            print(f"[WORKFLOW] 6b. Message saved to session successfully")
        except Exception as e:
            print(f"[ERROR] Failed to save message to session: {e}")

        # collect citations
        citations = []
        for r in results:
            for c in getattr(r, "citations", []):
                citations.append({"source": c.source, "snippet": c.snippet})

        print(f"[WORKFLOW] 7. Final response generated.")
        
        try:
            # Print order details and database status after every response
            self._print_order_status_and_db(session_id, results)
        except Exception as e:
            print(f"[ERROR] Failed to print order status: {e}")
        
        print("="*50 + "\n")
        
        try:
            return {"response": final_text, "citations": citations, "intents": intents}
        except Exception as e:
            print(f"[ERROR] Failed to return response: {e}")
            return {"response": "An error occurred while processing your request.", "citations": [], "intents": intents}
    
    def _distribute_memory_to_agents(self, memory_context: Dict[str, Any], intents: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Distribute memory context to agents based on intent and importance.
        
        Args:
            memory_context: Full memory context from session manager
            intents: List of detected intents
            
        Returns:
            Dictionary mapping intent to agent-specific memory context
        """
        distribution = {}
        
        for intent in intents:
            if intent == "general_info":
                # General Info Agent: Summary + Last 10 messages + Rule base
                distribution[intent] = {
                    "summary": memory_context.get("summary"),
                    "last_10_messages": memory_context.get("last_10_messages"),
                    "rule_base": memory_context.get("rule_base")
                }
            elif intent == "product_info":
                # Product Info Agent: Summary + Last 10 messages + Important features + Database + Rule base + Cart info
                distribution[intent] = {
                    "summary": memory_context.get("summary"),
                    "last_10_messages": memory_context.get("last_10_messages"),
                    "important_features": memory_context.get("important_features"),
                    "database_info": memory_context.get("database_info"),
                    "rule_base": memory_context.get("rule_base"),
                    "cart_info": memory_context.get("cart_state")
                }
            elif intent == "order":
                # Order Agent: Cart state (1st priority) + Important features + Database (2nd priority) + Summary + Last 10 messages + Rule base
                distribution[intent] = {
                    "cart_state": memory_context.get("cart_state"),  # 1st priority
                    "important_features": memory_context.get("important_features"),
                    "database_info": memory_context.get("database_info"),  # 2nd priority
                    "summary": memory_context.get("summary"),
                    "last_10_messages": memory_context.get("last_10_messages"),
                    "rule_base": memory_context.get("rule_base")
                }
        
        return distribution
    
    def _enhance_prompt_with_memory(self, base_prompt: str, memory_context: Dict[str, Any], facts_blocks: List[str]) -> str:
        """
        Enhance the existing prompt with memory context without replacing your prompt_builder.py rules.
        
        Args:
            base_prompt: The prompt built by your existing prompt_builder.py
            memory_context: Memory context from Enhanced API
            facts_blocks: Agent facts
            
        Returns:
            Enhanced prompt with memory context
        """
        # Add memory context section to your existing prompt
        memory_section = f"""
        
        ========================================
        ENHANCED MEMORY CONTEXT (LLM-Derived)
        ========================================
        
        MEMORY SUMMARY: {memory_context.get('summary', 'No summary available')}
        
        IMPORTANT FEATURES (LLM-Extracted):
        {chr(10).join([f"- {feature}" for feature in memory_context.get('important_features', [])])}
        
        CART STATE FROM MEMORY:
        {json.dumps(memory_context.get('cart_state', {}), indent=2)}
        
        RULE BASE (LLM-Identified):
        {chr(10).join([f"- {rule}" for rule in memory_context.get('rule_base', [])])}
        
        ========================================
        END MEMORY CONTEXT
        ========================================
        
        """
        
        # Insert memory context after your existing prompt rules
        enhanced_prompt = base_prompt + memory_section
        
        return enhanced_prompt
    
    def _format_conversation_for_prompt(self, session_id: str) -> str:
        """Format conversation history for prompt building."""
        conversation = self.session_manager.get_conversation_context(session_id)
        formatted = []
        for msg in conversation[-Config.MAX_CONVERSATION_TURNS:]:  # Last N messages per config
            role = msg.get('role', 'unknown')
            message = msg.get('message', '')
            formatted.append(f"{role}: {message}")
        return "\n".join(formatted)
    
    def _print_order_status_and_db(self, session_id: str, results: List[AgentResult]):
        """Print order details and database status for debugging."""
        try:
            from ..data.database import SessionLocal
            from ..data.models import Product, Order, OrderItem, Customer
        except ImportError as e:
            print(f"[ERROR] Failed to import database modules: {e}")
            return
        
        print("\n" + "="*60)
        print("ORDER STATUS & DATABASE SNAPSHOT")
        print("="*60)
        
        # Check if order agent was involved
        order_agent = AGENT_MAP.get("order")
        if order_agent and hasattr(order_agent, 'carts'):
            cart = order_agent.carts.get(session_id)
            if cart:
                print(f"\n[ORDER DETAILS FOR SESSION: {session_id}]")
                print(f"Cart Items: {len(cart.items)}")
                if cart.items:
                    for item in cart.items:
                        print(f"  - {item['quantity']}x {item['product'].name} @ ${item['product'].price}")
                    print(f"  Total: ${cart.get_total():.2f}")
                
                print(f"\n[COLLECTED DETAILS]")
                print(f"Customer Name: {cart.customer_info.get('name', 'NOT SET')}")
                print(f"Phone Number: {cart.customer_info.get('phone_number', 'NOT SET')}")
                print(f"Fulfillment Type: {cart.fulfillment_type or 'NOT SET'}")
                print(f"Branch: {cart.branch_name or 'NOT SET'}")
                print(f"Payment Method: {cart.payment_method or 'NOT SET'}")
                
                if cart.fulfillment_type == 'pickup':
                    print(f"Pickup Time: {cart.pickup_info.get('pickup_time', 'NOT SET')}")
                elif cart.fulfillment_type == 'delivery':
                    print(f"Delivery Address: {cart.delivery_info.get('address', 'NOT SET')}")
                    print(f"Delivery Time: {cart.delivery_info.get('delivery_time', 'NOT SET')}")
                
                print(f"\n[ORDER STATUS]")
                print(f"Awaiting Fulfillment: {cart.awaiting_fulfillment}")
                print(f"Awaiting Details: {cart.awaiting_details}")
                print(f"Awaiting Confirmation: {cart.awaiting_confirmation}")
                
                # Show missing details
                if hasattr(order_agent, '_get_missing_details'):
                    missing = order_agent._get_missing_details(cart)
                    if missing:
                        print(f"Missing Details: {', '.join(missing)}")
                    else:
                        print("Missing Details: None - Ready for confirmation!")
            else:
                print(f"\n[ORDER DETAILS FOR SESSION: {session_id}]")
                print("No active cart")
        
        # Database status
        # Note: Database status is already printed by _finalize_order method after committing changes
        # This avoids showing stale data from a separate session
        print(f"\n[DATABASE STATUS]")
        print("(Database status shown by _finalize_order method after order completion)")
        
        print("="*60 + "\n")
