"""
self_doubt.py — ARIA-Lite++
Second-pass reasoning: returns structured factor list with type, msg, impact.
"""

from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent


def generate_self_doubt(parsed: "ParsedIntent", trust: Dict, graph: Dict = None) -> List[Dict]:
    """
    Generates display-facing self-doubt flags.
    Always includes UNCERTAINTY. Additional flags are context-driven.
    impact is a float (fraction of confidence affected).
    """
    doubts: List[Dict] = []
    graph = graph or {}
    node_count = len(graph.get("nodes", []))

    # Always present
    doubts.append({
        "type":   "UNCERTAINTY",
        "msg":    "Model confidence is probabilistic, not deterministic.",
        "impact": 0.05,
    })

    verb = getattr(parsed, "action_verb", "")
    _risky_verbs = {"destructive", "mutating", "risky_mutating", "scaling"}

    if trust.get("confidence", 1.0) < 0.30:
        doubts.append({
            "type":   "LOW_CONFIDENCE",
            "msg":    f"Confidence {trust['confidence']:.2f} — decision reliability is low.",
            "impact": 0.10,
        })

    if trust.get("policy_score", 1.0) < 0.20:
        doubts.append({
            "type":   "POLICY_RISK",
            "msg":    f"Policy score {trust['policy_score']:.2f} — high-privilege policy introduces hidden risks.",
            "impact": 0.15,
        })

    if trust.get("blast_radius", 0.0) > 0.30:
        node_str = f"{node_count} dependent service(s)" if node_count else "downstream services"
        doubts.append({
            "type":   "CASCADE_RISK",
            "msg":    f"Blast radius {trust['blast_radius']:.2f} — {node_str} may be affected.",
            "impact": 0.10,
        })

    if getattr(parsed, "environment", "unknown") == "unknown" and verb in _risky_verbs:
        doubts.append({
            "type":   "UNKNOWN_ENV",
            "msg":    "Environment not specified — routing to human review.",
            "impact": 0.10,
        })

    scale = getattr(parsed, "scope", {}).get("scale_factor", 1)
    if scale > 20:
        doubts.append({
            "type":   "EXTREME_SCALE",
            "msg":    f"Scale factor {scale:.0f}× exceeds safe operational threshold.",
            "impact": 0.15,
        })

    if getattr(parsed, "contradictions", []):
        doubts.append({
            "type":   "CONTRADICTION",
            "msg":    f"Conflicting signals: {parsed.contradictions[0].split(':')[0]}",
            "impact": 0.15,
        })

    if getattr(parsed, "environment", "") == "production" and verb == "destructive":
        doubts.append({
            "type":   "PROD_RISK",
            "msg":    "Production environment detected — elevated caution applied.",
            "impact": 0.15,
        })

    return doubts


def apply_self_doubt(
    parsed: "ParsedIntent",
    trust: Dict,
    confidence: float,
) -> Tuple[float, List[Dict]]:
    factors: List[Dict] = []
    verb = getattr(parsed, "action_verb", "")
    raw  = getattr(parsed, "raw_ticket", "").lower()

    # CONTRADICTION ×0.85
    if ("safe" in raw or "safely" in raw) and verb == "destructive":
        confidence *= 0.85
        factors.append({"type": "CONTRADICTION", "msg": "Safe wording conflicts with destructive action", "impact": "-15%"})

    if getattr(parsed, "contradictions", []):
        confidence *= 0.85
        factors.append({"type": "CONTRADICTION", "msg": f"Parser detected: {parsed.contradictions[0]}", "impact": "-15%"})

    # PROD_RISK ×0.80
    if getattr(parsed, "environment", "") == "production" and verb == "destructive":
        confidence *= 0.80
        factors.append({"type": "PROD_RISK", "msg": "Destructive action in production", "impact": "-20%"})

    # CASCADE_RISK ×0.90
    if trust["blast_radius"] > 0.25 and confidence > 0.50:
        confidence *= 0.90
        factors.append({"type": "CASCADE_RISK", "msg": f"Blast radius {trust['blast_radius']:.2f} — cascade risk", "impact": "-10%"})

    # EXTREME_SCALE ×0.80
    scale = getattr(parsed, "scope", {}).get("scale_factor", 1)
    if scale > 20:
        confidence *= 0.80
        factors.append({"type": "EXTREME_SCALE", "msg": f"Scale factor {scale} exceeds safe threshold", "impact": "-20%"})

    # UNKNOWN_ENV ×0.95 (safe verbs) / ×0.85 (risky verbs)
    _safe_verbs  = {"safe", "safe_mutating", "read"}
    _risky_verbs = {"destructive", "mutating", "risky_mutating", "scaling"}
    if getattr(parsed, "environment", "unknown") == "unknown":
        if verb in _safe_verbs:
            confidence *= 0.95
            factors.append({"type": "UNKNOWN_ENV", "msg": "Environment unknown — minor scoring uncertainty", "impact": "-5%"})
        elif verb in _risky_verbs:
            confidence *= 0.85
            factors.append({"type": "UNKNOWN_ENV", "msg": "Environment context unknown — scoring less reliable", "impact": "-15%"})

    return round(confidence, 4), factors
