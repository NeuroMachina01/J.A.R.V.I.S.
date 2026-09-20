import pytest
from agents.agent_registry import AgentRegistry
from core.router import LLMRouter
from agents._base import AgentInput

EVAL_DATASET = [
    ("Hello there!", "general"),
    ("What's 2 + 2?", "general"),
    ("What is on my screen right now?", "vision_solver"),
    ("Look at my screen, what IDE am I using?", "vision_solver"),
    ("Tell me a bedtime story about a cyber dragon.", "general"),
    ("Search the web for the latest Python version.", "nexus_agent"),
]

@pytest.fixture
def router():
    registry = AgentRegistry()
    registry.discover("agents")
    manifest = registry.routing_manifest()
    return LLMRouter(routing_manifest=manifest)

@pytest.mark.parametrize("query, expected_agent", EVAL_DATASET)
def test_router_accuracy(router, query, expected_agent):
    agent_input = AgentInput(
        query=query,
        vision_description="",
        context={},
        session_id="eval_session"
    )
    
    predicted_agent, confidence = router.route(agent_input)
    assert predicted_agent == expected_agent, f"Expected {expected_agent}, but got {predicted_agent}"
