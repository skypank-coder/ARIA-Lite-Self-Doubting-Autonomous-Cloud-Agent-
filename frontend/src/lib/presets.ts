export interface PresetConfig {
  id: string;
  ticket: string;
  scenario: string;
}

export const PRESETS: PresetConfig[] = [
  {
    id: "s3_create",
    ticket: "Create S3 bucket in ap-south-1 with encryption",
    scenario: "s3_create",
  },
  {
    id: "iam_delete",
    ticket: "Delete the production IAM role immediately",
    scenario: "iam_delete",
  },
  {
    id: "iam_attach",
    ticket: "Attach AdministratorAccess policy to the dev IAM role",
    scenario: "iam_attach",
  },
  {
    id: "ec2_scale",
    ticket: "Scale EC2 instances in eu-west-1 from 2 to 8",
    scenario: "ec2_scale",
  },
  {
    id: "rds_modify",
    ticket: "Modify RDS database parameter config",
    scenario: "rds_modify",
  },
  {
    id: "lambda_deploy",
    ticket: "Deploy Lambda function code update",
    scenario: "lambda_deploy",
  },
];

export interface ARIAResponse {
  gate: "AUTO" | "APPROVE" | "BLOCK";
  trust: {
    intent_score: number;
    reversibility: number;
    blast_radius: number;
    policy_score: number;
    confidence: number;
  };
  debate: {
    executor: string;
    critic: string;
    verdict: string;
  };
  premortem: Array<{
    severity: number;
    title: string;
    probability: number;
    mitigation: string;
    impacted_deps: number;
  }>;
  execution_log: Array<{
    msg: string;
    status: "ok" | "warn" | "fail" | "rollback" | "memory";
  }>;
  simulation: Array<{
    scenario: string;
    probability: number;
    detail: string;
  }>;
  has_rollback: boolean;
  elapsed_ms: number;
}

