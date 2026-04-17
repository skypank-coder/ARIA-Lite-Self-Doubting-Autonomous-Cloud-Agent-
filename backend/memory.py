"""
Memory Store v5 — ARIA-Lite++
Cumulative incident tracking with pattern detection and graduated penalties.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any


class MemoryStore:
    def __init__(self):
        self.incidents: Dict[str, List[Dict]] = {}
        self.patterns:  Dict[str, str] = {}
        self.audit_log: List[Dict] = []

    # ── Incident recording ────────────────────────────────────────────────────

    def record(self, intent: str, outcome: str, note: str, confidence: float) -> None:
        if intent not in self.incidents:
            self.incidents[intent] = []
        self.incidents[intent].append({
            "outcome":    outcome,
            "note":       note,
            "confidence": confidence,
            "ts":         datetime.now(timezone.utc).isoformat(),
        })
        self._detect_pattern(intent)

    def _detect_pattern(self, intent: str) -> None:
        count = len(self.incidents.get(intent, []))
        if count >= 3:
            self.patterns[intent] = "REPEATED_FAILURE"
        elif count >= 2:
            self.patterns[intent] = "RECURRING_RISK"
        elif count == 1:
            self.patterns[intent] = "PRIOR_INCIDENT"

    # ── Legacy add_memory (backward compat) ───────────────────────────────────

    def add_memory(self, key: str, value: Dict) -> None:
        self.record(
            intent=key,
            outcome=value.get("outcome", "UNKNOWN"),
            note=value.get("note", ""),
            confidence=value.get("confidence", 0.0),
        )

    def get_memory(self, key: str) -> List[Dict]:
        return self.incidents.get(key, [])

    def has_prior_failure(self, key: str) -> bool:
        return len(self.incidents.get(key, [])) > 0

    def clear_memory(self, key: str) -> None:
        self.incidents.pop(key, None)
        self.patterns.pop(key, None)

    # ── Penalty computation ───────────────────────────────────────────────────

    def get_penalty(self, intent: str) -> Dict[str, Any]:
        """
        Returns graduated penalty dict.
        Each incident adds weight, capped at severity=3.
        """
        incidents = self.incidents.get(intent, [])
        count = len(incidents)
        if count == 0:
            return {"active": False, "note": None, "multiplier": 1.0}

        severity = min(count, 3)
        return {
            "active":                True,
            "count":                 count,
            "pattern":               self.patterns.get(intent, "PRIOR_INCIDENT"),
            "note":                  incidents[-1]["note"],
            "reversibility_penalty": 0.05 * severity,
            "policy_penalty":        0.05 * severity,
            "blast_penalty":         0.03 * severity,
            "multiplier":            max(0.70, 1.0 - (0.05 * severity)),
        }

    # ── Audit log ─────────────────────────────────────────────────────────────

    def write_audit(self, entry: Dict) -> None:
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **entry,
        })

    def get_audit_log(self) -> List[Dict]:
        return list(self.audit_log)

    def clear_audit_log(self) -> None:
        self.audit_log = []

    # ── Legacy data property (backward compat) ────────────────────────────────

    @property
    def data(self) -> Dict[str, List[Dict]]:
        return self.incidents


# Global singleton
memory = MemoryStore()
