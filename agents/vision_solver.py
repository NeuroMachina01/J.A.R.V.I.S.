# agents/vision_solver.py
# Handles on-screen problems after Eyes has described them.
# This is the agent that SOLVES — Eyes only described.

from agents._base import BaseAgent, AgentInput, AgentOutput
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage


class VisionSolverAgent(BaseAgent):
    name = "vision_solver"
    description = (
        "The primary agent for analyzing the user's screen. Use this ONLY for queries "
        "asking what is on the screen, or solving errors, diagrams, or math equations that are VISIBLE ON SCREEN. "
        "NEVER use this agent for general math or logic questions unless the user mentions looking at the screen."
    )
    triggers = [
        "solve this", "fix this", "debug this",
        "what's the error", "explain this error",
    ]

    def __init__(self):
        # Use Flash because the Pro models are restricted to 0 quota on this free-tier key
        from langchain_groq import ChatGroq
        import os
        
        primary_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, max_retries=0)
        
        fallback_llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.2,
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        self.llm = primary_llm.with_fallbacks([fallback_llm])

    def run(self, input: AgentInput) -> AgentOutput:
        context = input.vision_description or input.query
        
        system_prompt = (
            "You are JARVIS's expert problem solver. "
            "IMPORTANT: The user's screen content has already been captured by your visual cortex "
            "and is provided to you below as 'Screen content' data. "
            "ABSOLUTE RULES: "
            "1. NEVER say 'I cannot see your screen', 'I don't have access', or 'I am an AI'. "
            "2. You DO have access. Treat the 'Screen content' text as exactly what is on the screen right now. "
            "3. Solve the user's problem based on this data clearly, concisely, and directly. "
            "4. Format your answer so it sounds natural when spoken out loud by a text-to-speech engine. "
            "Avoid using heavy markdown, asterisks, or long code blocks unless the user explicitly asks you to dictate code."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Screen content: {context}\n\nUser asked: {input.query}")
        ]

        from io_layer.hud import hud
        hud.update_status("SOLVING VISUAL QUERY...")

        response = self.llm.invoke(messages)
        result = response.content

        return AgentOutput(
            result=result,
            confidence=0.9,
            source=self.name,
            metadata={"vision_context": context},
        )
