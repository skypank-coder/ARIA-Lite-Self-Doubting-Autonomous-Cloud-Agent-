# ARIA-LITE++ — Trust-Aware Autonomous Cloud Operator

> "An SRE at 3am doesn't need another chatbot. They need a system that doubts itself before it acts."

**SDACA v2 · Self-Doubting Autonomous Cloud Agent**
Hackathon Project · INNOVITUS 1.0 · AWS Track · v5.0.0

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

ARIA-LITE++ answers that question. Deterministically. In under 50ms. With a full audit trail.

---

## The Core Insight

Cloud operation risk is **multiplicative, not additive**.

If you average four risk dimensions, a dangerous operation with high intent clarity can average out a near-zero reversibility score. That is the wrong model.

ARIA-LITE++ uses:

```
confidence = intent_score × reversibility × (1 − blast_radius) × policy_score
```

This is the **weakest-link formula**. Any single dimension near zero collapses the entire confidence score to near zero. You cannot compensate for irreversibility with good intentions. You cannot compensate for a 70% blast radius with a clear ticket description.

This is the mathematical formalization of the SRE principle: *the blast radius of your worst-case failure determines your safety posture, not the average case.*

---

## What Makes v5 Different

Previous versions were scenario classifiers with fixed scores. v5 is a **context-sensitive risk engine**.

Every input now produces genuinely different outputs based on:

| Signal | Example impact |
|--------|----------------|
| Action verb (priority over service noun) | "delete bucket" → destructive on S3, not an S3 create |
| Environment | production+destructive → policy_score hard floor 0.05 |
| Scale factor | 2→200 vs 2→3 produce different confidence scores |
| Named IAM policy | ReadOnlyAccess → AUTO; AdministratorAccess → BLOCK |
| Urgency | "immediately" on production → intent −0.12, policy −0.20 |
| Contradictions | URGENCY_PROD_CONFLICT detected and penalised |
| Memory | Prior rollback → cumulative confidence degradation |

---

## How It Works

```
Ticket Text
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  MULTI-SIGNAL PARSER (v5)                               │
│  extract_verb()     → destructive/mutating/scaling/safe │
│  extract_service()  → s3/iam/ec2/rds/lambda/...         │
│  extract_env()      → production/staging/dev/unknown    │
│  extract_urgency()  → high/normal/low                   │
│  extract_scope()    → scale_factor, privilege_level,    │
│                        iam_policy_name, public_access    │
│  extract_risk_signals() → prod_destructive, admin_priv  │
│  detect_contradictions() → URGENCY_PROD_CONFLICT, ...   │
│                                                         │
│  VERB TAKES PRIORITY OVER SERVICE NOUN                  │
│  "delete bucket" = destructive/s3, NOT safe/s3          │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  DYNAMIC TRUST ENGINE (v5)                              │
│  intent_score    ← verb + env + urgency + contradictions│
│  reversibility   ← verb + service + scale_factor        │
│  blast_radius    ← NetworkX graph × verb_multiplier     │
│                    + service_additive + scale_amplifier  │
│  policy_score    ← env + privilege + IAM simulator      │
│                                                         │
│  NO hardcoded per-scenario values                       │
│  NO blast radius caps                                   │
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
│  ADVERSARIAL DEBATE (live data injection)               │
│  EXEC  — Strongest argument FOR execution               │
│  CRIT  — Binding constraint + contradiction flags       │
│  VERDICT — Final structured decision                    │
│  second_pass flag when AUTO + contradictions present    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  UNCERTAINTY MODEL                                      │
│  Separate signal from confidence                        │
│  HIGH uncertainty → "CLARIFY INPUT" recommendation     │
│  Catches: unknown service, unknown verb, contradictions │
│  boundary confidence (within 0.05 of gate threshold)   │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PRE-MORTEM + AUDIT                                     │
│  Context-aware failure modes (not static lookup)        │
│  Timestamped execution log with all 6 parsed signals    │
│  Persistent audit trail (GET /audit)                    │
│  Cumulative memory: PRIOR_INCIDENT → RECURRING_RISK     │
│                     → REPEATED_FAILURE                  │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

### Backend — Python / FastAPI

```
backend/
├── main.py              # FastAPI v5, 9 endpoints, startup graph init
├── parser.py            # Multi-signal parser: verb/service/env/urgency/scope/signals
├── trust_engine.py      # Dynamic trust computation, debate, simulation, uncertainty
├── iam_simulator.py     # Local IAM policy evaluation (no AWS credentials required)
├── memory.py            # Cumulative incident tracking, pattern detection, audit log
├── dependency_graph.py  # NetworkX DiGraph, blast radius traversal, graph serialization
├── scenarios.py         # Pre-mortem library, legacy graph resource definitions
├── premortem.py         # Pre-mortem lookup delegate
├── risk_analyzer.py     # Multi-dimensional risk scoring (5 dimensions)
├── failure_simulator.py # Cascading failure propagation simulator
├── incident_memory.py   # Pattern detection: failure-prone actions, cascade chains
└── requirements.txt     # fastapi, uvicorn, pydantic, networkx, groq
```

### Frontend — React / TypeScript / Vite

```
frontend/src/
├── App.tsx                      # Grid layout, API calls, toast system
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
| POST | `/process_ticket` | Main analysis endpoint (v5 pipeline) |
| POST | `/v2/analyze` | Alias for process_ticket |
| POST | `/analyze_custom` | Arbitrary ticket with optional Groq LLM scoring |
| POST | `/trust/explain` | Step-by-step formula trace + binding constraint |
| GET | `/graph/{intent}` | Dependency graph + blast radius visualization |
| GET | `/scenarios` | All 6 scenarios with full metadata |
| GET | `/audit` | Full timestamped audit trail |
| GET | `/memory` | Current incident memory state + patterns |

