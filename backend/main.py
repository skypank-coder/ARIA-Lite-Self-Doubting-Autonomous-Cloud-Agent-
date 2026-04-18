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
from ai_debate import run_ai_debate
from self_doubt import apply_self_doubt, generate_self_doubt
from simulation_engine import run_simulation
from dynamic_graph import get_affected_nodes, build_dynamic_graph
from ai_layer import ai_adjustment
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
    Uses dynamic_graph to derive affected_nodes from parsed service.
    """
    affected = get_affected_nodes(parsed)
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


# ── Premortem builder (dynamic) ──────────────────────────────────────────────

def _build_premortem(parsed: ParsedIntent, trust: Dict, graph: Dict) -> List[Dict]:
    """
    Generates pre-mortem risks entirely from trust scores, environment,
    scale, and graph node count. No static template lookup.
    """
    risks = []
    node_count = len(graph.get("nodes", []))
    scale      = parsed.scope.get("scale_factor", 1)
    blast      = trust["blast_radius"]
    rev        = trust["reversibility"]
    policy     = trust["policy_score"]
    conf       = trust["confidence"]

    if policy < 0.20:
        risks.append({
            "severity": 5,
            "title": "Privilege escalation risk",
            "probability": 85,
            "mitigation": "Replace with least-privilege policy. Use IAM Access Analyzer.",
            "impacted_deps": node_count,
        })

    if parsed.environment == "production" and parsed.action_verb == "destructive":
        risks.append({
            "severity": 5,
            "title": "Production outage — destructive action on live environment",
            "probability": 75,
            "mitigation": "Stage in dev/staging first. Require 2-person approval.",
            "impacted_deps": node_count,
        })

    if blast > 0.20:
        risks.append({
            "severity": 4,
            "title": f"Cascade failure — {node_count} dependent service(s) at risk",
            "probability": round(blast * 100),
            "mitigation": "Implement circuit breakers. Test in staging with traffic mirroring.",
            "impacted_deps": node_count,
        })

    if rev < 0.30:
        risks.append({
            "severity": 4,
            "title": "Low reversibility — recovery window is narrow",
            "probability": round((1 - rev) * 80),
            "mitigation": "Create snapshot/backup before execution. Verify rollback procedure.",
            "impacted_deps": max(1, node_count - 1),
        })

    if scale > 50:
        risks.append({
            "severity": 5,
            "title": f"Extreme scale change ({scale}×) — infrastructure shock risk",
            "probability": 70,
            "mitigation": "Use incremental scaling with canary deployment. Monitor RDS pool.",
            "impacted_deps": node_count,
        })
    elif scale > 10:
        risks.append({
            "severity": 3,
            "title": f"Large scale change ({scale}×) — resource contention likely",
            "probability": 45,
            "mitigation": "Pre-warm dependent services. Set scaling cooldown period.",
            "impacted_deps": max(1, node_count - 1),
        })

    if "public_s3" in parsed.risk_signals:
        risks.append({
            "severity": 5,
            "title": "Public S3 bucket — data exposure risk",
            "probability": 90,
            "mitigation": "Enable S3 Block Public Access. Audit bucket policy.",
            "impacted_deps": 1,
        })

    if conf < 0.30 and not risks:
        risks.append({
            "severity": 3,
            "title": "Low confidence decision — outcome uncertain",
            "probability": round((1 - conf) * 60),
            "mitigation": "Clarify ticket intent. Add environment and scope context.",
            "impacted_deps": node_count,
        })

    # Always return at least one item, cap at 3
    if not risks:
        risks.append({
            "severity": 1,
            "title": "No critical failure modes identified",
            "probability": 5,
            "mitigation": "Standard monitoring applies.",
            "impacted_deps": 0,
        })

    return risks[:3]


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


# _build_simulation removed — run_simulation from simulation_engine.py is used directly


# ── Core response builder ─────────────────────────────────────────────────────

def _build_response(ticket: str, parsed: ParsedIntent) -> Dict:
    v3_input = _to_v3(parsed)

    # ── Base scoring (trust_engine_v3 only) ──────────────────────────────────
    trust = run_trust_engine(v3_input)
    trust["affected_count"] = len(v3_input["affected_nodes"])

    # ── Memory penalty (softened: max 0.80, step 0.05) ──────────────────────
    penalty = memory.get_penalty(
        service=parsed.service,
        verb=parsed.action_verb,
        env=parsed.environment,
    )
    count = penalty.get("count", 0)
    memory_factor = max(0.80, 1.0 - 0.05 * count) if count > 0 else 1.0
    conf = round(trust["confidence"] * memory_factor, 4)

    # ── Unknown service guard (hard block only) ───────────────────────────────
    if parsed.service == "unknown":
        conf = round(conf * 0.70, 4)

    # ── AI layer (semantic reasoning) ────────────────────────────────────────
    conf, ai_notes = ai_adjustment(ticket, conf)

    # ── Dynamic graph (needed by self-doubt for node count) ──────────────────
    graph = build_dynamic_graph(parsed)

    # ── Self-doubt: display flags (for UI) ───────────────────────────────────
    trust["confidence"] = conf
    _, doubt_factors = apply_self_doubt(parsed, trust, conf)
    display_doubt_flags = generate_self_doubt(parsed, trust, graph)

    # ── Controlled self-doubt penalties (max 2, context-aware) ───────────────
    _DESTRUCTIVE_VERBS = {"delete", "remove", "destroy", "terminate", "purge", "drop", "wipe"}
    penalties_applied = 0

    if parsed.contradictions and penalties_applied < 2:
        conf = round(conf * 0.85, 4)
        penalties_applied += 1

    if parsed.scope.get("scale_factor", 1) > 20 and penalties_applied < 2:
        conf = round(conf * 0.80, 4)
        penalties_applied += 1

    if (parsed.environment == "unknown"
            and parsed.action_verb in _DESTRUCTIVE_VERBS
            and penalties_applied < 2):
        conf = round(conf * 0.85, 4)
        penalties_applied += 1

    # ── Stability boost: safe ops cannot be dragged below 90% of raw score ───
    _SAFE_VERBS = {"safe", "safe_mutating", "create", "attach", "deploy", "backup",
                   "snapshot", "restore", "read", "list", "describe"}
    if parsed.action_verb in _SAFE_VERBS:
        conf = max(conf, round(trust["confidence"] * 0.90, 4))

    # ── Clamp ─────────────────────────────────────────────────────────────────
    final_conf = round(max(0.01, min(0.99, conf)), 4)
    trust["confidence"] = final_conf

    # ── Gate (recomputed after all adjustments) ───────────────────────────────
    gate = _map_gate(gate_decision(final_conf))
    # ── Memory learning ───────────────────────────────────────────────────────
    if gate == "BLOCK":
        # BUG 1 FIX: record only FAIL — never also RISKY_PATTERN for same ticket
        memory.record(service=parsed.service, verb=parsed.action_verb,
                      env=parsed.environment, outcome="FAIL", gate=gate,
                      confidence=final_conf, note="Blocked high-risk operation")
    elif gate == "AUTO":
        memory.record(service=parsed.service, verb=parsed.action_verb,
                      env=parsed.environment, outcome="SUCCESS", gate=gate,
                      confidence=final_conf)
    elif gate == "APPROVE" and 0.30 <= final_conf <= 0.60:
        # Only record RISKY_PATTERN when gate is APPROVE (not BLOCK)
        memory.record(service=parsed.service, verb=parsed.action_verb,
                      env=parsed.environment, outcome="RISKY_PATTERN", gate=gate,
                      confidence=final_conf, note="Borderline risky operation")

    # EC2 rollback learning
    has_rollback = False
    if parsed.service == "ec2" and parsed.action_verb == "scaling" and gate == "AUTO":
        has_rollback = True
        memory.record(service=parsed.service, verb=parsed.action_verb,
                      env=parsed.environment, outcome="ROLLBACK", gate=gate,
                      confidence=final_conf, note="RDS pool exhaustion")

    # ── AI Debate ─────────────────────────────────────────────────────────────
    debate = run_ai_debate(
        ticket, trust,
        graph=graph,
        contradictions=parsed.contradictions,
        env=parsed.environment,
        verb=parsed.action_verb,
        scale=parsed.scope.get("scale_factor", 1.0),
    )

    # Agent contradiction penalty — close scores signal genuine ambiguity
    if debate.get("agent_contradiction"):
        final_conf = round(final_conf * 0.90, 4)
        trust["confidence"] = final_conf

    # ── Simulation ────────────────────────────────────────────────────────────
    simulation = run_simulation(parsed, trust)

    # ── Pre-mortem + execution log + IAM sim ───────────────────────────────
    premortem     = _build_premortem(parsed, trust, graph)
    execution_log = _build_execution_log(parsed, trust, gate)
    iam_sim       = get_iam_simulation(parsed.scope, parsed.action_verb)

    scenario_label = f"{parsed.service}_{parsed.action_verb}"
    _write_audit(ticket, final_conf, gate)

    return {
        "scenario":  scenario_label,
        "gate":      gate,
        "trust": {
            "intent_score":  trust["intent_score"],
            "reversibility": trust["reversibility"],
            "blast_radius":  trust["blast_radius"],
            "policy_score":  trust["policy_score"],
            "confidence":    final_conf,
        },
        "debate":        {
            **debate,
            "executor_strength": debate.get("scores", {}).get("executor_strength"),
            "critic_strength":   debate.get("scores", {}).get("critic_strength"),
            "agent_contradiction": debate.get("agent_contradiction"),
        },
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
        "contradictions":  parsed.contradictions,
        "iam_simulation":  iam_sim,
        "graph":           graph,
        "self_doubt":      doubt_factors,
        "self_doubt_flags": [
            {"type": f["type"], "msg": f["msg"],
             "impact": f"-{int(f['impact'] * 100)}%"}
            for f in display_doubt_flags
        ],
        "ai_notes":        ai_notes,
        "parsed_meta": {
            "verb_class":   parsed.action_verb,
            "service":      parsed.service,
            "environment":  parsed.environment,
            "urgency":      parsed.urgency,
            "risk_signals": parsed.risk_signals,
        },
        "memory_timeline": memory.get_timeline(parsed.service),
        "memory": {
            "active":      penalty["active"],
            "count":       penalty["count"],
            "pattern":     penalty.get("pattern"),
            "note":        penalty.get("note"),
            "penalty":     penalty["penalty"],
            "total_count": memory.total_count,
        },
        "uncertainty": {
            "score": round(
                0.40 if parsed.service == "unknown" else
                0.20 if parsed.environment == "unknown" else 0.05, 2
            ),
            "level": (
                "HIGH"   if parsed.service == "unknown" else
                "MEDIUM" if parsed.environment == "unknown" else "LOW"
            ),
            "signals":        [f["type"] for f in doubt_factors],
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
            "audit_count": len(memory.get_audit_log()),
            "total_count": memory.total_count}


@app.get("/memory/timeline/{service}")
def memory_timeline(service: str):
    entries = memory.get_timeline(service)
    return {"service": service, "entries": entries}


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


# ── Audit report ──────────────────────────────────────────────────────────────

class AuditReportRequest(BaseModel):
    ticket: str
    groq_api_key: str = ""


def _rule_based_audit(ticket: str, parsed, trust: Dict, gate: str,
                      penalty: Dict, doubt_factors: List, ai_notes: List) -> str:
    """
    Generates a structured audit report without LLM.
    Used when no Groq API key is provided.
    """
    conf    = trust["confidence"]
    blast   = trust["blast_radius"]
    rev     = trust["reversibility"]
    policy  = trust["policy_score"]
    intent  = trust["intent_score"]

    risk_level = "HIGH" if conf < 0.30 else "MEDIUM" if conf < 0.65 else "LOW"

    doubt_summary = ", ".join(
        f"{f['type']} ({f['impact']})" for f in doubt_factors
    ) if doubt_factors else "None detected"

    ai_summary = "; ".join(ai_notes) if ai_notes else "No semantic anomalies"

    memory_summary = (
        f"{penalty['count']} prior incident(s) — penalty {penalty['penalty']:.2f}x applied"
        if penalty["active"] else "No prior incidents on record"
    )

    # Determine verdict
    if gate == "BLOCK" and conf < 0.15:
        verdict = "APPROPRIATE"
        verdict_reason = "System correctly identified high-risk operation and blocked it."
    elif gate == "AUTO" and conf > 0.80 and not doubt_factors:
        verdict = "APPROPRIATE"
        verdict_reason = "High confidence with no self-doubt signals — auto-execution justified."
    elif gate == "APPROVE" and 0.50 <= conf < 0.80:
        verdict = "APPROPRIATE"
        verdict_reason = "Borderline confidence correctly routed to human review."
    elif gate == "AUTO" and doubt_factors:
        verdict = "RISKY"
        verdict_reason = "Auto-executed despite active self-doubt signals — warrants review."
    elif gate == "BLOCK" and conf > 0.45:
        verdict = "CONSERVATIVE"
        verdict_reason = "Blocked at relatively high confidence — may be over-cautious."
    else:
        verdict = "APPROPRIATE"
        verdict_reason = "Decision aligns with computed risk profile."

    # Top 3 failure modes
    failure_modes = []
    if blast > 0.30:
        failure_modes.append(f"Cascade failure — blast radius {blast:.2f} affects downstream services")
    if rev < 0.30:
        failure_modes.append(f"Irreversible damage — reversibility {rev:.2f} means recovery is difficult")
    if policy < 0.50:
        failure_modes.append(f"Policy violation — score {policy:.2f} indicates compliance risk")
    if parsed.environment == "production" and parsed.action_verb == "destructive":
        failure_modes.append("Production outage — destructive action on live environment")
    if not failure_modes:
        failure_modes.append("No critical failure modes identified at current risk level")
    failure_modes = failure_modes[:3]

    report = f"""═══════════════════════════════════════════════════════════
