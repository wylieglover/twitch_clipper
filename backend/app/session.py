import os
import shutil
import tempfile
import threading
from typing import Optional, List
import uuid
import time

BASE_OUTPUT_DIR = os.path.abspath("output")
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

class Session:
    """Manages isolated session for each user/request with thread safety"""
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.output_dir = os.path.join(BASE_OUTPUT_DIR, self.session_id)
        self.created_at = time.time()
        self.lock = threading.Lock()  # Thread safety for concurrent operations
        self.temp_dirs: List[str] = []  # Track temp dirs for cleanup
        self.is_active = True
        
        # Create session directory
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"[session] Created session {self.session_id} at {self.output_dir}")
    
    def cleanup(self):
        """Clean up session directory and temp dirs - thread safe"""
        with self.lock:
            if not self.is_active:
                return  # Already cleaned up
            
            try:
                # Clean up any tracked temp directories
                for temp_dir in self.temp_dirs:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"[session] Cleaned temp dir: {temp_dir}")
                
                # Clean up session directory
                if os.path.exists(self.output_dir):
                    shutil.rmtree(self.output_dir)
                    print(f"[session] Cleaned session directory: {self.output_dir}")
                
                self.is_active = False
                print(f"[session] Session {self.session_id} cleaned up successfully")
                
            except Exception as e:
                print(f"[cleanup] Error cleaning session {self.session_id}: {e}")
    
    def create_temp_dir(self, prefix: str = "") -> str:
        """Create and track temporary directory - thread safe"""
        with self.lock:
            if not self.is_active:
                raise RuntimeError(f"Session {self.session_id} is no longer active")
            
            temp_dir = tempfile.mkdtemp(dir=self.output_dir, prefix=prefix)
            self.temp_dirs.append(temp_dir)
            print(f"[session] Created temp dir: {temp_dir}")
            return temp_dir
    
    def remove_temp_dir(self, temp_dir: str):
        """Remove a single temp dir and stop tracking it."""
        with self.lock:
            if temp_dir in self.temp_dirs:
                try:
                    shutil.rmtree(temp_dir)
                    self.temp_dirs.remove(temp_dir)
                    print(f"[session] Removed temp dir: {temp_dir}")
                except Exception as e:
                    print(f"[session] Error removing temp dir {temp_dir}: {e}")
                    
    def get_file_path(self, filename: str) -> str:
        """Get file path within session directory"""
        if not self.is_active:
            raise RuntimeError(f"Session {self.session_id} is no longer active")
        return os.path.join(self.output_dir, filename)
    
    def list_files(self) -> List[str]:
        """List all files in the session directory"""
        if not self.is_active or not os.path.exists(self.output_dir):
            return []
        
        files = []
        for root, dirs, filenames in os.walk(self.output_dir):
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), self.output_dir)
                files.append(rel_path)
        return files
    
    def get_file_size(self, filename: str) -> int:
        """Get size of a file in the session directory"""
        file_path = self.get_file_path(filename)
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
    
    def get_session_size(self) -> int:
        """Get total size of all files in the session directory"""
        if not os.path.exists(self.output_dir):
            return 0
        
        total_size = 0
        for root, dirs, files in os.walk(self.output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
        return total_size
    
    def get_session_info(self) -> dict:
        """Get comprehensive session information"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "output_dir": self.output_dir,
            "is_active": self.is_active,
            "files": self.list_files(),
            "total_size_bytes": self.get_session_size(),
            "temp_dirs_count": len(self.temp_dirs)
        }
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically cleanup"""
        self.cleanup()
    
    def __del__(self):
        """Destructor - ensure cleanup happens"""
        if hasattr(self, 'is_active') and self.is_active:
            self.cleanup()