"""
Intelligent Parser — ARIA-Lite++ v5
Multi-signal ticket analysis: verb, service, environment, urgency, scope, risk signals.
Verb takes priority over service noun. "delete bucket" = destructive on S3, not a create.
"""

import re
import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from scenarios import SCENARIOS

try:
    from groq import Groq
except ImportError:
    Groq = None


# ── Verb taxonomy ─────────────────────────────────────────────────────────────

_DESTRUCTIVE_VERBS = {
    "delete", "destroy", "terminate", "purge", "remove", "drop",
    "wipe", "revoke", "decommission", "deprovision", "disable",
    "detach", "deregister", "expire", "flush", "truncate",
}

_MUTATING_VERBS = {
    "modify", "update", "change", "configure", "patch", "edit",
    "alter", "adjust", "set", "override", "replace", "migrate",
    "rotate", "renew", "refresh", "reboot", "restart", "reset",
}

_SCALING_VERBS = {
    "scale", "resize", "expand", "shrink", "autoscale", "launch",
    "provision", "spin up", "spin down", "increase", "decrease",
}

_SAFE_VERBS = {
    "create", "add", "enable", "deploy", "attach", "backup",
    "snapshot", "export", "copy", "clone", "tag", "list",
    "describe", "get", "read", "view", "check", "validate",
    "test", "audit", "monitor", "restore", "import",
}


def extract_verb(ticket: str) -> str:
    t = ticket.lower()
    # Destructive checked first — highest priority
    for v in _DESTRUCTIVE_VERBS:
        if re.search(rf"\b{re.escape(v)}\b", t):
            return "destructive"
    for v in _SCALING_VERBS:
        if re.search(rf"\b{re.escape(v)}\b", t):
            return "scaling"
    for v in _MUTATING_VERBS:
        if re.search(rf"\b{re.escape(v)}\b", t):
            return "mutating"
    for v in _SAFE_VERBS:
        if re.search(rf"\b{re.escape(v)}\b", t):
            return "safe"
    return "unknown"


# ── Service mapping ───────────────────────────────────────────────────────────

_SERVICE_PATTERNS: List[tuple] = [
    # (regex pattern, canonical service name)
    (r"\b(s3|bucket|object storage|blob)\b",          "s3"),
    (r"\b(iam|role|policy|permission|credential|access key)\b", "iam"),
    (r"\b(ec2|instance|server|vm|virtual machine|autoscal)\b",  "ec2"),
    (r"\b(rds|database|db|postgres|mysql|aurora|sql)\b",        "rds"),
    (r"\b(lambda|function|serverless|faas)\b",                  "lambda"),
    (r"\b(cloudwatch|cw|metric|alarm|log group)\b",             "cloudwatch"),
    (r"\b(secrets manager|secret|secretsmanager)\b",            "secrets"),
    (r"\b(alb|elb|load balancer|target group)\b",               "alb"),
    (r"\b(cloudfront|cdn|distribution)\b",                      "cloudfront"),
    (r"\b(vpc|subnet|security group|nacl|route table)\b",       "vpc"),
    (r"\b(kms|key|encryption key)\b",                           "kms"),
    (r"\b(cloudtrail|trail|audit log)\b",                       "cloudtrail"),
]


def extract_service(ticket: str) -> str:
    t = ticket.lower()
    for pattern, service in _SERVICE_PATTERNS:
        if re.search(pattern, t):
            return service
    return "unknown"


# ── Environment ───────────────────────────────────────────────────────────────

def extract_env(ticket: str) -> str:
    t = ticket.lower()
    if re.search(r"\b(production|prod|live|prd)\b", t):
        return "production"
    if re.search(r"\b(staging|stage|qa|uat|pre-prod|preprod)\b", t):
        return "staging"
    if re.search(r"\b(dev|development|test|sandbox|local|lower)\b", t):
        return "dev"
    return "unknown"


# ── Urgency ───────────────────────────────────────────────────────────────────

