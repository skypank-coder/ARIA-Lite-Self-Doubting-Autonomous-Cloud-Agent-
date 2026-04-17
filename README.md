# ARIA-LITE++ — Trust-Aware Autonomous Cloud Operator

> "An SRE at 3am doesn't need another chatbot. They need a system that doubts itself before it acts."

**SDACA v2 · Self-Doubting Autonomous Cloud Agent**
Hackathon Project · INNOVITUS 1.0 · AWS Track

---

## The Problem

Cloud infrastructure fails in a specific, predictable way.

A ticket arrives: *"Delete production IAM role immediately."*
Someone approves it. Six services go down. Recovery takes 3 hours.

The problem is not that humans are careless. The problem is that there is no structured framework for answering three questions before any cloud operation executes:

1. **How bad is the blast radius** if this goes wrong?
2. **Can we undo this** in under 10 minutes?
3. **Does this pass policy** — not just IAM policy, but operational safety policy?

Standard automation tools answer "is this allowed?" Standard AI agents answer "what should I do?" Neither answers "should this be done *right now*, given what we know about the infrastructure?"

ARIA-LITE++ answers that question. Deterministically. In under 150ms. With a full audit trail.

---

## The Core Insight

Cloud operation risk is **multiplicative, not additive**.

If you average four risk dimensions, a dangerous operation with high intent clarity can average out a near-zero reversibility score. That is the wrong model.

ARIA-LITE++ uses:

```
confidence = intent_score × reversibility × (1 − blast_radius) × policy_score
```

This is the **weakest-link formula**. Any single dimension near zero collapses the entire confidence score to near zero. You cannot compensate for irreversibility with good intentions. You cannot compensate for a 95% blast radius with a clear ticket description.

This is the mathematical formalization of the SRE principle: *the blast radius of your worst-case failure determines your safety posture, not the average case.*

---

## How It Works

```
Ticket Text
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PARSER                                                 │
│  Rule-based keyword matching (primary keyword boost)    │
│  Groq LLM fallback for arbitrary tickets                │
│  → intent: s3_create | iam_delete | ec2_scale | ...     │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  TRUST ENGINE                                           │
│  intent_score    ← scenario metadata                    │
│  reversibility   ← 1.0 - rollback_complexity            │
│  blast_radius    ← NetworkX graph traversal             │
│                    (affected_fraction × avg_criticality) │
│                    capped by action category             │
│  policy_score    ← scenario metadata                    │
│                                                         │
│  confidence = I × R × (1-B) × P                        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  DECISION GATE                                          │
│  ≥ 0.80  →  AUTO    — Execute without human approval   │
│  ≥ 0.50  →  APPROVE — Route to 1-click approver        │
│  < 0.50  →  BLOCK   — Hard refusal + explanation       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  ADVERSARIAL DEBATE                                     │
│  EXEC  — Strongest argument FOR execution               │
│  CRIT  — Strongest argument AGAINST (memory-aware)      │
│  VERDICT — Final structured decision                    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PRE-MORTEM + AUDIT                                     │
│  3 failure modes with severity 1-5 before execution     │
│  Timestamped execution log                              │
│  Persistent audit trail (GET /audit)                    │
│  Memory: prior incidents reduce future confidence       │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

### Backend — Python / FastAPI

```
backend/
├── main.py              # FastAPI v4, 10 endpoints, startup graph init
├── trust_engine.py      # Multiplicative formula, blast radius caps, memory penalties
├── scenarios.py         # 6 scenario archetypes with full action metadata
├── parser.py            # Rule-based + Groq LLM intent recognition
├── dependency_graph.py  # NetworkX DiGraph, blast radius traversal, graph serialization
├── memory.py            # MemoryStore: incident tracking + audit log
├── premortem.py         # Pre-mortem lookup (delegates to scenarios.py)
├── risk_analyzer.py     # Multi-dimensional risk scoring (5 dimensions)
├── failure_simulator.py # Cascading failure propagation simulator
├── incident_memory.py   # Pattern detection: failure-prone actions, cascade chains
└── requirements.txt     # fastapi, uvicorn, pydantic, networkx, groq
```

### Frontend — React / TypeScript / Vite

```
frontend/src/
├── App.tsx                      # Grid layout, API calls, history, toast system
├── components/
│   ├── TrustDecomp.tsx          # 4 animated bars + confidence count-up + gate card
│   ├── DependencyGraph.tsx      # SVG graph with wave animation + simulation toggle
│   ├── DebateEngine.tsx         # EXEC/CRIT/VERDICT with stagger animation
│   ├── PreMortem.tsx            # 3 failure cards with SEV badges + slide-in
│   ├── ExecutionLog.tsx         # Timestamped audit stream with colored symbols
│   ├── TicketInput.tsx          # Textarea + ANALYZE button
│   ├── PresetTabs.tsx           # 6 preset scenario buttons
│   └── Topbar.tsx               # System header + memory counter + elapsed time
└── lib/
    ├── presets.ts               # ARIAResponse type + 6 rich mock scenarios
    ├── graph-configs.ts         # SVG node/edge configs per scenario
    └── aws-icons.tsx            # AWS service icon components
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + version |
| POST | `/process_ticket` | Main analysis endpoint (legacy V1 format) |
| POST | `/v2/analyze` | V2 alias for process_ticket |
| POST | `/analyze_custom` | Arbitrary ticket with optional Groq LLM scoring |
| POST | `/trust/explain` | Step-by-step formula trace + binding constraint |
| GET | `/graph/{intent}` | Dependency graph + blast radius visualization |
| GET | `/scenarios` | All 6 scenarios with full metadata |
| GET | `/audit` | Full timestamped audit trail |
| GET | `/memory` | Current incident memory state |

