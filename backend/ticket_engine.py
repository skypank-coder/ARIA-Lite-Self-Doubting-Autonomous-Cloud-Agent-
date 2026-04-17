from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import traceback

from parser import parse_ticket, ParsedIntent
from trust_engine_v3 import run_trust_engine, gate_decision
from iam_simulator import get_iam_simulation
from memory import memory

app = FastAPI(title="ARIA-Lite++ v5", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ─────────────────────────────────

class TicketInput(BaseModel):
    ticket: str

class ExplainRequest(BaseModel):
    ticket: str


# ── Helpers ───────────────────────────────────────

def _write_audit(ticket: str, confidence: float, decision: str):
    memory.write_audit({
        "ticket_preview": ticket[:80],
        "confidence": round(confidence, 3),
        "decision": decision,
        "engine": "v3",
    })


def _convert_parsed_to_v3(parsed: ParsedIntent):
    return {
        "verb": parsed.action_verb,
        "service": parsed.service,
        "env": parsed.environment,
        "scope": parsed.scope,
        "affected_nodes": parsed.scope.get("affected_nodes", []),
    }


def _build_response(ticket: str, parsed: ParsedIntent):
    ticket_dict = _convert_parsed_to_v3(parsed)

    trust = run_trust_engine(ticket_dict)

    decision = gate_decision(trust["confidence"])

    # Basic debate (lightweight)
    debate = {
        "executor": f"Operation {parsed.action_verb} on {parsed.service}",
        "critic": f"Blast radius {trust['blast_radius']}, policy {trust['policy_score']}",
        "verdict": f"{decision} — confidence {trust['confidence']:.2f}",
    }

    # Simple premortem
    premortem = [{
        "severity": 3,
        "title": "Potential system impact",
        "probability": int(trust["blast_radius"] * 100),
        "mitigation": "Review dependencies before execution",
        "impacted_deps": len(ticket_dict["affected_nodes"]),
    }]

    # Execution log
    execution_log = [
        {"msg": f"Parsed → {parsed.action_verb}/{parsed.service}", "status": "ok"},
        {"msg": f"Confidence → {trust['confidence']:.3f}", "status": "ok"},
        {"msg": f"Decision → {decision}", "status": "ok"},
    ]

    # Simulation (simple placeholder)
    simulation = [
        {"scenario": "Success", "probability": int(trust["confidence"] * 100), "detail": "Execution successful"},
        {"scenario": "Failure", "probability": int((1 - trust["confidence"]) * 100), "detail": "Failure scenario"},
    ]

    iam_sim = get_iam_simulation(parsed.scope, parsed.action_verb)

    _write_audit(ticket, trust["confidence"], decision)

    return {
        "scenario": f"{parsed.service}_{parsed.action_verb}",
        "gate": decision,
        "trust": {
            "intent_score": trust["intent_score"],
            "reversibility": trust["reversibility"],
            "blast_radius": trust["blast_radius"],
            "policy_score": trust["policy_score"],
            "confidence": trust["confidence"],
        },
        "debate": debate,
        "premortem": premortem,
        "execution_log": execution_log,
        "simulation": simulation,
        "has_rollback": False,
        "elapsed_ms": 0,

        # keep frontend compatibility
        "parsed": {
            "action_verb": parsed.action_verb,
            "service": parsed.service,
            "environment": parsed.environment,
            "urgency": parsed.urgency,
            "scope": parsed.scope,
            "risk_signals": parsed.risk_signals,
        },
        "contradictions": parsed.contradictions,
        "iam_simulation": iam_sim,
        "memory": {
            "active": False,
            "count": 0,
            "pattern": None,
            "note": None,
        },
    }


# ── Endpoints ─────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "engine": "v3-only"}


@app.post("/process_ticket")
def process_ticket(input_data: TicketInput):
    try:
        ticket = input_data.ticket.strip()

        if not ticket:
            return {"gate": "BLOCK", "reason": "Empty ticket", "confidence": 0.0}

        parsed = parse_ticket(ticket)

        if parsed.service == "unknown" and parsed.action_verb == "unknown":
            return {
                "gate": "BLOCK",
                "confidence": 0.0,
                "reason": "Unrecognized input",
            }

        return _build_response(ticket, parsed)

    except Exception as e:
        traceback.print_exc()
        return {"gate": "BLOCK", "confidence": 0.0, "reason": str(e)}


@app.post("/trust/explain")
def explain(req: ExplainRequest):
    parsed = parse_ticket(req.ticket)
    ticket_dict = _convert_parsed_to_v3(parsed)

    trust = run_trust_engine(ticket_dict)

    weakest = min(
        ["intent_score", "reversibility", "blast_radius", "policy_score"],
        key=lambda k: trust[k] if k != "blast_radius" else (1 - trust[k])
    )

    return {
        "confidence": trust["confidence"],
        "decision": gate_decision(trust["confidence"]),
        "binding_constraint": weakest,
        "scores": trust,
    }