def extract_urgency(ticket: str) -> str:
    t = ticket.lower()
    if re.search(r"\b(immediately|urgent|asap|right now|emergency|now|critical|hotfix)\b", t):
        return "high"
    if re.search(r"\b(carefully|slowly|safely|with review|after audit|planned|scheduled)\b", t):
        return "low"
    return "normal"


# ── Scope / parameters ────────────────────────────────────────────────────────

def extract_scope(ticket: str) -> Dict[str, Any]:
    scope: Dict[str, Any] = {}
    t = ticket.lower()

    # EC2 scale factor
    m = re.search(r"from\s+(\d+)\s+to\s+(\d+)", t)
    if m:
        current = int(m.group(1))
        target = int(m.group(2))
        scope["current"] = current
        scope["target"] = target
        scope["scale_factor"] = round(target / max(current, 1), 2)

    # IAM privilege level
    if re.search(r"\b(administratoraccess|administrator access|admin access|admin policy|full access|root)\b", t):
        scope["privilege_level"] = "admin"
    elif re.search(r"\b(poweruser|power user)\b", t):
        scope["privilege_level"] = "power"
    elif re.search(r"\b(readonly|read.only|read only)\b", t):
        scope["privilege_level"] = "readonly"

    # Detect named IAM policy
    policy_match = re.search(
        r"\b(AdministratorAccess|PowerUserAccess|ReadOnlyAccess|SecurityAudit|"
        r"IAMFullAccess|S3FullAccess|EC2FullAccess|RDSFullAccess|LambdaFullAccess)\b",
        ticket  # case-sensitive for policy names
    )
    if policy_match:
        scope["iam_policy_name"] = policy_match.group(1)

    # S3 public access
    if re.search(r"\b(public.access|public acl|acl public|publicly accessible|open access)\b", t):
        scope["public_access"] = True

    # RDS destructive
    if re.search(r"\b(drop|delete|destroy|wipe)\b", t) and re.search(r"\b(rds|database|db)\b", t):
        scope["destructive"] = True

    # Cross-account
    if re.search(r"\b(cross.account|assume.role|cross account)\b", t):
        scope["cross_account"] = True

    # No rollback signal
    if re.search(r"\b(no rollback|irreversible|cannot undo|no undo)\b", t):
        scope["no_rollback"] = True

    return scope


# ── Risk signals ──────────────────────────────────────────────────────────────

def extract_risk_signals(ticket: str, service: str, verb: str, env: str, scope: Dict) -> List[str]:
    signals = []
    t = ticket.lower()

    if service == "s3" and scope.get("public_access"):
        signals.append("public_s3")

    if env == "production" and verb == "destructive":
        signals.append("prod_destructive")

    if service == "iam" and scope.get("privilege_level") == "admin":
        signals.append("admin_privilege")

    scale_factor = scope.get("scale_factor", 1)
    if scale_factor > 10:
        signals.append("extreme_scale")
    elif scale_factor > 5:
        signals.append("large_scale")

    if service == "rds" and verb == "destructive":
        signals.append("irreversible_db")

    if scope.get("cross_account"):
        signals.append("cross_account")

    if scope.get("no_rollback"):
        signals.append("no_rollback")

    if env == "production" and re.search(r"\b(immediately|urgent|asap|emergency)\b", t):
        signals.append("prod_urgency")

    if service == "kms" and verb == "destructive":
        signals.append("key_deletion")

    if service == "cloudtrail" and verb == "destructive":
        signals.append("audit_trail_deletion")

    return signals


# ── Contradiction detection ───────────────────────────────────────────────────