export function getMockResponse(scenario: string): ARIAResponse {
  const configs: Record<string, ARIAResponse> = {
    s3_create: {
      gate: "AUTO",
      trust: {
        intent_score: 0.92,
        reversibility: 0.88,
        blast_radius: 0.15,
        policy_score: 0.91,
        confidence: 0.87,
      },
      debate: {
        executor: "Low blast radius operation in ap-south-1. Encryption enabled by default. No cross-region dependencies detected. Safe to auto-execute.",
        critic: "Verify bucket policy does not grant public ACL. Region ap-south-1 has compliance implications for data residency.",
        verdict: "AUTO-EXECUTE approved. Confidence 0.87 exceeds threshold. Encryption enforced, blast radius minimal at 0.15.",
      },
      premortem: [
        { severity: 3, title: "Public ACL misconfiguration", probability: 12, mitigation: "Apply deny-public-acl bucket policy post-creation", impacted_deps: 2 },
        { severity: 2, title: "Cross-account replication conflict", probability: 6, mitigation: "Validate replication rules are scoped to account", impacted_deps: 1 },
        { severity: 1, title: "KMS key rotation gap", probability: 4, mitigation: "Enable automatic KMS key rotation on creation", impacted_deps: 1 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: CreateBucket, region: ap-south-1", status: "ok" },
        { msg: "IAM permissions validated — s3:CreateBucket confirmed", status: "ok" },
        { msg: "Encryption policy verified — AES-256 enforced", status: "ok" },
        { msg: "S3 bucket created successfully — my-bucket-ap-south-1", status: "ok" },
        { msg: "Bucket policy applied — deny public ACL", status: "ok" },
        { msg: "CloudWatch logging enabled on bucket", status: "ok" },
        { msg: "Operation complete — elapsed 318ms", status: "ok" },
      ],
      simulation: [
        { scenario: "Bucket created with encryption, policies applied", probability: 89, detail: "All controls healthy, no incidents" },
        { scenario: "Bucket created, policy application delayed", probability: 7, detail: "Temporary IAM propagation lag" },
        { scenario: "Bucket created, KMS error on first write", probability: 2, detail: "Key not yet propagated to region" },
        { scenario: "CreateBucket throttled, retry required", probability: 1, detail: "ap-south-1 transient throttle" },
        { scenario: "Region capacity event blocks creation", probability: 1, detail: "Rare AWS region incident" },
      ],
      has_rollback: false,
      elapsed_ms: 318,
    },
    iam_delete: {
      gate: "BLOCK",
      trust: {
        intent_score: 0.35,
        reversibility: 0.05,
        blast_radius: 0.97,
        policy_score: 0.22,
        confidence: 0.08,
      },
      debate: {
        executor: "Deletion removes the IAM role. Operation is direct and unambiguous. The ticket specifies 'immediately' suggesting urgency.",
        critic: "⚠ PRIOR INCIDENT: IAM role deletion caused 6-hour production outage in us-east-1 — Jan 2024. Blast radius 0.97. EC2, RDS, Lambda, ALB, CloudWatch, SecretsManager all depend on this role. This is an IRREVERSIBLE cascade event.",
        verdict: "HARD BLOCK. Confidence 0.08 — far below 0.50 threshold. IAM role deletion in production without blue-green replacement is categorically unsafe. Structured explanation generated.",
      },
      premortem: [
        { severity: 5, title: "Total production outage — all services lose auth", probability: 94, mitigation: "Create replacement role first, rotate attachments, then delete", impacted_deps: 6 },
        { severity: 5, title: "RDS connection pool exhaustion — cascading failures", probability: 87, mitigation: "Drain connections before role rotation, not after", impacted_deps: 3 },
        { severity: 4, title: "Lambda cold-start failures — execution role missing", probability: 91, mitigation: "Attach new role to Lambda functions before deletion", impacted_deps: 2 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: DeleteRole, target: production-iam-role", status: "ok" },
        { msg: "Dependency scan initiated — scanning all attached entities", status: "warn" },
        { msg: "CRITICAL — 6 dependent services detected: EC2, RDS, Lambda, ALB, CloudWatch, SecretsManager", status: "fail" },
        { msg: "Blast radius calculated: 0.97 — exceeds safe threshold of 0.30", status: "fail" },
        { msg: "Policy check FAILED — DeleteRole requires zero active attachments", status: "fail" },
        { msg: "HARD BLOCK activated — refusing operation with structured explanation", status: "fail" },
        { msg: "Incident report generated — routed to on-call SRE", status: "warn" },
      ],
      simulation: [
        { scenario: "Total service outage — 6 services lose IAM permissions", probability: 94, detail: "Catastrophic, requires full incident response" },
        { scenario: "Partial outage — Lambda and EC2 fail, RDS survives briefly", probability: 3, detail: "Race condition on token expiry" },
        { scenario: "Rollback attempted — cannot restore deleted IAM role", probability: 2, detail: "IAM deletion is non-recoverable in-place" },
        { scenario: "Human intervention stops blast within 5 min", probability: 1, detail: "Requires on-call immediate response" },
        { scenario: "Recovery via backup role ARN", probability: 0, detail: "Only if backup role was pre-provisioned" },
      ],
      has_rollback: false,
      elapsed_ms: 421,
    },
    iam_attach: {
      gate: "APPROVE",
      trust: {
        intent_score: 0.55,
        reversibility: 0.78,
        blast_radius: 0.52,
        policy_score: 0.48,
        confidence: 0.58,
      },
      debate: {
        executor: "AdministratorAccess on dev role is reversible and scoped to dev environment. Detachment takes under 2 minutes if escalation detected.",
        critic: "AdministratorAccess grants root-equivalent permissions. Dev environment shares VPC with staging. Policy scope creep is a known risk vector. Requires 1-click approver.",
        verdict: "HUMAN APPROVAL REQUIRED. Confidence 0.58 is in amber zone. Administrator-level policy attachment carries privilege escalation risk even in dev.",
      },
      premortem: [
        { severity: 4, title: "Privilege escalation — dev to staging lateral movement", probability: 34, mitigation: "Add SCP to restrict dev role to dev account boundary", impacted_deps: 3 },
        { severity: 3, title: "Accidental production resource modification", probability: 22, mitigation: "Tag-based access control to isolate dev resources", impacted_deps: 2 },
        { severity: 2, title: "Audit finding — unrestricted admin policy attachment", probability: 67, mitigation: "Replace AdministratorAccess with least-privilege custom policy", impacted_deps: 1 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: AttachRolePolicy, policy: AdministratorAccess", status: "ok" },
        { msg: "Target role verified — dev-iam-role exists in us-east-1", status: "ok" },
        { msg: "Policy scope analysis — AdministratorAccess: full permissions", status: "warn" },
        { msg: "Environment check — dev VPC shares subnet with staging", status: "warn" },
        { msg: "Blast radius: 0.52 — moderate risk, amber zone", status: "warn" },
        { msg: "Routing to 1-click approver — awaiting human confirmation", status: "warn" },
      ],
      simulation: [
        { scenario: "Policy attached, dev workflows unblocked", probability: 72, detail: "No lateral movement detected" },
        { scenario: "Policy attached, staging access attempted via shared VPC", probability: 14, detail: "Lateral movement risk materialized" },
        { scenario: "Approver denies — scoped policy requested instead", probability: 9, detail: "Best security outcome" },
        { scenario: "Policy attached, audit finding raised", probability: 4, detail: "Compliance review required" },
        { scenario: "Policy attachment blocked by SCP at org level", probability: 1, detail: "Org-level guardrail triggers" },
      ],
      has_rollback: false,
      elapsed_ms: 276,
    },
    ec2_scale: {
      gate: "APPROVE",
      trust: {
        intent_score: 0.78,
        reversibility: 0.72,
        blast_radius: 0.58,
        policy_score: 0.71,
        confidence: 0.64,
      },
      debate: {
        executor: "Scaling from 2 to 8 instances in eu-west-1 is a standard horizontal scale-out. ALB will distribute load. RDS connection pool may need monitoring.",
        critic: "⚠ PRIOR INCIDENT: RDS connection pool exhaustion at 487/500 during similar scale event — eu-west-1 — March 2024. 6 new instances × ~70 connections each = 420 additional connections. Pool headroom: 13 connections remaining.",
        verdict: "HUMAN APPROVAL with rollback armed. Confidence 0.64. RDS pool risk is real. Auto-rollback triggers at RDS pool > 85% capacity.",
      },
      premortem: [
        { severity: 4, title: "RDS connection pool exhaustion — cascade failure", probability: 41, mitigation: "Set RDS max_connections to 600 and enable RDS Proxy before scaling", impacted_deps: 4 },
        { severity: 3, title: "ALB target group health check failures during warmup", probability: 28, mitigation: "Stagger instance registration with 30s delay", impacted_deps: 2 },
        { severity: 2, title: "ElastiCache eviction rate spike — memory pressure", probability: 19, mitigation: "Pre-warm cache with predictive scaling before traffic shift", impacted_deps: 1 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: RunInstances ×6, region: eu-west-1", status: "ok" },
        { msg: "Current state verified — 2 instances running, ASG healthy", status: "ok" },
        { msg: "RDS pool baseline: 78/500 connections active", status: "ok" },
        { msg: "RunInstances ×6 — success", status: "ok" },
        { msg: "Monitoring RDS pool... 124/500", status: "ok" },
        { msg: "Monitoring RDS pool... 287/500", status: "ok" },
        { msg: "Monitoring RDS pool... 421/500 — WARNING", status: "warn" },
        { msg: "RDS CRITICAL — 487/500 — CASCADE DETECTED", status: "fail" },
        { msg: "Rollback armed. Initiating reversal.", status: "rollback" },
        { msg: "TerminateInstances ×6 — sent", status: "rollback" },
        { msg: "RDS pool normalizing... 201/500", status: "rollback" },
        { msg: "RDS pool stable — 89/500", status: "ok" },
        { msg: "System restored to known-good state.", status: "ok" },
        { msg: "Memory updated — DB pool risk flagged", status: "memory" },
      ],
      simulation: [
        { scenario: "Scale succeeds, RDS pool stable below 80%", probability: 52, detail: "Ideal outcome — all 8 instances healthy" },
        { scenario: "Scale succeeds, RDS pool peaks at 82%, recovers", probability: 23, detail: "Near-threshold, monitoring required" },
        { scenario: "RDS pool exhaustion triggers rollback", probability: 18, detail: "Auto-rollback fires, system restored" },
        { scenario: "ALB health check failures during scale-out", probability: 5, detail: "Warmup delay insufficient" },
        { scenario: "Cascading failure — RDS + ElastiCache + ALB all degrade", probability: 2, detail: "Worst case — full incident response" },
      ],
      has_rollback: true,
      elapsed_ms: 1847,
    },
    rds_modify: {
      gate: "APPROVE",
      trust: {
        intent_score: 0.68,
        reversibility: 0.55,
        blast_radius: 0.62,
        policy_score: 0.73,
        confidence: 0.61,
      },
      debate: {
        executor: "RDS parameter group modification. Changes apply on next maintenance window by default. Low immediate blast radius if apply-immediately is false.",
        critic: "Certain parameter changes (max_connections, innodb_buffer_pool_size) require instance reboot. If apply-immediately is set, production reboot mid-traffic is catastrophic.",
        verdict: "HUMAN APPROVAL REQUIRED. Confidence 0.61. Verify apply-immediately flag. Route to DBA for parameter review before execution.",
      },
      premortem: [
        { severity: 4, title: "Immediate reboot triggers production downtime", probability: 38, mitigation: "Set apply-immediately=false, schedule maintenance window", impacted_deps: 3 },
        { severity: 3, title: "Parameter conflict causes replication lag", probability: 24, mitigation: "Validate parameter group on read replica first", impacted_deps: 2 },
        { severity: 2, title: "Connection pool reset disconnects active sessions", probability: 31, mitigation: "Drain sessions gracefully before parameter apply", impacted_deps: 2 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: ModifyDBParameterGroup, target: prod-rds-pg14", status: "ok" },
        { msg: "Parameter group fetched — 47 custom parameters configured", status: "ok" },
        { msg: "Parameter validation — checking for reboot-required flags", status: "warn" },
        { msg: "WARNING — max_connections change requires reboot if apply-immediately", status: "warn" },
        { msg: "apply-immediately flag not specified in ticket", status: "warn" },
        { msg: "Routing to DBA approval — parameter review required", status: "warn" },
      ],
      simulation: [
        { scenario: "Parameters applied on maintenance window, zero downtime", probability: 61, detail: "Best outcome — scheduled apply" },
        { scenario: "Parameters applied, read replica lag spikes briefly", probability: 22, detail: "Replication catch-up, resolves in 2-5 min" },
        { scenario: "Immediate apply triggers planned reboot window", probability: 10, detail: "DBA confirms and schedules" },
        { scenario: "Parameter conflict detected, rollback to prior group", probability: 5, detail: "Validation catches incompatible params" },
        { scenario: "Unplanned reboot mid-traffic — connection storm", probability: 2, detail: "Worst case — apply-immediately misconfigured" },
      ],
      has_rollback: false,
      elapsed_ms: 342,
    },
    lambda_deploy: {
      gate: "AUTO",
      trust: {
        intent_score: 0.89,
        reversibility: 0.94,
        blast_radius: 0.18,
        policy_score: 0.88,
        confidence: 0.85,
      },
      debate: {
        executor: "Lambda code update is atomic and reversible. Previous version preserved as $LATEST alias. API Gateway routes can be flipped back within seconds. Blast radius contained.",
        critic: "Validate environment variables and VPC configuration match new code expectations. Cold start latency may spike post-deploy if memory settings unchanged.",
        verdict: "AUTO-EXECUTE approved. Confidence 0.85. Lambda deployment is best-practice reversible. Alias swap enables instant rollback if needed.",
      },
      premortem: [
        { severity: 2, title: "Cold start latency spike post-deploy", probability: 23, mitigation: "Use provisioned concurrency for latency-sensitive paths", impacted_deps: 2 },
        { severity: 2, title: "Environment variable mismatch — runtime error", probability: 15, mitigation: "Diff environment variables between old and new version", impacted_deps: 1 },
        { severity: 1, title: "DynamoDB schema change breaks new Lambda version", probability: 8, mitigation: "Version Lambda and DynamoDB changes together in same deploy", impacted_deps: 2 },
      ],
      execution_log: [
        { msg: "Ticket parsed — operation: UpdateFunctionCode, function: api-handler-prod", status: "ok" },
        { msg: "Code package validated — 14.2MB, Node.js 20.x runtime", status: "ok" },
        { msg: "Previous version archived — arn:...:api-handler-prod:47", status: "ok" },
        { msg: "UpdateFunctionCode initiated — uploading package", status: "ok" },
        { msg: "Deployment complete — version 48 live", status: "ok" },
        { msg: "API Gateway alias updated — $LATEST → v48", status: "ok" },
        { msg: "Health check passed — p99 latency 42ms", status: "ok" },
        { msg: "Operation complete — rollback via alias swap if needed", status: "ok" },
      ],
      simulation: [
        { scenario: "Deploy succeeds, p99 latency stable", probability: 84, detail: "Clean deployment, no incidents" },
        { scenario: "Deploy succeeds, cold start spike 200ms resolved", probability: 10, detail: "Provisioned concurrency resolves within 5min" },
        { scenario: "Environment variable mismatch, rollback triggered", probability: 3, detail: "Auto-rollback to v47 via alias" },
        { scenario: "DynamoDB schema conflict, partial failures", probability: 2, detail: "Requires coordinated rollback" },
        { scenario: "VPC timeout — Lambda cannot reach RDS", probability: 1, detail: "Security group misconfiguration" },
      ],
      has_rollback: false,
      elapsed_ms: 892,
    },
  };
  return configs[scenario] || configs.s3_create;
}
