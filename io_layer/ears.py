import os
import speech_recognition as sr
import logging
from dotenv import load_dotenv
from groq import Groq
from io_layer.hud import hud

load_dotenv()
logger = logging.getLogger(__name__)

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    logger.error("GROQ_API_KEY not found in .env")

class Ears:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.client = Groq(api_key=groq_api_key) if groq_api_key else None

        hud.update_status("Calibrating mic (Groq STT)...")
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            self.recognizer.energy_threshold = max(300, self.recognizer.energy_threshold)
            self.recognizer.dynamic_energy_threshold = True
            
        # Optimize for conversational speech
        self.recognizer.pause_threshold = 1.2
        self.recognizer.non_speaking_duration = 0.5
        hud.update_status("Mic calibrated.")

    def listen(self) -> str:
        """Listens to microphone, uses Groq Whisper to transcribe. Returns text."""
        if not self.client:
            logger.error("Groq client not initialized (missing API key).")
            return ""

        hud.update_status("Awaiting Push-to-Talk (Press 'ctrl' to speak)...")
        
        # Simple blocking listen for now, can be hooked to a hotkey later
        import keyboard
        keyboard.wait('ctrl')
        hud.update_status("Listening...")

        with sr.Microphone() as source:
            try:
                # 5s timeout to start speaking, 15s max phrase length
                audio_data = self.recognizer.listen(source, timeout=5.0, phrase_time_limit=15.0)
                hud.update_status("Processing audio via Groq Whisper...")
                
                # Save audio to a temporary file for Groq
                with open("temp_ears.wav", "wb") as f:
                    f.write(audio_data.get_wav_data())

                # Transcribe with Groq Whisper
                with open("temp_ears.wav", "rb") as file:
                    transcription = self.client.audio.transcriptions.create(
                        file=("temp_ears.wav", file.read()),
                        model="whisper-large-v3",
                        prompt="Transcribe accurately. Includes Indian English and Hindi.",
                        response_format="json",
                        language="en",
                        temperature=0.0
                    )
                
                if os.path.exists("temp_ears.wav"):
                    os.remove("temp_ears.wav")

                text = transcription.text.strip()
                if text:
                    logger.info(f"Heard (Groq): {text}")
                return text

            except sr.WaitTimeoutError:
                return ""
            except Exception as e:
                logger.error(f"Ears error (Groq): {e}")
                return ""