---

## Dry-Run Test Results

All values computed live from the v5 engine. Zero hallucinated values.

```
┌────┬──────────────────────────────────────┬──────┬──────┬──────┬──────┬────────┬────────┬──────────┐
│ #  │ Ticket                               │  I   │  R   │  B   │  P   │  Conf  │  Gate  │ Uncert.  │
├────┼──────────────────────────────────────┼──────┼──────┼──────┼──────┼────────┼────────┼──────────┤
│ 1  │ Create S3 bucket in ap-south-1       │ 0.95 │ 0.92 │ 0.01 │ 1.00 │ 0.8653 │  AUTO  │ LOW      │
│ 2  │ Delete production IAM role           │ 0.05 │ 0.03 │ 0.70 │ 0.05 │ 0.0100 │ BLOCK  │ LOW      │
│ 3  │ Attach AdministratorAccess to dev    │ 0.95 │ 0.97 │ 0.03 │ 0.05 │ 0.0448 │ BLOCK  │ LOW      │
│ 4  │ Scale EC2 from 2 to 8               │ 0.95 │ 0.88 │ 0.03 │ 1.00 │ 0.8109 │  AUTO  │ LOW      │
│ 5  │ Create S9 (unknown service)          │ 0.95 │ 0.92 │ 0.00 │ 1.00 │ 0.8740 │  AUTO* │ HIGH     │
│ 6  │ asdkj123@@!! (garbage)              │  —   │  —   │  —   │  —   │ 0.0000 │ BLOCK  │ HIGH     │
└────┴──────────────────────────────────────┴──────┴──────┴──────┴──────┴────────┴────────┴──────────┘

* AUTO gate but HIGH uncertainty — system flags "CLARIFY INPUT"
Formula: confidence = I × R × (1-B) × P
Gates:   AUTO ≥ 0.80 | APPROVE 0.50–0.79 | BLOCK < 0.50
```

---

## Full Stress Test — 12/12 Pass

```
✓ [BLOCK  ] conf=0.0148 | delete old s3 bucket in dev
✓ [BLOCK  ] conf=0.3962 | create s3 bucket with public access
✓ [BLOCK  ] conf=0.2327 | scale ec2 from 2 to 200 in production immediately
✓ [APPROVE] conf=0.5157 | carefully rotate IAM credentials
✓ [AUTO   ] conf=0.8276 | backup RDS database
✓ [BLOCK  ] conf=0.0100 | delete production IAM role immediately
✓ [AUTO   ] conf=0.9123 | deploy lambda function to dev
✓ [AUTO   ] conf=0.8509 | attach ReadOnlyAccess to dev role
✓ [BLOCK  ] conf=0.0410 | attach AdministratorAccess to prod role
✓ [AUTO   ] conf=0.8109 | scale ec2 from 2 to 3
✓ [APPROVE] conf=0.5029 | scale ec2 from 2 to 50 in production
✓ [BLOCK  ] conf=0.3895 | scale ec2 from 2 to 200 in production
```

