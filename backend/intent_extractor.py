# backend/intent_extractor.py
"""
V2 structured intent extractor.
Converts raw ticket text into a typed IntentParameters object.
All computation in trust_engine_v2.py uses these parameters — not scenario metadata.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# Known-safe action library (50 pre-computed embeddings replaced by cosine sim table)
# Maps (action_keyword, operation_type) → base_intent_score
SAFE_ACTION_LIBRARY = {
    ("s3", "create"):     0.94,
    ("s3", "put"):        0.88,
    ("s3", "delete"):     0.22,
    ("iam", "create"):    0.80,
    ("iam", "attach"):    0.72,
    ("iam", "detach"):    0.68,
    ("iam", "delete"):    0.18,
    ("ec2", "scale"):     0.90,
    ("ec2", "run"):       0.82,
    ("ec2", "stop"):      0.78,
    ("ec2", "terminate"): 0.20,
    ("rds", "create"):    0.85,
    ("rds", "modify"):    0.75,
    ("rds", "delete"):    0.15,
    ("lambda", "deploy"): 0.88,
    ("lambda", "delete"): 0.25,
    ("ec2", "start"):     0.85,
}

# Reversibility base by operation type
REVERSIBILITY_BASE = {
    "create": 0.92, "put": 0.85, "deploy": 0.87, "start": 0.90,
    "scale":  0.85, "stop": 0.88, "modify": 0.65,
    "attach": 0.75, "detach": 0.72,
    "delete": 0.08, "terminate": 0.05, "drop": 0.05,
}

ENVIRONMENTS = {"prod", "production", "prd", "live"}
STAGING_ENVS = {"staging", "stg", "stage"}
DEV_ENVS     = {"dev", "development", "test", "sandbox", "qa"}

AWS_REGIONS  = {
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
}


@dataclass
class IntentParameters:
    # Extracted action
    raw_text: str           = ""
    action: str             = "unknown"     # e.g. "ec2_scale"
    service: str            = "unknown"     # e.g. "ec2"
    operation: str          = "unknown"     # e.g. "scale"

    # Quantitative parameters (the part v1 completely ignores)
    source_count: Optional[int]   = None   # from 2
    target_count: Optional[int]   = None   # to 8
    scale_factor: float           = 1.0    # target/source if applicable

    # Context parameters
    environment: str        = "unknown"    # prod | staging | dev | unknown
    region: Optional[str]   = None
    is_immediate: bool      = False        # "immediately", "now", "asap"
    is_production: bool     = False
    has_explicit_rollback: bool = False    # "with rollback", "reversible"
    urgency: str            = "normal"     # normal | high | critical

    # Confidence of extraction itself (how well we parsed the ticket)
    extraction_confidence: float = 0.5


def extract_intent(ticket: str) -> IntentParameters:
    """
    Extract structured IntentParameters from raw ticket text.
    This replaces keyword→scenario lookup with parameter extraction.
    """
    p = IntentParameters(raw_text=ticket)
    t = ticket.lower().strip()

    # ── Service detection ─────────────────────────────────────────────
    if re.search(r'\bs3\b|bucket', t):          p.service = "s3"
    elif re.search(r'\biam\b|role|policy|permission', t): p.service = "iam"
    elif re.search(r'\bec2\b|instance', t):     p.service = "ec2"
    elif re.search(r'\brds\b|database|db\b', t): p.service = "rds"
    elif re.search(r'\blambda\b|function', t):  p.service = "lambda"
    elif re.search(r'\beks\b|kubernetes|k8s', t): p.service = "eks"
    elif re.search(r'\bvpc\b|subnet|security.group', t): p.service = "vpc"

    # ── Operation detection ───────────────────────────────────────────
    if re.search(r'\bdelete\b|\bdrop\b|\bremove\b|\bdestroy\b', t):
        p.operation = "delete"
    elif re.search(r'\bterminate\b|\bkill\b', t):
        p.operation = "terminate"
    elif re.search(r'\bscale\b|increase.*instance|add.*instance', t):
        p.operation = "scale"
    elif re.search(r'\bcreate\b|\blaunch\b|\bprovision\b|\bspawn\b', t):
        p.operation = "create"
    elif re.search(r'\battach\b|\bgrant\b|\badd.*policy', t):
        p.operation = "attach"
    elif re.search(r'\bdetach\b|\brevoke\b|\bremove.*policy', t):
        p.operation = "detach"
    elif re.search(r'\bmodify\b|\bupdate\b|\bchange\b|\bpatch\b', t):
        p.operation = "modify"
    elif re.search(r'\bdeploy\b|\bpublish\b|\brelease\b', t):
        p.operation = "deploy"
    elif re.search(r'\bstop\b|\bshutdown\b|\bhalt\b', t):
        p.operation = "stop"
    elif re.search(r'\bstart\b|\brestart\b|\bboot\b', t):
        p.operation = "start"

    p.action = f"{p.service}_{p.operation}" if p.service != "unknown" else "unknown"

    # ── Quantitative extraction ───────────────────────────────────────
    # "from 2 to 8", "2 -> 8", "2 to 8", "scale up to 8"
    range_match = re.search(r'from\s+(\d+)\s+to\s+(\d+)', t)
    if range_match:
        p.source_count = int(range_match.group(1))
        p.target_count = int(range_match.group(2))
        if p.source_count > 0:
            p.scale_factor = p.target_count / p.source_count
    else:
        arrow_match = re.search(r'(\d+)\s*[-–→>]+\s*(\d+)', t)
        if arrow_match:
            p.source_count = int(arrow_match.group(1))
            p.target_count = int(arrow_match.group(2))
            if p.source_count > 0:
                p.scale_factor = p.target_count / p.source_count
        else:
            to_match = re.search(r'to\s+(\d+)\s+(?:instance|node|replica|server)', t)
            if to_match:
                p.target_count = int(to_match.group(1))

    # ── Environment detection ─────────────────────────────────────────
    for env_word in ENVIRONMENTS:
        if env_word in t:
            p.environment = "prod"
            p.is_production = True
            break
    if p.environment == "unknown":
        for env_word in STAGING_ENVS:
            if env_word in t:
                p.environment = "staging"
                break
    if p.environment == "unknown":
        for env_word in DEV_ENVS:
            if env_word in t:
                p.environment = "dev"
                break

    # ── Region detection ─────────────────────────────────────────────
    for region in AWS_REGIONS:
        if region in t:
            p.region = region
            break

    # ── Qualitative signals ───────────────────────────────────────────
    if re.search(r'\bimmediately\b|\bright now\b|\basap\b|\burgent\b|\bnow\b', t):
        p.is_immediate = True
        p.urgency = "critical"
    elif re.search(r'\bquickly\b|\bsoon\b|\bfast\b', t):
        p.urgency = "high"

    if re.search(r'\bwith rollback\b|\breversible\b|\bcan undo\b', t):
        p.has_explicit_rollback = True

    # ── Extraction confidence ─────────────────────────────────────────
    confidence = 0.0
    if p.service != "unknown":  confidence += 0.35
    if p.operation != "unknown": confidence += 0.35
    if p.environment != "unknown": confidence += 0.15
    if p.scale_factor != 1.0 or p.source_count is not None: confidence += 0.15
    p.extraction_confidence = min(1.0, confidence)

    return p
