# agents/tool_agent.py
# An agent capable of executing Python functions (tools) mid-thought to fetch real data.

import logging
from agents._base import BaseAgent, AgentInput, AgentOutput
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from agents.tools import jarvis_tools

logger = logging.getLogger(__name__)

class ToolAgent(BaseAgent):
    name = "tool_agent"
    description = (
        "Handles queries requiring real-time data, mathematics, weather, time, "
        "or external API calls. Also acts as an AI Tutor fetching practice questions."
    )
    triggers = ["weather", "time", "calculate", "math", "practice", "question"]
    
    def __init__(self):
        from dotenv import load_dotenv
        import os
        from langchain_groq import ChatGroq
        
        load_dotenv()
        
        # Primary LLM: Gemini 2.5 Flash
        primary_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0.2,
            max_retries=0
        )
        
        # Fallback LLM: Groq (supports tool calling)
        fallback_llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.2,
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        # Bind tools to the LLM with fallbacks
        self.llm = primary_llm.with_fallbacks([fallback_llm]).bind_tools(jarvis_tools)
        
        # Build a lookup dictionary for easy tool execution
        self.tools_map = {t.name: t for t in jarvis_tools}

    def run(self, input: AgentInput) -> AgentOutput:
        lang = input.language or "en"
        
        lang_rule = (
            "Respond entirely in Hindi (Devanagari script) using natural conversational tone."
            if lang == "hi"
            else "Respond in clear, conversational English."
        )

        system_prompt = (
            "You are JARVIS. You have access to tools that can fetch real-world "
            "information (time, weather, math, tutor questions). "
            "Always use a tool if it can help answer the user's query accurately. "
            "If a tool returns an error, gracefully explain the issue to the user. "
            "Keep your final response concise and natural, as it will be spoken out loud. "
            "You can use multiple tools in sequence if needed. "
            "Always think step-by-step. "
            f"\n\nLANGUAGE RULE: {lang_rule}"
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input.query)
        ]
        
        from io_layer.hud import hud
        
        try:
            hud.update_status("🛠️ Agentic Loop Initiated...")
        except Exception:
            pass
            
        max_iterations = 5
        iterations = 0
        
        while iterations < max_iterations:
            try:
                hud.update_status("EVALUATING TOOL USAGE...")
                response = self.llm.invoke(messages)
            except Exception as e:
                logger.error(f"Error executing LLM: {e}")
                return AgentOutput(
                    result=f"Error executing LLM: {e}",
                    confidence=0.95,
                    source=self.name,
                    requires_voice=True,
                    language=lang,
                )
            
            # If the LLM doesn't want to call any more tools, we have our final answer!
            if not response.tool_calls:
                return AgentOutput(
                    result=response.content,
                    confidence=0.95,
                    source=self.name,
                    requires_voice=True,
                    language=lang,
                )
                
            # Append the LLM's tool requests to the chat history
            messages.append(response)
            
            # Execute each requested tool
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                hud.update_status(f"EXECUTING TOOL: {tool_name.upper()}...")
                logger.info(f"ToolAgent invoking {tool_name} with args: {tool_args}")
                
                if tool_name in self.tools_map:
                    try:
                        tool_result = self.tools_map[tool_name].invoke(tool_args)
                    except Exception as e:
                        logger.error(f"Error executing {tool_name}: {e}")
                        tool_result = f"Error: {e}"
                else:
                    tool_result = f"Error: Tool '{tool_name}' not found."
                    
                logger.info(f"Tool Result: {tool_result}")
                
                # Append the tool's result back to the LLM
                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id
                ))
            
            iterations += 1
            
        return AgentOutput(
            result="I apologize, but I reached the maximum number of reasoning steps without finding an answer.",
            confidence=0.95,
            source=self.name,
            requires_voice=True,
            language=lang,
        )
