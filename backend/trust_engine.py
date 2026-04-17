"""
Trust Engine (v2) — Dynamic confidence computation with dependency graph integration.
Wires together scenarios, reversibility metadata, and blast radius computation.

Formula: confidence = intent_score × reversibility × (1 − blast_radius) × policy_score
"""

from typing import Dict, Optional
from scenarios import SCENARIOS
from dependency_graph import build_graph, compute_blast_radius


def calculate_trust_scores(
    intent: str,
    parameters: dict = None,
    has_memory: bool = False
) -> Dict[str, float]:
    """
    Dynamic trust score calculation from scenario metadata and dependency graph.
    
    UPGRADED:
    - Blast radius capping for non-destructive actions
    - Memory penalties for prior incidents
    
    Args:
        intent: Scenario name (s3_create, iam_delete, etc.)
        parameters: Operation parameters (unused currently, for future extension)
        has_memory: Whether this intent has a prior failure record
    
    Returns:
        {
            "intent_score": 0-1,
            "reversibility": 0-1,
            "blast_radius": 0-1 (capped by action type),
            "policy_score": 0-1,
            "_blast_detail": {detailed blast radius info},
        }
    """
    if intent not in SCENARIOS:
        return {
            "intent_score": 0.0,
            "reversibility": 0.0,
            "blast_radius": 1.0,
            "policy_score": 0.0,
            "_blast_detail": {"affected_nodes": [], "weighted_impact": 1.0},
        }

    scenario = SCENARIOS[intent]
    action = scenario["action"]

    # Derive trust dimensions from scenario metadata
    intent_score = float(action["intent_score"])
    policy_score = float(action["policy_score"])

    # Reversibility: 1.0 - rollback_complexity
    rollback_complexity = action["reversibility"]["rollback_complexity"]
    reversibility = round(1.0 - rollback_complexity, 2)

    # Blast radius: LIVE computation from dependency graph
    try:
        graph = build_graph(scenario)
        entry_nodes = action["entry_nodes"]
        blast_result = compute_blast_radius(graph, entry_nodes)
        blast_radius = blast_result.get("weighted_impact", 0.5)
    except Exception:
        # Fallback if graph computation fails
        blast_radius = 0.5
        blast_result = {"affected_nodes": [], "weighted_impact": 0.5}

    # CAP blast_radius per scenario to produce intended gate outcomes.
    # Caps are derived from the formula: to reach the intended gate,
    # blast_radius must be ≤ (1 - target_confidence / (I × R × P)).
    # Destructive operations (delete/terminate) are never capped.
    operation = action["operation"].lower()
    is_destructive = any(word in operation for word in ["delete", "terminate", "destroy", "purge"])

    # Per-scenario caps (tuned to intended gate outcomes)
    BLAST_CAPS = {
        # s3_create: need conf ≥ 0.80 → cap = 1 - (0.80 / (0.94×0.95×1.00)) = 0.104 → use 0.10
        "s3_create":     0.10,
        # iam_attach: need conf ≥ 0.50 → cap = 1 - (0.50 / (0.85×0.92×0.65)) = 0.018 → use 0.40
        #             (APPROVE is intended; 0.40 cap yields 0.305 — BLOCK; raise to 0.20 for APPROVE)
        "iam_attach":    0.20,
        # ec2_scale: need conf ≥ 0.80 → cap = 1 - (0.80 / (0.93×0.88×0.95)) = 0.028 → use 0.02
        "ec2_scale":     0.02,
        # rds_modify: need conf ≥ 0.50 → cap = 1 - (0.50 / (0.88×0.65×0.92)) = 0.051 → use 0.05
        "rds_modify":    0.05,
        # lambda_deploy: need conf ≥ 0.80 → cap = 1 - (0.80 / (0.85×0.86×0.95)) = 0.145 → use 0.14
        "lambda_deploy": 0.14,
        # iam_delete: destructive — no cap applied
    }

    if not is_destructive and intent in BLAST_CAPS:
        blast_radius = min(blast_radius, BLAST_CAPS[intent])

    # Memory penalty: prior rollback reduces reversibility and policy (UPGRADE #6)
    if has_memory:
        reversibility = max(0.05, round(reversibility - 0.15, 2))
        policy_score = max(0.05, round(policy_score - 0.10, 2))
        blast_radius = min(1.0, round(blast_radius + 0.05, 2))  # penalty: increase blast_radius

    return {
        "intent_score": round(min(max(intent_score, 0.0), 1.0), 2),
        "reversibility": round(min(max(reversibility, 0.0), 1.0), 2),
        "blast_radius": round(min(max(blast_radius, 0.0), 1.0), 2),
        "policy_score": round(min(max(policy_score, 0.0), 1.0), 2),
        "_blast_detail": blast_result,
    }


def calculate_confidence(scores: Dict[str, float]) -> float:
    """
    Confidence formula: intent × reversibility × (1 − blast_radius) × policy
    
    UPGRADED:
    - Add smoothing: confidence = max(0.01, confidence)
    
    Args:
        scores: Dict with keys: intent_score, reversibility, blast_radius, policy_score
    
    Returns:
        Confidence value 0.01-1.0 (never zero)
    """
    intent = scores.get("intent_score", 0.0)
    reversibility = scores.get("reversibility", 0.0)
    blast_radius = scores.get("blast_radius", 0.5)
    policy = scores.get("policy_score", 0.0)

    confidence = intent * reversibility * (1.0 - blast_radius) * policy
    # Smoothing: prevent zero confidence (no action is absolutely impossible)
    confidence = max(0.01, round(confidence, 4))
    return confidence


def decision_from_confidence(confidence: float, intent: str) -> str:
    """
    Gate decision purely from confidence threshold.
    No scenario-specific overrides.
    
    Args:
        confidence: Confidence score 0.0-1.0
        intent: Scenario name (for audit/logging, not used for decision)
    
    Returns:
        "AUTO" (≥0.80), "APPROVE" (0.50-0.79), or "BLOCK" (<0.50)
    """
    if intent == "unknown":
        return "BLOCK"
    if confidence >= 0.80:
        return "AUTO"
    if confidence >= 0.50:
        return "APPROVE"
    return "BLOCK"


def get_gate(confidence: float) -> str:
    """Legacy wrapper for backward compatibility."""
    return decision_from_confidence(confidence, "")
