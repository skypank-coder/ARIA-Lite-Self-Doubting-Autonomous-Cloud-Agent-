"""
ai_debate.py — ARIA-Lite++
Multi-agent adversarial debate: Executor vs Critic.
Each agent builds arguments from trust signals — no static templates.
Includes reasoning strength scoring and contradiction detection.
"""

import os
from typing import Dict, List, Optional, Tuple


# ── Reasoning strength scores ─────────────────────────────────────────────────

def _compute_scores(trust: Dict) -> Tuple[float, float]:
    rev    = trust.get("reversibility", 0.5)
    conf   = trust.get("confidence", 0.0)
    blast  = trust.get("blast_radius", 0.0)
    policy = trust.get("policy_score", 1.0)

    exec_score   = (rev + conf + (1.0 - blast)) / 3.0
    critic_score = ((1.0 - conf) + blast + (1.0 - policy)) / 3.0

    return round(exec_score, 3), round(critic_score, 3)


# ── Contradiction detection ───────────────────────────────────────────────────

def _detect_contradiction(exec_score: float, critic_score: float) -> Optional[str]:
    if abs(exec_score - critic_score) < 0.10:
        return (
            f"Agent scores are close (exec={exec_score:.2f}, critic={critic_score:.2f}) "
            f"— high uncertainty, outcome is genuinely ambiguous"
        )
    return None


# ── Executor argument builder ─────────────────────────────────────────────────

def _executor_argument(trust: Dict, node_count: int, env: str, scale: float) -> str:
    rev    = trust.get("reversibility", 0.5)
    conf   = trust.get("confidence", 0.0)
    blast  = trust.get("blast_radius", 0.0)
    policy = trust.get("policy_score", 1.0)
    intent = trust.get("intent_score", 0.5)

    parts: List[str] = []

    # Reversibility reasoning
    if rev >= 0.80:
        parts.append(f"high reversibility ({rev:.2f}) enables clean rollback within minutes")
    elif rev >= 0.55:
        parts.append(f"reversibility {rev:.2f} — compensating transaction path is available")
    elif rev >= 0.35:
        parts.append(f"partial reversibility ({rev:.2f}) — recovery requires manual steps but is feasible")
    else:
        parts.append(f"reversibility {rev:.2f} is low, but operation is scoped and operationally necessary")

    # Blast radius reasoning
    if blast < 0.10:
        parts.append(f"blast radius {blast:.2f} is negligible — failure is fully contained")
    elif blast < 0.20:
        parts.append(f"blast radius {blast:.2f} is limited to {node_count} service(s) — impact is bounded")
    elif blast < 0.35:
        parts.append(f"blast radius {blast:.2f} affects {node_count} service(s) but remains within acceptable bounds")

    # Environment reasoning
    if env == "dev":
        parts.append("dev environment isolates blast from production traffic")
    elif env == "staging":
        parts.append("staging environment provides a production-equivalent safety buffer")

    # Scale reasoning
    if scale <= 3:
        parts.append(f"scale factor {scale:.1f}× is incremental — systemic disruption is unlikely")
    elif scale <= 10:
        parts.append(f"scale factor {scale:.1f}× is moderate — pre-warming dependent services mitigates risk")

    # Policy reasoning
    if policy >= 0.80:
        parts.append(f"policy score {policy:.2f} — no compliance violations detected")
    elif policy >= 0.50:
        parts.append(f"policy score {policy:.2f} is acceptable — standard review applies")

    # Confidence reasoning
    if conf >= 0.80:
        parts.append(f"confidence {conf:.2f} clears the AUTO execution threshold")
    elif conf >= 0.60:
        parts.append(f"confidence {conf:.2f} supports execution with human oversight")

    if not parts:
        parts.append(f"intent score {intent:.2f} — operation appears manageable with controlled risk factors")

    return "EXEC: " + ". ".join(parts) + "."


# ── Critic argument builder ───────────────────────────────────────────────────

