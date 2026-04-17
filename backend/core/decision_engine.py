"""
V2 Decision Engine: Convert risk profile + context into decisions.

Decision gates:
  confidence >= 0.80  → AUTO (execute immediately)
  0.50-0.79          → APPROVE (route to human)
  < 0.50             → BLOCK (reject)

Includes:
- Debate generation (executor vs critic)
- Dynamic simulation generation
- Audit trail integration
- Memory-aware penalties
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from core.intent_analyzer import IntentAnalysis, Action, Resource, Environment
from core.risk_model import RiskProfile


@dataclass
class Decision:
    """Final decision on infrastructure operation."""
    
    gate: str  # AUTO | APPROVE | BLOCK
    confidence: float  # 0-1
    
    # Rationale
    binding_constraint: str
    reason: str
    
    # Forensics
    analysis: Dict  # All parameters the decision was based on
    debate: Dict    # Executor vs Critic
    simulations: List[Dict]  # Possible outcomes
    premortem: List[Dict]  # Failure modes
    
    # Audit
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def make_debate(analysis: IntentAnalysis, risk_profile: RiskProfile) -> Dict:
    """
    Generate executor (optimist) vs critic (pessimist) dialog.
    
    EXECUTOR: Why this should work
    CRITIC: Why this might fail
    VERDICT: Synthesized recommendation
    """
    resource_str = analysis.resource.value if analysis.resource else "unknown"
    action_str = analysis.action.value if analysis.action else "unknown"
    env_str = analysis.environment.value if analysis.environment else "unknown"
    
    # Build operation description
    op_desc = f"{action_str.upper()} {resource_str.upper()}"
    if analysis.environment != Environment.UNKNOWN:
        op_desc += f" in {env_str}"
    
    # Base case: invalid operation
    if not analysis.is_valid:
        return {
            "executor": "Cannot determine operation type.",
            "critic": f"Invalid or ambiguous operation: {analysis.raw_text[:100]}",
            "verdict": "✕ BLOCK — Cannot classify operation",
        }
    
    # Context description
    context_tags = []
    if analysis.context.is_temporary:
        context_tags.append("temporary")
    if analysis.context.is_unused:
        context_tags.append("unused/orphaned")
    if analysis.context.is_low_traffic:
        context_tags.append("low-traffic")
    if analysis.context.has_backup:
        context_tags.append("backed-up")
    if analysis.context.is_critical_path:
        context_tags.append("critical")
    if analysis.context.is_admin_access:
        context_tags.append("⚠️ ADMIN-LEVEL")
    
    context_str = ", ".join(context_tags) if context_tags else "standard"
    
    # Executor: optimistic case
    if analysis.action == Action.CREATE:
        executor = f"{op_desc} is well-scoped and creates new isolated resource. No dependent services affected."
    elif analysis.action == Action.SCALE and analysis.scale_factor < 2:
        executor = f"{op_desc} is a minor scale adjustment ({analysis.scale_factor:.1f}x), easily reversible."
    elif analysis.action == Action.SCALE:
        executor = f"{op_desc} scales to {analysis.target_count} instances. Autoscaling is tested, ALB configured."
    elif analysis.action == Action.DEPLOY:
        executor = f"{op_desc} deployment is isolated, previous version available for rollback."
    elif analysis.action == Action.MODIFY:
        executor = f"{op_desc} changes are backward-compatible, non-destructive."
    elif analysis.action == Action.STOP or analysis.action == Action.START:
        executor = f"{op_desc} is a state change, fully reversible in seconds."
    elif analysis.action == Action.ATTACH:
        executor = f"{op_desc} grants specific permissions, scoped to least-privilege."
    elif analysis.action == Action.DETACH:
        executor = f"{op_desc} removes permissions safely, maintaining critical access for other roles."
    elif analysis.action == Action.DELETE:
        if analysis.context.is_unused:
            executor = f"{op_desc} removes unused/orphaned resource ({context_str}). No active dependents."
        else:
            executor = f"{op_desc} removes resource. Verify no active dependents before proceeding."
    else:
        executor = f"Execute {op_desc}."
    
    # Critic: pessimistic case
    if analysis.action == Action.DELETE and not analysis.context.is_unused:
        critic = f"⚠️ {op_desc.upper()} is IRREVERSIBLE. Dependency analysis required. " \
                 f"Is this backup'd? Any active clients? Data retention policy?"
        if analysis.environment == Environment.PRODUCTION:
            critic += " ❌ PRODUCTION DELETION BLOCKED without explicit approval."
    elif analysis.action == Action.ATTACH and analysis.context.is_admin_access:
        critic = f"⚠️ POLICY RISK: {op_desc} grants ADMIN-level access. " \
                 f"Verify: Is least-privilege enforced? Time-limited? Audit trail enabled?"
    elif analysis.action == Action.SCALE and analysis.scale_factor > 10:
        critic = f"⚠️ Extreme scaling ({analysis.scale_factor:.1f}x). Verify: " \
                 f"Cost implications? VPC limits? ASG capacity? Gradual rollout?"
    elif analysis.action == Action.DEPLOY and analysis.environment == Environment.PRODUCTION:
        critic = f"⚠️ Production deployment. Verify: Canary deployed? Metrics monitored? " \
                 f"Rollback plan? Breaking changes?"
    elif analysis.action == Action.MODIFY and analysis.environment == Environment.PRODUCTION:
        critic = f"⚠️ Production modification. Backup snapshot required. " \
                 f"Zero-downtime or acceptable window? Rollback tested?"
    else:
        critic = f"Standard caution: Verify operation parameters and dependencies before {action_str}."
    
    # Verdict based on confidence
    if risk_profile.confidence >= 0.80:
        verdict_emoji = "✓"
        verdict_action = "AUTO-EXECUTE"
    elif risk_profile.confidence >= 0.50:
        verdict_emoji = "⊙"
        verdict_action = "ROUTE TO APPROVER"
    else:
        verdict_emoji = "✕"
        verdict_action = "BLOCK"
    
    verdict = f"{verdict_emoji} VERDICT: {op_desc} — {verdict_action} " \
              f"(confidence: {risk_profile.confidence:.1%}, binding: {risk_profile.binding_constraint})"
    
    return {
        "executor": executor,
        "critic": critic,
        "verdict": verdict,
        "context": context_str,
    }


def generate_simulations(
    analysis: IntentAnalysis,
    risk_profile: RiskProfile,
    affected_nodes: int = 0,
) -> List[Dict]:
    """
    Generate 3-4 dynamic outcome scenarios based on actual risk profile.
    
    NOT fixed scenarios. These change based on parameters.
    """
    simulations = []
    
    # Success scenario
    success_prob = risk_profile.confidence
    simulations.append({
        "scenario": f"{analysis.action.value.upper()} {analysis.resource.value.upper()} succeeds",
        "probability": int(success_prob * 100),
        "detail": "All controls nominal, operation completes as expected",
        "type": "success",
    })
    
    # Degraded/partial failure based on availability risk
    if risk_profile.availability_risk > 0.2:
        degraded_prob = risk_profile.availability_risk * 0.4
        simulations.append({
            "scenario": f"Partial degradation (brief service impact)",
            "probability": int(degraded_prob * 100),
            "detail": f"Affects {affected_nodes} dependent services, recovers within SLA",
            "type": "degraded",
        })
    
    # Cascading failure if HIGH risk and many affected nodes
    if affected_nodes > 2 and risk_profile.availability_risk > 0.5:
        cascade_prob = (1 - risk_profile.confidence) * 0.3
        simulations.append({
            "scenario": "Cascading failure propagates",
            "probability": int(cascade_prob * 100),
            "detail": f"Affects {affected_nodes} services, requires emergency response",
            "type": "cascading_failure",
        })
    
    # Cost overrun for scaling operations
    if analysis.action == Action.SCALE and risk_profile.cost_risk > 0.3:
        cost_prob = risk_profile.cost_risk * 0.2
        simulations.append({
            "scenario": "Cost overrun (runtime anomaly)",
            "probability": int(cost_prob * 100),
            "detail": "Utilization exceeds forecast, unexpected charges",
            "type": "cost_anomaly",
        })
    
    # Rollback needed for high-risk operations
    if risk_profile.reversibility < 0.6 and risk_profile.intent_clarity < 0.7:
        rollback_prob = (1 - risk_profile.reversibility) * 0.15
        simulations.append({
            "scenario": "Operation requires manual intervention/rollback",
            "probability": int(rollback_prob * 100),
            "detail": "Unexpected state requires DBA/SRE recovery action",
            "type": "intervention_required",
        })
    
    # Normalize probabilities to 100%
    total_prob = sum(s["probability"] for s in simulations)
    if total_prob > 0:
        simulations = [{
            **s,
            "probability": int((s["probability"] / total_prob) * 100)
        } for s in simulations]
    
    # Fix rounding
    current_total = sum(s["probability"] for s in simulations)
    if current_total < 100 and simulations:
        simulations[0]["probability"] += (100 - current_total)
    
    return simulations[:4]


def generate_premortem(analysis: IntentAnalysis, risk_profile: RiskProfile) -> List[Dict]:
    """
    Pre-mortem: What could go wrong with this operation?
    
    Dynamically generated based on action, resource, and risk profile.
    """
    premortem = []
    
    # Availability failure modes
    if risk_profile.availability_risk > 0.4:
        premortem.append({
            "failure": "Downstream service connection timeout",
            "severity": 3 + int(risk_profile.availability_risk * 2),
            "probability": int(risk_profile.availability_risk * 100),
            "mitigation": "Gradual rollout with canary monitoring, fast rollback enabled",
            "impacted_services": "dependent resources",
        })
    
    # Security failure modes
    if risk_profile.security_risk > 0.4:
        premortem.append({
            "failure": "Unauthorized access via new permissions",
            "severity": 4,
            "probability": int(risk_profile.security_risk * 100),
            "mitigation": "Audit trail, IAM MFA required, least-privilege validation",
            "impacted_services": "security posture",
        })
    
    # Data loss failure modes
    if analysis.action == Action.DELETE and risk_profile.reversibility < 0.5:
        premortem.append({
            "failure": "Irreversible data loss if delete proceeds",
            "severity": 5,
            "probability": 40,
            "mitigation": "Backup verification, RTO/RPO validation, staged deletion",
            "impacted_services": "data integrity",
        })
    
    # Cost failure modes
    if risk_profile.cost_risk > 0.3:
        premortem.append({
            "failure": "Cost spike from resource utilization",
            "severity": 2,
            "probability": int(risk_profile.cost_risk * 100),
            "mitigation": "Establish cost alerts, budget limits, usage monitoring",
            "impacted_services": "budget impact",
        })
    
    # Rollback failure modes
    if risk_profile.reversibility < 0.3:
        premortem.append({
            "failure": "Cannot rollback cleanly — stuck in bad state",
            "severity": 4,
            "probability": int((1 - risk_profile.reversibility) * 80),
            "mitigation": "Test rollback procedure, SRE on-call, runbook prepared",
            "impacted_services": "operational continuity",
        })
    
    # Scale-specific failures
    if analysis.action == Action.SCALE and analysis.scale_factor > 5:
        premortem.append({
            "failure": "Sudden spike causes cache/connection pool exhaustion",
            "severity": 3,
            "probability": 30,
            "mitigation": "Connection pooling tuned, cache warmed, gradual ramp",
            "impacted_services": "mid-tier services",
        })
    
    return premortem


def make_decision(
    analysis: IntentAnalysis,
    risk_profile: RiskProfile,
    affected_nodes: int = 0,
) -> Decision:
    """
    Convert analysis + risk profile into a Decision.
    """
    
    # Determine gate
    if risk_profile.confidence >= 0.80:
        gate = "AUTO"
    elif risk_profile.confidence >= 0.50:
        gate = "APPROVE"
    else:
        gate = "BLOCK"
    
    # Generate supporting materials
    debate = make_debate(analysis, risk_profile)
    simulations = generate_simulations(analysis, risk_profile, affected_nodes)
    premortem = generate_premortem(analysis, risk_profile)
    
    # Reason
    if not analysis.is_valid:
        reason = f"Operation could not be parsed. Raw text: {analysis.raw_text[:80]}"
    elif gate == "AUTO":
        reason = f"{debate['context']}: {risk_profile.binding_constraint} acceptable, reversible, low-risk."
    elif gate == "APPROVE":
        reason = f"Requires human approval due to {risk_profile.binding_constraint} risk. Review debate and simulations."
    else:  # BLOCK
        reason = f"Blocked due to {risk_profile.binding_constraint}. See premortem for concerns."
    
    # Analysis payload for transparency
    analysis_payload = {
        "action": str(analysis.action.value),
        "resource": str(analysis.resource.value),
        "environment": str(analysis.environment.value),
        "scale_factor": analysis.scale_factor,
        "parameters": {
            "source_count": analysis.source_count,
            "target_count": analysis.target_count,
            "region": analysis.region,
        },
        "context": {
            "is_temporary": analysis.context.is_temporary,
            "is_unused": analysis.context.is_unused,
            "is_admin_access": analysis.context.is_admin_access,
            "is_critical_path": analysis.context.is_critical_path,
            "has_backup": analysis.context.has_backup,
        },
        "extraction_confidence": analysis.extraction_confidence,
    }
    
    risk_payload = {
        "availability_risk": risk_profile.availability_risk,
        "security_risk": risk_profile.security_risk,
        "cost_risk": risk_profile.cost_risk,
        "reversibility": risk_profile.reversibility,
        "intent_clarity": risk_profile.intent_clarity,
        "binding_constraint": risk_profile.binding_constraint,
    }
    
    decision = Decision(
        gate=gate,
        confidence=risk_profile.confidence,
        binding_constraint=risk_profile.binding_constraint,
        reason=reason,
        analysis=analysis_payload,
        debate=debate,
        simulations=simulations,
        premortem=premortem,
    )
    
    return decision
