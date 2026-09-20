import os
import time
import base64
import tempfile
import threading
import queue
import logging
import winsound
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
logger = logging.getLogger(__name__)

sarvam_api_key = os.getenv("SARVAM_API_KEY")
if sarvam_api_key:
    client = SarvamAI(api_subscription_key=sarvam_api_key)
else:
    logger.error("SARVAM_API_KEY not found in .env")
    client = None

class Mouth:
    def __init__(self):
        self.speech_queue = queue.Queue()
        self._lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker_thread.start()

    def _speak_worker(self):
        while True:
            text = self.speech_queue.get()
            if text is None: 
                break
                
            self.speak_and_wait(text)
            self.speech_queue.task_done()

    def speak(self, text: str):
        """Asynchronous: Adds text to the queue and returns immediately."""
        self.speech_queue.put(text)

    def speak_and_wait(self, text: str):
        """Synchronous: Blocks the thread until the audio is finished."""
        if not text.strip():
            return
            
        with self._lock:
            try:
                if not client:
                    logger.error("Sarvam AI client not initialized.")
                    return

                # Convert text to speech using Sarvam AI (Indian accent + code-switching)
                response = client.text_to_speech.convert(
                    text=text,
                    language_code="hi-IN", # Supports Hinglish natively
                    speaker="shubh",
                    model="bulbul:v3"
                )
                
                if response and response.audios and len(response.audios) > 0:
                    audio_data = base64.b64decode(response.audios[0])
                    
                    # Create a temporary file to play the WAV audio
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                        f.write(audio_data)
                        temp_path = f.name
                        
                    # Play the audio file
                    winsound.PlaySound(temp_path, winsound.SND_FILENAME)
                    
                    # Clean up
                    os.remove(temp_path)
            except Exception as e:
                logger.error(f"Mouth output error: {e}")

# --- THE SINGLETON INSTANCE ---
mouth = Mouth()