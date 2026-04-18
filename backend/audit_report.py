"""
audit_report.py — ARIA-Lite++
Structured 8-section audit report for APPROVE-gate operations.
Designed for human reviewers: readable in under 2 minutes.
"""

from datetime import datetime
from typing import Dict, List, Any


# ── Section builders ──────────────────────────────────────────────────────────

def build_header(parsed, gate: str) -> Dict:
    risk_level = (
        "CRITICAL" if parsed.environment == "production" and parsed.action_verb == "destructive"
        else "HIGH"   if parsed.environment == "production" or parsed.action_verb == "destructive"
        else "MEDIUM" if gate == "APPROVE"
        else "LOW"
    )
    return {
        "action":      parsed.action_verb.upper().replace("_", " "),
        "service":     parsed.service.upper(),
        "environment": parsed.environment.upper(),
        "urgency":     parsed.urgency.upper(),
        "risk_level":  risk_level,
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def build_decision(trust: Dict, gate: str) -> Dict:
    conf = trust["confidence"]
    verdict_map = {
        "AUTO":    "AUTO APPROVE",
        "APPROVE": "HUMAN APPROVAL REQUIRED",
        "BLOCK":   "BLOCKED",
    }

    # Dynamic reason from binding constraint
    components = {
        "intent":        trust["intent_score"],
        "reversibility": trust["reversibility"],
        "policy":        trust["policy_score"],
        "blast_margin":  round(1.0 - trust["blast_radius"], 3),
    }
    weakest     = min(components, key=components.get)
    weakest_val = components[weakest]

    reason_map = {
        "reversibility": f"Reversibility {weakest_val:.2f} — recovery path is limited",
        "policy":        f"Policy score {weakest_val:.2f} — compliance concern detected",
        "blast_margin":  f"Blast radius {trust['blast_radius']:.2f} — downstream cascade risk",
        "intent":        f"Intent score {weakest_val:.2f} — operation clarity is low",
    }

    return {
        "verdict":            verdict_map.get(gate, gate),
        "confidence":         round(conf, 3),
        "binding_constraint": weakest,
        "reason":             reason_map.get(weakest, "Borderline confidence requires human review"),
    }


def build_risk_factors(trust: Dict, parsed, graph: Dict) -> Dict:
    node_count  = len(graph.get("nodes", []))
    affected    = [n["id"].upper() for n in graph.get("nodes", []) if n["id"] != parsed.service]
    blast       = trust["blast_radius"]
    rev         = trust["reversibility"]
    policy      = trust["policy_score"]

    rev_label = (
        "High — rollback viable within minutes" if rev >= 0.70
        else "Partial — manual recovery required" if rev >= 0.35
        else "Low — recovery is difficult"
    )
    policy_label = (
        "No violations detected" if policy >= 0.70
        else "Elevated compliance risk" if policy >= 0.40
        else "Critical policy concern"
    )
    blast_label = (
        f"Contained — {node_count} service(s) in scope" if blast < 0.20
        else f"Moderate — {node_count} service(s) at risk" if blast < 0.40
        else f"High — {node_count} service(s) at risk, cascade likely"
    )

    return {
        "blast_radius":    blast_label,
        "affected":        affected,
        "reversibility":   rev_label,
        "policy":          policy_label,
        "environment":     parsed.environment.upper(),
        "risk_signals":    parsed.risk_signals,
        "contradictions":  [c.split(":")[0] for c in parsed.contradictions],
    }


def build_impact(graph: Dict, parsed) -> Dict:
    paths = [
        f"{e['from'].upper()} → {e['to'].upper()}"
        for e in graph.get("edges", [])
    ]
    return {
        "primary_service": parsed.service.upper(),
        "paths":           paths,
        "summary":         graph.get("explanation", "Impact path derived from service topology"),
        "node_count":      len(graph.get("nodes", [])),
    }


def build_premortem(trust: Dict, parsed, graph: Dict) -> Dict:
    failures: List[str] = []
    blast  = trust["blast_radius"]
    rev    = trust["reversibility"]
    policy = trust["policy_score"]
    nodes  = len(graph.get("nodes", []))

    if policy < 0.20:
        failures.append("Privilege escalation — high-permission policy may grant unintended access")
    if parsed.environment == "production" and parsed.action_verb == "destructive":
        failures.append("Production outage — destructive action on live environment with no rollback window")
    if blast > 0.25:
        failures.append(f"Cascade failure — blast radius {blast:.2f} propagates across {nodes} service(s)")
    if rev < 0.35:
        failures.append(f"Slow recovery — reversibility {rev:.2f} means manual reconfiguration required")
    if parsed.scope.get("scale_factor", 1) > 20:
        failures.append(f"Infrastructure shock — scale factor {parsed.scope['scale_factor']}× may exhaust resource pools")
    if "public_s3" in parsed.risk_signals:
        failures.append("Data exposure — public S3 access violates least-privilege principle")

    if not failures:
        failures.append("No critical failure modes identified at current risk level")

    likelihood = min(95, max(10, round((1 - trust["confidence"]) * 100)))

    return {
        "failures":   failures[:3],
        "likelihood": likelihood,
    }


def build_debate(debate: Dict) -> Dict:
    exec_text  = debate.get("executor", "")
    crit_text  = debate.get("critic", "")
    verdict    = debate.get("verdict", "")
    exec_score = debate.get("executor_strength") or debate.get("scores", {}).get("executor_strength", 0)
    crit_score = debate.get("critic_strength")   or debate.get("scores", {}).get("critic_strength", 0)

    if exec_score and crit_score:
        if crit_score > exec_score + 0.10:
            conclusion = "Critic concerns outweigh executor confidence — proceed with caution"
        elif exec_score > crit_score + 0.10:
            conclusion = "Executor argument is stronger — operation appears manageable"
        else:
            conclusion = "Agents are closely matched — outcome is genuinely uncertain"
    else:
        conclusion = verdict

    return {
        "executor":   exec_text,
        "critic":     crit_text,
        "conclusion": conclusion,
        "exec_score": round(exec_score, 2) if exec_score else None,
        "crit_score": round(crit_score, 2) if crit_score else None,
    }


def build_recommendation(parsed, trust: Dict, graph: Dict) -> List[str]:
    steps: List[str] = []
    svc   = parsed.service
    blast = trust["blast_radius"]
    rev   = trust["reversibility"]

    # Service-specific steps
    if svc == "iam":
        steps.append("Run IAM Access Analyzer to identify active role dependencies")
        steps.append("Verify no running EC2/Lambda instances rely on this role")
        if parsed.action_verb == "destructive":
            steps.append("Create a backup role with identical permissions before deletion")
    elif svc == "ec2":
        steps.append("Check ALB target group health before scaling")
        steps.append("Monitor RDS connection pool — set CloudWatch alarm at 80% capacity")
    elif svc == "rds":
        steps.append("Take a manual RDS snapshot before applying changes")
        steps.append("Verify replication lag is < 5s before proceeding")
    elif svc == "s3":
        steps.append("Enable S3 versioning before destructive operations")
        steps.append("Verify no active Lambda triggers depend on this bucket")
    elif svc == "lambda":
        steps.append("Archive current function version before deploying update")
        steps.append("Verify API Gateway integration after deployment")

    # Environment-specific
    if parsed.environment == "production":
        steps.append("Test identical operation in staging environment first")
        steps.append("Ensure on-call SRE is available during execution window")

    # Reversibility
    if rev < 0.40:
        steps.append("Document manual rollback procedure before proceeding")

    # Blast radius
    if blast > 0.25:
        affected = [n["id"].upper() for n in graph.get("nodes", []) if n["id"] != svc]
        if affected:
            steps.append(f"Notify dependent service owners: {', '.join(affected[:3])}")

    return steps[:5]


def build_final_call(trust: Dict, gate: str) -> Dict:
    conf = trust["confidence"]

    if gate == "BLOCK" or conf < 0.50:
        return {
            "recommendation": "DO NOT EXECUTE",
            "symbol":         "✗",
            "color":          "red",
            "note":           "Confidence and risk profile do not support execution",
        }
    elif conf < 0.70:
        return {
            "recommendation": "PROCEED WITH CAUTION",
            "symbol":         "⚠",
            "color":          "amber",
            "note":           "Complete checklist and obtain explicit SRE sign-off before executing",
        }
    else:
        return {
            "recommendation": "LIKELY SAFE TO APPROVE",
            "symbol":         "✓",
            "color":          "green",
            "note":           "Confidence is near AUTO threshold — verify environment and scope",
        }


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_audit_report(
    ticket: str,
    parsed,
    trust: Dict,
    gate: str,
    graph: Dict,
    debate: Dict,
    memory_penalty: Dict,
    ai_notes: List[str],
) -> Dict:
    return {
        "ticket":         ticket,
        "header":         build_header(parsed, gate),
        "decision":       build_decision(trust, gate),
        "risk_factors":   build_risk_factors(trust, parsed, graph),
        "impact":         build_impact(graph, parsed),
        "premortem":      build_premortem(trust, parsed, graph),
        "debate":         build_debate(debate),
        "recommendation": build_recommendation(parsed, trust, graph),
        "final_call":     build_final_call(trust, gate),
        "memory": {
            "prior_incidents": memory_penalty.get("count", 0),
            "penalty_applied": memory_penalty.get("penalty", 1.0),
            "pattern":         memory_penalty.get("pattern"),
        },
        "ai_notes": ai_notes,
        "scores": {
            "intent_score":  trust["intent_score"],
            "reversibility": trust["reversibility"],
            "blast_radius":  trust["blast_radius"],
            "policy_score":  trust["policy_score"],
            "confidence":    trust["confidence"],
        },
    }
