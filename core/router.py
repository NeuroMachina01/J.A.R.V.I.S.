import json
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents._base import AgentInput

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.65

ROUTER_SYSTEM_PROMPT = """You are JARVIS's routing brain.
Your ONLY job is to read a user query and decide which agent should handle it.

Rules:
- Respond with ONLY valid JSON. No explanation, no preamble.
- Format: {{"agent": "<agent_name>", "confidence": <0.0-1.0>}}
- Pick the MOST specific agent. If unsure, use "general".
- confidence = how certain you are (0.0 = guessing, 1.0 = certain)

{routing_manifest}
"""

class LLMRouter:
    def __init__(self, routing_manifest: str, model: str = "gemini-2.5-flash"):
        """
        routing_manifest: string from AgentRegistry.routing_manifest()
        Uses Gemini Flash — cheapest, fastest for routing.
        """
        # Initialize LangChain's Gemini integration with Groq Fallback
        from langchain_groq import ChatGroq
        import os
        
        primary_llm = ChatGoogleGenerativeAI(model=model, temperature=0.0, max_retries=0)
        
        fallback_llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.0,
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        self.llm = primary_llm.with_fallbacks([fallback_llm])
        
        self.system_prompt = ROUTER_SYSTEM_PROMPT.format(
            routing_manifest=routing_manifest
        )

    def route(self, input: AgentInput) -> tuple[str, float]:
        query = self._build_query(input)

        try:
            # LangChain uses a list of Message objects
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=query)
            ]
            
            response = self.llm.invoke(messages)
            raw = response.content.strip()

            # Clean up potential markdown formatting Gemini might add
            if raw.startswith("```json"):
                raw = raw[7:-3].strip()
            elif raw.startswith("```"):
                raw = raw[3:-3].strip()

            parsed = json.loads(raw)

            agent_name = parsed.get("agent", "general")
            confidence = float(parsed.get("confidence", 0.5))

            if confidence < CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Router confidence {confidence:.2f} below threshold "
                    f"for '{agent_name}' → falling back to general"
                )
                return "general", confidence

            logger.info(f"Router selected: {agent_name} ({confidence:.2f})")
            return agent_name, confidence

        except json.JSONDecodeError as e:
            logger.error(f"Router returned invalid JSON: {e}\nRaw: {raw}")
            return "general", 0.0
        except Exception as e:
            logger.error(f"Router LLM call failed: {e}")
            return "general", 0.0

    def _build_query(self, input: AgentInput) -> str:
        # ... (This method stays exactly the same) ...
        parts = []
        if input.vision_description:
            parts.append(f"[Screen content]: {input.vision_description}")
        parts.append(f"[User query]: {input.query}")
        if input.context.get("last_agent"):
            parts.append(f"[Last agent used]: {input.context['last_agent']}")
        return "\n".join(parts)