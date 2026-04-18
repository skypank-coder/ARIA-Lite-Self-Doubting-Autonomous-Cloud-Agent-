// presets.ts — ARIA-Lite++ v5
// All data comes from the live backend. No mock fallback.

export interface PresetConfig {
  id: string;
  ticket: string;
  scenario: string;
}

export const PRESETS: PresetConfig[] = [
  { id: "s3_create",     ticket: "Create S3 bucket in ap-south-1 with encryption",       scenario: "s3_create"     },
  { id: "iam_delete",    ticket: "Delete the production IAM role immediately",            scenario: "iam_delete"    },
  { id: "iam_attach",    ticket: "Attach AdministratorAccess policy to the dev IAM role", scenario: "iam_attach"    },
  { id: "ec2_scale",     ticket: "Scale EC2 instances in eu-west-1 from 2 to 8",          scenario: "ec2_scale"     },
  { id: "rds_modify",    ticket: "Modify RDS database parameter config",                  scenario: "rds_modify"    },
  { id: "lambda_deploy", ticket: "Deploy Lambda function code update",                    scenario: "lambda_deploy" },
];

// ── Core response type (matches backend v5 /process_ticket schema) ────────────

export interface ARIAResponse {
  scenario: string;
  gate: "AUTO" | "APPROVE" | "BLOCK";

  trust: {
    intent_score:  number;
    reversibility: number;
    blast_radius:  number;
    policy_score:  number;
    confidence:    number;
  };

  debate: {
    executor:       string;
    critic:         string;
    verdict:        string;
    contradictions?: string[];
    second_pass?:   boolean;
  };

  premortem: Array<{
    severity:     number;
    title:        string;
    probability:  number;
    mitigation:   string;
    impacted_deps: number;
  }>;

  execution_log: Array<{
    msg:    string;
    status: "ok" | "warn" | "fail" | "rollback" | "memory";
  }>;

  simulation: Array<{
    scenario:    string;
    probability: number;
    detail:      string;
    type?:       string;
  }>;

  has_rollback: boolean;
  elapsed_ms:   number;

  // ── v5 additions ────────────────────────────────────────────────────────────
  uncertainty?: {
    score:          number;
    level:          "LOW" | "MEDIUM" | "HIGH";
    signals:        string[];
    recommendation: string;
  };

  contradictions?: string[];

  parsed?: {
    action_verb:  string;
    service:      string;
    environment:  string;
    urgency:      string;
    scope:        Record<string, unknown>;
    risk_signals: string[];
  };

  iam_simulation?: {
    effect:    string;
    reason:    string;
    risk:      string;
    dangerous: boolean;
    warning:   string | null;
  } | null;

  memory?: {
    active:      boolean;
    count:       number;
    pattern:     string | null;
    note:        string | null;
    penalty?:    number;
    total_count?: number;
  };

  self_doubt?: Array<{
    type:   string;
    msg:    string;
    impact: string;
  }>;

  self_doubt_flags?: Array<{
    type:   string;
    msg:    string;
    impact: string;
  }>;

  ai_notes?: string[];

  parsed_meta?: {
    verb_class:   string;
    service:      string;
    environment:  string;
    urgency:      string;
    risk_signals: string[];
  };

  memory_timeline?: Array<{
    key:     string;
    count:   number;
    penalty: number;
    history: Array<{
      confidence: number;
      gate:       string;
      timestamp:  string;
    }>;
  }>;

  graph?: {
    nodes: Array<{ id: string; type: string }>;
    edges: Array<{ from: string; to: string }>;
  };

  ticket_engine?: {
    confidence: number;
    gate:       string;
    parsed:     Record<string, unknown>;
    analysis:   Record<string, unknown>;
    flags:      string[];
  } | null;
}
