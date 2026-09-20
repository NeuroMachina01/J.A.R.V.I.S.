import os
import time
import tempfile
import threading
import queue
import logging
import asyncio
import edge_tts
import pygame

logger = logging.getLogger(__name__)

# Initialize PyGame mixer for audio playback
pygame.mixer.init()

class Mouth:
    def __init__(self):
        self.speech_queue = queue.Queue()
        self._lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker_thread.start()

    def _speak_worker(self):
        while True:
            item = self.speech_queue.get()
            if item is None: 
                break
                
            text, on_ready_callback = item
            self.speak_and_wait(text, on_ready_callback)
            self.speech_queue.task_done()

    def speak(self, text: str, on_ready_callback=None):
        """Asynchronous: Adds text to the queue and returns immediately."""
        self.speech_queue.put((text, on_ready_callback))

    def speak_and_wait(self, text: str, on_ready_callback=None):
        """Synchronous: Blocks the thread until the audio is finished."""
        if not text.strip():
            if on_ready_callback: on_ready_callback()
            return
            
        with self._lock:
            try:
                import re
                voice = "en-IN-NeerjaNeural"
                
                # Split text into sentences for ultra-low latency chunking
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
                if not sentences:
                    sentences = [text.strip()]
                    
                file_queue = queue.Queue()
                
                def prefetcher():
                    for i, sentence in enumerate(sentences):
                        try:
                            temp_path = os.path.join(tempfile.gettempdir(), f"jarvis_speech_{i}_{int(time.time())}.mp3")
                            communicate = edge_tts.Communicate(sentence, voice, rate="+15%")
                            asyncio.run(communicate.save(temp_path))
                            file_queue.put(temp_path)
                        except Exception as e:
                            logger.error(f"TTS fetch error: {e}")
                    file_queue.put(None)
                    
                # Start downloading sentences in the background
                threading.Thread(target=prefetcher, daemon=True).start()
                
                callback_fired = False
                
                while True:
                    path = file_queue.get()
                    if path is None:
                        break
                        
                    # Trigger the UI exactly as the first sentence is ready to play
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

# --- THE SINGLETON INSTANCE ---
mouth = Mouth()