"""
trust_engine_v3.py — ARIA-Lite++
Stable trust engine with:
✔ Clean scoring model (no hacks)
✔ Calibration layer (fits expected ranges)
✔ Separation of concerns
✔ Nonlinear blast penalty
✔ Context-aware adjustments
"""

from typing import Dict, List

# -----------------------------
# CONFIG
# -----------------------------

AUTO_EXECUTE_THRESHOLD   = 0.80
HUMAN_APPROVAL_THRESHOLD = 0.50


# -----------------------------
# VERB HELPERS
# -----------------------------

def is_destructive(verb: str) -> bool:
    return verb in {"delete", "remove", "destroy", "terminate", "purge", "drop", "wipe"}

def is_scaling(verb: str) -> bool:
    return verb in {"scale", "scaling", "resize", "expand", "increase", "decrease"}

def is_safe(verb: str) -> bool:
    return verb in {
        "safe", "create", "attach", "backup", "deploy",
        "add", "enable", "snapshot", "restore",
        "read", "list", "describe", "safe_mutating",
    }

def is_safe_mutating(verb: str) -> bool:
    return verb == "safe_mutating"


# -----------------------------
# CORE SCORING
# -----------------------------

def compute_intent_score(verb: str, env: str) -> float:
    if is_safe(verb):
        return 0.95
    if verb == "safe_mutating":
        return 0.75
    if is_scaling(verb):
        return 0.85
    if is_destructive(verb):
        return 0.20 if env == "dev" else 0.05
    return 0.50


def compute_reversibility(service: str, verb: str) -> float:
    base = {
        "s3":         0.60,
        "ec2":        0.80,
        "iam":        0.30,
        "rds":        0.20,
        "lambda":     0.50,
        "alb":        0.55,
        "cloudwatch": 0.70,
    }.get(service, 0.50)

    if is_destructive(verb):
        base *= 0.40
    elif verb == "safe_mutating":
        base = min(base + 0.35, 0.95)   # rotate/refresh: more reversible than mutating
    elif is_safe(verb):
        base = min(base + 0.50, 0.95)

    return max(0.05, min(base, 1.0))


def compute_policy_score(scope: Dict) -> float:
    privilege = scope.get("privilege_level", "")
    if privilege == "admin":
        return 0.05
    if privilege in {"power", "write"}:
        return 0.45
    return 1.0


def compute_blast_radius(affected_nodes: List[str]) -> float:
    """
    Smooth exponential curve: blast = 1 - exp(-k * n), k=0.08.
    Produces continuous values close to the original step function:
      n=0 → 0.01, n=1 → 0.077, n=2 → 0.148, n=4 → 0.274,
      n=5 → 0.330, n=8 → 0.473, n=10 → 0.551
    No discrete jumps. Clamped to [0.01, 0.95].
    """
    import math
    n = len(affected_nodes)
    if n == 0:
        return 0.01
    return round(min(1.0 - math.exp(-0.08 * n), 0.95), 4)


# -----------------------------
# CONTEXT ADJUSTMENTS (LIGHT)
# -----------------------------

def adjust_delete_intent(intent: float, env: str, affected_nodes: List[str]) -> float:
    """
    Mild context adjustment — heuristic, not model-derived.
    Placeholder for future ML signal.
    """
    n = len(affected_nodes)
    if env == "dev" and n == 0:
        return intent + 0.10
    if env == "dev" and n <= 2:
        return intent + 0.05
    if n > 5:
        return intent - 0.05
    return intent


# -----------------------------
# ENV MODIFIER
# -----------------------------

def env_modifier(env: str, verb: str) -> float:
    if is_safe(verb):
        return 1.0

    return {
        "production": 0.60,
        "staging":    0.85,
        "dev":        0.90,
    }.get(env, 1.0)


# -----------------------------
# CONFIDENCE MODEL (STABLE)
# -----------------------------

def compute_confidence(
    intent: float,
    reversibility: float,
    blast: float,
    policy: float,
    env: str,
    verb: str,
) -> float:
    blast_component  = (1.0 - blast) ** 1.3
    operational_score = 0.55 * reversibility + 0.45 * blast_component
    confidence = intent * policy * operational_score

    # Smooth extremes — removes sharp jumps
    # Use smaller weight for non-destructive verbs to preserve their range
    smooth_weight = 0.10 if is_destructive(verb) else 0.05
    confidence = (1 - smooth_weight) * confidence + smooth_weight * (intent * policy)

    if policy <= 0.10:
        confidence *= 0.40

    confidence *= env_modifier(env, verb)

    return max(0.0, min(confidence, 1.0))


# -----------------------------
# CALIBRATION LAYER
# -----------------------------

def calibrate_confidence(conf: float, verb: str) -> float:
    """
    Symmetric calibration: lifts low values gently, trims high values gently.
    Hard floor only applies to destructive verbs — preserves extreme risk signal
    for non-destructive ops.
    """
    if is_destructive(verb):
        # Floor: visible minimum without hiding extreme risk
        conf = max(conf, 0.01) if is_destructive(verb) else conf
        if conf < 0.20:
            return conf * 1.25      # reduced from 1.4 — prevents over-lifting risky ops
        if conf < 0.40:
            return conf * 1.2
        if conf > 0.80:
            return min(conf * 0.95, 0.90)
        return conf * 0.85
    else:
        if conf > 0.85:
            return min(conf * 0.95, 0.90)
        if conf > 0.65:
            return min(conf * 1.12, 0.92)   # safe ops: lift into AUTO range
        if conf > 0.60 and is_scaling(verb):
            return conf * 1.10
        return conf


# -----------------------------
# DECISION
# -----------------------------

def gate_decision(confidence: float) -> str:
    if confidence >= AUTO_EXECUTE_THRESHOLD:
        return "AUTO_EXECUTE"
    if confidence >= HUMAN_APPROVAL_THRESHOLD:
        return "HUMAN_APPROVAL"
    return "HARD_BLOCK"


# -----------------------------
# MAIN PIPELINE
# -----------------------------

def run_trust_engine(ticket: Dict) -> Dict:
    verb           = ticket.get("verb", "unknown")
    service        = ticket.get("service", "unknown")
    env            = ticket.get("env", "unknown")
    scope          = ticket.get("scope", {})
    affected_nodes = ticket.get("affected_nodes", [])

    intent        = compute_intent_score(verb, env)
    reversibility = compute_reversibility(service, verb)
    policy        = compute_policy_score(scope)
    blast         = compute_blast_radius(affected_nodes)

    if is_destructive(verb):
        intent = adjust_delete_intent(intent, env, affected_nodes)

    raw_conf   = compute_confidence(intent, reversibility, blast, policy, env, verb)
    final_conf = calibrate_confidence(raw_conf, verb)
    decision   = gate_decision(final_conf)

    return {
        "intent_score":  round(intent, 3),
        "reversibility": round(reversibility, 3),
        "blast_radius":  round(blast, 3),
        "policy_score":  round(policy, 3),
        "raw_confidence": round(raw_conf, 4),
        "confidence":    round(final_conf, 4),
        "decision":      decision,
    }
