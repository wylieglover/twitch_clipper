import asyncio
import traceback

from fastapi import BackgroundTasks, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from app.pipeline import process_from_twitch_clips, process_from_vod
from app.session_manager import SessionManager, remove_background_task, set_background_task
from app.services.background import send_keepalive_signals

async def process_clips_background(
    session_id: str,
    source: str,
    time_window: str,
    vod: bool,
    max_clips: int,
    segment_duration: int,
    include_subtitles: bool,
    min_views: int,
    shutdown_event
):
    """Enhanced background processing with SQLite persistence"""
    try:
        if not SessionManager.session_exists(session_id):
            print(f"[background] Session {session_id} not found, aborting")
            return
            
        # Update status to processing
        SessionManager.update_session_status(session_id, "processing")
        
        session_obj = SessionManager.get_session(session_id)
        
        # Create keepalive task
        keepalive_task = asyncio.create_task(send_keepalive_signals(session_id, shutdown_event))
        
        try:
            # Check for shutdown during processing
            if shutdown_event.is_set():
                SessionManager.update_session_status(session_id, "cancelled")
                return
                
            # Run processing with regular status updates
            if vod:
                outputs = await run_in_threadpool(
                    process_from_vod, source, max_clips, segment_duration, session_obj, include_subtitles
                )
            else:
                outputs = await run_in_threadpool(
                    process_from_twitch_clips, source, time_window, max_clips, session_obj, include_subtitles, min_views
                )
            
            # Final status update
            if SessionManager.session_exists(session_id):
                SessionManager.update_session_status(session_id, "completed")
                SessionManager.update_session_results(session_id, outputs)
                print(f"[session] {session_id} completed processing")
            
        except Exception as e:
            if SessionManager.session_exists(session_id):
                SessionManager.update_session_status(session_id, "error", str(e))
            raise
            
        finally:
            # Cancel keepalive and remove background task
            keepalive_task.cancel()
            remove_background_task(session_id)
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        
    except asyncio.CancelledError:
        print(f"[session] {session_id} processing cancelled")
        SessionManager.update_session_status(session_id, "cancelled")
    except Exception as e:
        print(f"[session] {session_id} error: {e}")
        traceback.print_exc()
        SessionManager.update_session_status(session_id, "error", str(e))