def _critic_argument(trust: Dict, node_count: int, contradictions: List[str],
                     env: str, verb: str, scale: float) -> str:
    blast  = trust.get("blast_radius", 0.0)
    policy = trust.get("policy_score", 1.0)
    rev    = trust.get("reversibility", 0.5)
    conf   = trust.get("confidence", 0.0)

    parts: List[str] = []

    # Policy risk — highest priority
    if policy < 0.10:
        parts.append(
            f"policy score {policy:.2f} indicates critical privilege level "
            f"— least-privilege principle is violated, blast is unrestricted"
        )
    elif policy < 0.30:
        parts.append(
            f"policy score {policy:.2f} — high-privilege policy introduces hidden escalation paths"
        )
    elif policy < 0.55:
        parts.append(f"policy score {policy:.2f} signals elevated compliance risk")

    # Blast radius risk
    if blast > 0.40:
        parts.append(
            f"blast radius {blast:.2f} propagates nonlinearly across {node_count} service(s) "
            f"— cascade failure probability is high"
        )
    elif blast > 0.25:
        parts.append(
            f"blast radius {blast:.2f} affects {node_count} dependent service(s) "
            f"— cascade failure probability is non-trivial"
        )

    # Reversibility risk
    if rev < 0.20:
        parts.append(
            f"reversibility {rev:.2f} — recovery requires manual intervention; "
            f"any failure may be permanent within the incident window"
        )
    elif rev < 0.40:
        parts.append(f"reversibility {rev:.2f} — recovery path exists but is slow and error-prone")

    # Production + destructive
    if env == "production" and verb == "destructive":
        parts.append(
            "destructive action on live production environment — "
            "blast radius is real, not simulated; rollback window is narrow"
        )
    elif env == "production":
        parts.append("production environment amplifies the impact of any failure")

    # Scale risk
    if scale > 50:
        parts.append(
            f"scale factor {scale:.0f}× introduces infrastructure shock — "
            f"dependent resource pools (RDS, ALB) may be exhausted"
        )
    elif scale > 20:
        parts.append(f"scale factor {scale:.0f}× risks resource contention across {node_count} downstream service(s)")
    elif scale > 10:
        parts.append(f"scale factor {scale:.0f}× may exhaust downstream connection limits")

    # Contradiction signals
    if contradictions:
        label = contradictions[0].split(":")[0]
        parts.append(f"contradiction detected ({label}) — intent signal is ambiguous, increasing error probability")

    # Low confidence
    if conf < 0.20:
        parts.append(f"confidence {conf:.2f} is critically low — outcome prediction is unreliable")
    elif conf < 0.40:
        parts.append(f"confidence {conf:.2f} is below safe execution threshold")

    if not parts:
        parts.append(
            f"no dominant risk factor detected, but hidden dependencies "
            f"across {node_count} service(s) may introduce unforeseen failure modes"
        )

    return "CRITIC: " + ". ".join(parts) + "."


# ── Verdict ───────────────────────────────────────────────────────────────────

def _verdict(conf: float, exec_score: float, critic_score: float) -> str:
    delta = exec_score - critic_score

    if conf < 0.30 or delta < -0.20:
        return "HARD BLOCK — critic dominates; confidence and score delta both below safe floor"
    if conf < 0.70 or abs(delta) < 0.20:
        return "ROUTE TO HUMAN — scores are close or confidence is borderline"
    return "PROCEED — executor dominates; confidence clears AUTO threshold"


# ── Grok xAI call ─────────────────────────────────────────────────────────────

def _call_grok(prompt: str, api_key: str) -> Optional[str]:
    try:
        import requests  # type: ignore
        resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "grok-3-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 200,
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ── Public interface ──────────────────────────────────────────────────────────

def run_ai_debate(
    ticket: str,
    trust: Dict,
    graph: Optional[Dict] = None,
    contradictions: Optional[List[str]] = None,
    env: str = "unknown",
    verb: str = "unknown",
    scale: float = 1.0,
) -> Dict:
    conf       = trust.get("confidence", 0.0)
    blast      = trust.get("blast_radius", 0.0)
    node_count = len((graph or {}).get("nodes", [])) or 1
    contras    = contradictions or []

    exec_score, critic_score = _compute_scores(trust)
    contradiction_note       = _detect_contradiction(exec_score, critic_score)

    api_key = os.getenv("GROK_API_KEY", "")
    executor_text: Optional[str] = None
    critic_text:   Optional[str] = None

    if api_key:
        base = (
            f"Operation: {ticket}\n"
            f"Confidence: {conf:.3f} | Reversibility: {trust.get('reversibility', 0):.3f} | "
            f"Blast radius: {blast:.3f} | Policy score: {trust.get('policy_score', 1):.3f}\n"
            f"Affected services: {node_count} | Environment: {env} | Scale factor: {scale:.1f}\n"
            f"Executor strength: {exec_score:.2f} | Critic strength: {critic_score:.2f}\n"
            "Reason concisely in 1-2 sentences. Do not repeat numbers verbatim."
        )
        executor_text = _call_grok(
            base + "\n\nRole: Executor. Argue why this operation should proceed. "
                   "Focus on recoverability, operational necessity, and mitigations. "
                   "Return ONLY: EXEC: <argument>",
            api_key,
        )
        critic_text = _call_grok(
            base + "\n\nRole: Critic. Argue why this operation is risky. "
                   "Focus on cascade failures, policy violations, and long-term impact. "
                   "Return ONLY: CRITIC: <argument>",
            api_key,
        )

    # Signal-driven fallback — always different per input
    if not executor_text:
        executor_text = _executor_argument(trust, node_count, env, scale)
    if not critic_text:
        critic_text = _critic_argument(trust, node_count, contras, env, verb, scale)

    verdict = _verdict(conf, exec_score, critic_score)

    result = {
        "executor":       executor_text,
        "critic":         critic_text,
        "verdict":        verdict,
        "contradictions": contras,
        "second_pass":    conf > 0.80 and blast > 0.20,
        "scores": {
            "executor_strength": exec_score,
            "critic_strength":   critic_score,
        },
        "source": "grok" if api_key and executor_text.startswith("EXEC:") else "rule_based",
    }

    if contradiction_note:
        result["agent_contradiction"] = contradiction_note

    return result
