"""
ai_layer.py — ARIA-Lite++
Semantic AI adjustment layer: urgency, uncertainty, large-scale detection.
Hybrid rule-based + pattern reasoning — no external API required.
"""

import re
from typing import List, Tuple


def ai_adjustment(ticket: str, confidence: float) -> Tuple[float, List[str]]:
    """
    Applies semantic adjustments to confidence based on ticket language.
    Returns (adjusted_confidence, list_of_notes).
    """
    t     = ticket.lower()
    notes: List[str] = []

    # Urgency language
    if any(w in t for w in ["immediately", "urgent", "asap", "right now", "emergency", "hotfix"]):
        confidence *= 0.85
        notes.append("Urgency language increases operational risk")

    # Uncertainty / hedging
    if any(w in t for w in ["maybe", "possibly", "try", "might", "perhaps", "not sure"]):
        confidence *= 0.90
        notes.append("Uncertain intent detected — operator may not have full context")

    # Large numbers — only flag when scale context words are present
    _SCALE_CONTEXT = [
        "to", "from", "scale", "instance", "instances",
        "nodes", "replicas", "containers", "pods", "servers",
    ]
    numbers = re.findall(r"\b\d+\b", t)   # word-boundary: won't match digits inside words
    if numbers:
        max_val = max(map(int, numbers))
        has_scale_context = any(w in t for w in _SCALE_CONTEXT)
        if max_val > 100 and has_scale_context:
            confidence *= 0.75
            notes.append(f"Large-scale operation detected (max value: {max_val})")
        elif max_val > 50 and has_scale_context:
            confidence *= 0.88
            notes.append(f"Elevated scale detected (max value: {max_val})")

    # Explicit risk language
    if any(w in t for w in ["all", "every", "entire", "whole", "global"]):
        confidence *= 0.85
        notes.append("Broad-scope language — operation may affect more than intended")

    # No-backup / no-rollback language
    if any(w in t for w in ["no backup", "no rollback", "without backup", "skip backup"]):
        confidence *= 0.80
        notes.append("No safety net language detected")

    return round(confidence, 4), notes
