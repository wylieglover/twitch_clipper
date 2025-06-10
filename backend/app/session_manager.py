import time
import uuid
import threading
from typing import Dict, Optional, List
from fastapi import HTTPException
from app.session import Session
from app.database import db_manager, SessionData

# Cache for ProcessingSession objects (not persisted, just for performance)
_session_cache: Dict[str, Session] = {}
_cache_lock = threading.Lock()

CLEANUP_INTERVAL = 3600 * 24  # 24 hours

class SessionManager:
    """Enhanced session manager using SQLite for persistence"""
    
    @staticmethod
    def create_session() -> str:
        """Create a new session with SQLite persistence"""
        try:
            session_id = str(uuid.uuid4())
            current_time = time.time()
            
            # Create ProcessingSession object
            try:
                processing_session = Session(session_id)
            except Exception as e:
                print(f"[session] ERROR creating ProcessingSession object: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")
            
            # Create session data for database
            session_data = SessionData(
                session_id=session_id,
                created_at=current_time,
                status="active",
                results=[],
                current_step="",
                progress=0,
                last_activity=current_time,
                error=None
            )
            
            # Save to database
            success = db_manager.create_session(session_data)
            if not success:
                # Clean up ProcessingSession if database save failed
                processing_session.cleanup()
                raise HTTPException(status_code=500, detail="Failed to save session to database")
            
            # Cache the ProcessingSession object
            with _cache_lock:
                _session_cache[session_id] = processing_session
            
            return session_id
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[session] Unexpected error in create_session: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")
    
    @staticmethod
    def get_session(session_id: str) -> Session:
        """Get ProcessingSession object, checking cache first"""
        # Check cache first
        with _cache_lock:
            if session_id in _session_cache:
                # Update last activity in database
                db_manager.update_last_activity(session_id)
                return _session_cache[session_id]
        
        # Check if session exists in database
        session_data = db_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        try:
            # Create ProcessingSession object and cache it
            processing_session = Session(session_id)
            with _cache_lock:
                _session_cache[session_id] = processing_session
            
            # Update last activity
            db_manager.update_last_activity(session_id)
            return processing_session
            
        except Exception as e:
            print(f"[session] Error recreating ProcessingSession for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to access session: {e}")
    
    @staticmethod
    def get_session_data(session_id: str) -> Optional[SessionData]:
        """Get session data from database"""
        return db_manager.get_session(session_id)
    
    @staticmethod
    def update_session_status(session_id: str, status: str, error: Optional[str] = None) -> bool:
        """Update session status"""
        session_data = db_manager.get_session(session_id)
        if not session_data:
            return False
        
        session_data.status = status
        session_data.last_activity = time.time()
        if error:
            session_data.error = error
        
        return db_manager.update_session(session_data)
    
    @staticmethod
    def add_result_to_session(session_id: str, result: dict) -> bool:
        """Add a result to session's results array"""
        return db_manager.add_result_to_session(session_id, result)
    
    @staticmethod
    def update_session_progress(session_id: str, step: str, progress: int = 0) -> bool:
        """Update session progress"""
        session_data = db_manager.get_session(session_id)
        if not session_data:
            return False
        
        session_data.current_step = step
        session_data.progress = progress
        session_data.last_activity = time.time()
        
        return db_manager.update_session(session_data)
    
    @staticmethod
    def update_session_results(session_id: str, results: List[dict]) -> bool:
        """Update session results completely"""
        session_data = db_manager.get_session(session_id)
        if not session_data:
            return False
        
        session_data.results = results
        session_data.last_activity = time.time()
        
        return db_manager.update_session(session_data)
    
    @staticmethod
    def session_exists(session_id: str) -> bool:
        """Check if session exists"""
        return db_manager.get_session(session_id) is not None
    
    @staticmethod
    def list_sessions(limit: Optional[int] = None) -> List[SessionData]:
        """List all sessions"""
        return db_manager.list_sessions(limit)
    
    @staticmethod
    def cleanup_session(session_id: str) -> bool:
        """Clean up a specific session"""
        try:
            # Remove from cache
            with _cache_lock:
                if session_id in _session_cache:
                    try:
                        _session_cache[session_id].cleanup()
                    except Exception as e:
                        print(f"[cleanup] Error cleaning ProcessingSession {session_id}: {e}")
                    del _session_cache[session_id]
            
            # Remove from database
            success = db_manager.delete_session(session_id)
            if success:
                print(f"[cleanup] Cleaned up session: {session_id}")
            return success
            
        except Exception as e:
            print(f"[cleanup] Error cleaning session {session_id}: {e}")
            return False
    
    @staticmethod
    def cleanup_old_sessions() -> int:
        """Clean up old sessions"""
        try:
            # Get sessions to cleanup before deleting from database
            old_sessions = []
            current_time = time.time()
            sessions = db_manager.list_sessions()
            
            for session_data in sessions:
                if current_time - session_data.created_at > CLEANUP_INTERVAL:
                    old_sessions.append(session_data.session_id)
            
            # Clean up ProcessingSession objects from cache
            with _cache_lock:
                for session_id in old_sessions:
                    if session_id in _session_cache:
                        try:
                            _session_cache[session_id].cleanup()
                        except Exception as e:
                            print(f"[cleanup] Error cleaning ProcessingSession {session_id}: {e}")
                        del _session_cache[session_id]
            
            # Clean up from database
            deleted_count = db_manager.cleanup_old_sessions(CLEANUP_INTERVAL)
            
            if deleted_count > 0:
                print(f"[cleanup] Cleaned up {deleted_count} old sessions")
            
            return deleted_count
            
        except Exception as e:
            print(f"[cleanup] Error during cleanup: {e}")
            return 0
    
    @staticmethod
    def get_session_counts() -> Dict[str, int]:
        """Get session statistics"""
        return {
            "active_sessions": db_manager.get_active_sessions_count(),
            "processing_sessions": db_manager.get_processing_sessions_count(),
            "cached_sessions": len(_session_cache)
        }
    
    @staticmethod
    def initialize():
        """Initialize the SessionManager"""
        try:
            print(f"[session_manager] Initializing SQLite-based SessionManager")
            
            # Database is already initialized in db_manager
            counts = SessionManager.get_session_counts()
            print(f"[session_manager] Found {counts['active_sessions']} existing sessions in database")
            print(f"[session_manager] Initialization complete")
            
        except Exception as e:
            print(f"[session_manager] ERROR during initialize(): {e}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def shutdown():
        """Clean shutdown of SessionManager"""
        try:
            print("[session_manager] Shutting down...")
            
            # Clean up all cached ProcessingSession objects
            with _cache_lock:
                for session_id, processing_session in _session_cache.items():
                    try:
                        processing_session.cleanup()
                    except Exception as e:
                        print(f"[shutdown] Error cleaning session {session_id}: {e}")
                _session_cache.clear()
            
            # Close database connections
            db_manager.close_all_connections()
            print("[session_manager] Shutdown complete")
            
        except Exception as e:
            print(f"[session_manager] Error during shutdown: {e}")

# Background task tracking (still needed for cancellation)
_background_tasks: Dict[str, object] = {}
_tasks_lock = threading.Lock()

def set_background_task(session_id: str, task):
    """Set background task for a session"""
    with _tasks_lock:
        _background_tasks[session_id] = task

def get_background_task(session_id: str):
    """Get background task for a session"""
    with _tasks_lock:
        return _background_tasks.get(session_id)

def remove_background_task(session_id: str):
    """Remove background task for a session"""
    with _tasks_lock:
        _background_tasks.pop(session_id, None)

def cancel_background_task(session_id: str) -> bool:
    """Cancel background task for a session"""
    with _tasks_lock:
        if task := _background_tasks.get(session_id):
            task.cancel()
            del _background_tasks[session_id]
            return True
        return False