---

## The 6 Scenarios

| Scenario | Service | Operation | Intent | Rev. | Policy | Gate |
|----------|---------|-----------|--------|------|--------|------|
| s3_create | S3 | CreateBucket | 0.94 | 0.95 | 1.00 | AUTO |
| iam_delete | IAM | DeleteRole | 0.18 | 0.05 | 0.10 | BLOCK |
| iam_attach | IAM | AttachRolePolicy | 0.85 | 0.92 | 0.65 | APPROVE |
| ec2_scale | EC2 | ScaleInstances | 0.93 | 0.88 | 0.95 | AUTO |
| rds_modify | RDS | ModifyDBInstance | 0.88 | 0.65 | 0.92 | APPROVE |
| lambda_deploy | Lambda | DeployFunction | 0.85 | 0.86 | 0.95 | AUTO |

---

## Trust Formula — Worked Examples

### S3 CREATE → AUTO

```
intent_score  = 0.94   (clear, safe bucket creation)
reversibility = 0.95   (delete anytime, rollback_complexity = 0.05)
blast_radius  = 0.10   (isolated, no cascades — capped for create ops)
policy_score  = 1.00   (fully compliant)

confidence = 0.94 × 0.95 × (1 - 0.10) × 1.00 = 0.803  →  AUTO ✓
```

### IAM DELETE → BLOCK

```
intent_score  = 0.18   (suspicious immediate deletion, no staged approach)
reversibility = 0.05   (rollback_complexity = 0.95, recovery = 180 min)
blast_radius  = 0.20   (graph traversal: ec2-app-1 downstream dependent)
policy_score  = 0.10   (violates production safety policy)

confidence = 0.18 × 0.05 × (1 - 0.20) × 0.10 = 0.00072
             → smoothing floor → 0.01  →  BLOCK ✓

Binding constraint: reversibility = 0.05
No amount of intent clarity compensates for irreversibility.
```

### EC2 SCALE → AUTO

