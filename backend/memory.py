"""
memory.py — ARIA-Lite++
Production-ready memory store with 3-key keying, verb normalization,
exponential decay penalty, and pattern detection.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any


class Memory:
    def __init__(self):
        self.patterns:  Dict[str, Dict] = {}   # key → {count, history}
        self.audit_log: List[Dict] = []

    # ── Normalization ─────────────────────────────────────────────────────────

    def normalize_verb(self, verb: str) -> str:
        if verb in {"delete", "remove", "destroy", "purge", "drop",
                    "terminate", "wipe", "revoke"}:
            return "destructive"
        if verb in {"scale", "increase", "decrease", "resize",
                    "expand", "shrink", "autoscale"}:
            return "scaling"
        if verb in {"create", "attach", "deploy", "add", "enable",
                    "backup", "snapshot", "restore"}:
            return "safe"
        if verb in {"modify", "update", "change", "configure",
                    "patch", "rotate", "mutating"}:
            return "mutating"
        return verb

    def build_key(self, service: str, verb: str, env: str) -> str:
        norm = self.normalize_verb(verb)
        return f"{service}_{norm}_{env}"

    # ── Record ────────────────────────────────────────────────────────────────

    def record(self, service: str = None, verb: str = None, env: str = None,
               outcome: str = "UNKNOWN", confidence: float = 0.0, note: str = "",
               gate: str = "",
               intent: str = None, **kwargs) -> None:
        """
        Record an incident. Supports both new 3-key API and legacy intent-key API.
        """
        if intent is not None:
            key = intent
        else:
            key = self.build_key(service or "unknown", verb or "unknown", env or "unknown")

        if key not in self.patterns:
            self.patterns[key] = {"count": 0, "history": [], "confidence_timeline": []}

        self.patterns[key]["count"] += 1
        self.patterns[key]["history"].append({
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "outcome":    outcome,
            "confidence": confidence,
            "note":       note,
        })

        # Confidence timeline — capped at 8 entries
        tl = self.patterns[key]["confidence_timeline"]
        tl.append({
            "confidence": round(confidence, 3),
            "gate":       gate or ("AUTO" if confidence >= 0.80 else "APPROVE" if confidence >= 0.50 else "BLOCK"),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        })
        if len(tl) > 8:
            self.patterns[key]["confidence_timeline"] = tl[-8:]

    # ── Penalty ───────────────────────────────────────────────────────────────

    def get_penalty(self, service: str = None, verb: str = None, env: str = None,
                    intent: str = None) -> Dict[str, Any]:
        """
        Returns penalty dict. Supports both new 3-key API and legacy intent-key API.
        """
        if intent is not None:
            key = intent
        else:
            key = self.build_key(service or "unknown", verb or "unknown", env or "unknown")

        if key not in self.patterns:
            return {"count": 0, "penalty": 1.0, "active": False,
                    "pattern": None, "note": None}

        count = self.patterns[key]["count"]
        decay = round(max(0.70, 1.0 - 0.08 * count), 3)

        history = self.patterns[key]["history"]
        last_note = history[-1]["note"] if history else None

        pattern = (
            "REPEATED_FAILURE" if count >= 3 else
            "RECURRING_RISK"   if count >= 2 else
            "PRIOR_INCIDENT"
        )

        return {
            "count":   count,
            "penalty": decay,
            "active":  True,
            "pattern": pattern,
            "note":    last_note,
            # legacy fields
            "multiplier":            decay,
            "reversibility_penalty": 0.05 * min(count, 3),
            "policy_penalty":        0.05 * min(count, 3),
            "blast_penalty":         0.03 * min(count, 3),
        }

    # ── Audit ─────────────────────────────────────────────────────────────────

    def write_audit(self, data: Dict) -> None:
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

    def get_audit_log(self) -> List[Dict]:
        return list(self.audit_log)

    def clear_audit_log(self) -> None:
        self.audit_log = []

    # ── Legacy compat ─────────────────────────────────────────────────────────

    def add_memory(self, key: str, value: Dict) -> None:
        self.record(intent=key, outcome=value.get("outcome", "UNKNOWN"),
                    note=value.get("note", ""), confidence=value.get("confidence", 0.0))

    def get_memory(self, key: str) -> List[Dict]:
        return self.patterns.get(key, {}).get("history", [])

    def has_prior_failure(self, key: str) -> bool:
        return self.patterns.get(key, {}).get("count", 0) > 0

    def clear_memory(self, key: str) -> None:
        self.patterns.pop(key, None)

    def get_timeline(self, service: str) -> List[Dict]:
        """Return all memory entries whose key starts with service."""
        result = []
        for key, val in self.patterns.items():
            if key.startswith(service + "_"):
                count = val["count"]
                decay = round(max(0.70, 1.0 - 0.08 * count), 3)
                result.append({
                    "key":     key,
                    "count":   count,
                    "penalty": decay,
                    "history": val.get("confidence_timeline", []),
                })
        return result

    @property
    def total_count(self) -> int:
        return sum(v["count"] for v in self.patterns.values())

    @property
    def incidents(self) -> Dict:
        return {k: v["history"] for k, v in self.patterns.items()}

    @property
    def data(self) -> Dict:
        return self.incidents


# Global singleton
memory = Memory()