ARIA-LITE++ CLOUD RISK AUDIT REPORT
═══════════════════════════════════════════════════════════
Ticket   : {ticket}
Service  : {parsed.service.upper()}  |  Action: {parsed.action_verb}
Env      : {parsed.environment}  |  Gate: {gate}  |  Risk: {risk_level}
───────────────────────────────────────────────────────────

1. EXECUTIVE SUMMARY
   Decision: {gate} with confidence {conf:.4f}.
   Service {parsed.service.upper()} {parsed.action_verb} in {parsed.environment} environment.
   Risk level assessed as {risk_level} based on blast radius {blast:.2f} and reversibility {rev:.2f}.

2. RISK ASSESSMENT
   Intent Score  : {intent:.3f}  — {'clear operational intent' if intent > 0.70 else 'ambiguous or risky intent'}
   Reversibility : {rev:.3f}  — {'easily reversible' if rev > 0.70 else 'difficult to reverse' if rev < 0.30 else 'partially reversible'}
   Blast Radius  : {blast:.3f}  — {'isolated impact' if blast < 0.15 else 'moderate cascade risk' if blast < 0.40 else 'HIGH cascade risk'}
   Policy Score  : {policy:.3f}  — {'compliant' if policy > 0.70 else 'policy concern' if policy < 0.40 else 'borderline compliance'}
   Confidence    : {conf:.4f}

