# tests/run_evals.py
# An automated evaluation pipeline to benchmark JARVIS's performance (routing + latency + accuracy).
# Implements "LLM-as-a-Judge" to grade responses.

import os
import sys
import time
import json
import logging
from typing import Dict, Any

# Add root directory to sys.path so we can import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Disable noisy logging for a clean console output
logging.getLogger().setLevel(logging.CRITICAL)

# Fix Windows console emoji encoding issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Mute the visual HUD during headless testing
class DummyHUD:
    def update_status(self, msg): pass
    def clear(self): pass
    def update_image_bytes(self, b, c=""): pass
sys.modules['io_layer.hud'] = type('hud', (), {'hud': DummyHUD()})()

# Monkey-patch the real mouth to silence TTS
from io_layer.mouth import mouth
mouth.speak = lambda text, language="en", on_ready_callback=None: on_ready_callback() if on_ready_callback else None
mouth.speak_and_wait = lambda text, language="en", on_ready_callback=None: on_ready_callback() if on_ready_callback else None

from dotenv import load_dotenv
load_dotenv()

from core.brain import Brain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

def run_evals():
    print("==================================================")
    print("JARVIS BENCHMARK REPORT (v2.0)")
    print("==================================================")
    
    # Load dataset
    dataset_path = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    print(f"Total Tests Run: {len(dataset)}")
    
    # Initialize Brain
    brain = Brain()
    
    from langchain_groq import ChatGroq
    
    # Initialize Judge LLM (Gemini Flash -> Groq Fallback)
    primary_judge = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        temperature=0.0,
        max_retries=0
    )
    fallback_judge = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.0,
        api_key=os.environ.get("GROQ_API_KEY")
    )
    judge_llm = primary_judge.with_fallbacks([fallback_judge])
    
    total_latency = 0
    correct_routing = 0
    
    results = []
    
    # Execute pipeline headless
    for i, test in enumerate(dataset):
        query = test["query"]
        expected_agent = test["expected_agent"]
        criteria = test["eval_criteria"]
        
        print(f"Running test {i+1}/{len(dataset)}: '{query}'...")
        start_time = time.time()
        
        # Process through JARVIS pipeline
        # (This bypasses ears/mouth and goes straight to the engine)
        output = brain.process(query)
        
        latency_ms = int((time.time() - start_time) * 1000)
        total_latency += latency_ms
        
        actual_agent = output.source
        response_text = output.result
        
        if actual_agent == expected_agent:
            correct_routing += 1
            
        # Judge the response
        judge_prompt = f"""
        You are an expert AI evaluator judging an AI assistant's response.
        
        Query: {query}
        Success Criteria: {criteria}
        Actual Response: {response_text}
        
        Evaluate the response on a scale of 1 to 5, where 5 is perfect.
        Output ONLY valid JSON in this exact format, with no markdown formatting:
        {{"score": 5, "reason": "brief explanation of the score"}}
        """
        
        try:
            judge_res = judge_llm.invoke([HumanMessage(content=judge_prompt)])
            # Clean JSON (sometimes Gemini wraps in ```json)
            clean_json = judge_res.content.replace("```json", "").replace("```", "").strip()
            evaluation = json.loads(clean_json)
            score = evaluation.get("score", 0)
            reason = evaluation.get("reason", "No reason provided")
        except Exception as e:
            score = 0
            reason = f"Judge failed to evaluate: {e}"
            
        results.append({
            "id": i + 1,
            "query": query,
            "expected_agent": expected_agent,
            "actual_agent": actual_agent,
            "latency_ms": latency_ms,
            "score": score,
            "reason": reason
        })

    avg_latency = total_latency // len(dataset)
    routing_acc = (correct_routing / len(dataset)) * 100
    
    # Print Summary
    latency_color = "[PASS]" if avg_latency < 2000 else "[WARN]" if avg_latency < 4000 else "[FAIL]"
    routing_color = "[PASS]" if routing_acc >= 80 else "[WARN]" if routing_acc >= 60 else "[FAIL]"
    
    print(f"Average Latency: {avg_latency}ms  {latency_color} (Target: <2000ms)")
    print(f"Routing Accuracy: {routing_acc:.0f}%   {routing_color} ({correct_routing}/{len(dataset)} correctly routed)\n")
    
    # Print Test Breakdown
    for res in results:
        agent_match = "[PASS]" if res["actual_agent"] == res["expected_agent"] else "[FAIL] (Routing Failure)"
        lat_match = "[PASS]" if res["latency_ms"] < 2000 else "[WARN]"
        score_match = "[PASS]" if res["score"] >= 4 else "[FAIL]"
        
        print(f"[TEST {res['id']}] Query: \"{res['query']}\"")
        print(f"  -> Expected Agent : {res['expected_agent']}")
        print(f"  -> Actual Agent   : {res['actual_agent']} {agent_match}")
        print(f"  -> Latency        : {res['latency_ms']}ms {lat_match}")
        print(f"  -> Judge Score    : {res['score']}/5 {score_match} ({res['reason']})")
        print("-" * 50)
        
    print("==================================================")

if __name__ == "__main__":
    run_evals()
