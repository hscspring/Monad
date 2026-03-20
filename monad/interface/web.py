"""
MONAD Web Interface
FastAPI-based web UI with WebSocket communication.
"""

import asyncio
import os
import queue
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from monad.config import CONFIG
from monad.core.loop import MonadLoop
from monad.interface.output import Output
from monad.interface.voice_input import VoiceInput

input_queue: queue.Queue[str] = queue.Queue()


def _sanitize_upload_filename(name: str | None, max_component_len: int = 200) -> str:
    """Return a single path-safe filename component (no directories, no traversal)."""
    if not name or not str(name).strip():
        return "upload.bin"
    base = Path(str(name)).name
    if not base or base in (".", ".."):
        return "upload.bin"
    base = base.replace("\x00", "")
    if len(base) > max_component_len:
        stem = Path(base).stem[: max_component_len - 16]
        suf = (Path(base).suffix or ".bin")[:12]
        base = stem + suf
    return base


class WebInput(VoiceInput):
    """Input handler that waits on a queue from the web interface."""

    def listen(self) -> str:
        try:
            return input_queue.get()
        except Exception:
            return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background MONAD worker with asyncio log queue for WebSockets."""
    loop = asyncio.get_running_loop()
    log_q: asyncio.Queue[str] = asyncio.Queue()
    app.state.log_queue = log_q

    def enqueue_log(msg: str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(log_q.put(msg), loop)
        except RuntimeError:
            pass

    def monad_worker() -> None:
        Output.set_queue(enqueue_log)
        agent_loop = MonadLoop()
        agent_loop.input = WebInput()

        import monad.tools.ask_user

        monad.tools.ask_user.custom_input_handler = lambda: input_queue.get()

        try:
            agent_loop.start()
        except Exception as e:
            logger.exception("MONAD worker crashed")
            Output.error(f"MONAD crashed: {e}")

    worker = threading.Thread(target=monad_worker, daemon=True)
    worker.start()
    yield


app = FastAPI(title="MONAD Web Interface", lifespan=lifespan)

static_dir = os.path.dirname(__file__)
static_path = os.path.join(static_dir, "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

output_path = str(CONFIG.output_path)
app.mount("/output", StaticFiles(directory=output_path), name="output")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept file uploads, save to input dir, return the local path."""
    safe_name = _sanitize_upload_filename(file.filename)
    root = Path(CONFIG.input_path).resolve()
    dest = (root / safe_name).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        return JSONResponse({"error": "Invalid filename"}, status_code=400)

    max_bytes = CONFIG.web_max_upload_bytes
    body = await file.read(max_bytes + 1)
    if len(body) > max_bytes:
        return JSONResponse(
            {"error": f"File too large (max {max_bytes} bytes)"},
            status_code=413,
        )

    dest.write_bytes(body)
    return JSONResponse({"path": str(dest), "filename": safe_name, "size": len(body)})


@app.get("/")
async def get_index():
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>MONAD Web Interface Static Files Not Found</h1>")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    log_q: asyncio.Queue[str] = websocket.app.state.log_queue
    await websocket.accept()
    try:
        while True:
            msg = await log_q.get()
            await websocket.send_text(msg)
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


def start_web(host: str | None = None, port: int | None = None) -> None:
    """Start the web server and background worker."""
    bind_host = CONFIG.web_host if host is None else host
    bind_port = CONFIG.web_port if port is None else port

    def open_browser() -> None:
        time.sleep(1.0)
        logger.info(f"Opening browser at http://{bind_host}:{bind_port}")
        try:
            webbrowser.open(f"http://{bind_host}:{bind_port}")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host=bind_host, port=bind_port, log_level="warning")
    except KeyboardInterrupt:
        logger.info("MONAD Web Interface shutting down")