3. KEY FAILURE MODES
   {''.join(f'   [{i+1}] {fm}{chr(10)}' for i, fm in enumerate(failure_modes))}
4. SYSTEM BEHAVIOR ANALYSIS
   Decision correctness : {verdict_reason}
   Overconfidence check : {'Possible — high confidence despite risk signals' if gate == 'AUTO' and doubt_factors else 'Not detected'}
   Underestimation check: {'Possible — blocked at moderate confidence' if gate == 'BLOCK' and conf > 0.40 else 'Not detected'}

5. MEMORY IMPACT
   {memory_summary}
   {'Penalty reduced confidence from base score.' if penalty['active'] else 'No memory adjustment applied.'}

6. SELF-DOUBT ANALYSIS
   Signals detected : {doubt_summary}
   AI layer notes   : {ai_summary}
   {'Self-doubt correctly reduced confidence before gate decision.' if doubt_factors else 'No anomalies — scoring proceeded without adjustment.'}

7. FINAL VERDICT
   ▶ {verdict}
   {verdict_reason}
═══════════════════════════════════════════════════════════"""

    return report


@app.post("/audit/report")
def audit_report(req: AuditReportRequest):
    """
    Generates a structured AI Cloud Risk Audit Report for a ticket.
    Uses Groq LLM if api key provided, falls back to rule-based generation.
    """
    try:
        ticket = req.ticket.strip()
        if not ticket:
            return {"error": "Empty ticket"}

        # Run full pipeline to get all data
        parsed        = parse_ticket(ticket)
        v3_input      = _to_v3(parsed)
        trust         = run_trust_engine(v3_input)
        trust["affected_count"] = len(v3_input["affected_nodes"])

        penalty           = memory.get_penalty(service=parsed.service,
                                               verb=parsed.action_verb,
                                               env=parsed.environment)
        conf              = round(trust["confidence"] * penalty["penalty"], 4)
        if parsed.service == "unknown":
            conf = round(conf * 0.70, 4)
        conf, ai_notes    = ai_adjustment(ticket, conf)
        trust["confidence"] = conf
        conf, doubt_factors = apply_self_doubt(parsed, trust, conf)
        conf              = round(max(0.0, min(1.0, conf)), 4)
        trust["confidence"] = conf
        gate              = _map_gate(gate_decision(conf))

        # Try Groq LLM first
        if req.groq_api_key:
            try:
                import os
                from groq import Groq
                doubt_str = "\n  ".join(
                    f"- {f['type']}: {f['msg']} ({f['impact']})" for f in doubt_factors
                ) or "  None"

                prompt = f"""You are an AI Cloud Risk Auditor.

