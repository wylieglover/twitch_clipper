import asyncio
from app.session_manager import SessionManager

async def send_keepalive_signals(session_id: str, shutdown_event):
    try:
        while SessionManager.session_exists(session_id) and not shutdown_event.is_set():
            session_data = SessionManager.get_session_data(session_id)
            if not session_data or session_data.status != "processing":
                break

            SessionManager.update_session_progress(session_id, session_data.current_step, session_data.progress)

            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=30.0)
                break
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        print(f"[keepalive] Keepalive cancelled for session {session_id}")
