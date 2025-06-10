from contextlib import asynccontextmanager
import asyncio
import signal
import sys
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.session import router as session_router
from app.api.tiktok import router as tiktok_router
from app.api.policy import router as policy_router
from app.utils.events import shutdown_event

from app.session_manager import (
    SessionManager,
    CLEANUP_INTERVAL,
)

# Path setup for static docs 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "assets", "documents")

def is_reloader_process():
    return os.environ.get("RUN_MAIN") == "true" or "--reload" in sys.argv

def signal_handler(signum, frame):
    print(f"[shutdown] Received signal {signum}, initiating graceful shutdown…")
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except RuntimeError:
        asyncio.run(shutdown_event.set())

if not is_reloader_process():
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        print("[startup] Signal handlers registered")
    except ValueError as e:
        print(f"[startup] Could not register signal handlers: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] FastAPI server starting with SQLite session management")
    SessionManager.initialize()
    cleanup_task = asyncio.create_task(periodic_cleanup())
    try:
        yield
    finally:
        print("[shutdown] Cleaning up all sessions...")
        shutdown_event.set()
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

async def periodic_cleanup():
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CLEANUP_INTERVAL)
            break
        except asyncio.TimeoutError:
            SessionManager.cleanup_old_sessions()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(session_router)
app.include_router(tiktok_router)
app.include_router(policy_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