Analyze the following autonomous decision made by a cloud orchestration system.

INPUT:
- Ticket: "{ticket}"
- Parsed Intent:
  Service: {parsed.service}
  Action: {parsed.action_verb}
  Environment: {parsed.environment}
  Scope: {parsed.scope}
  Risk Signals: {parsed.risk_signals}

- Trust Scores:
  Intent Score: {trust['intent_score']}
  Reversibility: {trust['reversibility']}
  Blast Radius: {trust['blast_radius']}
  Policy Score: {trust['policy_score']}
  Final Confidence: {conf}
  Decision: {gate}

- Memory:
  Prior Incidents Count: {penalty['count']}
  Penalty Applied: {penalty['penalty']}

- Self-Doubt Signals:
  {doubt_str}

TASK:
Generate a structured audit report with:

1. EXECUTIVE SUMMARY (2-3 lines)
2. RISK ASSESSMENT (why this is safe/risky)
3. KEY FAILURE MODES (top 3 realistic risks)
4. SYSTEM BEHAVIOR ANALYSIS
   - Was the decision correct?
   - Any overconfidence or underestimation?
5. MEMORY IMPACT
   - Did past incidents influence decision?
6. SELF-DOUBT ANALYSIS
   - Were contradictions or anomalies detected?
7. FINAL VERDICT
   - APPROPRIATE / CONSERVATIVE / RISKY

