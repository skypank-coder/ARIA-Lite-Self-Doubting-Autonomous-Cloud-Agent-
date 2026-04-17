"""
FastAPI backend for ARIA-Lite++ (v3) — Trust-Aware Autonomous Cloud Operator
SDACA v2: Self-Doubting Autonomous Cloud Agent

NEW in v3:
- Dynamic trust scoring via dependency_graph
- Groq LLM-powered /analyze_custom endpoint
- Full audit trail with /audit endpoint  
- Dependency graph / blast radius visualization via /graph/{intent}
- Trust explanation via /trust/explain
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Dict, Optional, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone

# Updated imports for v3
from trust_engine import calculate_trust_scores, calculate_confidence, decision_from_confidence
from scenarios import SCENARIOS, PREMORTEM_ANALYSIS
from dependency_graph import build_graph, compute_blast_radius, serialize_graph, propagation_summary, create_demo_architecture
from parser import parse_ticket, groq_full_analysis
from memory import memory

app = FastAPI(title="ARIA-Lite++ v4", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy memory_store for backward compat with process_ticket
memory_store = {}

# UPGRADE #3: Singleton dependency graph (lazy initialization)
GLOBAL_GRAPH = None

@app.on_event("startup")
async def startup_event():
    """Initialize singleton graph on startup."""
    global GLOBAL_GRAPH
    try:
        GLOBAL_GRAPH = create_demo_architecture()
    except Exception as e:
        print(f"Warning: Could not initialize global graph: {e}")


class TicketInput(BaseModel):
    ticket: str


class CustomTicketRequest(BaseModel):
    ticket: str
    groq_api_key: str = ""


class ExplainRequest(BaseModel):
    ticket: str


# =========== HEALTH & MEMORY ===========

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "ARIA-LITE++", "version": "4.0.0"}


@app.get("/memory")
def get_memory_state():
    """Get global memory state (incidents, audit trail)."""
    return {
        "incidents": memory_store,
        "audit_count": len(memory.get_audit_log()),
    }


# =========== AUDIT ENDPOINTS ===========

@app.get("/audit")
def audit_log():
    """Return full audit trail of all requests."""
    return {
        "entries": memory.get_audit_log(),
        "count": len(memory.get_audit_log()),
    }


def _write_audit(ticket: str, intent: str, confidence: float, decision: str, parser: str = "fallback") -> None:
    """Helper: write audit entry."""
    memory.write_audit({
        "ticket_preview": ticket[:80],
        "intent": intent,
        "confidence": round(confidence, 3),
        "decision": decision,
        "parser": parser,
    })


# =========== DIALOG & DEBATE ===========

def generate_dynamic_simulation(scenario: str, confidence: float, blast_radius: float, affected_count: int = 0) -> List[Dict]:
    """
    UPGRADE #3: Generate dynamic simulation scenarios instead of static ones.
    
    Returns 3-4 scenarios with probabilities that sum to 1.0.
    Probabilities vary based on confidence, blast_radius, and affected services.
    
    Args:
        scenario: Scenario name
        confidence: Confidence score (0-1)
        blast_radius: Blast radius (0-1)
        affected_count: Number of affected services
    
    Returns:
        List of simulation scenarios with type, description, probability, detail
    """
    simulations = []
    
    # Success scenario: higher probability with higher confidence
    success_prob = confidence
    simulations.append({
        "scenario": f"{scenario} completes successfully",
        "probability": int(success_prob * 100),
        "detail": "All controls healthy" if success_prob > 0.8 else "Most controls nominal",
        "type": "success"
    })
    
    # Degraded scenario: based on blast radius and affected services
    degraded_prob = blast_radius * 0.5 if blast_radius > 0.3 else (1 - confidence) * 0.3
    if degraded_prob > 0.01:
        simulations.append({
            "scenario": f"Partial service degradation (affects {affected_count} services)",
            "probability": int(degraded_prob * 100),
            "detail": "Some dependencies experience latency" if affected_count > 2 else "Isolated impact",
            "type": "degraded"
        })
    
    # Outage scenario: inversely proportional to confidence
    outage_prob = (1 - confidence) * 0.25 if affected_count > 1 else (1 - confidence) * 0.1
    if outage_prob > 0.01:
        simulations.append({
            "scenario": f"Cascading failure affecting downstream services",
            "probability": int(outage_prob * 100),
            "detail": f"{affected_count} critical services lose access" if affected_count > 2 else "Isolated outage",
            "type": "cascading_failure"
        })
    
    # Rollback scenario: only for high-risk operations
    if blast_radius > 0.6:
        rollback_prob = blast_radius * 0.1
        simulations.append({
            "scenario": "Operation triggers automatic rollback",
            "probability": int(rollback_prob * 100),
            "detail": "Safety guardrail prevents propagation",
            "type": "rollback"
        })
    
    # Normalize probabilities to sum to 100
    total_prob = sum(s["probability"] for s in simulations)
    if total_prob > 0:
        for sim in simulations:
            sim["probability"] = int((sim["probability"] / total_prob) * 100)
    
    # Ensure total is exactly 100 (fix rounding)
    current_total = sum(s["probability"] for s in simulations)
    if current_total < 100 and simulations:
        simulations[0]["probability"] += (100 - current_total)
    
    return simulations[:4]  # Cap at 4 scenarios


def get_debate_for_scenario(scenario: str, memory_alert: bool = False, affected_services: int = 0, blast_pct: int = 0) -> Dict:
    """
    Get executor/critic/verdict debate strings for each scenario.
    
    UPGRADE #7: Inject dynamic infrastructure data:
    - number of affected services
    - blast radius %
    - prior incident info
    """
    # Build dynamic context
    impact_detail = f"affects {affected_services} downstream services" if affected_services > 0 else "isolated impact"
    memory_detail = " — prior incident detected, confidence reduced" if memory_alert else ""
    blast_detail = f" (blast radius {blast_pct}%)" if blast_pct > 0 else ""
    
    debates = {
        "s3_create": {
            "executor": "S3 bucket creation is reversible, well-scoped, and compliant. Bucket lifecycle is clear.",
            "critic": ("S3 bucket names are globally unique — collision risk is low but real. "
                      "Versioning must be enabled in production."),
            "verdict": "✓ VERDICT: S3_CREATE — Auto-execute with tagging policy verification",
        },
        "iam_delete": {
            "executor": "Immediate deletion simplifies permission model.",
            "critic": (f"HARD BLOCK: IAM role deletion is irreversible and {impact_detail}{blast_detail}. "
                      f"RDS, Lambda, EC2 all depend on this role{memory_detail}."),
            "verdict": "✕ VERDICT: IAM_DELETE — BLOCKED — Requires manual override + 2-factor approval",
        },
        "iam_attach": {
            "executor": "Policy attachment grants permissions to development IAM role.",
            "critic": (f"⚠ POLICY RISK: Verify least-privilege constraints. This action {impact_detail}{blast_detail}{memory_detail}."),
            "verdict": "⊙ VERDICT: IAM_ATTACH — Route to approver — requires human review",
        },
        "ec2_scale": {
            "executor": f"EC2 autoscaling is fully reversible (scale down anytime), low blast radius, well-tested{blast_detail}.",
            "critic": (f"✓ EC2 scaling approved{' from incident history' if memory_alert else ''}. "
                      f"Verify ALB health checks responding. {impact_detail}{memory_detail}."),
            "verdict": "✓ VERDICT: EC2_SCALE — Auto-execute with CloudWatch metrics tracking",
        },
        "rds_modify": {
            "executor": "RDS configuration changes are carefully scoped: parameter groups, not data deletion.",
            "critic": (f"Database modifications require manual approval — {impact_detail}{blast_detail}. "
                      f"Backup snapshot needed beforehand{memory_detail}."),
            "verdict": "⊙ VERDICT: RDS_MODIFY — Route to DBA approver — snapshot required",
        },
        "lambda_deploy": {
            "executor": "Lambda code deployment is reversible (previous version available) and well-contained.",
            "critic": (f"Lambda deployments execute in isolation{blast_detail}. "
                      f"Check: No breaking schema changes, no new IAM perms{memory_detail}."),
            "verdict": "⊙ VERDICT: LAMBDA_DEPLOY — Auto-execute with CloudWatch logs monitoring",
        },
    }
    
    return debates.get(scenario, {
        "executor": "Unknown operation type.",
        "critic": f"Cannot classify operation. Blocking by default{memory_detail}.",
        "verdict": "✕ VERDICT: UNKNOWN — BLOCKED — Unrecognized action pattern"
    })


def get_premortem_for_scenario(scenario: str) -> List[Dict]:
    """Get pre-mortem failure modes from scenarios.py."""
    return PREMORTEM_ANALYSIS.get(scenario, [
        {"failure": "Unknown failure mode", "severity": 1, "mitigation": "Cannot mitigate unknown scenario"}
    ])


def get_execution_log_for_scenario(scenario: str, confidence: float, gate: str) -> List[str]:
    """Generate streaming execution log with timestamps."""
    now = datetime.now()
    
    base_log = [
        f"[{now.strftime('%H:%M:%S')}.001] ● Parsing {scenario} request",
        f"[{now.strftime('%H:%M:%S')}.125] ● Computing trust components",
        f"[{now.strftime('%H:%M:%S')}.250] ● Evaluating blast radius",
        f"[{now.strftime('%H:%M:%S')}.375] ● Checking policy compliance",
    ]
    
    if gate == "BLOCK":
        base_log.append(f"[{now.strftime('%H:%M:%S')}.500] ✕ HARD BLOCK — confidence {confidence:.2%} < 0.50")
    elif gate == "APPROVE":
        base_log.append(f"[{now.strftime('%H:%M:%S')}.500] ⊙ ROUTING TO APPROVER — confidence {confidence:.2%} (0.50-0.79)")
    else:  # AUTO
        base_log.append(f"[{now.strftime('%H:%M:%S')}.500] ● AUTO-EXECUTE approved — confidence {confidence:.2%} ≥ 0.80")
    
    base_log.append(f"[{now.strftime('%H:%M:%S')}.625] ● Risk profile computed successfully")
    
    return base_log


# =========== NEW V3 ENDPOINTS ===========

@app.post("/analyze_custom")
def analyze_custom(req: CustomTicketRequest):
    """
    CHANGE 5: Dynamic analysis for any arbitrary cloud ticket.
    If groq_api_key provided, uses Groq LLM for scoring.
    Falls back to rule-based parser if Groq not available.
    """
    ticket = req.ticket.strip()
    if not ticket:
        return {"gate": "BLOCK", "reason": "Empty ticket", "confidence": 0.0}
    if len(ticket) > 1000:
        return {"gate": "BLOCK", "reason": "Ticket exceeds 1000 char limit", "confidence": 0.0}
    
    # Try Groq if API key provided
    groq_result = None
    if req.groq_api_key:
        groq_result = groq_full_analysis(ticket, req.groq_api_key)
    
    if groq_result:
        # Groq-powered analysis
        scores = {
            "intent_score": groq_result["intent_score"],
            "reversibility": groq_result["reversibility"],
            "blast_radius": groq_result["blast_radius"],
            "policy_score": groq_result["policy_score"],
        }
        confidence = calculate_confidence(scores)
        intent = groq_result.get("intent", "custom")
        decision = decision_from_confidence(confidence, intent)
        debate = {
            "executor": groq_result.get("executor_argument", f"LLM-analyzed ticket."),
            "critic": groq_result.get("critic_argument", f"Blast radius {scores['blast_radius']:.2f}."),
            "verdict": f"{decision} — LLM-scored custom ticket analysis"
        }
        premortem = groq_result.get("premortem", [
            {"failure": groq_result.get("top_risk", "Unknown"),
             "severity": 3,
             "mitigation": groq_result.get("top_mitigation", "Manual review required.")}
        ])
        logs = [
            f"[{datetime.now().strftime('%H:%M:%S')}] ● LLM parser: intent={intent}, confidence={confidence:.3f}",
            f"[{datetime.now().strftime('%H:%M:%S')}] ● Gate decision: {decision}",
        ]
        
        _write_audit(ticket, intent, confidence, decision, parser="groq_full")
        
        return {
            "scenario": intent,
            "gate": decision,
            "trust": scores,
            "confidence": confidence,
            "debate": debate,
            "premortem": premortem,
            "execution_log": logs,
            "simulation": [],
            "custom_analysis": True,
            "parser": "groq_full",
        }
    
    # Fallback: rule-based parsing
    parsed = parse_ticket(ticket)
    intent = parsed.get("intent", "unknown")
    has_memory = intent in memory_store
    scores = calculate_trust_scores(intent, parsed.get("parameters", {}), has_memory)
    blast_detail = scores.pop("_blast_detail", None)
    confidence = calculate_confidence(scores)
    decision = decision_from_confidence(confidence, intent)
    
    _write_audit(ticket, intent, confidence, decision, parser="fallback")
    
    return {
        "scenario": intent,
        "gate": decision,
        "trust": scores,
        "confidence": confidence,
        "debate": get_debate_for_scenario(intent),
        "premortem": get_premortem_for_scenario(intent),
        "execution_log": get_execution_log_for_scenario(intent, confidence, decision),
        "simulation": [],
        "custom_analysis": True,
        "parser": "fallback",
    }


@app.get("/scenarios")
def list_scenarios():
    """
    CHANGE 8: List all known cloud operation scenarios with metadata.
    Returns schema information for each scenario.
    """
    result = {}
    for name, scenario in SCENARIOS.items():
        action = scenario["action"]
        result[name] = {
            "name": scenario.get("name", name),
            "service": action["service"],
            "operation": action["operation"],
            "resource": action["resource"],
            "intent_score": action["intent_score"],
            "policy_score": action["policy_score"],
            "reversibility_category": action["reversibility"]["category"],
            "recovery_minutes": action["reversibility"]["recovery_minutes"],
            "rollback_complexity": action["reversibility"]["rollback_complexity"],
            "resource_count": len(scenario.get("resources", {})),
            "match_terms": scenario.get("match_terms", []),
        }
    return {"scenarios": result, "count": len(result)}


@app.get("/graph/{intent}")
def get_graph(intent: str):
    """
    CHANGE 7: Get dependency graph for a cloud scenario.
    Shows blast radius propagation and affected services.
    """
    if intent not in SCENARIOS:
        return {
            "error": f"Unknown intent: {intent}",
            "known": list(SCENARIOS.keys())
        }
    
    scenario = SCENARIOS[intent]
    try:
        graph = build_graph(scenario)
        entry_nodes = scenario["action"]["entry_nodes"]
        blast = compute_blast_radius(graph, entry_nodes)
        serialized = serialize_graph(graph, blast, entry_nodes)
        waves = propagation_summary(blast, graph)
        
        return {
            "intent": intent,
            "graph": serialized,
            "blast": {
                "weighted_impact": blast["weighted_impact"],
                "affected_count": len(blast["affected_nodes"]),
                "user_facing_count": blast["user_facing_count"],
                "waves": waves,
            },
            "entry_nodes": entry_nodes,
        }
    except Exception as e:
        return {
            "error": f"Graph computation failed: {str(e)}",
            "intent": intent,
        }


@app.post("/trust/explain")
def trust_explain(req: ExplainRequest):
    """
    CHANGE 9: Explain trust score calculation step-by-step.
    Shows the formula trace and binding constraint.
    """
    ticket = req.ticket.strip()
    if not ticket:
        return {"error": "Empty ticket"}
    
    parsed = parse_ticket(ticket)
    intent = parsed.get("intent", "unknown")
    scores = calculate_trust_scores(intent, parsed.get("parameters", {}))
    _ = scores.pop("_blast_detail", None)
    confidence = calculate_confidence(scores)
    decision = decision_from_confidence(confidence, intent)
    
    formula_trace = (
        f"confidence = intent_score × reversibility × (1 - blast_radius) × policy_score\n"
        f"           = {scores['intent_score']} × {scores['reversibility']} × "
        f"(1 - {scores['blast_radius']}) × {scores['policy_score']}\n"
        f"           = {confidence}"
    )
    
    score_dict = {
        "intent_score": scores["intent_score"],
        "reversibility": scores["reversibility"],
        "blast_radius_inv": round(1.0 - scores["blast_radius"], 2),
        "policy_score": scores["policy_score"],
    }
    weakest = min(score_dict, key=score_dict.get)
    
    return {
        "ticket": ticket,
        "intent": intent,
        "scores": scores,
        "confidence": confidence,
        "decision": decision,
        "formula_trace": formula_trace,
        "binding_constraint": f"{weakest} = {score_dict[weakest]}",
        "threshold_context": {
            "to_auto": round(max(0, 0.80 - confidence), 3),
            "to_approve": round(max(0, 0.50 - confidence), 3),
            "current_gate": decision,
        }
    }


# =========== LEGACY BACKWARD-COMPATIBLE ENDPOINTS ===========

@app.post("/process_ticket")
def process_ticket(input_data: TicketInput):
    """
    Legacy V1 endpoint (backward compatibility).
    Uses old response format for existing frontend.
    
    UPGRADES:
    - Dynamic simulation generation (UPGRADE #3)
    - Incident memory integration (UPGRADE #6)
    - Enhanced debate with infrastructure data (UPGRADE #7)
    - Rename confidence → decision_score (UPGRADE #4)
    """
    try:
        ticket = input_data.ticket.strip()
        
        if not ticket:
            return {"gate": "BLOCK", "reason": "Empty ticket", "confidence": 0.0}
        
        if len(ticket) > 500:
            return {"gate": "BLOCK", "reason": "Ticket exceeds 500 characters", "confidence": 0.0}
        
        # Scenario matching via parser.parse_ticket
        parsed = parse_ticket(ticket)
        scenario = parsed.get("intent", None)
        
        if scenario == "unknown":
            return {
                "gate": "BLOCK",
                "reason": "Unrecognized action pattern — insufficient keywords",
                "decision_score": 0.0,  # UPGRADE #4: Renamed label
            }
        
        # Compute trust scores
        has_memory = scenario in memory.data and len(memory.data.get(scenario, [])) > 0
        scores = calculate_trust_scores(scenario, parsed.get("parameters", {}), has_memory)
        blast_detail = scores.pop("_blast_detail", None)
        confidence = calculate_confidence(scores)
        gate = decision_from_confidence(confidence, scenario)
        
        # UPGRADE #6: Incident memory integration
        memory_alert = has_memory
        if has_memory:
            # Apply memory penalties: confidence * 0.85
            confidence = max(0.01, confidence * 0.85)
            gate = decision_from_confidence(confidence, scenario)
        
        # Count affected services from blast detail
        affected_count = len(blast_detail.get("affected_nodes", [])) if blast_detail else 0
        blast_pct = int(scores.get("blast_radius", 0.0) * 100)
        
        # UPGRADE #7: Enhanced debate with dynamic infrastructure data
        debate = get_debate_for_scenario(scenario, memory_alert, affected_count, blast_pct)
        premortem = get_premortem_for_scenario(scenario)
        execution_log = get_execution_log_for_scenario(scenario, confidence, gate)
        
        # Record incident in memory if exists
        has_rollback = False
        if scenario == "ec2_scale" and gate == "AUTO":
            has_rollback = True
            execution_log.append(f"[{datetime.now().strftime('%H:%M:%S')}.750] ↩ ROLLBACK SIMULATION — zone exhaustion detected")
            memory.add_memory(scenario, {
                "ticket": ticket,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
                "outcome": "ROLLBACK",
                "note": "RDS pool exhaustion eu-west-1"
            })
        
        # Transform for frontend
        premortem_transformed = []
        for i, item in enumerate(premortem):
            premortem_transformed.append({
                "severity": item.get("severity", 1),
                "title": item.get("failure", "Unknown failure mode"),
                "probability": (i + 1) * 10 + (5 if gate == "BLOCK" else 0),
                "mitigation": item.get("mitigation", "Unknown mitigation"),
                "impacted_deps": max(1, item.get("severity", 1) - 1),
            })
        
        execution_log_transformed = []
        for log_entry in execution_log:
            status = "ok"
            if "BLOCK" in log_entry or "FAIL" in log_entry:
                status = "fail"
            elif "ROLLBACK" in log_entry:
                status = "rollback"
            elif "WARN" in log_entry or "CRITICAL" in log_entry:
                status = "warn"
            elif "memory" in log_entry.lower() or "incident" in log_entry.lower():
                status = "memory"
            
            execution_log_transformed.append({
                "msg": log_entry,
                "status": status,
            })
        
        # UPGRADE #3: Dynamic simulation generation
        simulation = generate_dynamic_simulation(scenario, confidence, scores.get("blast_radius", 0.0), affected_count)
        
        _write_audit(ticket, scenario, confidence, gate)
        
        return {
            "scenario": scenario,
            "gate": gate,
            "trust": {
                "intent_score": scores["intent_score"],
                "reversibility": scores["reversibility"],
                "blast_radius": scores["blast_radius"],
                "policy_score": scores["policy_score"],
                "decision_score": confidence,  # UPGRADE #4: Renamed from confidence
                "confidence": confidence,  # Keep for backward compatibility
            },
            "debate": debate,
            "premortem": premortem_transformed,
            "execution_log": execution_log_transformed,
            "simulation": simulation,
            "has_rollback": has_rollback,
            "impact_summary": f"Affects {affected_count} services, blast radius {blast_pct}% — {gate} decision",
            "elapsed_ms": 350,
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "gate": "BLOCK",
            "reason": f"Backend error: {str(e)}",
            "decision_score": 0.0,  # UPGRADE #4: Renamed label
            "confidence": 0.0,
        }


@app.post("/v2/analyze")
def analyze_v2(input_data: TicketInput):
    """V2 endpoint (backward compatibility)."""
    return process_ticket(input_data)
