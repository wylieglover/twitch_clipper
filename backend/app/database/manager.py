import sqlite3
import json
import time
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional
import platform
import tempfile
import os

from app.database.models import SessionData

# Cross-platform database path
if platform.system() == "Windows":
    DB_PATH = os.path.join(
        os.environ.get("TEMP", tempfile.gettempdir()),
        "twitch_sessions.db"
    )
else:
    DB_PATH = "/tmp/twitch_sessions.db"

# Thread-local storage for database connections
_local = threading.local()

class DatabaseManager:
    """Manages SQLite database operations with thread safety"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection"""
        if not hasattr(_local, 'connection'):
            _local.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            _local.connection.row_factory = sqlite3.Row
            _local.connection.execute("PRAGMA journal_mode=WAL")
            _local.connection.execute("PRAGMA synchronous=NORMAL")
            _local.connection.execute("PRAGMA temp_store=MEMORY")
            _local.connection.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        try:
            yield _local.connection
        except Exception as e:
            _local.connection.rollback()
            raise e
    
    def init_database(self):
        """Initialize database schema"""
        with self._lock:
            with self.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        created_at REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        results TEXT NOT NULL DEFAULT '[]',
                        current_step TEXT DEFAULT '',
                        progress INTEGER DEFAULT 0,
                        last_activity REAL NOT NULL,
                        error TEXT,
                        updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
                    )
                """)
                
                # Create index for efficient cleanup queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_last_activity 
                    ON sessions(last_activity)
                """)
                
                # Create index for status queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_status 
                    ON sessions(status)
                """)
                
                conn.commit()
                print(f"[database] Initialized SQLite database at {self.db_path}")
    
    def create_session(self, session_data: SessionData) -> bool:
        """Create a new session"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO sessions (
                        session_id, created_at, status, results, 
                        current_step, progress, last_activity, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_data.session_id,
                    session_data.created_at,
                    session_data.status,
                    json.dumps(session_data.results),
                    session_data.current_step,
                    session_data.progress,
                    session_data.last_activity,
                    session_data.error
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Session already exists
        except Exception as e:
            print(f"[database] Error creating session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM sessions WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                
                if row:
                    return SessionData(
                        session_id=row['session_id'],
                        created_at=row['created_at'],
                        status=row['status'],
                        results=json.loads(row['results']),
                        current_step=row['current_step'],
                        progress=row['progress'],
                        last_activity=row['last_activity'],
                        error=row['error']
                    )
                return None
        except Exception as e:
            print(f"[database] Error getting session {session_id}: {e}")
            return None
    
    def update_session(self, session_data: SessionData) -> bool:
        """Update existing session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE sessions SET 
                        status = ?, results = ?, current_step = ?, 
                        progress = ?, last_activity = ?, error = ?,
                        updated_at = strftime('%s', 'now')
                    WHERE session_id = ?
                """, (
                    session_data.status,
                    json.dumps(session_data.results),
                    session_data.current_step,
                    session_data.progress,
                    session_data.last_activity,
                    session_data.error,
                    session_data.session_id
                ))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[database] Error updating session {session_data.session_id}: {e}")
            return False
    
    def update_last_activity(self, session_id: str) -> bool:
        """Update just the last_activity timestamp"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE sessions SET 
                        last_activity = ?, 
                        updated_at = strftime('%s', 'now')
                    WHERE session_id = ?
                """, (time.time(), session_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[database] Error updating last activity for {session_id}: {e}")
            return False
    
    def add_result_to_session(self, session_id: str, result: Dict) -> bool:
        """Add a result to session's results array"""
        try:
            with self.get_connection() as conn:
                # Get current results
                cursor = conn.execute("""
                    SELECT results FROM sessions WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                
                if row:
                    current_results = json.loads(row['results'])
                    current_results.append(result)
                    
                    cursor = conn.execute("""
                        UPDATE sessions SET 
                            results = ?, 
                            last_activity = ?,
                            updated_at = strftime('%s', 'now')
                        WHERE session_id = ?
                    """, (json.dumps(current_results), time.time(), session_id))
                    conn.commit()
                    return cursor.rowcount > 0
                return False
        except Exception as e:
            print(f"[database] Error adding result to session {session_id}: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM sessions WHERE session_id = ?
                """, (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[database] Error deleting session {session_id}: {e}")
            return False
    
    def list_sessions(self, limit: Optional[int] = None) -> List[SessionData]:
        """List all sessions, optionally limited"""
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT * FROM sessions 
                    ORDER BY last_activity DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                
                sessions = []
                for row in rows:
                    sessions.append(SessionData(
                        session_id=row['session_id'],
                        created_at=row['created_at'],
                        status=row['status'],
                        results=json.loads(row['results']),
                        current_step=row['current_step'],
                        progress=row['progress'],
                        last_activity=row['last_activity'],
                        error=row['error']
                    ))
                return sessions
        except Exception as e:
            print(f"[database] Error listing sessions: {e}")
            return []
    
    def cleanup_old_sessions(self, max_age_seconds: int) -> int:
        """Remove sessions older than max_age_seconds"""
        try:
            cutoff_time = time.time() - max_age_seconds
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM sessions 
                    WHERE created_at < ?
                """, (cutoff_time,))
                conn.commit()
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    print(f"[database] Cleaned up {deleted_count} old sessions")
                
                return deleted_count
        except Exception as e:
            print(f"[database] Error during cleanup: {e}")
            return 0
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM sessions
                """)
                row = cursor.fetchone()
                return row['count'] if row else 0
        except Exception as e:
            print(f"[database] Error getting session count: {e}")
            return 0
    
    def get_processing_sessions_count(self) -> int:
        """Get count of sessions currently processing"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM sessions 
                    WHERE status = 'processing'
                """)
                row = cursor.fetchone()
                return row['count'] if row else 0
        except Exception as e:
            print(f"[database] Error getting processing session count: {e}")
            return 0
    
    def close_all_connections(self):
        """Close all database connections"""
        if hasattr(_local, 'connection'):
            try:
                _local.connection.close()
                delattr(_local, 'connection')
            except:
                pass

# Global database manager instance
db_manager = DatabaseManager()