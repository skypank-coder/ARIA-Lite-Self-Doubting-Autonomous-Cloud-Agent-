"""
self_doubt.py — ARIA-Lite++
Second-pass reasoning: returns structured factor list with type, msg, impact.
"""

from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent


def apply_self_doubt(
    parsed: "ParsedIntent",
    trust: Dict,
    confidence: float,
) -> Tuple[float, List[Dict]]:
    factors: List[Dict] = []

    verb = getattr(parsed, "action_verb", "")
    raw  = getattr(parsed, "raw_ticket", "").lower()

    # 1. Safe wording + destructive action
    if ("safe" in raw or "safely" in raw) and verb == "destructive":
        confidence *= 0.80
        factors.append({
            "type":   "CONTRADICTION",
            "msg":    "Safe wording conflicts with destructive action",
            "impact": "-20%",
        })

    # 2. Contradiction signals from parser
    if getattr(parsed, "contradictions", []):
        confidence *= 0.85
        factors.append({
            "type":   "CONTRADICTION",
            "msg":    f"Parser detected: {parsed.contradictions[0]}",
            "impact": "-15%",
        })

    # 3. High blast but high confidence
    if trust["blast_radius"] > 0.25 and confidence > 0.60:
        confidence *= 0.75
        factors.append({
            "type":   "OVERCONFIDENCE",
            "msg":    "High blast radius but high confidence",
            "impact": "-25%",
        })

    # 4. Extreme scaling
    scale = getattr(parsed, "scope", {}).get("scale_factor", 1)
    if scale > 20:
        confidence *= 0.70
        factors.append({
            "type":   "EXTREME_SCALE",
            "msg":    f"Scaling factor {scale} exceeds safe threshold",
            "impact": "-30%",
        })

    # 5. Production destructive
    if getattr(parsed, "environment", "") == "production" and verb == "destructive":
        confidence *= 0.75
        factors.append({
            "type":   "PROD_RISK",
            "msg":    "Destructive action in production",
            "impact": "-25%",
        })

    # 6. Unknown environment — only penalise risky verbs, not safe/safe_mutating
    _risky_verbs = {"destructive", "mutating", "risky_mutating", "scaling"}
    if getattr(parsed, "environment", "unknown") == "unknown" and verb in _risky_verbs:
        confidence *= 0.90
        factors.append({
            "type":   "UNKNOWN_ENV",
            "msg":    "Environment context unknown — scoring less reliable",
            "impact": "-10%",
        })

    return round(confidence, 4), factors
