# core/brain.py
# The JARVIS orchestrator. Ties keyword detector + router + agents + eyes.
# This is the single entry point for all input.

import logging
from typing import TypedDict, Any
from langgraph.graph import StateGraph, END

from agents._base import AgentInput, AgentOutput
from agents.agent_registry import AgentRegistry
from core.keyword_detector import KeywordDetector, InputMode
from core.router import LLMRouter
from io_layer.eyes import Eyes

logger = logging.getLogger(__name__)


# ─── Shared State ──────────────────────────────────────────────
# Flows through every node. Each node reads + writes what it needs.

class JARVISState(TypedDict):
    raw_input: str                   # original user text
    session_id: str

    # Vision
    needs_vision: bool
    vision_description: str          # populated by eyes_node
    image_bytes: bytes | None

    # Routing
    keyword_match_mode: str          # "vision" | "agent" | "brain"
    keyword_agent_hint: str | None   # fast-routed agent name
    selected_agent: str              # final agent chosen

    # Execution
    agent_input: dict | None         # serialized AgentInput
    agent_output: dict | None        # serialized AgentOutput

    # Context / Memory
    memory: dict
    last_agent: str


# ─── Brain ─────────────────────────────────────────────────────

class Brain:
    def __init__(self):
        self.registry = AgentRegistry()
        self.registry.discover("agents")

        self.detector = KeywordDetector(
            extra_triggers=self.registry.all_triggers()
        )
        self.router = LLMRouter(
            routing_manifest=self.registry.routing_manifest()
        )
        self.eyes = Eyes()

        self.graph = self._build_graph()
        logger.info(f"Brain initialized. Agents: {self.registry}")

    # ── Node: Keyword Detection ────────────────────────────────
    def keyword_node(self, state: JARVISState) -> JARVISState:
        """Stage 1: Fast keyword check. No LLM, no cost."""
        match = self.detector.detect(state["raw_input"])
        logger.info(f"Keyword match: {match.mode.value} / hint={match.agent_hint}")

        return {
            **state,
            "needs_vision": match.mode == InputMode.VISION,
            "keyword_match_mode": match.mode.value,
            "keyword_agent_hint": match.agent_hint,
        }

    # ── Node: Eyes (Vision) ────────────────────────────────────
    def eyes_node(self, state: JARVISState) -> JARVISState:
        """Captures screen and gets Vision LLM description."""
        vision_out = self.eyes.see_and_describe()
        description = self.eyes.build_description_string(vision_out)
        logger.info(f"Vision description: {description}")

        return {
            **state,
            "vision_description": description,
        }

    # ── Node: LLM Router ──────────────────────────────────────
    def router_node(self, state: JARVISState) -> JARVISState:
        """Stage 2: LLM picks the agent. Only runs if keyword had no match."""
        agent_input = AgentInput(
            query=state["raw_input"],
            vision_description=state.get("vision_description"),
            context=state.get("memory", {}),
            session_id=state["session_id"],
        )

        agent_name, confidence = self.router.route(agent_input)
        logger.info(f"LLM Router selected: {agent_name} ({confidence:.2f})")
        from io_layer.hud import hud
        hud.update_status(f"ROUTING TO: {agent_name.upper()}")

        return {**state, "selected_agent": agent_name}

    # ── Node: Agent Execution ──────────────────────────────────
    def execute_node(self, state: JARVISState) -> JARVISState:
        """Calls the selected agent and captures output."""
        agent_name = state["selected_agent"]
        agent = self.registry.get(agent_name)

        if not agent:
            logger.warning(f"Agent '{agent_name}' not found — using fallback")
            output = AgentOutput(
                result="I'm not sure how to handle that. Could you rephrase?",
                confidence=0.0,
                source="fallback",
            )
        else:
            agent_input = AgentInput(
                query=state["raw_input"],
                vision_description=state.get("vision_description"),
                context=state.get("memory", {}),
                session_id=state["session_id"],
            )
            output = agent.run(agent_input)
            logger.info(f"Agent '{agent_name}' responded (confidence={output.confidence:.2f})")

        return {
            **state,
            "agent_output": output.model_dump(),
            "last_agent": agent_name,
        }

    # ── Conditional Edge: after keyword node ──────────────────
    def route_after_keyword(self, state: JARVISState) -> str:
        mode = state["keyword_match_mode"]

        if mode == "vision":
            return "eyes"                    # capture screen first

        if mode == "agent" and state.get("keyword_agent_hint"):
            # Fast path: skip LLM router entirely
            return "fast_agent_assign"

        return "llm_router"                  # no keyword match → LLM decides

    # ── Node: Fast Agent Assignment ───────────────────────────
    def fast_assign_node(self, state: JARVISState) -> JARVISState:
        """Skips LLM router — uses keyword hint directly."""
        agent_name = state["keyword_agent_hint"]
        logger.info(f"Fast assignment → {agent_name}")
        return {**state, "selected_agent": agent_name}

    # ── Graph Assembly ─────────────────────────────────────────
    def _build_graph(self):
        g = StateGraph(JARVISState)

        # Nodes
        g.add_node("keyword_check", self.keyword_node)
        g.add_node("eyes", self.eyes_node)
        g.add_node("llm_router", self.router_node)
        g.add_node("fast_agent_assign", self.fast_assign_node)
        g.add_node("execute", self.execute_node)

        # Entry
        g.set_entry_point("keyword_check")

        # Conditional routing after keyword check
        g.add_conditional_edges(
            "keyword_check",
            self.route_after_keyword,
            {
                "eyes": "eyes",
                "fast_agent_assign": "fast_agent_assign",
                "llm_router": "llm_router",
            }
        )

        # After vision → always go to LLM router
        # (vision gives description, then brain picks agent based on it)
        g.add_edge("eyes", "llm_router")

        # Both routing paths converge at execute
        g.add_edge("llm_router", "execute")
        g.add_edge("fast_agent_assign", "execute")

        # Done
        g.add_edge("execute", END)

        return g.compile()

    def process(self, user_input: str, session_id: str = "default") -> AgentOutput:
        """Single entry point. Takes text, returns AgentOutput."""
        import time
        from core.db import db
        start_time = time.time()
        
        initial_state: JARVISState = {
            "raw_input": user_input,
            "session_id": session_id,
            "needs_vision": False,
            "vision_description": "",
            "image_bytes": None,
            "keyword_match_mode": "",
            "keyword_agent_hint": None,
            "selected_agent": "general",
            "agent_input": None,
            "agent_output": None,
            "memory": {},
            "last_agent": "",
        }

        from io_layer.hud import hud
        hud.clear()
        hud.update_status("PROCESSING DIRECTIVE...")

        final_state = self.graph.invoke(initial_state)
        output = AgentOutput(**final_state["agent_output"])
        
        latency_ms = int((time.time() - start_time) * 1000)
        db.log_interaction(
            query=user_input,
            agent=final_state["selected_agent"],
            response=output.result,
            latency_ms=latency_ms
        )
        
        return output
