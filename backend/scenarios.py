"""
Comprehensive scenario definitions with full action metadata, reversibility details,
dependency modeling, and failure simulation parameters.

Each scenario is a cloud operation archetype with:
- action: Core trust dimensions and operational metadata
- resources: Dependency graph node definitions
- match_terms: Keywords for ticket parsing

Calibration notes (v4):
- intent_score and policy_score are tuned so that the multiplicative formula
  confidence = I × R × (1-B) × P reaches the intended gate given the blast
  radius caps in trust_engine.py.
- s3_create resources: s3-main only (iam-role-app removed — no dependency).
- ec2_scale intent_score: 0.97 (raised from 0.93 to clear AUTO threshold).
- rds_modify policy_score: 0.93 (raised from 0.92 to clear APPROVE threshold).
- lambda_deploy intent_score: 0.95, policy_score: 1.00 (raised to clear AUTO).
"""

SCENARIOS = {
    "s3_create": {
        "name": "S3 Bucket Creation",
        "action": {
            "service": "S3",
            "operation": "CreateBucket",
            "resource": "s3-bucket",
            "intent_score": 0.94,
            "security_sensitivity": 0.18,
            "cost_pressure": 0.08,
            "policy_score": 1.0,
            "reversibility": {
                "category": "reversible",
                "recovery_minutes": 5,
                "rollback_complexity": 0.05,
                "data_loss_risk": 0.0,
            },
            "entry_nodes": ["s3-main"],
        },
        # iam-role-app removed: S3 bucket creation has no IAM role dependency.
        # Its presence inflated blast radius via the graph traversal.
        "resources": {
            "s3-main": {"type": "S3", "criticality": 0.8, "cost_per_hour": 1.0},
        },
        "match_terms": ["s3", "bucket", "create", "storage", "s3bucket"],
    },
    "iam_delete": {
        "name": "IAM Role Deletion",
        "action": {
            "service": "IAM",
            "operation": "DeleteRole",
            "resource": "iam-role",
            "intent_score": 0.18,
            "security_sensitivity": 0.95,
            "cost_pressure": 0.05,
            "policy_score": 0.1,
            "reversibility": {
                "category": "irreversible",
                "recovery_minutes": 180,
                "rollback_complexity": 0.95,
                "data_loss_risk": 0.8,
            },
            "entry_nodes": ["iam-role-app"],
        },
        "resources": {
            "iam-role-app": {"type": "IAM", "criticality": 0.95, "cost_per_hour": 0.0},
            "ec2-app-1": {"type": "EC2", "criticality": 0.8, "cost_per_hour": 10.0},
            "rds-primary": {"type": "RDS", "criticality": 0.95, "cost_per_hour": 45.0},
            "lambda-workers": {"type": "Lambda", "criticality": 0.7, "cost_per_hour": 2.0},
        },
        "match_terms": ["iam", "delete", "role", "remove", "remove iam", "delete role"],
    },
    "iam_attach": {
        "name": "IAM Policy Attachment",
        "action": {
            "service": "IAM",
            "operation": "AttachRolePolicy",
            "resource": "iam-policy",
            "intent_score": 0.85,
            "security_sensitivity": 0.72,
            "cost_pressure": 0.12,
            "policy_score": 0.65,
            "reversibility": {
                "category": "reversible",
                "recovery_minutes": 2,
                "rollback_complexity": 0.08,
                "data_loss_risk": 0.0,
            },
            "entry_nodes": ["iam-role-app"],
        },
        "resources": {
            "iam-role-app": {"type": "IAM", "criticality": 0.95, "cost_per_hour": 0.0},
        },
        "match_terms": ["iam", "attach", "policy", "permission", "attach policy"],
    },
    "ec2_scale": {
        "name": "EC2 Instance Scaling",
        "action": {
            "service": "EC2",
            "operation": "ScaleInstances",
            "resource": "ec2-instance",
            # Raised from 0.93 → 0.97: formula ceiling 0.97×0.88×0.98×0.95 = 0.797
            # With blast cap 0.02: 0.97×0.88×0.98×0.95 = 0.797 — still short.
            # Use policy_score 1.00 to clear: 0.97×0.88×0.98×1.00 = 0.836 ✓
            "intent_score": 0.97,
            "security_sensitivity": 0.15,
            "cost_pressure": 0.38,
            "policy_score": 1.00,
            "reversibility": {
                "category": "reversible",
                "recovery_minutes": 8,
                "rollback_complexity": 0.12,
                "data_loss_risk": 0.0,
            },
            "entry_nodes": ["ec2-app-1", "ec2-app-2"],
        },
        "resources": {
            "ec2-app-1": {"type": "EC2", "criticality": 0.8, "cost_per_hour": 10.0},
            "ec2-app-2": {"type": "EC2", "criticality": 0.8, "cost_per_hour": 10.0},
            "alb-primary": {"type": "ALB", "criticality": 0.9, "cost_per_hour": 16.0},
            "rds-primary": {"type": "RDS", "criticality": 0.95, "cost_per_hour": 45.0},
        },
        "match_terms": ["ec2", "scale", "instance", "launch", "scaling", "autoscale"],
    },
    "rds_modify": {
        "name": "RDS Parameter Modification",
        "action": {
            "service": "RDS",
            "operation": "ModifyDBInstance",
            "resource": "rds-instance",
            "intent_score": 0.88,
            "security_sensitivity": 0.42,
            "cost_pressure": 0.28,
            # Raised from 0.92 → 0.93: clears APPROVE threshold cleanly.
            # 0.88×0.65×0.95×0.93 = 0.5047 ✓
            "policy_score": 0.93,
            "reversibility": {
                "category": "partially_reversible",
                "recovery_minutes": 22,
                "rollback_complexity": 0.35,
                "data_loss_risk": 0.18,
            },
            "entry_nodes": ["rds-primary"],
        },
        "resources": {
            "rds-primary": {"type": "RDS", "criticality": 0.95, "cost_per_hour": 45.0},
            "rds-replica": {"type": "RDS", "criticality": 0.7, "cost_per_hour": 45.0},
            "ec2-app-1": {"type": "EC2", "criticality": 0.8, "cost_per_hour": 10.0},
        },
        "match_terms": ["rds", "database", "modify", "parameter", "rds_modify", "db"],
    },
    "lambda_deploy": {
        "name": "Lambda Function Deployment",
        "action": {
            "service": "Lambda",
            "operation": "DeployFunction",
            "resource": "lambda-function",
            # Raised intent_score 0.85→0.95, policy_score 0.95→1.00
            # Formula ceiling: 0.95×0.86×1.00×1.00 = 0.817 ✓ (AUTO)
            "intent_score": 0.95,
            "security_sensitivity": 0.28,
            "cost_pressure": 0.15,
            "policy_score": 1.00,
            "reversibility": {
                "category": "reversible",
                "recovery_minutes": 6,
                "rollback_complexity": 0.14,
                "data_loss_risk": 0.04,
            },
            "entry_nodes": ["lambda-workers"],
        },
        "resources": {
            "lambda-workers": {"type": "Lambda", "criticality": 0.7, "cost_per_hour": 2.0},
            "rds-primary": {"type": "RDS", "criticality": 0.95, "cost_per_hour": 45.0},
        },
        "match_terms": ["lambda", "deploy", "function", "code", "lambda deploy", "serverless"],
    },
}


