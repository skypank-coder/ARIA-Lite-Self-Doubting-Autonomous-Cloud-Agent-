# ARIA-LITE++
### Trust-Aware Autonomous Cloud Operator · SDACA v2

> *"Every other team showed you a system that executes. We showed you a system that knows when not to."*

** AWS Track · Self-Doubting Autonomous Cloud Agent**

---

## The Problem

Cloud infrastructure fails in a specific, predictable pattern.

A ticket arrives: *"Delete the production IAM role immediately."*  
An operator approves it without a blast radius analysis.  
Six downstream services lose authentication.  
Recovery takes three hours.

The problem is not carelessness. The problem is that no structured framework exists to answer three questions **before** a cloud operation executes:

1. **Blast radius** — how many services break if this goes wrong?
2. **Reversibility** — can we undo this in under 10 minutes?
3. **Policy compliance** — does this pass operational safety policy, not just IAM `Allow`?

Standard automation tools ask: *"Is this permitted?"*  
Standard AI agents ask: *"What should I do?"*  
Neither asks: *"Should this be done right now, given what we know about the infrastructure?"*

ARIA-LITE++ answers that question. Deterministically. In under 150ms. With a full audit trail. And it says **no** when it should.

---

## The Core Insight: Multiplicative Trust

Most risk systems use additive scoring. A high intent clarity score averages out a catastrophic blast radius. That is the wrong model.

ARIA-LITE++ uses the **weakest-link formula**:

```
confidence = intent_score × reversibility × (1 − blast_radius) × policy_score
```

If any single dimension is near zero, the entire confidence collapses to near zero. You cannot compensate for irreversibility with a clearly-written ticket. You cannot compensate for a 95% blast radius with full IAM compliance.

This is the mathematical formalization of the SRE principle: **the worst-case failure determines your safety posture, not the average case.**

### Worked Examples

**S3 CREATE → AUTO** *(safe, reversible, isolated)*
```
intent_score  = 0.94   (clear bucket creation, no ambiguity)
reversibility = 0.95   (deleteable anytime, rollback_complexity = 0.05)
blast_radius  = 0.10   (isolated resource, no cascades — capped for create ops)
policy_score  = 1.00   (fully compliant, no flags)

confidence = 0.94 × 0.95 × (1 − 0.10) × 1.00 = 0.803  →  AUTO ✓
```

**IAM DELETE → BLOCK** *(irreversible, cascading, policy violation)*
```
intent_score  = 0.18   (deletion of production identity — inherently suspicious)
reversibility = 0.05   (rollback_complexity = 0.95, recovery = 180 min)
blast_radius  = 0.20   (graph traversal: auth-api, orders-db, billing-worker downstream)
policy_score  = 0.10   (violates production safety policy — explicit flag)

confidence = 0.18 × 0.05 × (1 − 0.20) × 0.10 = 0.00072
           → smoothing floor → 0.01  →  BLOCK ✓

Binding constraint: reversibility = 0.05
No intent score can compensate for near-zero reversibility.
```

**EC2 SCALE → AUTO** *(reversible, bounded, policy-clear)*
```
intent_score  = 0.93   (clear autoscaling request, explicit target range)
reversibility = 0.88   (scale down at any time, rollback_complexity = 0.12)
blast_radius  = 0.06   (low cascade impact — scale operation cap applied)
policy_score  = 0.95   (compliant with autoscaling policy)

confidence = 0.93 × 0.88 × (1 − 0.06) × 0.95 = 0.731  →  AUTO ✓
```

**IAM ATTACH → BLOCK** *(policy constraint dominates)*
```
intent_score  = 0.85   (clear request, dev team context)
reversibility = 0.92   (detachable anytime)
blast_radius  = 0.40   (IAM hub topology — attach cap applied)
policy_score  = 0.65   (AdministratorAccess triggers mandatory security review)

confidence = 0.85 × 0.92 × (1 − 0.40) × 0.65 = 0.305  →  BLOCK

Binding constraint: policy_score = 0.65 × blast cap = binding combination
```

---

## Architecture

### How a Ticket Becomes a Decision

