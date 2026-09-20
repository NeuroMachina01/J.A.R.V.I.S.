# io_layer/hud.py
# JARVIS-wide HUD singleton.
# One window. Any agent can push to it via: from io_layer.hud import hud
# Supports image bytes directly — no temp file needed.

import io
import threading
import time
import logging
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, simpledialog, messagebox
import queue

logger = logging.getLogger(__name__)


class HUDController:
    def __init__(self):
        self.root       = None
        self.label      = None
        self.status_bar = None
        self.is_running = False
        self._lock      = threading.Lock()

    # ── Boot ──────────────────────────────────────────────────
    def start(self):
        """Spins up the HUD in a daemon thread. Safe to call once at startup."""
        with self._lock:
            if self.is_running:
                return                          # guard against double-start
        threading.Thread(target=self._run_gui, daemon=True).start()
        while not self.is_running:              # wait for window to render
            time.sleep(0.05)
        logger.info("HUD online.")


    def prompt_for_sources(self) -> tuple[list[str], list[str]]:
        """Launch the popup on the HUD's thread and wait for result."""
        res_queue = queue.Queue()

        def _task():
            urls = []
            pdf_paths = []
            
            # The HUD root is the parent to prevent 'deleted window' errors
            choice = messagebox.askyesnocancel(
                "Nexus Multi-Ingestion", 
                "Analyze local PDF documents?\n(Yes = Select PDFs | No = Enter URLs)",
                parent=self.root
            )
            
            if choice is True: 
                files = filedialog.askopenfilenames(
                    title="Select PDFs (Hold Ctrl to select multiple)",
                    filetypes=[("PDF Documents", "*.pdf")],
                    parent=self.root
                )
                if files:
                    pdf_paths.extend(list(files))
            elif choice is False:
                raw_urls = simpledialog.askstring(
                    "Nexus Multi-Ingestion",
                    "Enter URLs (separate with comma):",
                    parent=self.root
                )
                if raw_urls:
                    urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
                    urls = [u if u.startswith("http") else "https://" + u for u in urls]
            
            res_queue.put((urls, pdf_paths))

        # Push the task to the Tkinter thread
        self.root.after(0, _task)
        # Block the Agent thread until the user finishes the popup
        return res_queue.get()

    

    def _run_gui(self):
        self.root = tk.Tk()
        self.root.title("JARVIS — MARK V HUD")
        self.root.geometry("860x620")
        self.root.configure(bg="#030a16")
        self.root.resizable(True, True)

        # ── Outer tactical border ─────────────────────────────
        border = tk.Frame(self.root, bg="#00f3ff", bd=2)
        border.pack(expand=True, fill="both", padx=10, pady=(10, 4))

        inner = tk.Frame(border, bg="#030a16", bd=0)
        inner.pack(expand=True, fill="both", padx=2, pady=2)

        # ── Header bar ───────────────────────────────────────
        header = tk.Frame(inner, bg="#0a1a33", height=32)
        header.pack(fill="x")
        tk.Label(
            header, text="◈  MARK V INTELLIGENCE HUD  ◈",
            bg="#0a1a33", fg="#00f3ff",
            font=("Courier New", 11, "bold")
        ).pack(side="left", padx=12, pady=4)

        # ── Image display area ────────────────────────────────
        self.label = tk.Label(inner, bg="#030a16", text="")
        self.label.pack(expand=True, fill="both", padx=4, pady=4)

        # ── Status bar ────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root,
            text="AWAITING DIRECTIVE...",
            bg="#0a1a33", fg="#00f3ff",
            font=("Courier New", 10, "bold"),
            anchor="w",
        )
        self.status_bar.pack(fill="x", padx=10, pady=(0, 8))

        self.is_running = True
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()

    # ── Update Methods ─────────────────────────────────────────

    def update_image_bytes(self, img_bytes: bytes, caption: str = ""):
        """Push raw image bytes to the HUD. No temp file needed."""
        if not self._check_running():
            return

        def _update():
            try:
                img = Image.open(io.BytesIO(img_bytes))
                img.thumbnail((820, 540), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo, text="")
                self.label.image = photo          # prevent GC
                if caption and self.status_bar:
                    self.status_bar.config(text=f"  ◈  {caption}")
                    
                # Broadcast image to the Web UI
                try:
                    import base64
                    from ui.server import broadcast_message
                    b64_image = base64.b64encode(img_bytes).decode('utf-8')
                    broadcast_message({"type": "image", "content": b64_image, "caption": caption})
                except Exception as ex:
                    logger.error(f"Failed to broadcast image to Web HUD: {ex}")
                    
            except Exception as e:
                logger.error(f"HUD image render failed: {e}")
                self.label.config(
                    text=f"[Image render error]\n{e}",
                    image="", fg="#ff4444",
                    font=("Courier New", 12)
                )

        self.root.after(0, _update)

    def update_image_path(self, image_path: str, caption: str = ""):
        """Push an image from a file path. Kept for backward compatibility."""
        if not self._check_running():
            return
        try:
            with open(image_path, "rb") as f:
                self.update_image_bytes(f.read(), caption)
        except Exception as e:
            logger.error(f"HUD could not load {image_path}: {e}")

    def update_status(self, text: str):
        """Update the bottom status bar without changing the image."""
        if not self._check_running():
            return
        self.root.after(0, lambda: self.status_bar.config(text=f"  ◈  {text}"))
        try:
            from ui.server import broadcast_message
            broadcast_message({"type": "status", "message": text.upper()})
        except Exception:
            pass

    def clear(self):
        """Reset to idle state."""
        if not self._check_running():
            return

        def _clear():
            self.label.config(
                image="",
                text="AWAITING DIRECTIVE...",
                fg="#00f3ff",
                font=("Courier New", 14, "bold")
            )
            self.status_bar.config(text="  ◈  AWAITING DIRECTIVE...")
        self.root.after(0, _clear)
        try:
            from ui.server import broadcast_message
            broadcast_message({"type": "clear"})
        except Exception:
            pass

    # ── Internal ───────────────────────────────────────────────

    def _check_running(self) -> bool:
        if not self.is_running or not self.root:
            logger.warning("HUD.update called before start() — call hud.start() in main.py")
            return False
        return True

    def close(self):
        if self.root:
            self.is_running = False
            self.root.quit()


# ── JARVIS-wide singleton ──────────────────────────────────────
# Import this anywhere: from io_layer.hud import hud
# Start it once in main.py: hud.start()
hud = HUDController()
