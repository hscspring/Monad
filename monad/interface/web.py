import os
import queue
import threading
import asyncio
import webbrowser
import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from monad.core.loop import MonadLoop
from monad.interface.output import Output
from monad.interface.voice_input import VoiceInput

# Suppress uvicorn logging to avoid console spam
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Global queues
log_queue = queue.Queue()
input_queue = queue.Queue()

class WebInput(VoiceInput):
    """Input handler that waits on a queue from the web interface."""
    def listen(self) -> str:
        try:
            # Block until we receive an input from the web UI
            text = input_queue.get()
            return text
        except Exception:
            return ""

def monad_worker():
    """Run MONAD in a background thread."""
    # Set the queue for this thread so Output emits to it
    Output.set_queue(log_queue)
    
    agent_loop = MonadLoop()
    agent_loop.input = WebInput()
    
    # Hook ask_user tool to wait on the web queue instead of terminal input
    import monad.tools.ask_user
    monad.tools.ask_user.custom_input_handler = lambda: input_queue.get()
    
    try:
        agent_loop.start()
    except Exception as e:
        Output.error(f"MONAD crashed: {e}")

app = FastAPI(title="MONAD Web Interface")

# Mount static files (frontend assets)
static_dir = os.path.dirname(__file__)
static_path = os.path.join(static_dir, "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Mount output directory for file downloads
output_path = os.path.join(os.path.expanduser("~"), ".monad", "output")
os.makedirs(output_path, exist_ok=True)
app.mount("/output", StaticFiles(directory=output_path), name="output")

# Input directory for uploaded files
input_path = os.path.join(os.path.expanduser("~"), ".monad", "input")
os.makedirs(input_path, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept file uploads, save to ~/.monad/input/, return the local path."""
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest = os.path.join(input_path, safe_name)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return JSONResponse({"path": dest, "filename": safe_name, "size": len(content)})

@app.get("/")
async def get_index():
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>MONAD Web Interface Static Files Not Found</h1>")

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if not log_queue.empty():
                # We send all logs buffered so it's not super slow
                msgs = []
                while not log_queue.empty():
                    msgs.append(log_queue.get_nowait())
                # send individual messages
                for msg in msgs:
                    await websocket.send_text(msg)
            else:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            input_queue.put(data)
    except WebSocketDisconnect:
        pass

def start_web(host="127.0.0.1", port=8000):
    """Start the web server and background worker."""
    worker = threading.Thread(target=monad_worker, daemon=True)
    worker.start()
    
    # Open browser slightly after server starts
    def open_browser():
        import time
        time.sleep(1.0)
        print(f"Opening browser at http://{host}:{port} ...")
        # Use a background thread to open browser so it doesn't block
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:
            pass
            
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        # Run uvicorn directly
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        print("\nShutting down MONAD Web Interface...")