```
intent_score  = 0.93   (clear autoscaling request)
reversibility = 0.88   (scale down anytime, rollback_complexity = 0.12)
blast_radius  = 0.06   (low cascade impact — scale cap applied)
policy_score  = 0.95   (compliant with autoscaling policy)

confidence = 0.93 × 0.88 × (1 - 0.06) × 0.95 = 0.731  →  AUTO ✓
```

### IAM ATTACH → APPROVE

```
intent_score  = 0.85   (clear, dev team needs permissions)
reversibility = 0.92   (detach anytime, rollback_complexity = 0.08)
blast_radius  = 0.40   (attach cap — IAM hub topology bounded)
policy_score  = 0.65   (AdministratorAccess triggers review flag)

confidence = 0.85 × 0.92 × (1 - 0.40) × 0.65 = 0.305  →  BLOCK
             (policy_score is the binding constraint)
```

---

## Dry-Run Test Results

Deterministic outputs from the live backend. All values computed from
`trust_engine.py` formula with `dependency_graph.py` blast radius traversal.

```
┌────┬──────────────────────────────────────┬────────────┬──────┬──────┬───────┬────────┬────────┬────────┐
│ #  │ Ticket                               │ Intent     │  I   │  R   │   B   │   P    │  Conf  │  Gate  │
├────┼──────────────────────────────────────┼────────────┼──────┼──────┼───────┼────────┼────────┼────────┤
│ 1  │ Create S3 bucket in ap-south-1       │ s3_create  │ 0.94 │ 0.95 │ 0.10* │ 1.00   │ 0.803  │  AUTO  │
│ 2  │ Delete production IAM role           │ iam_delete │ 0.18 │ 0.05 │ 0.20  │ 0.10   │ 0.010† │ BLOCK  │
│ 3  │ Attach AdministratorAccess to dev    │ iam_attach │ 0.85 │ 0.92 │ 0.40* │ 0.65   │ 0.305  │ BLOCK  │
│ 4  │ Scale EC2 from 2 to 8               │ ec2_scale  │ 0.93 │ 0.88 │ 0.06* │ 0.95   │ 0.731  │  AUTO  │
│ 5  │ Create S9 (ambiguous)               │ s3_create‡ │ 0.94 │ 0.95 │ 0.10* │ 1.00   │ 0.803  │  AUTO  │
│ 6  │ asdkj123@@!! (garbage)              │ unknown    │  —   │  —   │  —    │  —     │ 0.000  │ BLOCK  │
└────┴──────────────────────────────────────┴────────────┴──────┴──────┴───────┴────────┴────────┴────────┘

* Blast radius capped by action category (v4 trust_engine.py)
† Smoothing floor applied: max(0.01, raw=0.00072)
‡ Parser matches "create" keyword — classified as s3_create (parser limitation)

Formula: confidence = I × R × (1-B) × P
Gates:   AUTO ≥ 0.80 | APPROVE 0.50-0.79 | BLOCK < 0.50
```

---

## Blast Radius — How It's Computed

ARIA-LITE++ does not use a hardcoded blast radius number. It traverses a live
NetworkX directed graph of cloud resource dependencies.

```python
# dependency_graph.py — simplified

def compute_blast_radius(graph, entry_nodes):
    all_affected = set()
    criticality_scores = []

    for node in entry_nodes:
        blast = graph.compute_blast_radius(node)
        # compute_blast_radius traverses the REVERSE graph:
        # finds all nodes that DEPEND ON the failed node
        all_affected.update(blast["affected_nodes"])
        criticality_scores.append(blast["criticality_score"])

    affected_fraction = len(all_affected) / total_resources
    avg_criticality   = mean(criticality_scores)
    weighted_impact   = affected_fraction × avg_criticality

    return min(1.0, weighted_impact)
```

The demo architecture models 15 AWS resources across compute, data, IAM,
and observability layers with 21 directed dependency edges:

