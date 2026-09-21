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
    ears = Ears()
    from core.events import event_bus
    
    while True:
        query, language = ears.listen()
        if query:
            logger.info(f"Processing Voice Input [{language}]: {query}")
            
            # Broadcast the voice query to the HUD
            event_bus.emit("broadcast", {
                "type": "result", "agent": "USER",
                "text": query, "confidence": 1.0,
            })
            event_bus.emit("broadcast", {
                "type": "status",
                "message": f"PROCESSING VOICE QUERY [{language.upper()}]...",
            })
            
            # Process with language context
            output = brain.process(query, language=language)
            
            import re
            def clean_text(text: str) -> str:
                text = re.sub(r'[\*\#\`\|]', '', text)
                text = re.sub(r'\[.*?\]\(.*?\)', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
                
            clean_result = clean_text(output.result)
            
            # Use the language from the agent's response (it may differ from input)
            response_lang = output.language or language

            def sync_display():
                if output.requires_display:
                    event_bus.emit("broadcast", {
                        "type": "result",
                        "agent": output.source,
                        "text": clean_result,
                        "confidence": output.confidence,
                    })

            if output.requires_voice:
                mouth.speak(clean_result, language=response_lang, on_ready_callback=sync_display)
            else:
                sync_display()

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