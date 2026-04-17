"""
Memory store: persistent state for rollback signals, failure history, and audit trails.
"""

from datetime import datetime, timezone
from typing import List, Dict


class MemoryStore:
    def __init__(self):
        self.data = {}
        self.audit_log: List[Dict] = []

    def add_memory(self, key: str, value: dict):
        """Store a memory event."""
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)

    def get_memory(self, key: str) -> list:
        """Retrieve all memory events for a key."""
        return self.data.get(key, [])

    def has_prior_failure(self, key: str) -> bool:
        """Check if a failure mode was previously recorded."""
        return len(self.data.get(key, [])) > 0

    def clear_memory(self, key: str):
        """Clear memory for a key."""
        if key in self.data:
            del self.data[key]
    
    def write_audit(self, entry: Dict) -> None:
        """Append audit log entry with timestamp."""
        entry_with_ts = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **entry
        }
        self.audit_log.append(entry_with_ts)
    
    def get_audit_log(self) -> List[Dict]:
        """Retrieve full audit log."""
        return list(self.audit_log)
    
    def clear_audit_log(self) -> None:
        """Clear audit log (use with caution)."""
        self.audit_log = []


# Global memory instance
memory = MemoryStore()
