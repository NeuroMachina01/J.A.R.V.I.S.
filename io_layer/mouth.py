# io_layer/mouth.py
# JARVIS Voice Output — Edge-TTS with language-aware voice selection.
# Supports English (Indian accent) and Hindi with automatic voice switching.
# Uses a background sentence prefetcher for ultra-low first-byte latency.

import os
import re
import time
import tempfile
import threading
import queue
import logging
import asyncio
import edge_tts
import pygame

from core.language import get_voice, detect_language

logger = logging.getLogger(__name__)

# Initialize PyGame mixer for audio playback
pygame.mixer.init()


class Mouth:
    def __init__(self):
        self.speech_queue = queue.Queue()
        self._lock = threading.Lock()
        self.worker_thread = threading.Thread(
            target=self._speak_worker, daemon=True
        )
        self.worker_thread.start()

    def _speak_worker(self):
        """Background worker that processes the speech queue sequentially."""
        while True:
            item = self.speech_queue.get()
            if item is None:
                break

            text, language, on_ready_callback = item
            self.speak_and_wait(text, language, on_ready_callback)
            self.speech_queue.task_done()

    def speak(self, text: str, language: str = "en", on_ready_callback=None):
        """Asynchronous: Adds text to the queue and returns immediately."""
        self.speech_queue.put((text, language, on_ready_callback))

    def speak_and_wait(
        self, text: str, language: str = "en", on_ready_callback=None
    ):
        """
        Synchronous: Blocks until the audio finishes playing.

        Args:
            text: The text to speak.
            language: ISO-639-1 code ("en" or "hi"). Selects the TTS voice.
            on_ready_callback: Called the instant before the first audio chunk
                               begins playing — used to sync UI text display.
        """
        if not text.strip():
            if on_ready_callback:
                on_ready_callback()
            return

        with self._lock:
            try:
                voice = get_voice(language)
                logger.info(f"Mouth: speaking [{language}] with voice {voice}")

                # Split text into sentences for low-latency streaming
                sentences = [
                    s.strip()
                    for s in re.split(r"(?<=[.!?।])\s+", text)
                    if s.strip()
                ]
                if not sentences:
                    sentences = [text.strip()]

                file_queue = queue.Queue()

                def prefetcher():
                    """Downloads TTS audio for each sentence in the background."""
                    for i, sentence in enumerate(sentences):
                        try:
                            temp_path = os.path.join(
                                tempfile.gettempdir(),
                                f"jarvis_speech_{i}_{int(time.time() * 1000)}.mp3",
                            )
                            communicate = edge_tts.Communicate(
                                sentence, voice, rate="+15%"
                            )
                            asyncio.run(communicate.save(temp_path))
                            file_queue.put(temp_path)
                        except Exception as e:
                            logger.error(f"TTS fetch error: {e}")
                    file_queue.put(None)  # Sentinel: end of stream

                # Start downloading sentences in the background
                threading.Thread(target=prefetcher, daemon=True).start()

                callback_fired = False

                while True:
                    path = file_queue.get()
                    if path is None:
                        break

                    # Fire the UI callback on the first chunk
                    if not callback_fired and on_ready_callback:
                        on_ready_callback()
                        callback_fired = True

                    try:
                        pygame.mixer.music.load(path)
                        pygame.mixer.music.play()

                        while pygame.mixer.music.get_busy():
                            time.sleep(0.05)

                        pygame.mixer.music.unload()
                        os.remove(path)
                    except Exception as e:
                        logger.error(f"Playback error: {e}")

            except Exception as e:
                logger.error(f"Mouth output error (Edge-TTS): {e}")


# ── JARVIS-wide singleton ──────────────────────────────────────
mouth = Mouth()