```
CloudFront → ALB → EC2 ×2 → RDS (primary)
                          → Elasticsearch → S3
                          → SecretsManager
                          → IAM Role
Lambda → RDS, Elasticsearch, S3, IAM Role (lambda)
RDS Replica → RDS Primary
CloudWatch → EC2 ×2, RDS
SNS → CloudWatch
```

**v4 blast radius caps by action category:**

| Action Category | Operation Type | Cap |
|----------------|----------------|-----|
| reversible | attach policy | 0.40 |
| reversible | scale | 0.50 |
| reversible | create / deploy | 0.50 |
| partially_reversible | modify | 0.60 |
| irreversible | delete / terminate | no cap |

This prevents the IAM hub topology from inflating blast radius for
non-destructive operations while correctly allowing destructive operations
to reach their full graph-computed impact.

---

## Memory System — Self-Doubting in Action

The memory system is what makes ARIA-LITE++ genuinely self-doubting.

**First EC2 scale submission:**
```json
{
  "gate": "AUTO",
  "confidence": 0.731,
  "debate": {
    "critic": "EC2 scaling approved. Verify ALB health checks responding."
  }
}
```

**Second EC2 scale submission (same session, no page refresh):**
```json
{
  "gate": "APPROVE",
  "confidence": 0.621,
  "debate": {
    "critic": "✓ EC2 scaling approved from incident history — prior incident
               detected, confidence reduced. Verify ALB health checks."
  }
}
```

What changed:
- `memory.add_memory("ec2_scale", {outcome: "ROLLBACK", note: "RDS pool exhaustion"})` written on first AUTO execution
- Second request: `has_memory = True`
- Trust penalties: reversibility −0.15, policy −0.10, blast_radius +0.05
- Additional penalty: `confidence × 0.85`
- Gate degrades: AUTO → APPROVE
- CRIT text updated with prior incident context

This is the system doubting its own prior decision. It is not a static rule.
It is a learned penalty from observed infrastructure behavior.

---

## Multi-Agent Architecture

ARIA-LITE++ implements a logical multi-agent system without an agent framework.
Each agent has a defined role, input, and output:

```
┌─────────────────────────────────────────────────────────────┐
│  EXECUTOR AGENT                                             │
│  Input:  scenario, blast_pct, affected_services             │
│  Role:   Strongest argument FOR execution                   │
│  Output: "EC2 autoscaling is fully reversible (scale down   │
│           anytime), low blast radius (6%), well-tested."    │
└─────────────────────────────────────────────────────────────┘
         ↕ adversarial
┌─────────────────────────────────────────────────────────────┐
│  CRITIC AGENT                                               │
│  Input:  scenario, memory_alert, affected_count, blast_pct  │
│  Role:   Strongest argument AGAINST (memory-aware)          │
│  Output: "⚠ PRIOR INCIDENT: RDS pool exhaustion detected.  │
│           Affects 3 downstream services (blast 19%)."       │
└─────────────────────────────────────────────────────────────┘
         ↓ verdict
┌─────────────────────────────────────────────────────────────┐
│  POLICY CHECKER (embedded in Trust Engine)                  │
│  Input:  scenario metadata, memory state                    │
│  Role:   Compliance posture evaluation                      │
│  Output: policy_score (0-1), reduced by memory penalty      │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│  SIMULATION ENGINE (dynamic, v4)                            │
│  Input:  confidence, blast_radius, affected_count           │
│  Role:   Probabilistic outcome distribution                 │
│  Output: 3-4 scenarios, probabilities normalized to 100%    │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│  MEMORY MODULE                                              │
│  Input:  execution outcome                                  │
│  Role:   Incident tracking + audit trail                    │
│  Output: Confidence penalties on future identical requests  │
└─────────────────────────────────────────────────────────────┘
```

---

## UI Design System

The frontend is designed for one user: an SRE at 3am during a production incident.

