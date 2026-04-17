"""
Trust Engine v5 — ARIA-Lite++
All trust dimensions computed dynamically from ParsedIntent.
No hardcoded per-scenario scores. No blast radius caps.
Formula: confidence = intent_score × reversibility × (1 − blast_radius) × policy_score
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent

from dependency_graph import create_demo_architecture, compute_blast_radius as _graph_blast

# Singleton graph — built once at import time
_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        try:
            _GRAPH = create_demo_architecture()
        except Exception:
            _GRAPH = None
    return _GRAPH


# ── Service → graph entry node mapping ───────────────────────────────────────

_SERVICE_ENTRY_NODES: Dict[str, List[str]] = {
    "s3":          ["s3-main"],
    "iam":         ["iam-role-app"],
    "ec2":         ["ec2-app-1", "ec2-app-2"],
    "rds":         ["rds-primary"],
    "lambda":      ["lambda-workers"],
    "cloudwatch":  ["cloudwatch"],
    "secrets":     ["secrets-manager"],
    "alb":         ["alb-primary"],
}

# Inherent blast additive per service — ONLY for destructive/mutating verbs.
# Safe/scaling verbs use a reduced additive to avoid over-penalising low-risk ops.
_SERVICE_BLAST_ADDITIVE_DESTRUCTIVE: Dict[str, float] = {
    "iam":         0.15,
    "rds":         0.10,
    "alb":         0.12,
    "ec2":         0.05,
    "lambda":      0.02,
    "s3":          0.00,
    "cloudwatch":  0.02,
    "secrets":     0.08,
    "cloudtrail":  0.03,
    "kms":         0.10,
    "vpc":         0.12,
}
_SERVICE_BLAST_ADDITIVE_SAFE: Dict[str, float] = {
    "iam":         0.02,   # attach/rotate — limited blast
    "rds":         0.02,   # backup/read — minimal blast
    "alb":         0.03,
    "ec2":         0.01,
    "lambda":      0.01,
    "s3":          0.00,
    "cloudwatch":  0.00,
    "secrets":     0.01,
    "cloudtrail":  0.00,
    "kms":         0.01,
    "vpc":         0.02,
}


# ── TrustScores dataclass ─────────────────────────────────────────────────────

@dataclass
class TrustScores:
    intent: float
    reversibility: float
    blast: float
    policy: float
    confidence: float
    affected_count: int
    affected_nodes: List[str]

    def to_dict(self) -> Dict[str, float]:
        return {
            "intent_score": self.intent,
            "reversibility": self.reversibility,
            "blast_radius": self.blast,
            "policy_score": self.policy,
            "confidence": self.confidence,
        }


# ── Component computers ───────────────────────────────────────────────────────

def compute_intent_score(parsed: "ParsedIntent") -> float:
    base = {
        "safe":        0.95,
        "mutating":    0.72,
        "scaling":     0.95,
        "destructive": 0.20,
        "unknown":     0.40,
    }.get(parsed.action_verb, 0.40)

    # Environment modifiers
    if parsed.environment == "production" and parsed.action_verb == "destructive":
        base = max(0.05, base - 0.15)
    elif parsed.environment == "dev":
        base = min(0.95, base + 0.08)
    elif parsed.environment == "staging":
        base = min(0.95, base + 0.03)

    # Urgency modifiers
    if parsed.urgency == "high":
        base = max(0.05, base - 0.12)
    elif parsed.urgency == "low":
        base = min(0.95, base + 0.05)

    # Contradiction penalty
    base = max(0.05, base - len(parsed.contradictions) * 0.08)

    # Risk signal penalties
    if "prod_destructive" in parsed.risk_signals:
        base = max(0.05, base - 0.10)
    if "extreme_scale" in parsed.risk_signals:
        base = max(0.05, base - 0.08)  # reduced: blast radius already captures the risk
    if "audit_trail_deletion" in parsed.risk_signals:
        base = max(0.05, base - 0.20)

    return round(min(0.98, max(0.02, base)), 3)


def compute_reversibility(parsed: "ParsedIntent") -> float:
    base = {
        "safe":        0.92,
        "scaling":     0.85,
        "mutating":    0.70,
        "destructive": 0.08,
        "unknown":     0.30,
    }.get(parsed.action_verb, 0.30)

    # Service-specific adjustments — verb-aware
    # Destructive/mutating verbs on stateful services are harder to reverse
    # Safe verbs (backup, read, attach readonly) are highly reversible
    if parsed.action_verb in ("destructive", "mutating"):
        service_mod = {
            "s3":         0.00,
            "lambda":    +0.05,
            "ec2":       +0.02,
            "iam":       +0.05,   # mutating IAM (rotate/modify) is reversible
            "rds":       -0.20,
            "secrets":   -0.15,
            "kms":       -0.25,
            "cloudtrail":-0.20,
        }.get(parsed.service, 0.0)
    else:  # safe / scaling / unknown
        service_mod = {
            "s3":         0.00,
            "lambda":    +0.05,
            "ec2":       +0.03,
            "iam":       +0.05,   # attach/rotate is easily reversible
            "rds":       -0.02,
            "secrets":   -0.05,
            "kms":       -0.10,
            "cloudtrail": 0.00,
        }.get(parsed.service, 0.0)
    base = min(0.98, max(0.02, base + service_mod))

    # Scale factor penalty — graduated, gentler rate
    scale_factor = parsed.scope.get("scale_factor", 1)
    if scale_factor > 5:
        penalty = min(0.30, (scale_factor - 5) * 0.01)
        base = max(0.40, base - penalty)

    # Explicit no-rollback signal
    if parsed.scope.get("no_rollback"):
        base = max(0.02, base - 0.30)

    # Production destructive: near-irreversible
    if parsed.action_verb == "destructive" and parsed.environment == "production":
        base = max(0.02, base - 0.10)

    return round(min(0.98, max(0.02, base)), 3)


def compute_blast_radius(parsed: "ParsedIntent") -> tuple[float, int, List[str]]:
    """
    Returns (blast_radius, affected_count, affected_nodes).
    Uses live graph traversal — no caps applied.
    """
    graph = _get_graph()
    graph_raw = 0.0
    affected_count = 0
    affected_nodes: List[str] = []

    if graph is not None:
        entry_nodes = _SERVICE_ENTRY_NODES.get(parsed.service, [])
        if entry_nodes:
            try:
                result = _graph_blast(graph, entry_nodes)
                graph_raw = result.get("weighted_impact", 0.0)
                affected_nodes = result.get("affected_nodes", [])
                affected_count = len(affected_nodes)
            except Exception:
                graph_raw = 0.10  # conservative fallback

    # Service inherent blast additive — verb-aware
    is_destructive_verb = parsed.action_verb in ("destructive",)
    additive_table = _SERVICE_BLAST_ADDITIVE_DESTRUCTIVE if is_destructive_verb else _SERVICE_BLAST_ADDITIVE_SAFE

    # Scale graph_raw by verb: safe/scaling ops don’t propagate failures the same way
    verb_graph_multiplier = {
        "destructive": 1.00,
        "mutating":    0.35,
        "scaling":     0.10,
        "safe":        0.03,
        "unknown":     0.50,
    }.get(parsed.action_verb, 0.50)
    scaled_graph_raw = round(graph_raw * verb_graph_multiplier, 4)

    base = scaled_graph_raw + additive_table.get(parsed.service, 0.0)

    # Scale factor multiplier — graduated, not binary
    scale_factor = parsed.scope.get("scale_factor", 1)
    if scale_factor > 20:
        base = min(0.95, base + 0.12)
    elif scale_factor > 10:
        base = min(0.95, base + 0.07)
    elif scale_factor > 5:
        base = min(0.95, base + 0.04)

    # Production amplifies blast — only for destructive/mutating verbs
    if parsed.environment == "production" and parsed.action_verb in ("destructive", "mutating"):
        base = min(0.95, base + 0.10)

    # Destructive on production: maximum blast signal
    if parsed.action_verb == "destructive" and parsed.environment == "production":
        base = min(0.95, base + 0.20)

    # Risk signal amplifiers
    if "extreme_scale" in parsed.risk_signals and parsed.action_verb != "scaling":
        base = min(0.95, base + 0.05)  # only amplify if not already captured by scale_factor branch
    if "irreversible_db" in parsed.risk_signals:
        base = min(0.95, base + 0.15)
    if "cross_account" in parsed.risk_signals:
        base = min(0.95, base + 0.12)

    return round(min(0.95, max(0.0, base)), 3), affected_count, affected_nodes


def compute_policy_score(parsed: "ParsedIntent") -> float:
    base = 1.0

    # Destructive on production: immediate policy violation
    if parsed.environment == "production" and parsed.action_verb == "destructive":
        base = 0.05

    # Admin privilege escalation
    if parsed.scope.get("privilege_level") == "admin":
        base = min(base, 0.45)

    # Admin in production: double penalty
    if parsed.scope.get("privilege_level") == "admin" and parsed.environment == "production":
        base = min(base, 0.15)

    # Public S3 access: explicit security policy violation
    if parsed.scope.get("public_access"):
        base = max(0.02, base - 0.50)

    # Unknown environment with destructive/mutating action — only penalise destructive
    if parsed.environment == "unknown" and parsed.action_verb == "destructive":
        base = min(base, 0.70)

    # High urgency on production: bypasses review gates
    if parsed.urgency == "high" and parsed.environment == "production":
        base = max(0.05, base - 0.20)

    # Cross-account: always requires review
    if "cross_account" in parsed.risk_signals:
        base = min(base, 0.30)

    # Audit trail deletion: critical policy violation
    if "audit_trail_deletion" in parsed.risk_signals:
        base = min(base, 0.05)

    # Key deletion: critical
    if "key_deletion" in parsed.risk_signals:
        base = min(base, 0.10)

    # IAM policy name detected — use IAM simulator to score the RISK of the policy
    # (not whether the caller can perform the action — that’s an authz question)
    iam_policy = parsed.scope.get("iam_policy_name")
    if iam_policy:
        from iam_simulator import evaluate_trust_from_iam, POLICY_RULES
        # Score based on the risk level of the policy being attached, not the attachment action
        policy_info = POLICY_RULES.get(iam_policy)
        if policy_info:
            from iam_simulator import _RISK_TO_SCORE
            risk_score = _RISK_TO_SCORE.get(policy_info["risk"], 0.50)
            # Dangerous actions within the policy reduce score further
            if policy_info["risk"] in ("CRITICAL", "HIGH"):
                risk_score = max(0.05, risk_score - 0.10)
            base = min(base, risk_score)
        else:
            base = min(base, 0.40)  # unknown policy = conservative

    return round(min(1.0, max(0.02, base)), 3)


# ── Main trust computation ────────────────────────────────────────────────────

def compute_trust(parsed: "ParsedIntent", memory_penalty: Dict) -> TrustScores:
    """
    Compute all four trust dimensions from ParsedIntent.
    Apply memory penalties if active.
    """
    intent      = compute_intent_score(parsed)
    reversibility = compute_reversibility(parsed)
    blast, affected_count, affected_nodes = compute_blast_radius(parsed)
    policy      = compute_policy_score(parsed)

    # Update parsed with affected count for debate/simulation use
    parsed.affected_count = affected_count

    # Apply cumulative memory penalties
    if memory_penalty.get("active"):
        reversibility = max(0.02, reversibility - memory_penalty["reversibility_penalty"])
        policy        = max(0.02, policy        - memory_penalty["policy_penalty"])
        blast         = min(0.95, blast         + memory_penalty["blast_penalty"])

    # Confidence formula
    raw_conf = intent * reversibility * (1.0 - blast) * policy
    # Smoothing floor — no action is absolutely impossible
    raw_conf = max(0.01, raw_conf)

    # Memory multiplier (applied after formula)
    if memory_penalty.get("active"):
        raw_conf = max(0.01, round(raw_conf * memory_penalty["multiplier"], 4))

    confidence = round(raw_conf, 4)

    return TrustScores(
        intent=round(intent, 3),
        reversibility=round(reversibility, 3),
        blast=round(blast, 3),
        policy=round(policy, 3),
        confidence=confidence,
        affected_count=affected_count,
        affected_nodes=affected_nodes,
    )


# ── Gate decision ─────────────────────────────────────────────────────────────

def decision_from_confidence(confidence: float, service: str = "") -> str:
    if service == "unknown" and confidence < 0.50:
        return "BLOCK"
    if confidence >= 0.80:
        return "AUTO"
    if confidence >= 0.50:
        return "APPROVE"
    return "BLOCK"


# ── Uncertainty modeling ──────────────────────────────────────────────────────

def compute_uncertainty(parsed: "ParsedIntent", trust: TrustScores) -> Dict:
    signals = []
    score = 0.0

    if parsed.service == "unknown":
        score += 0.30
        signals.append("SERVICE_UNRECOGNIZED: cannot model blast radius accurately")

    if parsed.environment == "unknown":
        score += 0.15
        signals.append("ENVIRONMENT_UNKNOWN: production/dev context affects scoring")

    if parsed.action_verb == "unknown":
        score += 0.20
        signals.append("ACTION_UNCLEAR: cannot determine reversibility without clear verb")

    if parsed.contradictions:
        score += 0.10 * len(parsed.contradictions)
        signals.append(
            f"CONTRADICTIONS_PRESENT: {len(parsed.contradictions)} conflicting signal(s) detected"
        )

    if 0.45 < trust.confidence < 0.55:
        score += 0.15
        signals.append(
            "CONFIDENCE_BOUNDARY: score within 0.05 of gate threshold — small input change would flip gate"
        )

    score = round(min(1.0, score), 2)
    level = "LOW" if score < 0.20 else "MEDIUM" if score < 0.45 else "HIGH"

    return {
        "score": score,
        "level": level,
        "signals": signals,
        "recommendation": (
            "CLARIFY INPUT" if level == "HIGH"
            else "PROCEED WITH NOTED FLAGS" if level == "MEDIUM"
            else "PROCEED"
        ),
    }


# ── Debate generation ─────────────────────────────────────────────────────────

def generate_debate(
    parsed: "ParsedIntent",
    trust: TrustScores,
    gate: str,
    contradictions: List[str],
    memory_note: str = None,
) -> Dict:
    # Identify weakest component
    components = {
        "intent":       trust.intent,
        "reversibility": trust.reversibility,
        "policy":       trust.policy,
        "blast_margin": round(1.0 - trust.blast, 3),
    }
    weakest_key = min(components, key=components.get)
    weakest_val = components[weakest_key]

    exec_text = (
        f"Executor proposes {parsed.service.upper()} {parsed.action_verb} — "
        f"intent clarity {trust.intent:.2f}, reversibility {trust.reversibility:.2f}. "
        f"Confidence {trust.confidence:.3f} "
        f"{'clears' if gate == 'AUTO' else 'approaches' if gate == 'APPROVE' else 'fails'} "
        f"gate threshold."
    )

    crit_parts = []
    if memory_note:
        crit_parts.append(f"⚠ PRIOR INCIDENT: {memory_note}.")
    if contradictions:
        crit_parts.append(f"CONTRADICTION DETECTED: {contradictions[0]}.")
    crit_parts.append(
        f"Critic flags {weakest_key} as binding constraint at {weakest_val:.2f}. "
        f"{'Blast radius ' + str(trust.blast) + ' affects ' + str(trust.affected_count) + ' downstream resources.' if trust.blast > 0.10 else 'No significant cascade risk detected.'}"
    )
    if gate == "AUTO" and contradictions:
        crit_parts.append(
            "Second-pass validation: contradictions present but below BLOCK threshold. Proceeding with flag."
        )
    elif gate == "BLOCK":
        crit_parts.append(
            "Critic veto: single-component collapse is sufficient for hard block."
        )

    verdict_map = {
        "AUTO":    f"PROCEED — {weakest_key} is limiting but confidence clears 0.80 gate",
        "APPROVE": f"ROUTE TO HUMAN — {weakest_key} at threshold, contradictions {'present' if contradictions else 'absent'}",
        "BLOCK":   f"HARD BLOCK — {weakest_key} collapse vetoes execution regardless of other components",
    }

    return {
        "executor": exec_text,
        "critic": " ".join(crit_parts),
        "verdict": verdict_map[gate],
        "contradictions": contradictions,
        "second_pass": gate == "AUTO" and len(contradictions) > 0,
    }


# ── Simulation generation ─────────────────────────────────────────────────────

def generate_simulation(parsed: "ParsedIntent", trust: TrustScores) -> List[Dict]:
    blast = trust.blast
    conf  = trust.confidence
    scale = parsed.scope.get("scale_factor", 1)
    is_prod = parsed.environment == "production"

    success_base = round(conf * 0.95 * 100)

    if scale > 10:
        success_base = max(20, success_base - 25)
    elif scale > 5:
        success_base = max(40, success_base - 12)

    if is_prod:
        success_base = max(10, success_base - 15)

    cascade_base = round(blast * 35)

    rollback_prob = 0
    if blast > 0.15 or scale > 5:
        rollback_prob = round((blast * 20) + (max(0, scale - 5) * 1.5))
        rollback_prob = min(rollback_prob, 30)

    remaining = 100 - success_base - cascade_base - rollback_prob
    degraded = max(0, remaining)

    no_impact = max(0, 100 - success_base - degraded - cascade_base - rollback_prob)

    scenarios = [
        {
            "scenario": "Clean success",
            "probability": success_base,
            "detail": f"Operation completes. {parsed.service.upper()} state matches intent.",
            "type": "success",
        },
        {
            "scenario": "Degraded execution",
            "probability": degraded,
            "detail": (
                "Scale lag on new instances." if parsed.service == "ec2"
                else "Retry required on one step."
            ),
            "type": "degraded",
        },
        {
            "scenario": "Cascade failure",
            "probability": cascade_base,
            "detail": f"Downstream impact on {trust.affected_count} dependent resource(s).",
            "type": "cascading_failure",
        },
        {
            "scenario": "Rollback triggered",
            "probability": rollback_prob,
            "detail": (
                "RDS pool risk detected." if parsed.service == "ec2"
                else "Compensating transaction required."
            ),
            "type": "rollback",
        },
        {
            "scenario": "No impact",
            "probability": no_impact,
            "detail": "Operation idempotent or resource already in target state.",
            "type": "no_impact",
        },
    ]

    # Normalize to exactly 100
    total = sum(s["probability"] for s in scenarios)
    if total != 100 and scenarios:
        scenarios[0]["probability"] += 100 - total

    return [s for s in scenarios if s["probability"] > 0]


# ── Pre-mortem (context-aware) ────────────────────────────────────────────────

def generate_premortem(parsed: "ParsedIntent") -> List[Dict]:
    """Generate context-aware pre-mortem failure modes."""
    from scenarios import PREMORTEM_ANALYSIS

    # Map service+verb to a scenario key for legacy premortem lookup
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
    key = scenario_map.get((parsed.service, parsed.action_verb))
    base = PREMORTEM_ANALYSIS.get(key, []) if key else []

    # Inject context-specific failure modes
    extra = []
    if "prod_destructive" in parsed.risk_signals:
        extra.append({
            "failure": "Production service outage from destructive action",
            "severity": 5,
            "mitigation": "Mandatory: stage in dev/staging first. Require 2-person approval.",
        })
    if "extreme_scale" in parsed.risk_signals:
        extra.append({
            "failure": f"Resource exhaustion from {parsed.scope.get('scale_factor', '?')}x scale factor",
            "severity": 4,
            "mitigation": "Implement gradual scale-out with health check gates between steps.",
        })
    if "public_s3" in parsed.risk_signals:
        extra.append({
            "failure": "Public S3 bucket exposes sensitive data",
            "severity": 5,
            "mitigation": "Apply bucket policy denying public access. Enable S3 Block Public Access.",
        })
    if "admin_privilege" in parsed.risk_signals:
        extra.append({
            "failure": "Admin privilege grants unrestricted AWS access",
            "severity": 5,
            "mitigation": "Replace with least-privilege policy scoped to required resources only.",
        })

    return (extra + base)[:3] or [{
        "failure": "Unknown failure mode",
        "severity": 2,
        "mitigation": "Manual review required — insufficient context to model failure modes.",
    }]


# ── Execution log ─────────────────────────────────────────────────────────────

def generate_execution_log(parsed: "ParsedIntent", trust: TrustScores, gate: str) -> List[Dict]:
    from datetime import datetime
    now = datetime.now()
    t = now.strftime('%H:%M:%S')

    entries: List[Dict] = []

    # ── Phase 1: Parse ────────────────────────────────────────────────────────
    entries.append({"msg": f"[{t}.001] ● PHASE 1 — TICKET PARSE", "status": "ok"})
    entries.append({"msg": f"[{t}.012] ● verb={parsed.action_verb}  service={parsed.service}  env={parsed.environment}  urgency={parsed.urgency}", "status": "ok"})
    entries.append({"msg": f"[{t}.025] ● scope={parsed.scope or '{}'}", "status": "ok"})

    if parsed.risk_signals:
        entries.append({"msg": f"[{t}.040] ▲ risk_signals={parsed.risk_signals}", "status": "warn"})
    else:
        entries.append({"msg": f"[{t}.040] ● risk_signals=none", "status": "ok"})

    if parsed.contradictions:
        for c in parsed.contradictions:
            entries.append({"msg": f"[{t}.055] ▲ CONTRADICTION: {c}", "status": "warn"})
    else:
        entries.append({"msg": f"[{t}.055] ● contradictions=none", "status": "ok"})

    # ── Phase 2: Trust computation ────────────────────────────────────────────
    entries.append({"msg": f"[{t}.080] ● PHASE 2 — TRUST ENGINE", "status": "ok"})
    entries.append({"msg": f"[{t}.095] ● intent_score    = {trust.intent:.3f}  (verb={parsed.action_verb}, env={parsed.environment})", "status": "ok"})
    entries.append({"msg": f"[{t}.110] ● reversibility   = {trust.reversibility:.3f}  (rollback complexity derived from verb+service)", "status": "ok"})
    entries.append({"msg": f"[{t}.130] ● graph traversal → {trust.affected_count} downstream node(s) affected", "status": "ok"})
    if trust.affected_nodes:
        entries.append({"msg": f"[{t}.145] ● affected_nodes  = {trust.affected_nodes}", "status": "ok"})
    entries.append({"msg": f"[{t}.160] ● blast_radius    = {trust.blast:.3f}", "status": "warn" if trust.blast > 0.30 else "ok"})
    entries.append({"msg": f"[{t}.175] ● policy_score    = {trust.policy:.3f}", "status": "warn" if trust.policy < 0.50 else "ok"})
    entries.append({"msg": f"[{t}.190] ● confidence      = {trust.intent:.3f} × {trust.reversibility:.3f} × (1-{trust.blast:.3f}) × {trust.policy:.3f} = {trust.confidence:.4f}", "status": "ok"})

    # ── Phase 3: Gate decision ────────────────────────────────────────────────
    entries.append({"msg": f"[{t}.210] ● PHASE 3 — GATE DECISION", "status": "ok"})
    if gate == "BLOCK":
        entries.append({"msg": f"[{t}.225] ■ HARD BLOCK — confidence {trust.confidence:.4f} < 0.50 threshold", "status": "fail"})
        # Identify binding constraint
        components = {"intent": trust.intent, "reversibility": trust.reversibility,
                      "policy": trust.policy, "blast_margin": round(1.0 - trust.blast, 3)}
        weakest = min(components, key=components.get)
        entries.append({"msg": f"[{t}.235] ■ binding_constraint={weakest} ({components[weakest]:.3f}) — single-component collapse", "status": "fail"})
        entries.append({"msg": f"[{t}.245] ■ operation refused — structured explanation generated", "status": "fail"})
        entries.append({"msg": f"[{t}.255] ▲ incident routed to on-call SRE for review", "status": "warn"})

    elif gate == "APPROVE":
        entries.append({"msg": f"[{t}.225] ⊙ APPROVE — confidence {trust.confidence:.4f} in [0.50, 0.80) zone", "status": "warn"})
        entries.append({"msg": f"[{t}.235] ⊙ routing to 1-click human approver", "status": "warn"})
        entries.append({"msg": f"[{t}.245] ⊙ awaiting approval token — operation suspended", "status": "warn"})

    else:  # AUTO
        entries.append({"msg": f"[{t}.225] ● AUTO-EXECUTE — confidence {trust.confidence:.4f} ≥ 0.80 threshold", "status": "ok"})
        entries.append({"msg": f"[{t}.235] ● pre-flight checks passed — initiating execution", "status": "ok"})

        # ── Phase 4: Execution (AUTO only) ───────────────────────────────────
        entries.append({"msg": f"[{t}.260] ● PHASE 4 — EXECUTION", "status": "ok"})
        svc = parsed.service.upper()
        verb = parsed.action_verb
        scope = parsed.scope

        if parsed.service == "ec2" and verb == "scaling":
            current = scope.get("current", "?")
            target  = scope.get("target", "?")
            sf      = scope.get("scale_factor", "?")
            entries.append({"msg": f"[{t}.275] ● EC2 scale request: {current} → {target} instances (×{sf})", "status": "ok"})
            entries.append({"msg": f"[{t}.290] ● verifying ASG health — all instances passing ALB health checks", "status": "ok"})
            entries.append({"msg": f"[{t}.310] ● RDS connection pool baseline: checking current utilisation", "status": "ok"})
            entries.append({"msg": f"[{t}.330] ● RunInstances ×{max(1, int(target) - int(current)) if str(target).isdigit() and str(current).isdigit() else '?'} — request sent to AWS", "status": "ok"})
            entries.append({"msg": f"[{t}.380] ● new instances registering with ALB target group", "status": "ok"})
            entries.append({"msg": f"[{t}.420] ▲ monitoring RDS pool — watching for connection exhaustion", "status": "warn"})

            # Rollback simulation for EC2 scaling
            entries.append({"msg": f"[{t}.460] ● PHASE 5 — ROLLBACK MONITOR (armed)", "status": "ok"})
            entries.append({"msg": f"[{t}.470] ● rollback trigger: RDS pool > 85% OR ALB health < 80%", "status": "ok"})
            entries.append({"msg": f"[{t}.490] ▲ RDS pool rising — 312/500 connections (62%)", "status": "warn"})
            entries.append({"msg": f"[{t}.520] ▲ RDS pool rising — 421/500 connections (84%) — WARNING threshold", "status": "warn"})
            entries.append({"msg": f"[{t}.550] ■ RDS pool CRITICAL — 487/500 connections (97%) — CASCADE DETECTED", "status": "fail"})
            entries.append({"msg": f"[{t}.560] ↩ ROLLBACK INITIATED — auto-reversal triggered by safety guardrail", "status": "rollback"})
            entries.append({"msg": f"[{t}.575] ↩ step 1/5 — suspending new instance registration with ALB", "status": "rollback"})
            entries.append({"msg": f"[{t}.590] ↩ step 2/5 — draining in-flight requests from new instances (30s grace)", "status": "rollback"})
            entries.append({"msg": f"[{t}.620] ↩ step 3/5 — TerminateInstances sent — waiting for EC2 state=terminated", "status": "rollback"})
            entries.append({"msg": f"[{t}.660] ↩ step 4/5 — RDS pool normalising — 287/500 (57%)", "status": "rollback"})
            entries.append({"msg": f"[{t}.700] ↩ step 5/5 — RDS pool stable — 89/500 (18%) — safe zone restored", "status": "rollback"})
            entries.append({"msg": f"[{t}.720] ● system restored to known-good state — {current} instances running", "status": "ok"})
            entries.append({"msg": f"[{t}.735] ◉ memory updated — ec2_scaling incident recorded for future penalty", "status": "memory"})
            entries.append({"msg": f"[{t}.750] ▲ recommendation: enable RDS Proxy before next scale attempt", "status": "warn"})

        elif parsed.service == "s3":
            entries.append({"msg": f"[{t}.275] ● S3 {verb} — validating bucket name uniqueness", "status": "ok"})
            entries.append({"msg": f"[{t}.295] ● IAM permissions verified — s3:CreateBucket confirmed", "status": "ok"})
            entries.append({"msg": f"[{t}.315] ● encryption policy applied — AES-256 enforced", "status": "ok"})
            entries.append({"msg": f"[{t}.335] ● bucket created — applying access control policy", "status": "ok"})
            entries.append({"msg": f"[{t}.355] ● CloudWatch logging enabled on bucket", "status": "ok"})
            entries.append({"msg": f"[{t}.370] ● operation complete — S3 state matches intent", "status": "ok"})

        elif parsed.service == "lambda":
            entries.append({"msg": f"[{t}.275] ● Lambda {verb} — validating function package", "status": "ok"})
            entries.append({"msg": f"[{t}.295] ● previous version archived — rollback alias preserved", "status": "ok"})
            entries.append({"msg": f"[{t}.315] ● UpdateFunctionCode initiated — uploading package", "status": "ok"})
            entries.append({"msg": f"[{t}.340] ● deployment complete — new version live", "status": "ok"})
            entries.append({"msg": f"[{t}.360] ● health check passed — p99 latency nominal", "status": "ok"})
            entries.append({"msg": f"[{t}.375] ● rollback available via alias swap if needed", "status": "ok"})

        elif parsed.service == "rds":
            entries.append({"msg": f"[{t}.275] ● RDS {verb} — fetching current parameter group", "status": "ok"})
            entries.append({"msg": f"[{t}.295] ▲ checking for reboot-required parameter flags", "status": "warn"})
            entries.append({"msg": f"[{t}.315] ● snapshot created — pre-change backup confirmed", "status": "ok"})
            entries.append({"msg": f"[{t}.335] ● parameter change applied — monitoring replication lag", "status": "ok"})
            entries.append({"msg": f"[{t}.360] ● read replica in sync — lag < 1s", "status": "ok"})

        else:
            entries.append({"msg": f"[{t}.275] ● {svc} {verb} — executing operation", "status": "ok"})
            entries.append({"msg": f"[{t}.310] ● operation complete — state matches intent", "status": "ok"})

    # ── Contradiction flags (always shown if present) ─────────────────────────
    if parsed.contradictions:
        entries.append({"msg": f"[{t}.800] ▲ CONTRADICTION FLAGS: {'; '.join(parsed.contradictions[:2])}", "status": "warn"})

    return entries


# ── Legacy compatibility shims ────────────────────────────────────────────────
# These allow /trust/explain and /analyze_custom to still call old-style functions.

def calculate_trust_scores(intent: str, parameters: dict = None, has_memory: bool = False) -> Dict:
    """Legacy shim: maps old scenario-name-based call to new ParsedIntent-based engine."""
    from parser import ParsedIntent

    # Build a synthetic ParsedIntent from the scenario name
    _SCENARIO_TO_PARSED = {
        "s3_create":     ("safe",        "s3",     "unknown", "normal"),
        "iam_delete":    ("destructive",  "iam",    "unknown", "normal"),
        "iam_attach":    ("safe",         "iam",    "unknown", "normal"),
        "ec2_scale":     ("scaling",      "ec2",    "unknown", "normal"),
        "rds_modify":    ("mutating",     "rds",    "unknown", "normal"),
        "lambda_deploy": ("safe",         "lambda", "unknown", "normal"),
    }
    verb, service, env, urgency = _SCENARIO_TO_PARSED.get(
        intent, ("unknown", "unknown", "unknown", "normal")
    )

    scope = parameters or {}
    parsed = ParsedIntent(
        action_verb=verb, service=service, environment=env,
        urgency=urgency, scope=scope, risk_signals=[],
        contradictions=[], raw_ticket=intent,
    )

    penalty = {"active": False}
    if has_memory:
        penalty = {
            "active": True,
            "reversibility_penalty": 0.15,
            "policy_penalty": 0.10,
            "blast_penalty": 0.05,
            "multiplier": 0.85,
        }

    trust = compute_trust(parsed, penalty)
    return {
        "intent_score": trust.intent,
        "reversibility": trust.reversibility,
        "blast_radius": trust.blast,
        "policy_score": trust.policy,
        "_blast_detail": {"affected_nodes": trust.affected_nodes, "weighted_impact": trust.blast},
    }


def calculate_confidence(scores: Dict) -> float:
    i = scores.get("intent_score", 0.0)
    r = scores.get("reversibility", 0.0)
    b = scores.get("blast_radius", 0.5)
    p = scores.get("policy_score", 0.0)
    return max(0.01, round(i * r * (1.0 - b) * p, 4))


def get_gate(confidence: float) -> str:
    return decision_from_confidence(confidence)
