"""Controller / Orchestrator to route queries to agents and manage NLU.

This is an initial implementation that uses rule-based NLU and agents stubs.
"""
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

        # routing: rules first
        print("[WORKFLOW] 2. Detecting intent...")
        intents = rule_based_intents(query)
        if not intents:
            print("[WORKFLOW] 2a. No rule-based intent found, trying LLM router...")
            routed = llm_route(query)
            intents = routed.get("intents", ["general_info"]) if isinstance(routed, dict) else ["general_info"]
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
            ordering_keywords = ["want", "order", "get", "take", "add", "cart", "pickup", "delivery", "please", "2", "two"]
            looks_like_order = any(keyword in query.lower() for keyword in ordering_keywords)
            
            # Route to order agent if in order flow OR if it looks like an ordering request
            if in_order_flow or looks_like_order:
                if "order" not in intents:
                    intents = ["order"] + [i for i in intents if i != "order"]
                    print(f"[WORKFLOW] 2c. Biased routing to order agent. In order flow: {in_order_flow}, Looks like order: {looks_like_order}")
        except Exception:
            pass
        print(f"[WORKFLOW] 2b. Intent(s) detected: {intents}")

        # extract entities once and pass them into agents via the conversation list
        print("[WORKFLOW] 3. Extracting entities...")
        extracted = self.entity_extractor.extract(query) if self.entity_extractor else {}
        print(f"[WORKFLOW] 3a. Entities extracted: {extracted}")

        # call agents
        print("[WORKFLOW] 4. Dispatching to agent(s)...")
        results: List[AgentResult] = []
        for intent in intents:
            agent = AGENT_MAP.get(intent)
            if not agent:
                continue
            # obtain conversation context and append an 'nlu' message containing extracted entities
            session_ctx = list(self.session_manager.get_conversation_context(session_id))
            # append a non-persistent local marker so agents can read entities from the last message
            session_with_entities = session_ctx + [{"role": "nlu", "message": extracted}]
            print(f"[WORKFLOW] 4a. Calling agent: '{agent.name}' for intent '{intent}'")
            res = agent.handle(session_id, query, session=session_with_entities)
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

        conversation_history = "\n".join([f"{m['role']}: {m['message']}" for m in self.session_manager.get_conversation_context(session_id)])

        print("[WORKFLOW] 5. Building prompt...")
        prompt = self.builder.build_prompt(
            query=query,
            context_docs=merged_context_docs,
            conversation_history=conversation_history + "\n\nFACTS:\n" + "\n".join(facts_blocks),
            intents=intents,
        )

        print("[WORKFLOW] 6. Generating final response with LLM...")
        final_text = self.builder.llm_generate(prompt)

        # save assistant response
        # Ensure we save the final text, not the whole object, to history
        response_text = final_text
        if isinstance(final_text, dict) and 'response' in final_text:
            response_text = final_text['response']
        elif not isinstance(final_text, str):
            response_text = str(final_text) # Fallback
        self.session_manager.add_message(session_id, "assistant", response_text)

        # collect citations
        citations = []
        for r in results:
            for c in getattr(r, "citations", []):
                citations.append({"source": c.source, "snippet": c.snippet})

        print(f"[WORKFLOW] 7. Final response generated.")
        
        # Print order details and database status after every response
        self._print_order_status_and_db(session_id, results)
        
        print("="*50 + "\n")
        return {"response": final_text, "citations": citations, "intents": intents}
    
    def _print_order_status_and_db(self, session_id: str, results: List[AgentResult]):
        """Print order details and database status for debugging."""
        from ..data.database import SessionLocal
        from ..data.models import Product, Order, OrderItem, Customer
        
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
        db = SessionLocal()
        try:
            print(f"\n[DATABASE STATUS]")
            
            # Products
            products = db.query(Product).all()
            print(f"\nProducts ({len(products)} total):")
            for p in products:
                print(f"  - {p.name}: {p.quantity_in_stock} in stock @ ${p.price}")
            
            # Orders
            orders = db.query(Order).all()
            print(f"\nOrders ({len(orders)} total):")
            if not orders:
                print("  No orders found")
            else:
                for o in orders:
                    customer = db.query(Customer).filter(Customer.id == o.customer_id).first()
                    customer_name = customer.name if customer else f"Customer #{o.customer_id}"
                    print(f"  - Order #{o.id}: {customer_name}, Status: {o.status.value}, Type: {o.pickup_or_delivery.value}, Total: ${o.total_amount or 0:.2f}")
            
            # Order Items
            order_items = db.query(OrderItem).all()
            print(f"\nOrder Items ({len(order_items)} total):")
            if not order_items:
                print("  No order items found")
            else:
                for oi in order_items:
                    print(f"  - Order #{oi.order_id}: {oi.quantity}x {oi.product.name} @ ${oi.price_at_time_of_order}")
                    
        except Exception as e:
            print(f"Error accessing database: {e}")
        finally:
            db.close()
        
        print("="*60 + "\n")