The same verb+service combination produces meaningfully different outputs:

| Ticket | Confidence | Gate | Why different |
|--------|-----------|------|---------------|
| scale ec2 from 2 to 3 | 0.811 | AUTO | scale_factor=1.5, no amplifiers |
| scale ec2 from 2 to 50 in production | 0.503 | APPROVE | scale_factor=25, prod context |
| scale ec2 from 2 to 200 in production | 0.390 | BLOCK | scale_factor=100, extreme_scale signal |

---

## Trust Formula — Worked Examples

### S3 CREATE → AUTO

```
verb=safe, service=s3, env=unknown, urgency=normal
risk_signals=[], contradictions=[]

intent_score  = 0.950  (safe base, no modifiers)
reversibility = 0.920  (safe base, s3 mod=0.00)
blast_radius  = 0.010  (graph_raw=0.0 × verb_mult=0.03 + s3_safe=0.00)
policy_score  = 1.000  (no risk signals)

confidence = 0.950 × 0.920 × (1 - 0.010) × 1.000 = 0.865  →  AUTO ✓
```

### IAM DELETE PRODUCTION → BLOCK

```
verb=destructive, service=iam, env=production, urgency=normal
risk_signals=[prod_destructive], contradictions=[]

intent_score  = 0.050  (destructive base=0.20, prod+dest −0.15, signal −0.10)
reversibility = 0.030  (destructive base=0.08, iam_dest +0.05, prod+dest −0.10)
blast_radius  = 0.700  (graph×1.00 + iam_dest=0.15 + prod+dest +0.10 + +0.20)
policy_score  = 0.050  (prod+destructive hard floor)

confidence = 0.050 × 0.030 × (1 - 0.700) × 0.050 = 0.0000225
             → smoothing floor → 0.010  →  BLOCK ✓

Binding constraint: reversibility = 0.030
Four dimensions collapse simultaneously. No single fix can rescue this.
```

### ATTACH ADMINISTRATORACCESS → BLOCK (IAM Simulator)

```
verb=safe, service=iam, env=dev, urgency=normal
scope={privilege_level: admin, iam_policy_name: AdministratorAccess}
risk_signals=[admin_privilege]

intent_score  = 0.950  (safe+dev, capped at 0.95)
reversibility = 0.970  (safe base=0.92, iam_safe +0.05)
blast_radius  = 0.028  (graph×0.03 + iam_safe=0.02)
policy_score  = 0.050  (IAM simulator: AdministratorAccess=CRITICAL → 0.10 − 0.10 = 0.05)

confidence = 0.950 × 0.970 × (1 - 0.028) × 0.050 = 0.0448  →  BLOCK ✓

Binding constraint: policy_score = 0.050
The IAM simulator correctly identifies CRITICAL risk regardless of environment.
```

---

## IAM Policy Simulator

ARIA-LITE++ includes a local IAM policy evaluation engine that runs without any AWS credentials. It scores the **risk level of the policy being attached**, not whether the caller can perform the attachment.

```python
# No AWS account required
simulate_iam_policy("iam:AttachRolePolicy", "*", "AdministratorAccess")
# → {effect: ALLOW, risk: CRITICAL, dangerous: True, warning: "..."}

simulate_iam_policy("iam:AttachRolePolicy", "*", "ReadOnlyAccess")
# → {effect: ALLOW, risk: LOW, dangerous: False, warning: None}
```

| Policy | Risk | policy_score | Gate impact |
|--------|------|-------------|-------------|
| AdministratorAccess | CRITICAL | 0.05 | BLOCK |
| IAMFullAccess | CRITICAL | 0.05 | BLOCK |
| RDSFullAccess | HIGH | 0.35 | BLOCK |
| PowerUserAccess | HIGH | 0.35 | BLOCK |
| S3FullAccess | MEDIUM | 0.50 | APPROVE |
| EC2FullAccess | MEDIUM | 0.50 | APPROVE |
| ReadOnlyAccess | LOW | 0.95 | AUTO |
| SecurityAudit | LOW | 0.95 | AUTO |

