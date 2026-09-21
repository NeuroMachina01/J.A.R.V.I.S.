# agents/tools.py
# Contains all the tools (Python functions) that the ToolAgent can invoke.

from langchain_core.tools import tool
import datetime
import requests
import json
import logging

logger = logging.getLogger(__name__)

@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Get the current time in a specific timezone (e.g. 'UTC', 'Asia/Kolkata', 'America/New_York')."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone)
    except Exception:
        # Fallback to UTC if timezone is invalid or zoneinfo fails
        import pytz
        tz = pytz.UTC
    
    return datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")

@tool
def get_weather(location: str) -> str:
    """Get the current weather for a specific location/city."""
    try:
        # Using wttr.in format=3 for concise format: condition temp
        r = requests.get(f"https://wttr.in/{location}?format=3", timeout=5)
        if r.status_code == 200:
            return r.text.strip()
        else:
            return f"Weather data unavailable for {location}."
    except Exception as e:
        logger.error(f"Weather tool error: {e}")
        return "Weather service unreachable."
        
@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use standard Python math syntax."""
    # Extremely basic safe eval for math expressions
    allowed_chars = set("0123456789+-*/(). %")
    if not all(c in allowed_chars for c in expression):
        return "Error: Invalid characters in mathematical expression. Only basic arithmetic allowed."
    
    try:
        # Evaluate safely using limited scope
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error evaluating: {e}"

# SuperKalam specific dummy tools for the Tutor workflow

@tool
def fetch_practice_question(topic: str, difficulty: str = "medium") -> str:
    """
    Fetch a practice question for a student. 
    Topics can be 'physics', 'math', 'chemistry', etc.
    Difficulty: 'easy', 'medium', 'hard'.
    """
    # Mocking a database query for SuperKalam AI Tutor
    db = {
        "physics": {
            "easy": "What is the formula for force?",
            "medium": "A car accelerates from 0 to 60 mph in 5 seconds. What is its average acceleration?",
            "hard": "Calculate the escape velocity of a planet with twice the mass and half the radius of Earth."
        },
        "math": {
            "medium": "Solve for x: 2x^2 - 5x + 3 = 0",
        }
    }
    
    topic = topic.lower()
    difficulty = difficulty.lower()
    
    if topic in db and difficulty in db[topic]:
        return json.dumps({
            "status": "success", 
            "question": db[topic][difficulty],
            "metadata": {"topic": topic, "difficulty": difficulty}
        })
    else:
        return json.dumps({
            "status": "success",
            "question": f"Explain the core concepts of {topic} as if to a 10 year old.",
            "metadata": {"topic": topic, "difficulty": difficulty}
        })

# The list of tools to bind to the LLM
jarvis_tools = [get_current_time, get_weather, calculate, fetch_practice_question]
