import pytest
from core.keyword_detector import KeywordDetector, InputMode

def test_keyword_detector_vision():
    detector = KeywordDetector()
    match = detector.detect("hey JARVIS look at my screen")
    assert match.mode == InputMode.VISION

def test_keyword_detector_agent_hint():
    detector = KeywordDetector({"test_agent": ["run test agent"]})
    match = detector.detect("please run test agent now")
    assert match.mode == InputMode.AGENT
    assert match.agent_hint == "test_agent"

def test_keyword_detector_brain_fallback():
    detector = KeywordDetector()
    match = detector.detect("what is the weather today?")
    assert match.mode == InputMode.BRAIN
