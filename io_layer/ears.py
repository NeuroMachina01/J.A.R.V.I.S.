import os
import tempfile
import speech_recognition as sr
import logging
import keyboard
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

class Ears:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        logger.info("Calibrating ambient noise...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        logger.info("Ears online. Push-To-Talk active (Hold Left Ctrl).")

    def listen(self) -> str:
        """Blocks until hotkey is pressed, then listens."""
        try:
            logger.info("Awaiting Push-to-Talk (Press 'ctrl' to speak)...")
            import time
            while True:
                if keyboard.is_pressed('ctrl') or keyboard.is_pressed('right ctrl') or keyboard.is_pressed('left ctrl'):
                    break
                time.sleep(0.05)
            
            with self.microphone as source:
                logger.info("Listening...")
                # Short timeout so it stops quickly if no voice is heard
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=10)
                
            if not client:
                logger.error("Sarvam AI STT client not initialized. Falling back to Google.")
                text = self.recognizer.recognize_google(audio)
            else:
                wav_bytes = audio.get_wav_data()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(wav_bytes)
                    temp_path = f.name
                
                try:
                    with open(temp_path, "rb") as audio_file:
                        response = client.speech_to_text.transcribe(
                            file=audio_file,
                            model="saaras:v4",
                            mode="transcribe"
                        )
                    # Support for response object or dict depending on SDK version
                    text = getattr(response, "transcript", "")
                    if not text and isinstance(response, dict):
                        text = response.get("transcript", "")
                finally:
                    os.remove(temp_path)
                
            logger.info(f"Heard: {text}")
            return text
            
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            logger.error(f"Ears error: {e}")
            return ""