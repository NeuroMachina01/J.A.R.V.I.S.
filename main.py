import uvicorn
import threading
import asyncio
import logging
import os
from dotenv import load_dotenv
from io_layer.hud import hud

# 1. CRITICAL: Load the .env file BEFORE importing any AI modules!
# This ensures LangChain can find your GOOGLE_API_KEY when the agents initialize.
load_dotenv()

# Quick sanity check on startup
if not os.getenv("GOOGLE_API_KEY"):
    print("⚠️  WARNING: GOOGLE_API_KEY not found! Make sure your .env file is set up correctly.")

# 2. Now it is safe to import your modules
from ui.server import app, brain, mouth
from io_layer.ears import Ears

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def audio_listener_loop():
    """Runs continuously, listening for voice commands."""
    # Ears can now initialize knowing the API key is ready
    ears = Ears()
    from core.events import event_bus
    
    while True:
        query = ears.listen()
        if query:
            logger.info(f"Processing Voice Input: {query}")
            
            # Broadcast the voice query to the HUD!
            event_bus.emit("broadcast", {"type": "result", "agent": "USER", "text": query, "confidence": 1.0})
            event_bus.emit("broadcast", {"type": "status", "message": "PROCESSING VOICE QUERY..."})
            
            # Synchronous call since we are in a background thread
            output = brain.process(query)
            
            if output.requires_display:
                event_bus.emit("broadcast", {
                    "type": "result",
                    "agent": output.source,
                    "text": output.result,
                    "confidence": output.confidence
                })
            
            if output.requires_voice:
                mouth.speak(output.result)

if __name__ == "__main__":

    # --- BOOT THE HUD FIRST ---
    logger.info("Initializing Tactical HUD...")
    hud.start()
    
    # 3. Start the Ears in a background thread
    audio_thread = threading.Thread(target=audio_listener_loop, daemon=True)
    audio_thread.start()

    # 4. Boot the UI / WebSocket server
    print("=====================================")
    print(" JARVIS CORE ONLINE")
    print(" Access HUD at: http://localhost:8000/static/index.html")
    print("=====================================")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")