---

## Contradiction Detection

The system detects conflicting signals in the ticket and penalises confidence:

| Contradiction | Trigger | Penalty |
|---------------|---------|---------|
| URGENCY_PROD_CONFLICT | high urgency + production | intent −0.08, policy −0.20 |
| VERB_QUALIFIER_CONFLICT | "safely" + destructive verb | intent −0.08 |
| SECURITY_POSTURE_CONFLICT | public access + S3 | intent −0.08 |
| SCALE_REASONABLENESS_CONFLICT | scale_factor > 50x | intent −0.08 |
| PRIVILEGE_ENV_CONFLICT | admin policy + production | intent −0.08, policy → 0.15 |
| IRREVERSIBILITY_PROD_CONFLICT | no_rollback + production | intent −0.08 |

---

## Uncertainty Model

Confidence and uncertainty are separate signals. A high-confidence decision on an unknown service should be flagged, not silently auto-executed.

```json
{
  "uncertainty": {
    "score": 0.45,
    "level": "HIGH",
    "signals": [
      "SERVICE_UNRECOGNIZED: cannot model blast radius accurately",
      "ENVIRONMENT_UNKNOWN: production/dev context affects scoring"
    ],
    "recommendation": "CLARIFY INPUT"
  }
}
```

| Level | Score | Recommendation |
|-------|-------|----------------|
| LOW | < 0.20 | PROCEED |
| MEDIUM | 0.20–0.44 | PROCEED WITH NOTED FLAGS |
| HIGH | ≥ 0.45 | CLARIFY INPUT |

---

## Memory System — Self-Doubting in Action

Memory is keyed by `service_verb` (e.g., `ec2_scaling`). Penalties are cumulative.

**First EC2 scale submission:**
```json
{"gate": "AUTO", "confidence": 0.811, "memory": {"active": false}}
```

**Second EC2 scale submission (same session):**
```json
{
  "gate": "APPROVE",
  "confidence": 0.621,
  "memory": {
    "active": true,
    "count": 1,
    "pattern": "PRIOR_INCIDENT",
    "note": "RDS pool exhaustion eu-west-1"
  }
}
```

**Third submission:**
```json
{
  "gate": "APPROVE",
  "confidence": 0.560,
  "memory": {"count": 2, "pattern": "RECURRING_RISK"}
}
```

**Penalty schedule:**

| Incidents | Pattern | Rev penalty | Policy penalty | Blast penalty | Multiplier |
|-----------|---------|-------------|----------------|---------------|------------|
| 1 | PRIOR_INCIDENT | −0.05 | −0.05 | +0.03 | ×0.95 |
| 2 | RECURRING_RISK | −0.10 | −0.10 | +0.06 | ×0.90 |
| 3+ | REPEATED_FAILURE | −0.15 | −0.15 | +0.09 | ×0.85 |

---

## Safety Guarantees

| Condition | Behavior |
|-----------|----------|
| Empty ticket | BLOCK — input validation, no computation |
| Ticket > 500 chars | BLOCK — length guard |
| service==unknown AND verb==unknown | BLOCK — hard early exit |
| Graph computation fails | blast_radius = 0.10 (conservative fallback) |
| Groq API unavailable | Graceful fallback to v5 rule-based parser |
| Any backend exception | BLOCK — try/except wraps entire request handler |
| Confidence = 0.0 | Smoothing floor: max(0.01, confidence) |
| Prior incident on record | Cumulative penalties, gate degradation |
| Unknown service, known verb | Proceed with HIGH uncertainty flag |

The system cannot produce AUTO or APPROVE for completely unrecognized input.
The system cannot crash on malformed input.
The system defaults to BLOCK when uncertain.

---

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Server: http://127.0.0.1:8001 · Docs: http://127.0.0.1:8001/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Server: http://localhost:5174

---

## Test All Scenarios

### Via UI Presets

Open http://localhost:5174 and click: **S3 CREATE**, **IAM DELETE**,
**IAM ATTACH**, **EC2 SCALE**, **RDS MODIFY**, **LAMBDA DEPLOY**