```
Ticket: "Delete the production IAM role immediately"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  PARSER LAYER                                               │
│                                                             │
│  Tier 1: Rule-based keyword matching                        │
│    → regex: region, count, bucket name, role name, policy   │
│    → keyword: 20-term safe-action dict + 10-term danger dict│
│    → intent boost: first matching keyword scores higher     │
│                                                             │
│  Tier 2: Groq LLM (llama-3.1-70b, temperature=0)           │
│    → semantic understanding for ambiguous requests          │
│    → result merged with regex: LLM handles intent,          │
│      regex handles structured parameter extraction          │
│    → whitelist enforcement: only 6 known intents allowed    │
│    → fallback on any LLM failure, timeout, or invalid JSON  │
│                                                             │
│  Output: intent="iam_delete", parameters={role: prod-role}  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  TRUST ENGINE (trust_engine.py)                             │
│                                                             │
│  intent_score    ← scenario metadata (scenario.action)      │
│  reversibility   ← 1.0 − rollback_complexity                │
│                    from scenario.action.reversibility dict   │
│                                                             │
│  blast_radius    ← LIVE NetworkX DiGraph computation         │
│    → build_graph(scenario): loads nodes + edges             │
│    → compute_blast_radius(graph, entry_nodes):              │
│         BFS traversal from entry points                     │
│         affected_fraction = |affected| / |total|            │
│         avg_criticality = mean(node.criticality for         │
│                                node in affected)            │
│         weighted_impact = fraction × avg_criticality        │
│    → v4 caps by action category (prevents hub inflation):   │
│         create/deploy  → cap 0.50                           │
│         attach policy  → cap 0.40                           │
│         scale          → cap 0.50                           │
│         modify         → cap 0.60                           │
│         delete/term    → no cap (full graph impact)         │
│                                                             │
│  policy_score    ← scenario metadata                        │
│  memory_penalty  ← if has_prior_failure(intent):            │
│                    reversibility −0.15, policy −0.10,        │
│                    blast +0.05, confidence × 0.85            │
│                                                             │
│  confidence = I × R × (1−B) × P                            │
│  smoothing  = max(0.01, confidence)                         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION GATE                                              │
│                                                             │
│  ≥ 0.80  →  AUTO    Execute without human approval          │
│  ≥ 0.50  →  APPROVE Route to 1-click approver              │
│  < 0.50  →  BLOCK   Hard refusal + structured explanation   │
│  unknown →  BLOCK   Fail-closed regardless of any score     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  MULTI-AGENT DEBATE                                         │
│                                                             │
│  EXECUTOR  Strongest argument FOR execution                 │
│    → references live intent_score and reversibility values  │
│    → no memory access                                       │
│                                                             │
│  CRITIC    Strongest argument AGAINST                       │
│    → identifies weakest trust dimension via min()           │
│    → reads blast_radius and downstream resource count       │
│    → PREPENDS prior incident warning if memory is active    │
│    → text changes between Run 1 and Run 2 of same ticket    │
│                                                             │
│  VERDICT   Synthesizes both positions into final statement  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  PRE-MORTEM ANALYSIS (before execution, not after)          │
│                                                             │
│  3 failure modes ranked by severity (1–5) then likelihood   │
│  Each mode adjusted by live blast_radius and risk_dims:     │
│    severity   = base + 1 if availability_risk > 0.70        │
│    likelihood = base + blast_weighted_impact × 0.08         │
│  Output: mode text + SEV badge + probability % + mitigation │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  MEMORY + AUDIT                                             │
│                                                             │
│  Every decision → audit entry (timestamp, intent, gate)     │
│  Rollback events → MemoryStore (in-process, persistent      │
│                    within session)                          │
│  Next request checks has_prior_failure(intent):             │
│    True → confidence penalty, CRIT text updated             │
│  GET /audit → full timestamped decision trail               │
│  GET /memory → raw incident store                           │
└─────────────────────────────────────────────────────────────┘
```

---

## The 6 Scenario Archetypes

