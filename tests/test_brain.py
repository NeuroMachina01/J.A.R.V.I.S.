import pytest
from core.brain import Brain

class MockEyes:
    def see_and_describe(self):
        return {"description": "Mocked screen content"}
    def build_description_string(self, out):
        return "Mocked screen content"

def test_brain_state_machine(monkeypatch):
    brain = Brain()
    # Mock eyes to prevent actual screen capture during CI/CD
    brain.eyes = MockEyes()
    
    # Mock HUD updates to prevent output spam
    def mock_update(*args, **kwargs): pass
    from io_layer.hud import hud
    monkeypatch.setattr(hud, "update_status", mock_update)
    monkeypatch.setattr(hud, "clear", mock_update)
    
    # Test fast agent routing
    out = brain.process("search the web for test")
    # Keyword detector should bypass router and go straight to web_search/nexus_agent
    
    assert out is not None
