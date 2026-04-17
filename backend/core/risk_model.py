"""
V2 Risk Model: Multi-dimensional, parameter-driven infrastructure risk computation.

Computes:
- Availability Risk: How likely is service disruption?
- Security Risk: How likely is unauthorized access or data exposure?
- Cost Risk: How likely is unexpected cost increase?
- Reversibility: Can we undo this action?

These combine into confidence via:
  confidence = (I × R × (1 - B) × P) with smoothing
  where I=intent, R=reversibility, B=availability_risk, P=security*cost

NO scenario lookups. Pure computation.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from core.intent_analyzer import (
    IntentAnalysis, Action, Resource, Environment, OperationContext
)


@dataclass
class RiskProfile:
    """Multi-dimensional risk assessment."""
    
    # Individual risk dimensions (0-1, higher = riskier)
    availability_risk: float = 0.0
    security_risk: float = 0.0
    cost_risk: float = 0.0
    reversibility: float = 1.0  # 1=fully reversible, 0=irreversible
    
    # Context-adjusted scores
    intent_clarity: float = 0.5  # How clear is the intent?
    expected_outcome: float = 0.5  # How confident in success?
    
    # Derived confidence (0-1)
    confidence: float = 0.0
    
    # Explainability
    binding_constraint: str = "unknown"
    risk_reasoning: Dict = field(default_factory=dict)


def compute_availability_risk(analysis: IntentAnalysis, affected_nodes: int = 0) -> tuple[float, Dict]:
    """
    Availability risk: probability of unintended downtime.
    
    Factors:
    - Action type (DELETE/SCALE up = risky, READ/START = safe)
    - Resource type (EC2 instance, RDS database more impactful)
    - Scale factor (8x scale up = more risk than 2x)
    - Environment (prod > staging > dev)
    - Affected nodes (more dependencies = higher risk)
    """
    base = 0.1  # Baseline
    
    # Action impact
    action_impact = {
        Action.DELETE: 0.60,
        Action.STOP: 0.50,
        Action.SCALE: 0.20,  # Scaling is reversible
        Action.MODIFY: 0.30,
        Action.ATTACH: 0.15,
        Action.DETACH: 0.25,
        Action.DEPLOY: 0.15,
        Action.START: 0.05,
        Action.CREATE: 0.10,
        Action.UNKNOWN: 0.70,
    }
    base = action_impact.get(analysis.action, 0.40)
    
    # Resource impact multiplier
    resource_impact = {
        Resource.RDS: 1.2,        # Database = most critical
        Resource.EC2: 1.0,        # Compute
        Resource.S3: 0.8,         # Storage less critical for runtime
        Resource.LAMBDA: 0.7,     # Serverless isolated
        Resource.IAM: 0.9,        # Policy impacts everything
        Resource.EKS: 1.1,        # K8s coordination critical
        Resource.VPC: 1.3,        # Network infrastructure
        Resource.UNKNOWN: 1.5,
    }
    base *= resource_impact.get(analysis.resource, 1.0)
    base = min(1.0, base)
    
    # Scale factor penalty (for SCALE operations)
    scale_penalty = 0.0
    if analysis.action == Action.SCALE:
        if analysis.scale_factor > 10:
            scale_penalty = 0.15
        elif analysis.scale_factor > 5:
            scale_penalty = 0.10
        elif analysis.scale_factor < 0.5:
            scale_penalty = 0.08  # Scaling down also risky
    base += scale_penalty
    
    # Environment multiplier
    env_mult = {
        Environment.PRODUCTION: 1.2,
        Environment.STAGING: 0.8,
        Environment.DEVELOPMENT: 0.5,
        Environment.UNKNOWN: 1.0,
    }
    base *= env_mult.get(analysis.environment, 1.0)
    
    # Affected nodes multiplier
    if affected_nodes > 5:
        base *= 1.3
    elif affected_nodes > 2:
        base *= 1.1
    
    base = min(1.0, base)
    
    # Context adjustments
    if analysis.context.has_backup:
        base *= 0.7  # Backup reduces risk
    if analysis.context.has_rollback_plan:
        base *= 0.8
    
    reasoning = {
        "action_base": action_impact.get(analysis.action, 0.40),
        "resource_multiplier": resource_impact.get(analysis.resource, 1.0),
        "scale_penalty": scale_penalty,
        "environment_multiplier": env_mult.get(analysis.environment, 1.0),
        "affected_nodes": affected_nodes,
    }
    
    return min(1.0, max(0.0, base)), reasoning


def compute_security_risk(analysis: IntentAnalysis) -> tuple[float, Dict]:
    """
    Security risk: probability of unauthorized access or data exposure.
    
    Factors:
    - Is it an IAM/permission action? (high security risk)
    - Is it admin-level access? (very high risk)
    - Is it deletion? (risk of data loss)
    - Is it to production? (higher sensitivity)
    """
    base = 0.1  # Baseline
    
    # Resource type security impact
    if analysis.resource == Resource.IAM:
        base = 0.65  # IAM changes are security-sensitive
    elif analysis.resource == Resource.S3 and analysis.action in [Action.MODIFY, Action.DELETE]:
        base = 0.55  # S3 permission/deletion risk
    elif analysis.resource == Resource.RDS and analysis.action in [Action.DELETE, Action.MODIFY]:
        base = 0.50  # Data exposure risk
    elif analysis.resource == Resource.VPC:
        base = 0.45
    
    # Action impact
    if analysis.action == Action.DELETE:
        base *= 1.3
    elif analysis.action == Action.ATTACH:
        base *= 1.4  # Attaching policies is high-risk
    elif analysis.action in [Action.DEPLOY, Action.CREATE]:
        base *= 1.1
    
    # Admin access penalty
    if analysis.context.is_admin_access:
        base *= 2.0  # Massive penalty for admin
    
    # Production penalty
    if analysis.environment == Environment.PRODUCTION:
        base *= 1.2
    
    # Read-only mitigation
    if analysis.context.is_read_only:
        base *= 0.2  # Read-only is safe
    
    base = min(1.0, base)
    
    reasoning = {
        "resource_type": str(analysis.resource),
        "action_type": str(analysis.action),
        "is_admin": analysis.context.is_admin_access,
        "is_production": analysis.environment == Environment.PRODUCTION,
        "is_readonly": analysis.context.is_read_only,
    }
    
    return min(1.0, max(0.0, base)), reasoning


def compute_cost_risk(analysis: IntentAnalysis) -> tuple[float, Dict]:
    """
    Cost risk: probability of unexpected cost increase.
    
    Factors:
    - Large scale-up operations (cost spike)
    - Resource type (compute > storage)
    - Production environment
    """
    base = 0.1
    
    # Scale factor impact
    if analysis.action == Action.SCALE and analysis.scale_factor > 5:
        base += 0.30  # Large scale-ups risky
    elif analysis.action == Action.SCALE and analysis.scale_factor > 2:
        base += 0.15
    
    # Resource type cost sensitivity
    if analysis.resource == Resource.EC2:
        base += 0.25
    elif analysis.resource == Resource.RDS:
        base += 0.20
    elif analysis.resource == Resource.LAMBDA:
        base += 0.05  # Pay-as-you-go, less predictable
    
    # Production multiplier
    if analysis.environment == Environment.PRODUCTION:
        base *= 1.3
    
    # Mitigations
    if analysis.context.is_low_traffic:
        base *= 0.5
    
    base = min(1.0, base)
    
    reasoning = {
        "action": str(analysis.action),
        "scale_factor": analysis.scale_factor,
        "resource": str(analysis.resource),
        "is_production": analysis.environment == Environment.PRODUCTION,
    }
    
    return min(1.0, max(0.0, base)), reasoning


def compute_reversibility(analysis: IntentAnalysis) -> tuple[float, Dict]:
    """
    Reversibility: Can we undo this action?
    
    Returns probability that we can revert successfully (0-1, higher = more reversible).
    
    Factors:
    - DELETE actions: NOT reversible unless resource is unused
    - READ/DESCRIBE: Fully reversible
    - SCALE/MODIFY: Usually reversible
    - ATTACH/DEPLOY: Reversible (detach/rollback)
    """
    base = 0.8  # Most operations are reversible
    
    # Action-based reversibility
    action_reversibility = {
        Action.DELETE: 0.10,      # Hard to undo DELETE
        Action.STOP: 0.95,        # START reverses STOP
        Action.SCALE: 0.85,       # Scale down reverses scale up
        Action.MODIFY: 0.70,      # Some configs hard to track
        Action.ATTACH: 0.90,      # DETACH reverses ATTACH
        Action.DETACH: 0.90,
        Action.DEPLOY: 0.75,      # Can rollback, but data may change
        Action.START: 0.95,
        Action.CREATE: 0.85,      # Can delete what we created
        Action.UNKNOWN: 0.01,
    }
    base = action_reversibility.get(analysis.action, 0.50)
    
    # Context improvements
    if analysis.context.is_temporary or analysis.context.is_unused:
        base = min(1.0, base + 0.2)  # Easier to undo temp/unused deletions
    
    if analysis.context.has_backup:
        base = min(1.0, base + 0.15)
    
    if analysis.context.has_rollback_plan:
        base = min(1.0, base + 0.10)
    
    # Production penalty
    if analysis.environment == Environment.PRODUCTION:
        base *= 0.9  # Prod is harder to rollback
    
    # Scale factor for DELETE
    if analysis.action == Action.DELETE and analysis.context.is_critical_path:
        base = max(0.0, base - 0.3)  # Critical resources harder to restore
    
    base = min(1.0, max(0.0, base))
    
    reasoning = {
        "action_reversibility": action_reversibility.get(analysis.action, 0.50),
        "is_temporary": analysis.context.is_temporary,
        "is_unused": analysis.context.is_unused,
        "has_backup": analysis.context.has_backup,
        "environment": str(analysis.environment),
    }
    
    return base, reasoning


def compute_risk_profile(
    analysis: IntentAnalysis,
    affected_nodes: int = 0,
    memory_penalty: bool = False,
) -> RiskProfile:
    """
    Compute full risk profile for the operation.
    
    Args:
        analysis: Structured intent analysis
        affected_nodes: Number of affected dependencies (from graph)
        memory_penalty: If True, apply penalties for repeated similar actions
    
    Returns:
        RiskProfile with all dimensions computed
    """
    if not analysis.is_valid:
        # Invalid operation → highest risk
        return RiskProfile(
            availability_risk=1.0,
            security_risk=1.0,
            cost_risk=1.0,
            reversibility=0.0,
            intent_clarity=0.0,
            expected_outcome=0.0,
            confidence=0.01,
            binding_constraint="invalid_operation",
            risk_reasoning={"error": "Could not parse operation"},
        )
    
    # Compute individual risk dimensions
    avail_risk, avail_reasoning = compute_availability_risk(analysis, affected_nodes)
    sec_risk, sec_reasoning = compute_security_risk(analysis)
    cost_risk, cost_reasoning = compute_cost_risk(analysis)
    reversibility, rev_reasoning = compute_reversibility(analysis)
    
    # Intent clarity from extraction confidence
    intent_clarity = analysis.extraction_confidence
    
    # Expected outcome: combination of low risk and high reversibility
    expected_outcome = max(0.01, (
        (1 - avail_risk) * 0.35 +
        (1 - sec_risk) * 0.35 +
        (1 - cost_risk) * 0.15 +
        reversibility * 0.15
    ))
    
    # Compute confidence
    # Formula: I × R × (1 - (A+S+C)/3) 
    # This balances intent clarity, reversibility, and average risk
    avg_risk = (avail_risk + sec_risk + cost_risk) / 3.0
    confidence = intent_clarity * reversibility * (1 - avg_risk)
    
    # Add extraction penalty if low confidence
    confidence *= analysis.extraction_confidence
    
    # Smoothing: avoid collapse to 0 or artificial highs
    confidence = max(0.05, min(0.95, confidence))
    
    # Memory penalty for repeated similar actions
    if memory_penalty:
        confidence *= 0.85  # 15% penalty for repeated risk
        reversibility *= 0.9
    
    # Determine binding constraint (most limiting factor)
    constraints = {
        "availability": avail_risk,
        "security": sec_risk,
        "cost": cost_risk,
        "reversibility": 1 - reversibility,  # Flip for comparison
    }
    binding_constraint = max(constraints, key=constraints.get)
    
    profile = RiskProfile(
        availability_risk=avail_risk,
        security_risk=sec_risk,
        cost_risk=cost_risk,
        reversibility=reversibility,
        intent_clarity=intent_clarity,
        expected_outcome=expected_outcome,
        confidence=confidence,
        binding_constraint=binding_constraint,
        risk_reasoning={
            "availability": avail_reasoning,
            "security": sec_reasoning,
            "cost": cost_reasoning,
            "reversibility": rev_reasoning,
        }
    )
    
    return profile