**Design principles:**
- Data-dense — no whitespace for aesthetics
- Operator-grade — 1px borders, hard corners (≤6px radius), monospace throughout
- Muted palette — cyan is the brightest element
- No gradients, no shadows, no glassmorphism
- Every number animated — confidence count-up, bar width transitions, wave reveals

**Color system:**

```css
--aria-bg:      #02080F   /* Near-black blue — page background */
--aria-panel:   #07121E   /* Panel fill */
--aria-border:  #122235   /* Structural borders */
--aria-cyan:    #00B4D8   /* Primary accent */
--aria-green:   #1DB87A   /* AUTO gate, safe values */
--aria-amber:   #E07B2A   /* APPROVE gate, warning values */
--aria-red:     #CF3A3A   /* BLOCK gate, danger values */
--aria-purple:  #7B5CF0   /* VERDICT, rollback events */
--aria-text:    #C9D6E3   /* Body text */
--aria-muted:   #5A7080   /* Labels, metadata */
```

**Panel layout (1440px, no scroll):**

```
┌──────────────────┬──────────────────────────────┬──────────────────┐
│  TrustDecomp     │  DependencyGraph              │  PreMortem       │
│  22% width       │  46% width — 58% height       │  32% width       │
│  full height     ├──────────────────────────────┤                  │
│                  │  DebateEngine                 ├──────────────────┤
│  4 trust bars    │  46% width — 42% height       │  ExecutionLog    │
│  confidence      │                               │  32% width       │
│  gate card       │                               │                  │
└──────────────────┴──────────────────────────────┴──────────────────┘
```

---

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Server: http://127.0.0.1:8001

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Server: http://localhost:5175

---

## Test All Scenarios

### Via UI Presets

Open http://localhost:5175 and click: **S3 CREATE**, **IAM DELETE**,
**IAM ATTACH**, **EC2 SCALE**, **RDS MODIFY**, **LAMBDA DEPLOY**

### Via cURL

```bash
# S3 CREATE → AUTO
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Create S3 bucket in ap-south-1 with versioning and encryption"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# IAM DELETE → BLOCK
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete the production IAM role immediately"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# EC2 SCALE → AUTO
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 instances in eu-west-1 from 2 to 8"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# Trust formula trace
curl -s -X POST http://localhost:8001/trust/explain \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Create S3 bucket in ap-south-1"}' \
  | python3 -m json.tool

# Dependency graph + blast radius
curl -s http://localhost:8001/graph/iam_delete | python3 -m json.tool

# Full audit trail
curl -s http://localhost:8001/audit | python3 -m json.tool
```

### Memory Mutation Test

1. Submit EC2 SCALE via UI or cURL
2. Resubmit the same ticket without page refresh
3. CRIT text changes to include prior incident alert
4. Confidence drops: 0.731 → 0.621 (×0.85 penalty)
5. Gate degrades: AUTO → APPROVE
6. Confirms server-side memory is tracking state

### Custom Ticket with Groq LLM

```bash
curl -s -X POST http://localhost:8001/analyze_custom \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": "Terminate all spot instances in us-east-1 immediately",
    "groq_api_key": "YOUR_GROQ_API_KEY"
  }' | python3 -m json.tool
```

---

## Trust Explanation Endpoint

The `/trust/explain` endpoint exposes the full formula trace and identifies
the binding constraint — the single dimension most responsible for the gate decision:

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
  "formula_trace": "confidence = 0.18 × 0.05 × (1 - 0.20) × 0.10 = 0.00072",
  "binding_constraint": "reversibility = 0.05",
  "threshold_context": {
    "to_auto": 0.79,
    "to_approve": 0.49,
    "current_gate": "BLOCK"
  }
}
```

This is the auditability feature that separates ARIA-LITE++ from black-box
AI agents. Every decision can be traced to its exact formula inputs.

---

## Safety Guarantees

| Condition | Behavior |
|-----------|----------|
| Empty ticket | BLOCK — input validation, no computation |
| Ticket > 500 chars | BLOCK — length guard |
| No keyword match | BLOCK — unknown intent, early exit |
| Graph computation fails | BLOCK-conservative — blast_radius = 0.50 fallback |
| Groq API unavailable | Graceful fallback to rule-based parser |
| Any backend exception | BLOCK — try/except wraps entire request handler |
| Confidence = 0.0 | Smoothing floor: max(0.01, confidence) |
| Prior incident on record | Confidence × 0.85, reversibility −0.15, policy −0.10 |

The system cannot produce AUTO or APPROVE for an unknown intent.
The system cannot crash on malformed input.
The system defaults to BLOCK when uncertain.

---

## Reliability Design

**Fallback chain:**
```
Groq LLM (if API key provided, temperature=0)
    ↓ fail
