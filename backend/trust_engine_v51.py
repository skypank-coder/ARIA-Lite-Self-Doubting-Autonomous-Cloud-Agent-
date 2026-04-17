"""
trust_engine_v51.py — ARIA-Lite++ v5.1
Improved trust scoring with higher floors, NetworkX blast radius,
and smoother confidence computation.
"""

from dataclasses import dataclass, field
from typing import List, Dict
import networkx as nx


# ---------------------------
# DATA STRUCTURES
# ---------------------------

@dataclass
class ParsedIntent:
    action_verb: str
    service: str
    environment: str
    urgency: str
    scope: Dict
    risk_signals: List[str]
    dependencies: List[str] = field(default_factory=list)


@dataclass
class TrustScore:
    intent: float
    reversibility: float
    blast: float
    policy: float
    confidence: float


# ---------------------------
# DEPENDENCY GRAPH
# ---------------------------

def build_service_graph() -> nx.DiGraph:
    """Build the canonical AWS service dependency graph."""
    G = nx.DiGraph()
    edges = [
        ("iam",    "ec2"),
        ("iam",    "lambda"),
        ("iam",    "api"),
        ("ec2",    "rds"),
        ("lambda", "api"),
        ("s3",     "lambda"),
        ("s3",     "analytics"),
    ]
    G.add_edges_from(edges)
    return G


# Singleton — built once
_SERVICE_GRAPH: nx.DiGraph = build_service_graph()


# ---------------------------
# INTENT SCORE
# ---------------------------

def compute_intent_score(p: ParsedIntent) -> float:
    base = {
        "safe":        0.95,
        "scaling":     0.95,
        "mutating":    0.75,
        "destructive": 0.35,
        "unknown":     0.40,
    }.get(p.action_verb, 0.40)

    if p.environment == "production":
        base -= 0.15 if p.action_verb == "destructive" else 0.05
    elif p.environment == "dev":
        base += 0.08

    if p.urgency == "high":
        base -= 0.10

    if "admin_privilege" in p.risk_signals:
        base -= 0.10
    if "prod_destructive" in p.risk_signals:
        base -= 0.10

    return max(0.05, min(base, 1.0))


# ---------------------------
# REVERSIBILITY
# ---------------------------

def compute_reversibility(p: ParsedIntent) -> float:
    base = {
        "safe":        0.92,
        "scaling":     0.85,
        "mutating":    0.70,
        "destructive": 0.25,
        "unknown":     0.30,
    }.get(p.action_verb, 0.30)

    if p.service == "iam":
        base += 0.05
    elif p.service == "rds":
        base -= 0.15

    scale = p.scope.get("scale_factor", 1)
    if scale > 5:
        base -= min(0.25, (scale - 5) * 0.02)

    if p.scope.get("no_rollback"):
        base -= 0.25

    if p.environment == "production" and p.action_verb == "destructive":
        base -= 0.10

    return max(0.15, min(base, 1.0))


# ---------------------------
# BLAST RADIUS
# ---------------------------

def compute_blast_radius(p: ParsedIntent, graph: nx.DiGraph = None) -> float:
    g = graph if graph is not None else _SERVICE_GRAPH

    if p.service not in g:
        return 0.10

    try:
        affected = nx.descendants(g, p.service)
    except Exception:
        affected = set()

    dep_count = len(affected)
    graph_score = min(0.60, dep_count * 0.08)

    verb_mult = {
        "safe":        0.05,
        "scaling":     0.12,
        "mutating":    0.40,
        "destructive": 1.00,
        "unknown":     0.50,
    }.get(p.action_verb, 0.50)

    blast = graph_score * verb_mult

    service_weight = {
        "iam": 0.25,
        "rds": 0.20,
        "ec2": 0.12,
        "s3":  0.10,
    }.get(p.service, 0.05)

    blast += service_weight

    scale = p.scope.get("scale_factor", 1)
    if scale > 10:
        blast += 0.15
    elif scale > 5:
        blast += 0.08

    if p.environment == "production":
        blast += 0.15

    if "public_access" in p.risk_signals:
        blast += 0.20

    return min(blast, 0.95)


# ---------------------------
# POLICY SCORE
# ---------------------------

def compute_policy_score(p: ParsedIntent) -> float:
    base = 1.0

    if p.environment == "production" and p.action_verb == "destructive":
        return 0.05

    if "admin_privilege" in p.risk_signals:
        base = min(base, 0.40)

    if "public_access" in p.risk_signals:
        base -= 0.50

    if p.scope.get("cross_account"):
        base = min(base, 0.30)

    return max(0.05, base)


# ---------------------------
# CONFIDENCE
# ---------------------------

def compute_confidence(intent: float, reversibility: float,
                        blast: float, policy: float) -> float:
    conf = intent * reversibility * (1.0 - blast) * policy
    return max(0.02, round(conf, 4))


# ---------------------------
# MAIN ENTRY
# ---------------------------

def compute_trust(parsed: ParsedIntent, graph: nx.DiGraph = None) -> TrustScore:
    intent        = compute_intent_score(parsed)
    reversibility = compute_reversibility(parsed)
    blast         = compute_blast_radius(parsed, graph)
    policy        = compute_policy_score(parsed)
    confidence    = compute_confidence(intent, reversibility, blast, policy)

    return TrustScore(
        intent=round(intent, 3),
        reversibility=round(reversibility, 3),
        blast=round(blast, 3),
        policy=round(policy, 3),
        confidence=round(confidence, 4),
    )


# ---------------------------
# ADAPTER — converts parser.ParsedIntent → v51 ParsedIntent
# ---------------------------

def from_parser_intent(p) -> ParsedIntent:
    """
    Convert a parser.ParsedIntent (v5) into a trust_engine_v51.ParsedIntent.
    Allows v51 to run on the same parsed data without re-parsing.
    """
    return ParsedIntent(
        action_verb=p.action_verb,
        service=p.service,
        environment=p.environment,
        urgency=p.urgency,
        scope=dict(p.scope),
        risk_signals=list(p.risk_signals),
        dependencies=list(getattr(p, "affected_nodes", []) or []),
    )