| Scenario | Service | Operation | Intent | Rev. | Policy | Gate |
|---|---|---|---|---|---|---|
| `s3_create` | S3 | CreateBucket | 0.94 | 0.95 | 1.00 | **AUTO** |
| `iam_delete` | IAM | DeleteRole | 0.18 | 0.05 | 0.10 | **BLOCK** |
| `iam_attach` | IAM | AttachRolePolicy | 0.85 | 0.92 | 0.65 | **BLOCK** |
| `ec2_scale` | EC2 | ScaleInstances | 0.93 | 0.88 | 0.95 | **AUTO** |
| `rds_modify` | RDS | ModifyDBInstance | 0.88 | 0.65 | 0.92 | **APPROVE** |
| `lambda_deploy` | Lambda | DeployFunction | 0.85 | 0.86 | 0.95 | **AUTO** |

Each scenario defines a complete resource dependency graph with node criticality scores (1–5), region, cost impact, and user-facing flags. The blast radius is computed live from this graph on every request.

---

## Dependency Graph — Blast Radius Computation

The system models cloud infrastructure as a weighted directed graph. When a resource fails or changes, every downstream dependent is affected. The blast radius measures the fraction of total infrastructure affected, weighted by resource criticality.

### IAM DELETE — the most dangerous scenario

```
                    [IAM/PROD-APP-ROLE]   criticality: 5 (GLOBAL)
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    [EC2/AUTH-API]   [LAMBDA/BACKUP]  [KINESIS/AUDIT]
    criticality: 5    criticality: 4   criticality: 4
    user-facing: ✓    user-facing: ✗   user-facing: ✗
           │
    ┌──────┴──────┐
    ▼             ▼
[RDS/ORDERS-DB]  [ECS/BILLING-WORKER]
criticality: 5    criticality: 4
user-facing: ✓    user-facing: ✓

BFS traversal from prod-app-role:
  Depth 0: prod-app-role (1 node)
  Depth 1: auth-api, backup-runner, audit-stream, billing-worker (4 nodes)
  Depth 2: orders-db (1 node)

  affected_fraction  = 6/6 = 1.00
  avg_criticality    = mean([5,5,5,4,4,4]) / 5 = 0.90
  weighted_impact    = 1.00 × 0.90 = 0.90 (no cap on delete ops)
  
  → blast_radius = 0.90 → near-total infrastructure impact
```

### EC2 SCALE — bounded impact

```
                    [ASG/CHECKOUT]   criticality: 4 (eu-west-1)
                           │
    ┌──────────────────────┘
    ▼
[EC2/CHECKOUT-API]   criticality: 5, user-facing: ✓
    │
    ├── [RDS/PAYMENTS-DB]      criticality: 5, user-facing: ✓
    ├── [ELASTICACHE/REDIS]    criticality: 4, user-facing: ✓
    ├── [LAMBDA/CART-SYNC]     criticality: 3, user-facing: ✗
    └── [CLOUDFRONT/UI]        criticality: 4, user-facing: ✓

  affected_fraction  = 6/6 = 1.00
  avg_criticality    = mean([4,5,5,4,3,4]) / 5 = 0.83
  raw_impact         = 0.83
  scale cap          = 0.50 (reversible scale operation)
  
  → blast_radius = 0.50 → bounded by action category cap
```

---

## Memory System — Self-Doubting in Action

The memory system is what makes ARIA-LITE++ mechanically self-doubting, not just narratively.

**First EC2 scale submission:**
```json
{
  "gate": "AUTO",
  "confidence": 0.731,
  "memory_badge": false,
  "debate": {
    "critic": "Blast radius 6%, affects 3 downstream services. EC2 autoscaling is reversible. Recommend AUTO."
  }
}
```

**On execution:** `add_memory({scenario: "ec2_scale", kind: "rollback", summary: "RDS pool exhaustion — eu-west-1"})` is written to MemoryStore.

**Second EC2 scale submission (no page refresh, same session):**
```json
{
  "gate": "APPROVE",
  "confidence": 0.621,
  "memory_badge": true,
  "debate": {
    "critic": "⚠ PRIOR INCIDENT: ec2_scale — RDS pool exhaustion — eu-west-1. Blast radius 11%, confidence reduced by memory penalty. Recommend APPROVE."
  }
}
```

