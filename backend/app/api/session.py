import asyncio
import os
from pathlib import Path
import shutil
import time
import traceback
import aiofiles
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.processing import process_clips_background
from app.session_manager import SessionManager, cancel_background_task, set_background_task
from app.utils.events import shutdown_event

router = APIRouter(prefix="/api/session")

@router.post("/process")
async def process_clip(
    background_tasks: BackgroundTasks,
    source: str = Form(...),
    time_window: str = Form("week"),
    vod: bool = Form(False),
    max_clips: int = Form(5),
    segment_duration: int = Form(30),
    session_id: str = Form(...),
    include_subtitles: bool = Form(False),
    min_views: int = Form(0),
):
    try:
        if not SessionManager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found. Create a session first using /api/session/create")
        
        # Reset session for new processing
        SessionManager.update_session_status(session_id, "processing")
        SessionManager.update_session_results(session_id, [])

        # Start background processing
        task = asyncio.create_task(
            process_clips_background(
                session_id, 
                source, 
                time_window, 
                vod, 
                max_clips, 
                segment_duration, 
                include_subtitles,
                min_views,
                shutdown_event=shutdown_event
            )
        )
        set_background_task(session_id, task)

        return {
            "status": "processing",
            "session_id": session_id,
            "message": "Processing started. Use /api/status/{session_id} to check progress."
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    
@router.get("/keepalive")
async def keepalive():
    """Enhanced keepalive with session count from database"""
    counts = SessionManager.get_session_counts()
    return {
        "status": "alive", 
        "timestamp": time.time(),
        "active_sessions": counts["active_sessions"],
        "processing_sessions": counts["processing_sessions"],
        "cached_sessions": counts["cached_sessions"]
    }

@router.post("/create")
async def create_session():
    """Create a new session without starting processing"""
    try:
        session_id = SessionManager.create_session()
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Session created successfully"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/output/{session_id}/{filename:path}")
async def serve_session_file(session_id: str, filename: str):
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SessionManager.get_session(session_id)
    file_path = Path(session.output_dir) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    async def generate():
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                yield chunk
    
    content_type = "application/octet-stream"
    if filename.endswith('.mp4'):
        content_type = "video/mp4"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        content_type = "image/jpeg"
    elif filename.endswith('.png'):
        content_type = "image/png"
    
    return StreamingResponse(
        generate(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Accept-Ranges": "bytes"
        }
    )

@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = SessionManager.get_session_data(session_id)
    
    resp = {
        "session_id": session_id,
        "status": session_data.status,
        "created_at": session_data.created_at,
        "last_activity": session_data.last_activity,
        "partial_results": session_data.results,
        "current_step": session_data.current_step,
        "progress": session_data.progress
    }
    
    if session_data.status == "completed":
        resp["outputs"] = session_data.results
    elif session_data.status == "error":
        resp["error"] = session_data.error or "Unknown error"
    
    return resp

@router.get("/download/{session_id}/{filename}")
async def download_single_file(session_id: str, filename: str):
    """Download a single file from a session - non-blocking"""
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SessionManager.get_session(session_id)
    file_path = Path(session.output_dir) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Stream the file for download
    async def generate():
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                yield chunk
    
    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/download_session/{session_id}")
async def download_session_clips(session_id: str):
    """Download all clips from a specific session - async"""
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SessionManager.get_session(session_id)
    
    if not os.path.exists(session.output_dir):
        raise HTTPException(status_code=404, detail="No files found for this session")
    
    # Create zip in thread pool to avoid blocking
    zip_name = f"clips_{session_id}"
    zip_path = await run_in_threadpool(
        shutil.make_archive, zip_name, 'zip', session.output_dir
    )
    
    # Stream the zip file
    async def generate():
        async with aiofiles.open(zip_path, 'rb') as f:
            while chunk := await f.read(8192):
                yield chunk
        # Clean up the temp zip file
        os.unlink(zip_path)
    
    return StreamingResponse(
        generate(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=clips_{session_id}.zip"
        }
    )

@router.get("/list")
async def list_sessions():
    """List all active sessions"""
    sessions = []
    session_list = SessionManager.list_sessions()
    
    for session_data in session_list:
        sessions.append({
            "session_id": session_data.session_id,
            "status": session_data.status,
            "created_at": session_data.created_at,
            "results_count": len(session_data.results)
        })
    
    return {"sessions": sessions}

@router.delete("/cancel/{session_id}")
async def cancel_processing(session_id: str):
    """Cancel an ongoing processing task"""
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cancel the background task
    cancelled = cancel_background_task(session_id)
    if cancelled:
        SessionManager.update_session_status(session_id, "cancelled")
        return {"message": f"Processing for session {session_id} cancelled"}
    
    return {"message": f"No active processing for session {session_id}"}

@router.delete("/cleanup/{session_id}")
async def cleanup_session(session_id: str):
    """Manually cleanup a specific session"""
    if not SessionManager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Cancel any background task
        cancel_background_task(session_id)
        
        # Cleanup session
        success = SessionManager.cleanup_session(session_id)
        if success:
            return {"message": f"Session {session_id} cleaned up successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to cleanup session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up session: {e}")
    