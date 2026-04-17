# backend/main_v2.py
"""
V2 API router. Mounted at /v2 prefix by main.py.
All existing /v1 endpoints remain unchanged.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from intent_extractor import extract_intent, IntentParameters
from trust_engine_v2  import compute_v2_trust, V2TrustScores
from iam_simulator    import simulate_iam_policy

# Import existing v1 graph for BFS blast radius
try:
    from main import GLOBAL_GRAPH
    HAS_GRAPH = True
except Exception:
    GLOBAL_GRAPH = None
    HAS_GRAPH = False

v2_router = APIRouter(tags=["v2"])


class V2TicketRequest(BaseModel):
    ticket: str
    use_iam_simulation: bool = True   # Use real boto3 if creds available
    anthropic_api_key: Optional[str] = None  # For LLM-enhanced scoring


class V2AnalyzeResponse(BaseModel):
    version: str = "v2"
    ticket: str
    extracted_intent: dict
    trust_scores: dict
    formula_trace: str
    binding_constraint: str
    gate: str
    confidence: float
    iam_simulation: dict
    parameter_changes_from_v1: dict
    what_v1_would_have_returned: dict


@v2_router.post("/analyze", response_model=None)
async def v2_analyze(req: V2TicketRequest):
    """
    V2 full analysis endpoint.
    Returns computed trust scores with full parameter trace.
    Shows what v1 would have returned vs what v2 actually computes.
    """
    params = extract_intent(req.ticket)

    # Real IAM simulation
    iam_result = None
    iam_simulation_data = {"available": False, "result": "not_requested"}
    if req.use_iam_simulation:
        iam_data = simulate_iam_policy(params.action)
        iam_simulation_data = iam_data
        if iam_data["available"] and iam_data.get("policy_score") is not None:
            iam_result = iam_data["result"]

    # Get graph blast radius from v1 graph if available
    graph_blast = None
    if HAS_GRAPH and GLOBAL_GRAPH and params.action != "unknown":
        try:
            blast_data = GLOBAL_GRAPH.compute_blast_radius(params.service)
            graph_blast = blast_data.get("blast_radius")
        except Exception:
            pass

    # Compute v2 trust scores
    trust = compute_v2_trust(
        params=params,
        graph_blast=graph_blast,
        iam_result=iam_result,
    )

    # What v1 would have returned for the same ticket
    v1_scenario_scores = {
        "ec2_scale":    {"intent": 0.93, "rev": 0.88, "blast": 0.06, "policy": 0.95, "confidence": 0.731, "gate": "AUTO"},
        "s3_create":    {"intent": 0.94, "rev": 0.95, "blast": 0.10, "policy": 1.00, "confidence": 0.803, "gate": "AUTO"},
        "iam_delete":   {"intent": 0.18, "rev": 0.05, "blast": 0.20, "policy": 0.10, "confidence": 0.010, "gate": "BLOCK"},
        "iam_attach":   {"intent": 0.85, "rev": 0.92, "blast": 0.40, "policy": 0.65, "confidence": 0.305, "gate": "BLOCK"},
        "rds_modify":   {"intent": 0.88, "rev": 0.65, "blast": 0.50, "policy": 0.92, "confidence": 0.264, "gate": "BLOCK"},
        "lambda_deploy":{"intent": 0.85, "rev": 0.86, "blast": 0.30, "policy": 0.95, "confidence": 0.484, "gate": "APPROVE"},
    }.get(params.action, {"note": "no v1 scenario — would have returned BLOCK for unknown"})

    return {
        "version": "v2",
        "ticket": req.ticket,

        "extracted_intent": {
            "action": params.action,
            "service": params.service,
            "operation": params.operation,
            "environment": params.environment,
            "region": params.region,
            "scale_factor": round(params.scale_factor, 2),
            "source_count": params.source_count,
            "target_count": params.target_count,
            "is_immediate": params.is_immediate,
            "is_production": params.is_production,
            "urgency": params.urgency,
            "has_explicit_rollback": params.has_explicit_rollback,
            "extraction_confidence": params.extraction_confidence,
        },

        "trust_scores": {
            "intent_score":  trust.intent_score,
            "reversibility": trust.reversibility,
            "blast_radius":  trust.blast_radius,
            "policy_score":  trust.policy_score,
            "traces": {
                "intent":       trust.intent_trace,
                "reversibility": trust.reversibility_trace,
                "blast":        trust.blast_trace,
                "policy":       trust.policy_trace,
            }
        },

        "formula_trace": trust.formula_trace,
        "binding_constraint": trust.binding_constraint,
        "gate": trust.gate,
        "confidence": trust.confidence,

        "iam_simulation": iam_simulation_data,

        "parameter_changes_from_v1": {
            "note": "These parameters change the score dynamically in v2 but were IGNORED in v1",
            "scale_factor": params.scale_factor,
            "environment":  params.environment,
            "urgency":      params.urgency,
            "is_immediate": params.is_immediate,
            "region":       params.region,
        },

        "what_v1_would_have_returned": v1_scenario_scores,
    }


@v2_router.post("/extract_intent")
async def v2_extract_intent_only(req: V2TicketRequest):
    """Show ONLY the parameter extraction — useful for the frontend demo panel."""
    params = extract_intent(req.ticket)
    return {
        "raw_ticket": req.ticket,
        "extracted": {
            "action": params.action,
            "service": params.service,
            "operation": params.operation,
            "environment": params.environment,
            "region": params.region,
            "scale_factor": round(params.scale_factor, 2),
            "source_count": params.source_count,
            "target_count": params.target_count,
            "is_immediate": params.is_immediate,
            "urgency": params.urgency,
            "extraction_confidence": params.extraction_confidence,
        },
        "what_changes_score": (
            "In v2, scale_factor, environment, urgency, and is_immediate "
            "directly modify blast_radius, reversibility, and policy_score. "
            "Same ticket with 'in prod' vs 'in dev' produces different confidence."
        )
    }


@v2_router.get("/iam_status")
async def v2_iam_status():
    """Check if real boto3 IAM simulation is available."""
    test_result = simulate_iam_policy("ec2_scale")
    return {
        "iam_simulation_available": test_result["available"],
        "status": test_result["result"],
        "error": test_result.get("error"),
        "setup_instructions": test_result.get("setup_instructions"),
    }


@v2_router.get("/compare/{action}")
async def v2_compare(action: str):
    """
    Show how v2 scores differ for different parameter contexts
    of the same action. This is the killer demo for judges.
    """
    # Same action, three different contexts
    test_cases = [
        f"{action.replace('_', ' ')} in dev",
        f"{action.replace('_', ' ')} in prod",
        f"{action.replace('_', ' ')} in prod immediately",
    ]
    if "scale" in action:
        test_cases = [
            f"scale ec2 from 2 to 3 in dev",
            f"scale ec2 from 2 to 8 in prod",
            f"scale ec2 from 2 to 50 in prod immediately",
        ]

    results = []
    for ticket in test_cases:
        params = extract_intent(ticket)
        trust  = compute_v2_trust(params)
        results.append({
            "ticket": ticket,
            "extracted": {"environment": params.environment, "scale_factor": params.scale_factor, "urgency": params.urgency},
            "scores": {"intent": trust.intent_score, "rev": trust.reversibility, "blast": trust.blast_radius, "policy": trust.policy_score},
            "confidence": trust.confidence,
            "gate": trust.gate,
        })

    return {
        "action": action,
        "demonstration": "Same action, different parameters → different scores",
        "v1_behavior": "All three tickets above would return IDENTICAL scores in v1",
        "v2_results": results,
    }
