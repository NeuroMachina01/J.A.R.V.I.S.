from agents._base import BaseAgent, AgentInput, AgentOutput
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
import os

class GeneralAgent(BaseAgent):
    name = "general"
    description = "Handles general conversation, greetings, and casual chat."
    triggers = ["hello", "hi", "how are you", "what's up"]

    def __init__(self):
        # We use flash here with a higher temperature so JARVIS sounds conversational
        primary_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7, max_retries=0)
        
        # Using the requested model (falling back to a known 70B if the string is invalid)
        fallback_llm = ChatGroq(
            model="openai/gpt-oss-120b", # Groq's GPT-OSS 120B model
            temperature=0.7,
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        self.llm = primary_llm.with_fallbacks([fallback_llm])

    def run(self, input: AgentInput) -> AgentOutput:
        # Determine language instruction based on detected language
        lang = input.language or "en"
        if lang == "hi":
            lang_instruction = (
                "\n\nIMPORTANT LANGUAGE RULE: The user is speaking in Hindi. "
                "You MUST respond entirely in Hindi (Devanagari script). "
                "Do NOT mix English words unless they are technical terms with no Hindi equivalent."
            )
        else:
            lang_instruction = (
                "\n\nIMPORTANT LANGUAGE RULE: The user is speaking in English. "
                "Respond in clear, natural English."
            )

        system_prompt = """
You are JARVIS — an autonomous AI agent created by Puskar.

Identity:
- Your name is JARVIS.
- You are NOT Google, Gemini, ChatGPT, OpenAI, or any third-party assistant.
- Never refer to yourself as another company's product.
- Speak as JARVIS naturally and consistently.

Capabilities:
- You understand and process text, conversation, reasoning, and multimodal context when available.
- You can coordinate specialized internal agents and tools.
- You adapt responses based on context and provide clear, concise, intelligent assistance.
- You are aware of your available capabilities but never claim abilities that are unavailable in the current runtime.

Behavior:
- Be concise, confident, and helpful.
- Respond naturally, like an advanced personal AI assistant.
- Avoid mentioning internal implementation details unless asked.
- If a capability is unavailable, explain the limitation without breaking character.

Style:
- Intelligent.
- Professional.
- Slightly futuristic (JARVIS-style).
- Never overly robotic.

Current mode:
You are operating as JARVIS.
""" + lang_instruction
        
        messages = [
            ("system", system_prompt),
            ("human", input.query)
        ]
        
        response = self.llm.invoke(messages)
        
        return AgentOutput(
            result=response.content,
            confidence=1.0,
            source=self.name,
            requires_voice=True,
            language=lang,
        )