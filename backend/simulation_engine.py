"""
simulation_engine.py — ARIA-Lite++
Generates outcome probability distributions from real risk factors.
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent


def run_simulation(parsed: "ParsedIntent", trust: Dict) -> List[Dict]:
    """
    Generates outcome scenarios based on blast radius, reversibility,
    confidence, risk signals, and environment.
    """
    blast = trust["blast_radius"]
    rev   = trust["reversibility"]
    conf  = trust["confidence"]

    risk_score = blast + (1.0 - rev)

    if "extreme_scale" in parsed.risk_signals:
        risk_score += 0.20
    if "prod_destructive" in parsed.risk_signals:
        risk_score += 0.15
    if "admin_privilege" in parsed.risk_signals:
        risk_score += 0.10
    if parsed.environment == "production":
        risk_score += 0.10

    risk_score = min(1.0, risk_score)

    success_raw  = int((1.0 - risk_score) * conf * 100)
    success_prob = max(5, min(90, success_raw))

    # Rollback only meaningful when blast > 0.10 or scale > 5
    scale = parsed.scope.get("scale_factor", 1)
    rollback_prob = 0
    if blast > 0.10 or scale > 5:
        rollback_prob = max(5, int(blast * 20 + max(0, scale - 5) * 1.5))
        rollback_prob = min(rollback_prob, 25)

    cascade_prob = max(0, int(blast * 25))
    degraded_prob = max(0, 100 - success_prob - rollback_prob - cascade_prob)

    scenarios = [
        {
            "scenario":    "Successful execution",
            "probability": success_prob,
            "detail":      f"{parsed.service.upper()} state matches intent.",
            "type":        "success",
        },
        {
            "scenario":    "Degraded execution",
            "probability": degraded_prob,
            "detail":      "Partial completion — retry required on one step.",
            "type":        "degraded",
        },
        {
            "scenario":    "Cascade failure",
            "probability": cascade_prob,
            "detail":      f"Downstream impact on {trust.get('affected_count', 0)} resource(s).",
            "type":        "cascading_failure",
        },
        {
            "scenario":    "Rollback triggered",
            "probability": rollback_prob,
            "detail":      "Auto-rollback armed — compensating transaction required.",
            "type":        "rollback",
        },
    ]

    # Normalize to exactly 100
    total = sum(s["probability"] for s in scenarios)
    if total != 100 and scenarios:
        scenarios[0]["probability"] += 100 - total

    return [s for s in scenarios if s["probability"] > 0]
