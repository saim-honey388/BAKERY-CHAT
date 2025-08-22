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
        # Bias routing to order agent if an order flow is in progress
        try:
            order_agent: OrderAgent = AGENT_MAP.get("order")  # type: ignore
            cart_state = order_agent.get_cart_state(session_id) if hasattr(order_agent, "get_cart_state") else {"has_cart": False}
            if cart_state.get("awaiting_fulfillment") or cart_state.get("awaiting_details") or cart_state.get("awaiting_confirmation"):
                if "order" not in intents:
                    intents = ["order"] + [i for i in intents if i != "order"]
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
        self.session_manager.add_message(session_id, "assistant", final_text)

        # collect citations
        citations = []
        for r in results:
            for c in getattr(r, "citations", []):
                citations.append({"source": c.source, "snippet": c.snippet})

        print(f"[WORKFLOW] 7. Final response generated.")
        print("="*50 + "\n")
        return {"response": final_text, "citations": citations, "intents": intents}
