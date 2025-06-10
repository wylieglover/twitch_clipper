from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class SessionData:
    """Data class for session information"""
    session_id: str
    created_at: float
    status: str = "active"
    results: List[Dict] = None
    current_step: str = ""
    progress: int = 0
    last_activity: float = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
        if self.last_activity is None:
            self.last_activity = self.created_at