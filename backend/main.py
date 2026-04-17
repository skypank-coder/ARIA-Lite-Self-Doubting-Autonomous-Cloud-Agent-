"""
ARIA-Lite++ — FastAPI backend
Single scoring engine: trust_engine_v3
"""

import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Dict, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

from parser import parse_ticket, ParsedIntent
from trust_engine_v3 import run_trust_engine, gate_decision
from iam_simulator import get_iam_simulation
from memory import memory
from scenarios import SCENARIOS
from dependency_graph import (
    build_graph, compute_blast_radius as _dep_blast,
    serialize_graph, propagation_summary, create_demo_architecture,
)

app = FastAPI(title="ARIA-Lite++ v3-engine", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton graph for /graph endpoint
_GRAPH = None


@app.on_event("startup")
async def startup_event():
    global _GRAPH
    try:
        _GRAPH = create_demo_architecture()
        print("INFO: dependency graph initialised")
    except Exception as e:
        print(f"WARNING: graph init failed: {e}")


# ── Request models ────────────────────────────────────────────────────────────

class TicketInput(BaseModel):
    ticket: str

class ExplainRequest(BaseModel):
    ticket: str


# ── Gate label mapping ────────────────────────────────────────────────────────
# v3 uses AUTO_EXECUTE / HUMAN_APPROVAL / HARD_BLOCK
# frontend expects AUTO / APPROVE / BLOCK

_GATE_MAP = {
    "AUTO_EXECUTE":   "AUTO",
    "HUMAN_APPROVAL": "APPROVE",
    "HARD_BLOCK":     "BLOCK",
}

def _map_gate(v3_decision: str) -> str:
    return _GATE_MAP.get(v3_decision, "BLOCK")


# ── Convert ParsedIntent → v3 ticket dict ────────────────────────────────────

def _to_v3(parsed: ParsedIntent) -> Dict:
    """
    Build the flat dict that trust_engine_v3.run_trust_engine expects.
    affected_nodes is derived from risk_signals so the blast radius
    reflects the actual parsed context.
    """
    # Map risk signals to a list of affected service names
    signal_nodes = {
        "prod_destructive": ["ec2", "rds", "lambda", "alb"],
        "admin_privilege":  ["ec2", "lambda", "api"],
        "extreme_scale":    ["rds", "alb", "cloudwatch"],
        "large_scale":      ["rds", "alb"],
        "irreversible_db":  ["ec2", "lambda"],
        "cross_account":    ["iam", "ec2"],
        "public_s3":        ["lambda", "cloudwatch"],
    }
    affected: List[str] = []
    for sig in parsed.risk_signals:
        for node in signal_nodes.get(sig, []):
            if node not in affected:
                affected.append(node)

    return {
        "verb":           parsed.action_verb,
        "service":        parsed.service,
        "env":            parsed.environment,
        "scope":          dict(parsed.scope),
        "affected_nodes": affected,
    }


# ── Audit ─────────────────────────────────────────────────────────────────────

def _write_audit(ticket: str, confidence: float, decision: str) -> None:
    memory.write_audit({
        "ticket_preview": ticket[:80],
        "confidence":     round(confidence, 3),
        "decision":       decision,
        "engine":         "v3",
    })


# ── Debate builder ────────────────────────────────────────────────────────────

def _build_debate(parsed: ParsedIntent, trust: Dict, gate: str) -> Dict:
    svc  = parsed.service.upper()
    verb = parsed.action_verb
    conf = trust["confidence"]
    blast = trust["blast_radius"]
    policy = trust["policy_score"]

    # Identify binding constraint
    components = {
        "intent":       trust["intent_score"],
        "reversibility": trust["reversibility"],
        "policy":       policy,
        "blast_margin": round(1.0 - blast, 3),
    }
    weakest = min(components, key=components.get)

    executor = (
        f"Executor proposes {svc} {verb} — "
        f"intent {trust['intent_score']:.2f}, reversibility {trust['reversibility']:.2f}. "
        f"Confidence {conf:.3f} {'clears' if gate == 'AUTO' else 'approaches' if gate == 'APPROVE' else 'fails'} gate."
    )

    crit_parts = []
    if parsed.contradictions:
        crit_parts.append(f"CONTRADICTION: {parsed.contradictions[0]}.")
    crit_parts.append(
        f"Critic flags {weakest} as binding constraint ({components[weakest]:.2f}). "
        f"{'Blast radius ' + str(blast) + ' — downstream impact detected.' if blast > 0.10 else 'No significant cascade risk.'}"
    )
    if gate == "BLOCK":
        crit_parts.append("Critic veto: component collapse sufficient for hard block.")

    verdict_map = {
        "AUTO":    f"PROCEED — {weakest} limiting but confidence clears 0.80",
        "APPROVE": f"ROUTE TO HUMAN — {weakest} at threshold",
        "BLOCK":   f"HARD BLOCK — {weakest} collapse vetoes execution",
    }

    return {
        "executor":      executor,
        "critic":        " ".join(crit_parts),
        "verdict":       verdict_map[gate],
        "contradictions": parsed.contradictions,
        "second_pass":   gate == "AUTO" and len(parsed.contradictions) > 0,
    }


# ── Premortem builder ─────────────────────────────────────────────────────────

def _build_premortem(parsed: ParsedIntent, gate: str) -> List[Dict]:
    from scenarios import PREMORTEM_ANALYSIS

    scenario_map = {
        ("s3",     "safe"):        "s3_create",
        ("s3",     "destructive"): "s3_create",
        ("iam",    "destructive"): "iam_delete",
        ("iam",    "safe"):        "iam_attach",
        ("iam",    "mutating"):    "iam_attach",
        ("ec2",    "scaling"):     "ec2_scale",
        ("ec2",    "safe"):        "ec2_scale",
        ("rds",    "mutating"):    "rds_modify",
        ("rds",    "destructive"): "rds_modify",
        ("lambda", "safe"):        "lambda_deploy",
        ("lambda", "mutating"):    "lambda_deploy",
    }
    key  = scenario_map.get((parsed.service, parsed.action_verb))
    base = PREMORTEM_ANALYSIS.get(key, []) if key else []

    extra = []
    if "prod_destructive" in parsed.risk_signals:
        extra.append({"failure": "Production outage from destructive action", "severity": 5,
                      "mitigation": "Stage in dev/staging first. Require 2-person approval."})
    if "admin_privilege" in parsed.risk_signals:
        extra.append({"failure": "Admin privilege grants unrestricted AWS access", "severity": 5,
                      "mitigation": "Replace with least-privilege policy."})
    if "public_s3" in parsed.risk_signals:
        extra.append({"failure": "Public S3 bucket exposes sensitive data", "severity": 5,
                      "mitigation": "Enable S3 Block Public Access."})

    items = (extra + base)[:3] or [{"failure": "Unknown failure mode", "severity": 2,
                                     "mitigation": "Manual review required."}]
    return [
        {
            "severity":     it.get("severity", 1),
            "title":        it.get("failure", "Unknown"),
            "probability":  (i + 1) * 10 + (5 if gate == "BLOCK" else 0),
            "mitigation":   it.get("mitigation", ""),
            "impacted_deps": max(1, it.get("severity", 1) - 1),
        }
        for i, it in enumerate(items)
    ]


# ── Execution log builder ─────────────────────────────────────────────────────

def _build_execution_log(parsed: ParsedIntent, trust: Dict, gate: str) -> List[Dict]:
    t = datetime.now().strftime("%H:%M:%S")

    entries = [
        {"msg": f"[{t}.001] ● PARSE  verb={parsed.action_verb} service={parsed.service} env={parsed.environment} urgency={parsed.urgency}", "status": "ok"},
        {"msg": f"[{t}.040] {'▲' if parsed.risk_signals else '●'} risk_signals={parsed.risk_signals or 'none'}", "status": "warn" if parsed.risk_signals else "ok"},
        {"msg": f"[{t}.080] {'▲' if parsed.contradictions else '●'} contradictions={len(parsed.contradictions)}", "status": "warn" if parsed.contradictions else "ok"},
        {"msg": f"[{t}.120] ● SCORE  intent={trust['intent_score']:.3f}  rev={trust['reversibility']:.3f}  blast={trust['blast_radius']:.3f}  policy={trust['policy_score']:.3f}", "status": "ok"},
        {"msg": f"[{t}.160] ● CONF   {trust['intent_score']:.3f} × {trust['reversibility']:.3f} × (1-{trust['blast_radius']:.3f}) × {trust['policy_score']:.3f} = {trust['raw_confidence']:.4f}", "status": "ok"},
        {"msg": f"[{t}.180] ● CALIB  raw={trust['raw_confidence']:.4f} → final={trust['confidence']:.4f}", "status": "ok"},
    ]

    if gate == "BLOCK":
        entries.append({"msg": f"[{t}.200] ■ HARD BLOCK — confidence {trust['confidence']:.4f} < 0.50", "status": "fail"})
        components = {"intent": trust["intent_score"], "reversibility": trust["reversibility"],
                      "policy": trust["policy_score"], "blast_margin": round(1.0 - trust["blast_radius"], 3)}
        weakest = min(components, key=components.get)
        entries.append({"msg": f"[{t}.210] ■ binding_constraint={weakest} ({components[weakest]:.3f})", "status": "fail"})
        entries.append({"msg": f"[{t}.220] ▲ incident routed to on-call SRE", "status": "warn"})

    elif gate == "APPROVE":
        entries.append({"msg": f"[{t}.200] ⊙ APPROVE — confidence {trust['confidence']:.4f} in [0.50, 0.80)", "status": "warn"})
        entries.append({"msg": f"[{t}.210] ⊙ routing to 1-click human approver — operation suspended", "status": "warn"})

    else:  # AUTO
        entries.append({"msg": f"[{t}.200] ● AUTO-EXECUTE — confidence {trust['confidence']:.4f} ≥ 0.80", "status": "ok"})
        entries.append({"msg": f"[{t}.210] ● pre-flight checks passed — initiating execution", "status": "ok"})

        svc = parsed.service
        if svc == "ec2" and parsed.action_verb == "scaling":
            scope = parsed.scope
            cur, tgt = scope.get("current", "?"), scope.get("target", "?")
            entries += [
                {"msg": f"[{t}.230] ● EC2 scale {cur} → {tgt} — RunInstances sent", "status": "ok"},
                {"msg": f"[{t}.260] ▲ monitoring RDS pool — watching for exhaustion", "status": "warn"},
                {"msg": f"[{t}.300] ▲ RDS pool rising — 421/500 (84%) WARNING", "status": "warn"},
                {"msg": f"[{t}.340] ■ RDS CRITICAL — 487/500 — CASCADE DETECTED", "status": "fail"},
                {"msg": f"[{t}.350] ↩ ROLLBACK INITIATED — auto-reversal triggered", "status": "rollback"},
                {"msg": f"[{t}.370] ↩ step 1/4 — suspending ALB registration", "status": "rollback"},
                {"msg": f"[{t}.390] ↩ step 2/4 — draining in-flight requests (30s grace)", "status": "rollback"},
                {"msg": f"[{t}.430] ↩ step 3/4 — TerminateInstances sent", "status": "rollback"},
                {"msg": f"[{t}.480] ↩ step 4/4 — RDS pool stable 89/500 — safe zone restored", "status": "rollback"},
                {"msg": f"[{t}.500] ● system restored to known-good state ({cur} instances)", "status": "ok"},
                {"msg": f"[{t}.510] ◉ memory updated — ec2_scaling incident recorded", "status": "memory"},
            ]
        elif svc == "s3":
            entries += [
                {"msg": f"[{t}.230] ● S3 {parsed.action_verb} — validating bucket name", "status": "ok"},
                {"msg": f"[{t}.250] ● encryption policy applied — AES-256 enforced", "status": "ok"},
                {"msg": f"[{t}.270] ● operation complete", "status": "ok"},
            ]
        elif svc == "lambda":
            entries += [
                {"msg": f"[{t}.230] ● Lambda deploy — previous version archived", "status": "ok"},
                {"msg": f"[{t}.260] ● UpdateFunctionCode complete — new version live", "status": "ok"},
                {"msg": f"[{t}.280] ● health check passed — rollback alias preserved", "status": "ok"},
            ]
        elif svc == "rds":
            entries += [
                {"msg": f"[{t}.230] ● RDS {parsed.action_verb} — snapshot created pre-change", "status": "ok"},
                {"msg": f"[{t}.260] ● parameter applied — replication lag nominal", "status": "ok"},
            ]
        else:
            entries.append({"msg": f"[{t}.230] ● {svc.upper()} {parsed.action_verb} — operation complete", "status": "ok"})

    if parsed.contradictions:
        entries.append({"msg": f"[{t}.800] ▲ CONTRADICTION: {parsed.contradictions[0]}", "status": "warn"})

    return entries


# ── Simulation builder ────────────────────────────────────────────────────────

def _build_simulation(trust: Dict, parsed: ParsedIntent) -> List[Dict]:
    import math
    conf  = trust["confidence"]
    blast = trust["blast_radius"]
    scale = parsed.scope.get("scale_factor", 1)

    success = max(10, round(conf * 95))
    if scale > 10:
        success = max(10, success - 25)
    cascade = round(blast * 30)
    rollback = round((blast * 15) + max(0, scale - 5) * 1.5) if blast > 0.10 or scale > 5 else 0
    rollback = min(rollback, 25)
    degraded = max(0, 100 - success - cascade - rollback)

    sims = [
        {"scenario": "Clean success",       "probability": success,  "detail": f"{parsed.service.upper()} state matches intent.", "type": "success"},
        {"scenario": "Degraded execution",  "probability": degraded, "detail": "Retry required on one step.",                    "type": "degraded"},
        {"scenario": "Cascade failure",     "probability": cascade,  "detail": f"Downstream impact detected.",                   "type": "cascading_failure"},
        {"scenario": "Rollback triggered",  "probability": rollback, "detail": "Auto-rollback armed.",                           "type": "rollback"},
    ]

    total = sum(s["probability"] for s in sims)
    if total != 100 and sims:
        sims[0]["probability"] += 100 - total

    return [s for s in sims if s["probability"] > 0]


# ── Core response builder ─────────────────────────────────────────────────────

def _build_response(ticket: str, parsed: ParsedIntent) -> Dict:
    v3_input = _to_v3(parsed)
    trust    = run_trust_engine(v3_input)          # only engine called
    gate     = _map_gate(trust["decision"])        # AUTO / APPROVE / BLOCK

    # Memory
    memory_key = f"{parsed.service}_{parsed.action_verb}"
    penalty    = memory.get_penalty(memory_key)

    # EC2 scaling AUTO → record rollback
    has_rollback = False
    if parsed.service == "ec2" and parsed.action_verb == "scaling" and gate == "AUTO":
        has_rollback = True
        memory.record(intent=memory_key, outcome="ROLLBACK",
                      note="RDS pool exhaustion eu-west-1", confidence=trust["confidence"])

    debate        = _build_debate(parsed, trust, gate)
    premortem     = _build_premortem(parsed, gate)
    execution_log = _build_execution_log(parsed, trust, gate)
    simulation    = _build_simulation(trust, parsed)
    iam_sim       = get_iam_simulation(parsed.scope, parsed.action_verb)

    scenario_label = f"{parsed.service}_{parsed.action_verb}"

    _write_audit(ticket, trust["confidence"], gate)

    return {
        "scenario":  scenario_label,
        "gate":      gate,
        "trust": {
            "intent_score":  trust["intent_score"],
            "reversibility": trust["reversibility"],
            "blast_radius":  trust["blast_radius"],
            "policy_score":  trust["policy_score"],
            "confidence":    trust["confidence"],
        },
        "debate":        debate,
        "premortem":     premortem,
        "execution_log": execution_log,
        "simulation":    simulation,
        "has_rollback":  has_rollback,
        "elapsed_ms":    0,
        "parsed": {
            "action_verb":  parsed.action_verb,
            "service":      parsed.service,
            "environment":  parsed.environment,
            "urgency":      parsed.urgency,
            "scope":        parsed.scope,
            "risk_signals": parsed.risk_signals,
        },
        "contradictions": parsed.contradictions,
        "iam_simulation": iam_sim,
        "memory": {
            "active":  penalty.get("active", False),
            "count":   penalty.get("count", 0),
            "pattern": penalty.get("pattern"),
            "note":    penalty.get("note"),
        },
        "uncertainty": {
            "score": round(0.30 if parsed.service == "unknown" else
                           0.15 if parsed.environment == "unknown" else 0.0, 2),
            "level": "HIGH" if parsed.service == "unknown" else
                     "MEDIUM" if parsed.environment == "unknown" else "LOW",
            "signals": [],
            "recommendation": "CLARIFY INPUT" if parsed.service == "unknown" else "PROCEED",
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ARIA-LITE++", "version": "5.0.0", "engine": "trust_engine_v3"}


@app.get("/memory")
def get_memory_state():
    return {"incidents": memory.incidents, "patterns": memory.patterns,
            "audit_count": len(memory.get_audit_log())}


@app.get("/audit")
def audit_log():
    log = memory.get_audit_log()
    return {"entries": log, "count": len(log)}


@app.post("/process_ticket")
def process_ticket(input_data: TicketInput):
    try:
        ticket = input_data.ticket.strip()
        if not ticket:
            return {"gate": "BLOCK", "reason": "Empty ticket", "confidence": 0.0}
        if len(ticket) > 500:
            return {"gate": "BLOCK", "reason": "Ticket exceeds 500 characters", "confidence": 0.0}

        parsed = parse_ticket(ticket)

        if parsed.service == "unknown" and parsed.action_verb == "unknown":
            return {
                "gate": "BLOCK", "confidence": 0.0,
                "reason": "Unrecognized input — no service or verb detected",
                "uncertainty": {"score": 1.0, "level": "HIGH",
                                "signals": ["SERVICE_UNRECOGNIZED", "ACTION_UNCLEAR"],
                                "recommendation": "CLARIFY INPUT"},
                "contradictions": [], "iam_simulation": None,
                "memory": {"active": False, "count": 0, "pattern": None, "note": None},
            }

        return _build_response(ticket, parsed)

    except Exception as e:
        traceback.print_exc()
        return {"gate": "BLOCK", "confidence": 0.0, "reason": str(e)}


@app.post("/v2/analyze")
def analyze_v2(input_data: TicketInput):
    return process_ticket(input_data)


@app.post("/trust/explain")
def trust_explain(req: ExplainRequest):
    ticket = req.ticket.strip()
    if not ticket:
        return {"error": "Empty ticket"}

    parsed   = parse_ticket(ticket)
    v3_input = _to_v3(parsed)
    trust    = run_trust_engine(v3_input)
    gate     = _map_gate(trust["decision"])

    components = {
        "intent_score":    trust["intent_score"],
        "reversibility":   trust["reversibility"],
        "blast_radius_inv": round(1.0 - trust["blast_radius"], 3),
        "policy_score":    trust["policy_score"],
    }
    weakest = min(components, key=components.get)

    return {
        "ticket":   ticket,
        "parsed":   {"action_verb": parsed.action_verb, "service": parsed.service,
                     "environment": parsed.environment, "urgency": parsed.urgency,
                     "scope": parsed.scope, "risk_signals": parsed.risk_signals},
        "scores":   trust,
        "confidence": trust["confidence"],
        "decision": gate,
        "formula_trace": (
            f"raw = intent × policy × (0.55×rev + 0.45×(1-blast)^1.3)\n"
            f"    = {trust['intent_score']} × {trust['policy_score']} × "
            f"(0.55×{trust['reversibility']} + 0.45×{round((1-trust['blast_radius'])**1.3,3)})\n"
            f"    = {trust['raw_confidence']}\n"
            f"calibrated = {trust['confidence']}"
        ),
        "binding_constraint": f"{weakest} = {components[weakest]}",
        "contradictions": parsed.contradictions,
        "threshold_context": {
            "to_auto":    round(max(0, 0.80 - trust["confidence"]), 3),
            "to_approve": round(max(0, 0.50 - trust["confidence"]), 3),
            "current_gate": gate,
        },
    }


@app.get("/scenarios")
def list_scenarios():
    result = {}
    for name, scenario in SCENARIOS.items():
        action = scenario["action"]
        result[name] = {
            "name":    scenario.get("name", name),
            "service": action["service"],
            "operation": action["operation"],
            "match_terms": scenario.get("match_terms", []),
        }
    return {"scenarios": result, "count": len(result)}


@app.get("/graph/{intent}")
def get_graph(intent: str):
    if intent not in SCENARIOS:
        return {"error": f"Unknown intent: {intent}", "known": list(SCENARIOS.keys())}
    scenario = SCENARIOS[intent]
    try:
        graph       = build_graph(scenario)
        entry_nodes = scenario["action"]["entry_nodes"]
        blast       = _dep_blast(graph, entry_nodes)
        serialized  = serialize_graph(graph, blast, entry_nodes)
        waves       = propagation_summary(blast, graph)
        return {
            "intent": intent,
            "graph":  serialized,
            "blast":  {"weighted_impact": blast["weighted_impact"],
                       "affected_count": len(blast["affected_nodes"]),
                       "waves": waves},
            "entry_nodes": entry_nodes,
        }
    except Exception as e:
        return {"error": str(e), "intent": intent}