Keep it concise but technical. Return clean structured text."""

                client   = Groq(api_key=req.groq_api_key)
                response = client.chat.completions.create(
                    model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800,
                )
                report_text = response.choices[0].message.content or ""
                if report_text.strip():
                    return {
                        "report":  report_text,
                        "source":  "groq_llm",
                        "gate":    gate,
                        "confidence": conf,
                    }
            except Exception:
                pass  # fall through to rule-based

        # Rule-based fallback
        report_text = _rule_based_audit(
            ticket, parsed, trust, gate, penalty, doubt_factors, ai_notes
        )
        return {
            "report":     report_text,
            "source":     "rule_based",
            "gate":       gate,
            "confidence": conf,
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# ── APPROVE-gate structured audit report ─────────────────────────────────

from audit_report import generate_audit_report


class ApproveAuditRequest(BaseModel):
    ticket: str


@app.post("/audit/approve")
def approve_audit(req: ApproveAuditRequest):
    """
    Structured 8-section audit report for APPROVE-gate tickets.
    Returns JSON with all sections for PDF rendering on the frontend.
    Returns 400-style error for AUTO/BLOCK gates.
    """
    try:
        ticket = req.ticket.strip()
        if not ticket:
            return {"error": "Empty ticket"}

        parsed   = parse_ticket(ticket)
        v3_input = _to_v3(parsed)
        trust    = run_trust_engine(v3_input)
        trust["affected_count"] = len(v3_input["affected_nodes"])

        penalty = memory.get_penalty(service=parsed.service,
                                     verb=parsed.action_verb,
                                     env=parsed.environment)
        conf, ai_notes = ai_adjustment(ticket, round(trust["confidence"] * penalty["penalty"], 4))
        trust["confidence"] = conf
        conf, _ = apply_self_doubt(parsed, trust, conf)
        conf = round(max(0.0, min(1.0, conf)), 4)
        trust["confidence"] = conf
        gate = _map_gate(gate_decision(conf))

        if gate != "APPROVE":
            return {
                "error": f"Ticket resolved as {gate} — audit report only available for APPROVE gate",
                "gate": gate,
                "confidence": conf,
            }

        graph  = build_dynamic_graph(parsed)
        debate = run_ai_debate(ticket, trust, graph=graph,
                               contradictions=parsed.contradictions,
                               env=parsed.environment, verb=parsed.action_verb,
                               scale=parsed.scope.get("scale_factor", 1.0))

        report = generate_audit_report(
            ticket=ticket,
            parsed=parsed,
            trust=trust,
            gate=gate,
            graph=graph,
            debate=debate,
            memory_penalty=penalty,
            ai_notes=ai_notes,
        )
        return report

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
