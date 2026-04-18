"""
dynamic_graph.py — ARIA-Lite++
Impact Propagation Graph engine.
- Verb-aware dependency selection (control_plane / compute / data / edge)
- Priority-based pruning: primary > critical > compute > edge > auxiliary
- Hard cap: 4 nodes
- Returns explanation of why nodes were selected
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent

# ── Type priority for pruning ─────────────────────────────────────────────────
_PRIORITY = {
    "primary":   5,
    "critical":  4,
    "compute":   3,
    "network":   2,
    "data":      2,
    "edge":      2,
    "monitor":   1,
    "messaging": 1,
}

_TYPE_WAVE = {
    "primary":   1,
    "critical":  1,
    "compute":   2,
    "network":   2,
    "data":      2,
    "edge":      2,
    "monitor":   3,
    "messaging": 3,
}

MAX_NODES = 4

# ── Verb-aware impact deps ────────────────────────────────────────────────────
# Each entry: (node_id, node_type, risk_score)

_IMPACT_DEPS: Dict[str, Dict[str, List[tuple]]] = {
    "iam": {
        "destructive":   [("ec2", "compute", 0.90), ("lambda", "compute", 0.90)],
        "safe":          [("ec2", "compute", 0.70), ("lambda", "compute", 0.70),
                          ("s3", "data", 0.50)],
        "safe_mutating": [("ec2", "compute", 0.75), ("lambda", "compute", 0.75)],
        "_default":      [("ec2", "compute", 0.60)],
    },
    "s3": {
        "destructive":   [("lambda", "compute", 0.80), ("cloudfront", "edge", 0.60)],
        "safe":          [("lambda", "compute", 0.50), ("cloudfront", "edge", 0.40)],
        "_default":      [("lambda", "compute", 0.55), ("cloudfront", "edge", 0.45)],
    },
    "ec2": {
        "scaling":       [("alb", "network", 0.80), ("rds", "critical", 0.90)],
        "destructive":   [("alb", "network", 0.85), ("rds", "critical", 0.95)],
        "_default":      [("alb", "network", 0.60), ("cloudwatch", "monitor", 0.40)],
    },
    "rds": {
        "destructive":   [("ec2", "compute", 0.90), ("lambda", "compute", 0.80)],
        "mutating":      [("ec2", "compute", 0.70), ("lambda", "compute", 0.60)],
        "_default":      [("ec2", "compute", 0.65), ("cloudwatch", "monitor", 0.45)],
    },
    "lambda": {
        "safe":          [("api", "edge", 0.70), ("cloudwatch", "monitor", 0.40)],
        "destructive":   [("api", "edge", 0.80), ("cloudwatch", "monitor", 0.50)],
        "_default":      [("api", "edge", 0.65), ("cloudwatch", "monitor", 0.40)],
    },
    "alb": {
        "_default":      [("ec2", "compute", 0.80), ("cloudwatch", "monitor", 0.40)],
    },
    "secrets": {
        "_default":      [("lambda", "compute", 0.75), ("ec2", "compute", 0.65)],
    },
    "kms": {
        "destructive":   [("s3", "data", 0.90), ("rds", "critical", 0.90)],
        "_default":      [("s3", "data", 0.70), ("rds", "critical", 0.70)],
    },
    "cloudwatch": {
        "_default":      [("sns", "messaging", 0.50)],
    },
    "vpc": {
        "_default":      [("ec2", "compute", 0.75), ("rds", "critical", 0.70)],
    },
}

_EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "iam": {
        "destructive":   "IAM deletion revokes execution roles — EC2 and Lambda lose access immediately",
        "safe":          "IAM policy attachment propagates permissions to compute and data services",
        "safe_mutating": "IAM credential rotation impacts active sessions on compute services",
        "_default":      "IAM change affects downstream service authorization",
    },
    "s3": {
        "destructive":   "S3 deletion breaks Lambda triggers and CloudFront origin",
        "safe":          "S3 creation enables Lambda event sources and CloudFront distribution",
        "_default":      "S3 change propagates to Lambda consumers and CDN edge",
    },
    "ec2": {
        "scaling":       "EC2 scaling increases ALB target group load and RDS connection pool pressure",
        "destructive":   "EC2 termination removes ALB targets and drops RDS connections",
        "_default":      "EC2 change affects load balancer routing and monitoring",
    },
    "rds": {
        "destructive":   "RDS deletion causes immediate data loss for EC2 app servers and Lambda functions",
        "mutating":      "RDS parameter change requires EC2 and Lambda reconnection",
        "_default":      "RDS change propagates to application compute layer",
    },
    "lambda": {
        "_default":      "Lambda update affects API Gateway routing and CloudWatch log streams",
    },
}


# ── Pruning ───────────────────────────────────────────────────────────────────

def _prune(nodes: List[Dict], edges: List[List[str]], max_n: int) -> tuple:
    if len(nodes) <= max_n:
        return nodes, edges

    sorted_nodes = sorted(
        nodes,
        key=lambda x: (_PRIORITY.get(x["type"], 0), x["risk"]),
        reverse=True,
    )
    selected = sorted_nodes[:max_n]
    allowed  = {n["id"] for n in selected}

    pruned_edges = [
        [a, b] for a, b in edges
        if a in allowed and b in allowed
    ]
    return selected, pruned_edges


# ── Public interface ──────────────────────────────────────────────────────────

def build_dynamic_graph(parsed: "ParsedIntent") -> Dict:
    """
    Returns:
      {
        nodes: [{id, type, wave, node_type, risk}],
        edges: [{from, to}],
        explanation: str
      }
    Hard cap: 4 nodes. Verb-aware. Priority-pruned.
    """
    service      = getattr(parsed, "service", "unknown")
    risk_signals = getattr(parsed, "risk_signals", [])
    verb         = getattr(parsed, "action_verb", "unknown")

    is_critical = (
        verb == "destructive" or
        any(s in risk_signals for s in
            {"prod_destructive", "admin_privilege", "irreversible_db", "credential_risk"})
    )

    # Primary node
    nodes: List[Dict] = [{
        "id":        service,
        "type":      "primary",
        "wave":      1,
        "node_type": "SOURCE",
        "risk":      1.0,
    }]
    edges: List[List[str]] = []

    # Verb-aware deps
    svc_map  = _IMPACT_DEPS.get(service, {})
    dep_list = svc_map.get(verb) or svc_map.get("_default") or []

    for nid, ntype, risk in dep_list:
        if nid == service:
            continue
        nodes.append({
            "id":        nid,
            "type":      ntype,
            "wave":      _TYPE_WAVE.get(ntype, 2),
            "node_type": "CRITICAL" if is_critical else "ACTIVE",
            "risk":      risk,
        })
        edges.append([service, nid])

    # Risk-signal additions (before pruning)
    existing = {n["id"] for n in nodes}

    def _add(nid: str, ntype: str, risk: float) -> None:
        if nid not in existing:
            nodes.append({
                "id": nid, "type": ntype,
                "wave": _TYPE_WAVE.get(ntype, 2),
                "node_type": "CRITICAL" if is_critical else "ACTIVE",
                "risk": risk,
            })
            edges.append([service, nid])
            existing.add(nid)

    if "admin_privilege" in risk_signals or "credential_risk" in risk_signals:
        _add("cloudtrail", "monitor", 0.70)
    if "prod_destructive" in risk_signals:
        _add("sns", "messaging", 0.55)
    if "public_s3" in risk_signals:
        _add("cloudwatch", "monitor", 0.60)

    # Prune to MAX_NODES
    nodes, raw_edges = _prune(nodes, edges, MAX_NODES)

    # Convert edges to {from, to} dicts, deduplicated
    allowed = {n["id"] for n in nodes}
    seen: set = set()
    unique_edges = []
    for a, b in raw_edges:
        key = (a, b)
        if key not in seen and a in allowed and b in allowed and a != b:
            seen.add(key)
            unique_edges.append({"from": a, "to": b})

    # Explanation
    svc_expl = _EXPLANATIONS.get(service, {})
    explanation = (
        svc_expl.get(verb) or
        svc_expl.get("_default") or
        f"Impact graph auto-pruned to top-risk dependencies (k={MAX_NODES})"
    )

    return {"nodes": nodes, "edges": unique_edges, "explanation": explanation}


def get_affected_nodes(parsed: "ParsedIntent") -> List[str]:
    graph = build_dynamic_graph(parsed)
    return [n["id"] for n in graph["nodes"] if n["id"] != getattr(parsed, "service", "unknown")]
