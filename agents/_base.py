# agents/_base.py
# THE CONTRACT — every agent must implement this

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any


class AgentInput(BaseModel):
    query: str
    image: bytes | None = None          # raw screen capture bytes
    vision_description: str | None = None  # pre-processed by Eyes
    context: dict = {}                  # memory / conversation history
    session_id: str = "default"
    language: str = "en"                # detected language: "en" or "hi"


class AgentOutput(BaseModel):
    result: str
    confidence: float                   # 0.0 - 1.0
    source: str                         # agent name that answered
    metadata: dict = {}                 # any extra data (sources, charts, etc.)
    requires_voice: bool = True         # should MOUTH speak this?
    requires_display: bool = True       # should FRONTEND show this?
    language: str = "en"                # language of the response: "en" or "hi"


class BaseAgent(ABC):
    """
    Every JARVIS agent signs this contract.
    Drop a new file in /agents/, inherit this, implement run().
    Registry auto-discovers it at startup — no other changes needed.
    """

    name: str           # unique snake_case ID  e.g. "nexus_agent"
    description: str    # LLM reads this for routing — be specific
    triggers: list[str] # fast keyword hints, bypass LLM routing if matched

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        """Core logic. Must be implemented by every agent."""
        ...

    def health_check(self) -> bool:
        """Optional: override to verify dependencies (API keys, DB connections)."""
        return True

    def __repr__(self):
        return f"<Agent: {self.name}>"