def detect_contradictions(ticket: str, verb: str, env: str, urgency: str, scope: Dict) -> List[str]:
    contradictions = []
    t = ticket.lower()

    if urgency == "high" and env == "production":
        contradictions.append(
            "URGENCY_PROD_CONFLICT: high urgency on production increases error probability"
        )

    if re.search(r"\b(safely|carefully|with review)\b", t) and verb == "destructive":
        contradictions.append(
            "VERB_QUALIFIER_CONFLICT: safety qualifier combined with destructive action — intent ambiguous"
        )

    if scope.get("public_access") and "s3" in t:
        contradictions.append(
            "SECURITY_POSTURE_CONFLICT: public access on S3 violates least-privilege principle"
        )

    scale_factor = scope.get("scale_factor", 1)
    if scale_factor > 50:
        contradictions.append(
            f"SCALE_REASONABLENESS_CONFLICT: scale factor {scale_factor}x exceeds operational norms (>50x)"
        )

    if scope.get("privilege_level") == "admin" and env == "production":
        contradictions.append(
            "PRIVILEGE_ENV_CONFLICT: admin-level policy attachment in production environment"
        )

    if scope.get("no_rollback") and env == "production":
        contradictions.append(
            "IRREVERSIBILITY_PROD_CONFLICT: explicitly irreversible action on production"
        )

    return contradictions


# ── ParsedIntent dataclass ────────────────────────────────────────────────────

@dataclass
class ParsedIntent:
    action_verb: str          # destructive / mutating / scaling / safe / unknown
    service: str              # s3 / iam / ec2 / rds / lambda / cloudwatch / secrets / alb / unknown
    environment: str          # production / staging / dev / unknown
    urgency: str              # high / normal / low
    scope: Dict[str, Any]     # extracted parameters
    risk_signals: List[str]   # detected risk flags
    contradictions: List[str] # detected contradictions
    raw_ticket: str           # original ticket text
    affected_count: int = 0   # filled in by trust engine after graph traversal


def parse_ticket(ticket: str) -> ParsedIntent:
    """
    Full multi-signal parse of a cloud operation ticket.
    Verb takes priority over service noun.
    """
    verb    = extract_verb(ticket)
    service = extract_service(ticket)
    env     = extract_env(ticket)
    urgency = extract_urgency(ticket)
    scope   = extract_scope(ticket)
    signals = extract_risk_signals(ticket, service, verb, env, scope)
    contras = detect_contradictions(ticket, verb, env, urgency, scope)

    return ParsedIntent(
        action_verb=verb,
        service=service,
        environment=env,
        urgency=urgency,
        scope=scope,
        risk_signals=signals,
        contradictions=contras,
        raw_ticket=ticket,
    )


# ── Groq LLM fallback (unchanged interface) ───────────────────────────────────

def _parse_json_object(text: str) -> Dict[str, Any]:
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        return {}


def groq_full_analysis(ticket: str, api_key: str) -> Optional[Dict[str, Any]]:
    if not api_key or not Groq:
        return None

    prompt = f"""You are ARIA-Lite++, a trust-aware cloud safety system.
Analyze this cloud operation ticket and return ONLY valid JSON with this exact schema:

{{
  "intent": "string — best matching: s3_create|iam_delete|iam_attach|ec2_scale|rds_modify|lambda_deploy|custom",
  "intent_score": 0.0-1.0,
  "reversibility": 0.0-1.0,
  "blast_radius": 0.0-1.0,
  "policy_score": 0.0-1.0,
  "top_risk": "one sentence",
  "top_mitigation": "one sentence",
  "executor_argument": "one sentence",
  "critic_argument": "one sentence",
  "reasoning": "two sentences"
}}

Rules:
- Dangerous operations (delete, terminate, purge production): intent_score<0.30, reversibility<0.20
- Risky privilege operations (admin, root, wildcard IAM): policy_score<0.50
- Read-only operations: blast_radius<0.10
- No markdown, no extra keys

Ticket: "{ticket}"
"""
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            top_p=1,
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_object(content)
        required = ["intent_score", "reversibility", "blast_radius", "policy_score"]
        for field_name in required:
            val = parsed.get(field_name)
            if not isinstance(val, (int, float)):
                return None
            parsed[field_name] = round(min(max(float(val), 0.0), 1.0), 2)
        return parsed
    except Exception:
        return None