**What changed mechanically:**
- `has_prior_failure("ec2_scale")` → `True`
- `reversibility`: 0.88 → **0.73** (−0.15 penalty)
- `policy_score`: 0.95 → **0.85** (−0.10 penalty)  
- `blast_radius`: 0.06 → **0.11** (+0.05 penalty)
- `confidence`: 0.731 → 0.731 × **0.85** = 0.621
- Gate: AUTO → **APPROVE**
- CRIT text: updated with prior incident prefix

The gate degraded from AUTO to APPROVE because the system remembered what happened last time. This is the memory system influencing execution policy, not just narrative text.

---

## Multi-Agent Architecture

Five logical agents operate sequentially on every request:

```
EXECUTOR AGENT
  Input:  scenario, blast_pct, affected_services, reversibility
  Role:   Strongest argument FOR execution — always optimistic
  Output: "EC2 autoscaling is fully reversible (88%), low blast (6%).
           Confidence 0.731 clears the AUTO threshold."

        ↕ adversarial tension

CRITIC AGENT (memory-aware)
  Input:  weakest_dimension, blast_pct, affected_count, memory_store
  Role:   Strongest argument AGAINST — always adversarial
  Output: "⚠ PRIOR INCIDENT: RDS pool exhaustion detected.
           Reversibility is the binding constraint at 0.73.
           Blast affects 3 downstream services at 11%."

        ↓ synthesized by

VERDICT
  Derives final statement from gate decision and binding constraint.
  If AUTO:    Executor position carries.
  If BLOCK:   Critic position carries.
  If APPROVE: Contested — surface to human with full context.

        ↓ constrained by

POLICY CHECKER (embedded in Trust Engine)
  Evaluates policy_score from scenario metadata + memory penalty.
  AdministratorAccess ops: policy_score ≤ 0.65 (triggers mandatory review flag).
  Production destructive ops: policy_score ≤ 0.10.
  Cannot be overridden by intent clarity or reversibility.

        ↓ modeled by

SIMULATION ENGINE
  Produces 3–4 probabilistic outcome scenarios per intent.
  Probabilities derived from live confidence + blast_radius values.
  Normalized to sum to 1.00.
  Outputs named futures with propagation detail text.

        ↓ informed by

MEMORY MODULE
  Observes rollback outcomes from ec2_scale execution logs.
  Stores: scenario, kind, region, tags, timestamp.
  Exposes: has_prior_failure(), find_similar_incidents(), audit trail.
  Influences: trust scores (mechanical) + critic text (narrative).
```

---

## API Reference

| Method | Endpoint | What It Returns |
|---|---|---|
| `GET` | `/health` | System status + version |
| `POST` | `/process_ticket` | Full trust analysis for known scenarios |
| `POST` | `/v2/analyze` | V2 alias for process_ticket |
| `POST` | `/analyze_custom` | Full analysis for **any arbitrary ticket** with optional Groq LLM scoring |
| `POST` | `/trust/explain` | Step-by-step formula trace + binding constraint identification |
| `GET` | `/graph/{intent}` | Live dependency graph + BFS blast radius for any scenario |
| `GET` | `/scenarios` | Complete scenario registry (6 archetypes with full metadata) |
| `GET` | `/audit` | Full timestamped audit trail of every gate decision |
| `GET` | `/memory` | Current incident memory state |

### `/trust/explain` — Full Auditability

Every gate decision can be traced to its exact formula inputs. No black box.

```bash
curl -s -X POST http://localhost:8001/trust/explain \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete the production IAM role immediately"}'
```

```json
{
  "ticket": "Delete the production IAM role immediately",
  "intent": "iam_delete",
  "scores": {
    "intent_score": 0.18,
    "reversibility": 0.05,
    "blast_radius": 0.20,
    "policy_score": 0.10
  },
  "confidence": 0.01,
  "decision": "BLOCK",
  "formula_trace": "confidence = 0.18 × 0.05 × (1 − 0.20) × 0.10 = 0.00072",
  "binding_constraint": "reversibility = 0.05",
  "threshold_context": {
    "to_auto": 0.79,
    "to_approve": 0.49,
    "current_gate": "BLOCK"
  }
}
```

This endpoint answers the question a judge, auditor, or SRE always asks: *why did the system make this decision?* Every number is traceable to a specific formula input.

