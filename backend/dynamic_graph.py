"""
dynamic_graph.py — ARIA-Lite++
Builds structured dependency graph from parsed intent + risk signals.
Nodes have id + type. Edges have from + to.
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent


def build_dynamic_graph(parsed: "ParsedIntent") -> Dict:
    """
    Returns {"nodes": [{id, type}], "edges": [{from, to}]}
    Expanded by service topology + risk signals + scope.
    """
    service      = getattr(parsed, "service", "unknown")
    risk_signals = getattr(parsed, "risk_signals", [])
    scope        = getattr(parsed, "scope", {})

    nodes: List[Dict] = [{"id": service, "type": "core"}]

    # Service-based topology
    if service == "s3":
        nodes += [{"id": "lambda", "type": "compute"}, {"id": "cloudfront", "type": "edge"}]
    elif service == "ec2":
        nodes += [{"id": "rds", "type": "database"}, {"id": "alb", "type": "network"}]
    elif service == "iam":
        nodes += [{"id": "ec2", "type": "compute"}, {"id": "lambda", "type": "compute"}]
    elif service == "rds":
        nodes += [{"id": "ec2", "type": "compute"}, {"id": "lambda", "type": "compute"}]
    elif service == "lambda":
        nodes += [{"id": "api", "type": "gateway"}, {"id": "s3", "type": "storage"}]
    elif service == "alb":
        nodes += [{"id": "ec2", "type": "compute"}]

    # Risk-signal expansion
    if "prod_destructive" in risk_signals:
        nodes.append({"id": "cloudwatch", "type": "monitoring"})
    if "extreme_scale" in risk_signals or "large_scale" in risk_signals:
        nodes.append({"id": "cloudwatch", "type": "monitoring"})
    if "public_s3" in risk_signals:
        nodes.append({"id": "cloudwatch", "type": "monitoring"})
    if "admin_privilege" in risk_signals:
        nodes.append({"id": "api", "type": "gateway"})

    # Scope-based expansion
    if scope.get("scale_factor", 1) > 20:
        nodes.append({"id": "autoscaling", "type": "system"})

    # Deduplicate preserving order
    seen = set()
    unique_nodes = []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            unique_nodes.append(n)

    # Connect all non-root nodes to root
    edges = [
        {"from": service, "to": n["id"]}
        for n in unique_nodes
        if n["id"] != service
    ]

    return {"nodes": unique_nodes, "edges": edges}


def get_affected_nodes(parsed: "ParsedIntent") -> List[str]:
    """Returns flat list of downstream node IDs for blast radius computation."""
    graph = build_dynamic_graph(parsed)
    return [n["id"] for n in graph["nodes"] if n["id"] != getattr(parsed, "service", "unknown")]
