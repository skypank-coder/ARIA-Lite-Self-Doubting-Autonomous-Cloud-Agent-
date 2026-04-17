"""
trust_engine_v2.py — ARIA-Lite++
Upgraded trust engine: weighted additive confidence, nonlinear blast penalty,
context-aware adjustments, environment modifier.
"""

from typing import Dict, List


# -----------------------------
# CONFIG
# -----------------------------

AUTO_EXECUTE_THRESHOLD   = 0.80
HUMAN_APPROVAL_THRESHOLD = 0.50


# -----------------------------
# PHASE 1 — VERB HELPERS
# -----------------------------

def is_destructive(verb: str) -> bool:
    return verb in {"delete", "remove", "destroy", "terminate", "purge", "drop", "wipe"}

def is_scaling(verb: str) -> bool:
    return verb in {"scale", "scaling", "resize", "expand", "increase", "decrease"}

def is_safe(verb: str) -> bool:
    return verb in {"safe", "create", "attach", "backup", "deploy", "add", "enable",
                    "snapshot", "restore", "read", "list", "describe"}


# -----------------------------
# PHASE 2 — COMPONENT SCORING
# -----------------------------

def compute_intent_score(verb: str, env: str) -> float:
    if is_safe(verb):
        return 0.95
    if is_scaling(verb):
        return 0.85
    if is_destructive(verb):
        # dev gets a higher base — less dangerous context
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
    elif is_safe(verb):
        # safe verbs (attach, create, backup) are highly reversible
        base = min(base + 0.50, 0.95)

    return max(0.05, min(base, 1.0))


def compute_policy_score(scope: Dict) -> float:
    privilege = scope.get("privilege_level", "")
    if privilege == "admin":
        return 0.05
    if privilege in {"power", "write"}:
        return 0.45
    # read_only, viewer, or unset → fully compliant
    return 1.0


def compute_blast_radius(affected_nodes: List[str]) -> float:
    """Nonlinear step function — each tier doubles the blast signal."""
    n = len(affected_nodes)
    if n == 0:
        return 0.01
    if n <= 2:
        return 0.05
    if n <= 5:
        return 0.15
    if n <= 8:
        return 0.30
    return 0.70


# -----------------------------
# CONTEXT ADJUSTMENTS
# -----------------------------

def adjust_delete_intent(intent: float, env: str, affected_nodes: List[str]) -> float:
    if env == "dev" and len(affected_nodes) == 0:
        return min(intent + 0.40, 0.65)  # isolated dev delete — meaningfully less alarming
    if env == "dev" and len(affected_nodes) <= 2:
        return min(intent + 0.20, 0.45)  # small blast dev delete
    if len(affected_nodes) > 5:
        return max(intent - 0.20, 0.01)
    return intent


def adjust_reversibility(r: float) -> float:
    """
    Soften the reversibility collapse at very low values.
    Prevents a single low-reversibility service from zeroing the whole score.
    """
    if r < 0.20:
        return r * 0.60
    return r


def env_modifier(env: str, verb: str = "unknown") -> float:
    """
    Multiplicative environment modifier.
    Only applied to destructive/scaling verbs — safe ops are not env-penalised.
    """
    if is_safe(verb):
        return 1.00   # safe ops unaffected by environment
    return {
        "production": 0.55,
        "staging":    0.85,
        "dev":        0.75,
    }.get(env, 1.00)


# -----------------------------
# FINAL CONFIDENCE
# -----------------------------

def compute_confidence(
    intent: float,
    reversibility: float,
    blast: float,
    policy: float,
    env: str,
    verb: str = "unknown",
) -> float:
    """
    Hybrid formula:
      - intent × policy acts as a multiplicative gate (both must be high)
      - reversibility and blast_component are averaged additively
      - env_modifier scales the result (only for non-safe verbs)

    This naturally produces:
      - Low intent OR low policy → low confidence (gate collapses)
      - High intent AND high policy → confidence driven by reversibility/blast
    """
    blast_component = (1.0 - blast) ** 1.5
    operational_score = 0.60 * reversibility + 0.40 * blast_component

    confidence = intent * policy * operational_score

    # Hard gate: critically low policy collapses further
    if policy <= 0.10:
        confidence *= 0.30

    confidence *= env_modifier(env, verb)

    return round(min(max(confidence, 0.01), 1.0), 4)

    return round(min(confidence, 1.0), 4)


# -----------------------------
# GATE DECISION
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
    """
    Full trust pipeline from a structured ticket dict.

    Expected keys:
        verb           : str   — action verb
        service        : str   — AWS service
        env            : str   — production / staging / dev / unknown
        scope          : dict  — {privilege_level, ...}
        affected_nodes : list  — downstream services impacted
    """
    verb           = ticket.get("verb", "unknown")
    service        = ticket.get("service", "unknown")
    env            = ticket.get("env", "unknown")
    scope          = ticket.get("scope", {})
    affected_nodes = ticket.get("affected_nodes", [])

    # Component scores
    intent        = compute_intent_score(verb, env)
    reversibility = compute_reversibility(service, verb)
    policy        = compute_policy_score(scope)
    blast         = compute_blast_radius(affected_nodes)

    # Context adjustments
    if is_destructive(verb):
        intent = adjust_delete_intent(intent, env, affected_nodes)

    reversibility = adjust_reversibility(reversibility)

    # Final confidence + gate
    confidence = compute_confidence(intent, reversibility, blast, policy, env, verb)
    decision   = gate_decision(confidence)

    return {
        "intent_score":  round(intent, 3),
        "reversibility": round(reversibility, 3),
        "blast_radius":  round(blast, 3),
        "policy_score":  round(policy, 3),
        "confidence":    confidence,
        "decision":      decision,
    }