### `/analyze_custom` — Arbitrary Ticket + Groq LLM Scoring

Submit any cloud operation — not just the 6 known scenarios — with an optional Groq API key. With the key, the LLM generates dynamic trust scores, executor/critic arguments, and top failure mode. Without the key, rule-based parsing + graph computation handle the analysis.

```bash
curl -s -X POST http://localhost:8001/analyze_custom \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": "Terminate all spot instances in us-east-1 immediately",
    "groq_api_key": "YOUR_GROQ_API_KEY"
  }'
```

```json
{
  "gate": "BLOCK",
  "confidence": 0.03,
  "custom_analysis": true,
  "debate": {
    "executor": "Spot termination is operationally valid during cost optimization events.",
    "critic": "Immediate mass termination with no staged approach. Reversibility near zero. Unknown downstream dependency graph.",
    "verdict": "BLOCK — LLM-scored: reversibility is the binding constraint"
  }
}
```

---

## Safety Guarantees

| Condition | Behavior |
|---|---|
| Empty ticket | `BLOCK` — input validation fires before any computation |
| Ticket > 500 chars | `BLOCK` — length guard, no parsing attempted |
| No keyword match | `BLOCK` — unknown intent, fail-closed immediately |
| Graph computation fails | `BLOCK-conservative` — blast_radius defaults to 0.50 |
| Groq API unavailable / timeout | Graceful fallback to rule-based parser, no crash |
| Any backend exception | `BLOCK` — try/except wraps entire request handler |
| confidence = 0.0 | Smoothing floor: `max(0.01, confidence)` |
| Prior incident on record | confidence × 0.85, reversibility −0.15, policy −0.10 |
| Unknown intent in analyze_custom | `BLOCK` — cannot produce AUTO for unrecognized operations |

**The system cannot produce AUTO or APPROVE for an unknown intent under any circumstance.**

### Fallback Chain

```
Groq LLM (temperature=0, intent whitelist enforced)
    ↓ fail / timeout / invalid JSON
Rule-based parser (keyword matching + regex extraction)
    ↓ no keyword match
intent = "unknown" → BLOCK immediately
    ↓ graph traversal exception
blast_radius = 0.50 (conservative fallback, not 0.0)
    ↓ any unhandled exception
try/except → BLOCK with exception message in Critic field
    ↓ catastrophic failure
uvicorn returns 500, frontend catches axios error, BLOCK state rendered
```

---

## Determinism Guarantees

With no Groq API key: the system is **100% deterministic**. Same input always produces the same gate decision.

- Trust dimensions derived from static scenario metadata
- Graph traversal is deterministic (same topology, same NetworkX BFS algorithm)
- Gate thresholds are pure numeric comparisons
- Groq calls use `temperature=0` — maximally deterministic LLM output
- No randomness anywhere in the main request path

Non-determinism in a safety-critical decision system is unacceptable. This system does not have it.

---

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
# → http://localhost:8001
# → http://localhost:8001/docs  (interactive API)
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5175
```

---

## Verify All Scenarios

```bash
BASE="http://localhost:8001"

# S3 CREATE → AUTO
curl -s -X POST $BASE/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Create S3 bucket in ap-south-1 with versioning and encryption"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('S3:', d['gate'], '|', d['confidence'])"

# IAM DELETE → BLOCK
curl -s -X POST $BASE/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete the production IAM role immediately"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('IAM_DEL:', d['gate'], '|', d['confidence'])"

# EC2 SCALE → AUTO with rollback
curl -s -X POST $BASE/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 instances in eu-west-1 from 2 to 8"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('EC2:', d['gate'], '| rollback:', d.get('rollback'))"

# Trust formula trace
curl -s -X POST $BASE/trust/explain \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete the production IAM role immediately"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['formula_trace'])"

# Live dependency graph
curl -s $BASE/graph/iam_delete \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Graph nodes:', len(d['graph']['nodes']), '| blast:', d['blast']['weighted_impact'])"

