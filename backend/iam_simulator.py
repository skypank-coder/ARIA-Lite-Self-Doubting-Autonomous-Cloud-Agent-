"""
IAM Simulator — ARIA-Lite++ v5
Local IAM policy evaluation without AWS credentials.
Simulates policy evaluation logic for trust scoring.
"""

from typing import Dict, Optional

POLICY_RULES: Dict[str, Dict] = {
    "AdministratorAccess": {
        "effect": "Allow", "actions": ["*"], "risk": "CRITICAL",
    },
    "PowerUserAccess": {
        "effect": "Allow", "actions": ["*"], "not_actions": ["iam:*"], "risk": "HIGH",
    },
    "ReadOnlyAccess": {
        "effect": "Allow",
        "actions": ["*:Describe*", "*:List*", "*:Get*"],
        "risk": "LOW",
    },
    "SecurityAudit": {
        "effect": "Allow",
        "actions": ["*:Get*", "*:List*", "*:Describe*"],
        "risk": "LOW",
    },
    "IAMFullAccess": {
        "effect": "Allow", "actions": ["iam:*"], "risk": "CRITICAL",
    },
    "S3FullAccess": {
        "effect": "Allow", "actions": ["s3:*"], "risk": "MEDIUM",
    },
    "EC2FullAccess": {
        "effect": "Allow", "actions": ["ec2:*"], "risk": "MEDIUM",
    },
    "RDSFullAccess": {
        "effect": "Allow", "actions": ["rds:*"], "risk": "HIGH",
    },
    "LambdaFullAccess": {
        "effect": "Allow", "actions": ["lambda:*"], "risk": "MEDIUM",
    },
}

DANGEROUS_ACTIONS = {
    "iam:DeleteRole", "iam:DeleteUser", "iam:CreateRole",
    "iam:AttachRolePolicy", "iam:PutRolePolicy", "iam:PassRole",
    "s3:DeleteBucket", "s3:PutBucketAcl", "s3:PutBucketPolicy",
    "ec2:TerminateInstances", "ec2:DeleteSecurityGroup",
    "rds:DeleteDBInstance", "rds:DeleteDBCluster",
    "kms:DeleteKey", "kms:DisableKey",
    "cloudtrail:DeleteTrail", "cloudtrail:StopLogging",
}

_RISK_TO_SCORE = {
    "LOW":     0.95,
    "MEDIUM":  0.75,
    "HIGH":    0.45,
    "CRITICAL": 0.10,
    "UNKNOWN": 0.20,
}


def simulate_iam_policy(action: str, resource: str, policy_name: str) -> Dict:
    policy = POLICY_RULES.get(policy_name)
    if not policy:
        return {
            "effect": "DENY",
            "reason": f"Policy {policy_name} not recognized",
            "risk": "UNKNOWN",
            "dangerous": False,
            "warning": None,
        }

    is_dangerous = action in DANGEROUS_ACTIONS
    allowed_actions = policy.get("actions", [])
    not_actions = policy.get("not_actions", [])

    # Wildcard allow
    if "*" in allowed_actions:
        action_prefix = action.split(":")[0] + ":*"
        excluded = any(
            na == action or na == action_prefix or action.startswith(na.replace("*", ""))
            for na in not_actions
        )
        if excluded:
            return {
                "effect": "DENY",
                "reason": f"{policy_name} excludes {action} via NotAction",
                "risk": policy["risk"],
                "dangerous": is_dangerous,
                "warning": None,
            }
        return {
            "effect": "ALLOW",
            "reason": f"{policy_name} grants wildcard access",
            "risk": policy["risk"],
            "dangerous": is_dangerous,
            "warning": (
                f"Action {action} is classified as DANGEROUS and should require additional approval"
                if is_dangerous else None
            ),
        }

    # Specific action match
    allowed = any(
        action == a or action.startswith(a.replace("*", ""))
        for a in allowed_actions
    )
    return {
        "effect": "ALLOW" if allowed else "DENY",
        "reason": f"{'Matched' if allowed else 'No match in'} {policy_name} action list",
        "risk": policy["risk"],
        "dangerous": is_dangerous,
        "warning": (
            f"Action {action} is classified as DANGEROUS" if is_dangerous and allowed else None
        ),
    }


def evaluate_trust_from_iam(policy_name: str, action: str) -> float:
    """Returns a policy_score (0–1) derived from IAM simulation result."""
    result = simulate_iam_policy(action, "*", policy_name)
    if result["effect"] == "DENY":
        return 0.0
    base = _RISK_TO_SCORE.get(result["risk"], 0.50)
    if result.get("dangerous"):
        base = max(0.05, base - 0.25)
    return round(base, 2)


def get_iam_simulation(parsed_scope: Dict, action_verb: str) -> Optional[Dict]:
    """
    Returns IAM simulation result if a policy name was detected in the ticket.
    Returns None if no policy name was found.
    """
    policy_name = parsed_scope.get("iam_policy_name")
    if not policy_name:
        return None

    action_map = {
        "destructive": "iam:DeleteRole",
        "safe":        "iam:AttachRolePolicy",
        "mutating":    "iam:PutRolePolicy",
        "scaling":     "iam:AttachRolePolicy",
    }
    action = action_map.get(action_verb, "iam:AttachRolePolicy")
    return simulate_iam_policy(action, "*", policy_name)
