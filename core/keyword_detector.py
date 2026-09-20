# core/keyword_detector.py
# STAGE 1 ROUTING — zero LLM calls, runs in microseconds.
# Checks for vision triggers first, then agent keyword triggers.
# Only falls through to LLM router if nothing matches.

import re
from dataclasses import dataclass
from enum import Enum


class InputMode(Enum):
    VISION   = "vision"    # screen capture needed
    AGENT    = "agent"     # specific agent triggered by keyword
    BRAIN    = "brain"     # no fast match — LLM router decides


@dataclass
class KeywordMatch:
    mode: InputMode
    agent_hint: str | None   # if AGENT mode, which agent
    confidence: float        # how confident the keyword match is
    matched_phrase: str      # which phrase triggered this


# ─── Vision Triggers ───────────────────────────────────────────
# These phrases mean "Eyes activate, capture screen first"

VISION_TRIGGERS = [
    # explicit screen references
    "look at this", "look at my screen", "what's on screen", "what's on my screen",
    "what is on screen", "what is on my screen", "read the screen", "read this",
    "what does this say", "what does it say", "what is happening in my screen",
    "what is happening on my screen", "my screen", "the screen",
    # problem solving
    "solve this", "help me with this", "fix this",
    "debug this", "explain this", "what is this",
    "how do i solve", "what's the error", "what is the error",
    # curiosity
    "what am i looking at", "can you see", "analyze this",
    "check this", "review this",
]

# ─── Agent Fast-Triggers ────────────────────────────────────────
# These phrases skip LLM routing and go directly to an agent.
# Populated at runtime from agent_registry.all_triggers()

# Hardcoded defaults — registry supplements these at startup
BUILTIN_AGENT_TRIGGERS: dict[str, list[str]] = {
    "sentinel_agent": [
        "stock price", "price of", "how is", "trading", "market",
        "nvda", "aapl", "portfolio", "buy signal", "short",
    ],
    "nexus_agent": [
        "search my docs", "find in", "what did i", "recall",
        "from my notes", "look up", "retrieve","run nexus"
    ],
    "web_search": [
        "search the web", "google", "look up online",
        "current news", "latest", "today's",
    ],
}


class KeywordDetector:
    def __init__(self, extra_triggers: dict[str, list[str]] | None = None):
        """
        extra_triggers: from AgentRegistry.all_triggers()
        Merges with builtins so registry-defined triggers work automatically.
        """
        self.agent_triggers = {**BUILTIN_AGENT_TRIGGERS}
        if extra_triggers:
            for agent_name, phrases in extra_triggers.items():
                existing = self.agent_triggers.get(agent_name, [])
                self.agent_triggers[agent_name] = list(set(existing + phrases))

    def detect(self, raw_text: str) -> KeywordMatch:
        """
        Main entry point.
        Returns a KeywordMatch with mode, agent_hint, and confidence.

        Priority:
          1. Vision triggers  → InputMode.VISION
          2. Agent triggers   → InputMode.AGENT
          3. No match         → InputMode.BRAIN (LLM decides)
        """
        text = raw_text.lower().strip()

        # ── Stage 1: Vision check ──────────────────────────────
        vision_match = self._check_vision(text)
        if vision_match:
            return KeywordMatch(
                mode=InputMode.VISION,
                agent_hint=None,             # brain decides AFTER vision
                confidence=0.9,
                matched_phrase=vision_match,
            )

        # ── Stage 2: Agent keyword check ──────────────────────
        agent_match = self._check_agents(text)
        if agent_match:
            agent_name, phrase = agent_match
            return KeywordMatch(
                mode=InputMode.AGENT,
                agent_hint=agent_name,
                confidence=0.85,
                matched_phrase=phrase,
            )

        # ── Stage 3: Fall through to LLM router ───────────────
        return KeywordMatch(
            mode=InputMode.BRAIN,
            agent_hint=None,
            confidence=0.0,
            matched_phrase="",
        )

    def _check_vision(self, text: str) -> str | None:
        """Returns matched phrase if vision trigger found, else None."""
        for phrase in VISION_TRIGGERS:
            if phrase in text:
                return phrase
        return None

    def _check_agents(self, text: str) -> tuple[str, str] | None:
        """Returns (agent_name, matched_phrase) or None."""
        for agent_name, phrases in self.agent_triggers.items():
            for phrase in phrases:
                if phrase in text:
                    return agent_name, phrase
        return None

    def add_trigger(self, agent_name: str, phrase: str) -> None:
        """Dynamically add a trigger at runtime."""
        if agent_name not in self.agent_triggers:
            self.agent_triggers[agent_name] = []
        self.agent_triggers[agent_name].append(phrase.lower())

    def list_triggers(self) -> dict:
        return {
            "vision": VISION_TRIGGERS,
            "agents": self.agent_triggers,
        }