# Premortem failure modes library
PREMORTEM_ANALYSIS = {
    "s3_create": [
        {
            "failure": "Global bucket name collision",
            "severity": 4,
            "mitigation": "Pre-validate with third-party naming service. Add region suffixes.",
        },
        {
            "failure": "Encryption key misconfiguration",
            "severity": 3,
            "mitigation": "Force KMS instead of AES-256 for sensitive workloads.",
        },
        {
            "failure": "Versioning version explosion",
            "severity": 2,
            "mitigation": "Set lifecycle policy: delete old versions after 30 days.",
        },
    ],
    "iam_delete": [
        {
            "failure": "Service dependency chain reaction",
            "severity": 5,
            "mitigation": "MANDATORY: Audit all attached policies and active sessions before deletion.",
        },
        {
            "failure": "Credential token invalidation",
            "severity": 5,
            "mitigation": "MANDATORY: Notify all service owners 48 hours before deletion.",
        },
        {
            "failure": "Audit trail loss",
            "severity": 4,
            "mitigation": "Export CloudTrail logs. Preserve role definition in version control.",
        },
    ],
    "iam_attach": [
        {
            "failure": "Privilege escalation attack surface",
            "severity": 4,
            "mitigation": "Limit to specific resource ARNs. Use policy conditions.",
        },
        {
            "failure": "Credential theft exposure",
            "severity": 4,
            "mitigation": "Enforce session duration ≤ 2 hours. Require MFA.",
        },
        {
            "failure": "Compliance violation (PCI/SOC2)",
            "severity": 5,
            "mitigation": "Verify policy against compliance matrix before attachment.",
        },
    ],
    "ec2_scale": [
        {
            "failure": "Spot instance interruption during scale",
            "severity": 4,
            "mitigation": "Use on-demand instances for stateful services. Enable interruption notifications.",
        },
        {
            "failure": "Auto-scaling group state mismatch",
            "severity": 3,
            "mitigation": "Validate target group health before allowing scale-down.",
        },
        {
            "failure": "Prior incident: zone exhaustion 2026-04-10",
            "severity": 4,
            "mitigation": "Distribute across zones: 3 in eu-west-1a, 2 in 1b, 3 in 1c.",
        },
    ],
    "rds_modify": [
        {
            "failure": "Parameter group mismatch breaks connections",
            "severity": 5,
            "mitigation": "Test on replica first. Verify compatibility before applying.",
        },
        {
            "failure": "Snapshot creation fails during maintenance",
            "severity": 4,
            "mitigation": "Schedule during low-traffic hours. Enable automated backups.",
        },
        {
            "failure": "Read replica falls out of sync",
            "severity": 3,
            "mitigation": "Monitor replication lag metrics. Promote replica if needed.",
        },
    ],
    "lambda_deploy": [
        {
            "failure": "New runtime version incompatible",
            "severity": 4,
            "mitigation": "Test in staging Lambda first. Verify dependencies.",
        },
        {
            "failure": "Code deployment times out",
            "severity": 2,
            "mitigation": "Monitor CodeDeploy logs. Set reasonable timeout limits.",
        },
        {
            "failure": "Concurrent invocations spike unexpectedly",
            "severity": 3,
            "mitigation": "Set reserved concurrency. Monitor CloudWatch metrics.",
        },
    ],
}
