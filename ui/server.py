import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from core.brain import Brain
from io_layer.mouth import Mouth

app = FastAPI()

# Mount the static frontend directory
app.mount("/static", StaticFiles(directory="ui/static"), name="static")

# Initialize core systems
brain = Brain()
mouth = Mouth()

import logging

server_loop = None
active_connections: list[WebSocket] = []

class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if server_loop and active_connections:
                for conn in active_connections:
                    asyncio.run_coroutine_threadsafe(conn.send_json({"type": "log", "message": msg}), server_loop)
        except Exception:
            pass

@app.on_event("startup")
async def startup_event():
    global server_loop
    server_loop = asyncio.get_running_loop()
    
    # Attach the WebSocket logger
    ws_handler = WebSocketLogHandler()
    ws_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logging.getLogger().addHandler(ws_handler)

def broadcast_message(msg: dict):
    """Thread-safe broadcast to all connected WebSockets."""
    if not server_loop:
        return
    for conn in active_connections:
        try:
            asyncio.run_coroutine_threadsafe(conn.send_json(msg), server_loop)
        except Exception as e:
            print(f"Broadcast error: {e}")

from core.events import event_bus
event_bus.subscribe("broadcast", broadcast_message)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            query = payload.get("query")
            
            if not query:
                continue

            # Detect language from typed text (Devanagari script detection)
            from core.language import detect_language
            language = payload.get("language") or detect_language(query)

            # Acknowledge receipt
            await websocket.send_json({
                "type": "status",
                "message": f"PROCESSING QUERY [{language.upper()}]...",
            })
            
            # Run the synchronous LangGraph brain in a separate thread
            output = await asyncio.to_thread(brain.process, query, "default", language)
            
            import re
            def clean_text(text: str) -> str:
                text = re.sub(r'[\*\#\`\|]', '', text)
                text = re.sub(r'\[.*?\]\(.*?\)', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
                
            clean_result = clean_text(output.result)
            response_lang = output.language or language
            
            # Synchronize UI with Audio
            def sync_display():
                if output.requires_display:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({
                            "type": "result",
                            "agent": output.source,
                            "text": clean_result,
                            "confidence": output.confidence,
                        }),
                        server_loop
                    )

            if output.requires_voice:
                mouth.speak(clean_result, language=response_lang, on_ready_callback=sync_display)
            else:
                sync_display()
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("UI disconnected.")