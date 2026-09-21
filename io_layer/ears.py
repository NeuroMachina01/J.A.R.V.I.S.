# io_layer/ears.py
# JARVIS Auditory System — Push-to-Talk → Groq Whisper Large V3 → text.
# Returns both the transcribed text AND the detected language code.

import os
import tempfile
import speech_recognition as sr
import logging
from dotenv import load_dotenv
from groq import Groq
from io_layer.hud import hud
from core.language import normalize_whisper_language, detect_language

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

    def listen(self) -> tuple[str, str]:
        """
        Listens to microphone, uses Groq Whisper to transcribe.

        Returns:
            (text, language_code) — e.g. ("नमस्ते", "hi") or ("Hello", "en").
            Returns ("", "en") on failure or timeout.
        """
        if not self.client:
            logger.error("Groq client not initialized (missing API key).")
            return "", "en"

        hud.update_status("Awaiting Push-to-Talk (Press 'ctrl' to speak)...")

        import keyboard
        keyboard.wait("ctrl")
        hud.update_status("LISTENING...")

        with sr.Microphone() as source:
            try:
                audio_data = self.recognizer.listen(
                    source, timeout=5.0, phrase_time_limit=15.0
                )
                hud.update_status("Processing audio via Groq Whisper...")

                # Write to a temp file with a unique name to avoid collisions
                temp_path = os.path.join(
                    tempfile.gettempdir(), f"jarvis_ears_{os.getpid()}.wav"
                )
                with open(temp_path, "wb") as f:
                    f.write(audio_data.get_wav_data())

                # Transcribe with Groq Whisper — auto-detect language
                with open(temp_path, "rb") as file:
                    transcription = self.client.audio.transcriptions.create(
                        file=("audio.wav", file.read()),
                        model="whisper-large-v3",
                        prompt="Transcribe accurately. Supports English and Hindi.",
                        response_format="verbose_json",
                        temperature=0.0,
                        # NOTE: language parameter is intentionally OMITTED
                        # so Whisper auto-detects Hindi vs English.
                    )

                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                text = transcription.text.strip()

                # Extract detected language from verbose_json response
                whisper_lang = getattr(transcription, "language", None) or ""
                language = normalize_whisper_language(whisper_lang)

                # Fallback: if Whisper didn't return a language, use script detection
                if not whisper_lang:
                    language = detect_language(text)

                if text:
                    logger.info(f"Heard (Groq): [{language}] {text}")
                    hud.update_status(
                        f"TRANSCRIBED [{language.upper()}]: {text[:60]}..."
                    )

                return text, language

            except sr.WaitTimeoutError:
                return "", "en"
            except Exception as e:
                logger.error(f"Ears error (Groq): {e}")
                return "", "en"