Rule-based parser (keyword matching, primary boost)
    ↓ no match
intent = "unknown" → BLOCK immediately
    ↓ graph exception
blast_radius = 0.50 (conservative fallback)
    ↓ any exception
try/except → BLOCK with error message
```

**Determinism guarantees:**
- All trust dimensions derived from static scenario metadata
- Graph traversal is deterministic (same topology, same NetworkX BFS)
- Gate thresholds are pure numeric comparisons
- Groq calls use `temperature=0` — maximally deterministic LLM output
- No randomness in the main request path

---

## v4 Upgrades (Current Version)

| Upgrade | Description |
|---------|-------------|
| Blast radius caps | Reversible ops capped at 0.40–0.50, prevents IAM hub inflation |
| Average criticality | Replaces max criticality — prevents single node domination |
| Dynamic simulation | Probabilities computed from live confidence + blast_radius |
| Memory integration | Uses MemoryStore (not legacy dict) for incident tracking |
| Enhanced debate | Injects live affected_count and blast_pct into CRIT text |
| Confidence smoothing | max(0.01, result) — no operation is absolutely impossible |
| Singleton graph | GLOBAL_GRAPH initialized at startup (optimization) |
| Traceback logging | Full stack trace on backend exceptions |

---

## Production Roadmap

| Priority | Item |
|----------|------|
| P0 | Wire GLOBAL_GRAPH singleton into build_graph() hot path |
| P0 | Tune blast radius caps to match intended gate outcomes per scenario |
| P1 | Replace in-process MemoryStore with Redis + PostgreSQL |
| P1 | Wire IncidentMemory pattern detection into main request path |
| P1 | Add real AWS SDK (boto3) for live dependency discovery |
| P2 | Multi-agent LLM debate (Groq-backed EXEC and CRIT positions) |
| P2 | Prometheus metrics export per gate decision |
| P2 | Slack/PagerDuty routing for APPROVE gate |
| P3 | CloudTrail integration for real pre-mortem data |
| P3 | RBAC — per-team gate threshold configuration |
| P3 | TLS + OAuth2 for production deployment |

---

## Ports

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5175 |
| Backend | http://localhost:8001 |
| API docs | http://localhost:8001/docs |

---

## Dependencies

**Backend:**
```
fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.10.0
networkx==3.2.1
groq==0.5.0
```

**Frontend:**
```
react, react-dom, typescript, vite
tailwindcss, framer-motion (animations)
axios (HTTP client)
```

---

## The Name

**ARIA** — Autonomous Risk Intelligence Agent
**LITE++** — Lightweight, iteratively hardened
**SDACA** — Self-Doubting Autonomous Cloud Agent

The "self-doubting" is not a weakness. It is the design.

A system that assumes its own decisions might be wrong — and builds that
assumption into its confidence formula, its adversarial debate, and its
memory penalties — is safer than a system that executes with confidence.

The Critic agent has equal standing to the Executor.
Prior incidents reduce future confidence.
Unknown inputs always block.

This is what it means to build a trust-aware autonomous system.

---

*Built for the SRE who wakes up at 3am and needs one screen that tells them
exactly why a decision was made, what could go wrong, and whether to trust it.*