### Via cURL

```bash
# S3 CREATE → AUTO
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Create S3 bucket in ap-south-1"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# IAM DELETE → BLOCK
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete production IAM role immediately"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# SCALE 2→200 PROD → BLOCK (context-sensitive)
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 from 2 to 200 in production immediately"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# SCALE 2→3 → AUTO (same verb+service, different context)
curl -s -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Scale EC2 from 2 to 3"}' \
  | python3 -m json.tool | grep -E '"gate"|"confidence"'

# Trust formula trace
curl -s -X POST http://localhost:8001/trust/explain \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete production IAM role immediately"}' \
  | python3 -m json.tool

# Full audit trail
curl -s http://localhost:8001/audit | python3 -m json.tool
```

### Memory Mutation Test

1. Submit `Scale EC2 from 2 to 3` via UI or cURL
2. Resubmit the same ticket without page refresh
3. CRIT text changes to include prior incident alert
4. Confidence drops: 0.811 → ~0.621 (×0.95 penalty)
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

```bash
curl -s -X POST http://localhost:8001/trust/explain \
  -H "Content-Type: application/json" \
  -d '{"ticket":"Delete production IAM role immediately"}'
```

```json
{
  "ticket": "Delete production IAM role immediately",
  "intent": "iam_delete",
  "parsed": {
    "action_verb": "destructive",
    "service": "iam",
    "environment": "production",
    "urgency": "normal",
    "scope": {},
    "risk_signals": ["prod_destructive"]
  },
  "scores": {
    "intent_score": 0.05,
    "reversibility": 0.03,
    "blast_radius": 0.70,
    "policy_score": 0.05,
    "confidence": 0.01
  },
  "decision": "BLOCK",
  "formula_trace": "confidence = 0.05 × 0.03 × (1 - 0.70) × 0.05 = 0.0000225",
  "binding_constraint": "reversibility = 0.03",
  "contradictions": [],
  "uncertainty": {"score": 0.0, "level": "LOW", "recommendation": "PROCEED"},
  "threshold_context": {
    "to_auto": 0.79,
    "to_approve": 0.49,
    "current_gate": "BLOCK"
  }
}
```

---

## v5 Response Schema

Every `/process_ticket` response includes:

```json
{
  "scenario": "iam_delete",
  "gate": "BLOCK",
  "trust": {
    "intent_score": 0.05,
    "reversibility": 0.03,
    "blast_radius": 0.70,
    "policy_score": 0.05,
    "confidence": 0.01
  },
  "debate": {
    "executor": "Executor proposes IAM destructive — intent clarity 0.05...",
    "critic": "Critic flags reversibility as binding constraint at 0.03...",
    "verdict": "HARD BLOCK — reversibility collapse vetoes execution",
    "contradictions": [],
    "second_pass": false
  },
  "uncertainty": {
    "score": 0.0,
    "level": "LOW",
    "signals": [],
    "recommendation": "PROCEED"
  },
  "contradictions": [],
  "parsed": {
    "action_verb": "destructive",
    "service": "iam",
    "environment": "production",
    "urgency": "normal",
    "scope": {},
    "risk_signals": ["prod_destructive"]
  },
  "iam_simulation": null,
  "memory": {
    "active": false,
    "count": 0,
    "pattern": null,
    "note": null
  }
}
```

---

## Ports

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5174 |
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
tailwindcss, framer-motion
```

---

## The Name

**ARIA** — Autonomous Risk Intelligence Agent
**LITE++** — Lightweight, iteratively hardened
**SDACA** — Self-Doubting Autonomous Cloud Agent

The "self-doubting" is not a weakness. It is the design.

A system that assumes its own decisions might be wrong — and builds that
assumption into its confidence formula, its adversarial debate, its
contradiction detection, its uncertainty model, and its memory penalties —
is safer than a system that executes with confidence.

The Critic agent has equal standing to the Executor.
Prior incidents reduce future confidence.
Contradictions are detected and penalised.
Unknown inputs surface HIGH uncertainty, not silent AUTO.

This is what it means to build a trust-aware autonomous system.

---

*Built for the SRE who wakes up at 3am and needs one screen that tells them
exactly why a decision was made, what could go wrong, and whether to trust it.*
