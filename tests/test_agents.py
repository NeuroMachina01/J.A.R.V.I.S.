import pytest
from agents._base import AgentInput
from agents.general import GeneralAgent
from agents.vision_solver import VisionSolverAgent
from dotenv import load_dotenv

load_dotenv()

def test_general_agent():
    agent = GeneralAgent()
    inp = AgentInput(query="Hello there", session_id="test")
    output = agent.run(inp)
    
    assert output.source == "general"
    assert output.confidence == 1.0
    assert len(output.result) > 0
    assert output.requires_voice is True

def test_vision_solver_agent():
    agent = VisionSolverAgent()
    inp = AgentInput(query="What does the code say?", vision_description="print('hello')", session_id="test")
    output = agent.run(inp)
    
    assert output.source == "vision_solver"
    assert output.confidence == 0.9
    assert "hello" in output.result.lower() or "print" in output.result.lower()