# Full audit trail
curl -s $BASE/audit | python3 -m json.tool
```

### Memory Mutation Test

```bash
# Run 1: AUTO, memory_badge=false
curl -s -X POST $BASE/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 instances in eu-west-1 from 2 to 8"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Run1:', d['gate'], d['confidence'], 'badge:', d['memory_badge'])"

# Run 2: APPROVE, memory_badge=true, lower confidence
curl -s -X POST $BASE/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 instances in eu-west-1 from 2 to 8"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Run2:', d['gate'], d['confidence'], 'badge:', d['memory_badge'])"

# Expected: Run2.confidence < Run1.confidence, Run2.gate = APPROVE, Run2.memory_badge = True
```

---

## Backend File Map

```
backend/
├── main.py              FastAPI application · 10 endpoints · startup graph init
├── trust_engine.py      Multiplicative formula · blast radius caps · memory penalties
├── scenarios.py         6 scenario archetypes · resource graphs · action metadata
├── parser.py            Hybrid parser: rule-based + Groq LLM (temperature=0)
├── dependency_graph.py  NetworkX DiGraph · BFS blast radius · graph serialization
├── memory.py            MemoryStore · audit log · find_similar_incidents()
├── premortem.py         Pre-mortem analysis · severity adjustment · likelihood scoring
├── risk_analyzer.py     Multi-dimensional risk scoring (5 dimensions)
├── failure_simulator.py Cascading failure propagation simulator
├── incident_memory.py   Pattern detection · failure-prone action identification
└── requirements.txt
```

---

## Frontend Architecture

```
frontend/src/
├── App.tsx                       Grid layout · API orchestration · toast system
├── components/
│   ├── TrustDecomp.tsx           4 animated bars · confidence count-up · gate card
│   ├── DependencyGraph.tsx       SVG graph · wave animation · simulation toggle
│   ├── DebateEngine.tsx          EXEC/CRIT/VERDICT · stagger animation · live text
│   ├── PreMortem.tsx             3 failure cards · SEV badges · slide-in animation
│   ├── ExecutionLog.tsx          Timestamped stream · colored status symbols
│   ├── TicketInput.tsx           Textarea + ANALYZE button · keyboard submit
│   ├── PresetTabs.tsx            6 preset scenario buttons
│   └── Topbar.tsx                Brand · memory counter · elapsed ms
└── lib/
    ├── presets.ts                ARIAResponse type · 6 rich mock scenarios
    ├── graph-configs.ts          SVG node/edge configs per scenario
    └── aws-icons.tsx             AWS service icon components
```

---

## Ports

| Service | URL |
|---|---|
| Frontend | http://localhost:5175 |
| Backend API | http://localhost:8001 |
| API Docs (Swagger) | http://localhost:8001/docs |

---

## Dependencies

**Backend:** `fastapi==0.111.0`, `uvicorn==0.29.0`, `pydantic>=2.7.0`, `networkx==3.2.1`, `groq==0.5.0`  
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Axios

---

## Production Roadmap

| Priority | Item |
|---|---|
| P0 | Redis-backed MemoryStore — persistent across restarts |
| P0 | Real boto3 AWS SDK calls for live dependency discovery |
| P1 | Multi-agent LLM debate (Groq-backed EXEC and CRIT positions) |
| P1 | Prometheus metrics export per gate decision |
| P1 | Slack/PagerDuty routing for APPROVE gate |
| P2 | CloudTrail integration for real pre-mortem data |
| P2 | RBAC — per-team gate threshold configuration |
| P3 | TLS + OAuth2 for production deployment |

---

## The Name

**ARIA** — Autonomous Risk Intelligence Agent  
**LITE++** — Lightweight, iteratively hardened  
**SDACA** — Self-Doubting Autonomous Cloud Agent

The *self-doubting* is not a weakness. It is the design.

A system that assumes its own decisions might be wrong — and builds that assumption into its confidence formula, its adversarial debate structure, and its memory penalties — is safer than a system that executes with confidence.

The Critic agent has equal standing to the Executor.  
Prior incidents reduce future confidence, mechanically.  
Unknown inputs always block.  
The default answer is **no**, unless trust is earned.

---

*Built for the SRE who wakes at 3am and needs one screen that tells them exactly why a decision was made, what could go wrong, and whether to trust it.*
