"""
ai_debate.py — ARIA-Lite++
Real LLM-based Executor vs Critic debate with rule-based fallback.
"""

from typing import Dict


def run_ai_debate(ticket: str, trust: Dict) -> Dict:
    """
    Runs adversarial executor/critic debate.
    Uses Groq LLM if available, falls back to rule-based generation.
    """
    conf  = trust.get("confidence", 0.0)
    blast = trust.get("blast_radius", 0.0)
    policy = trust.get("policy_score", 1.0)
    rev   = trust.get("reversibility", 0.5)

    try:
        from parser import groq_full_analysis
        # groq_full_analysis requires an api_key — skip LLM if not configured
        import os
        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key:
            result = groq_full_analysis(ticket, api_key)
            if result:
                executor = result.get("executor_argument", "")
                critic   = result.get("critic_argument", "")
                if executor and critic:
                    verdict = (
                        "PROCEED" if conf >= 0.80 else
                        "REVIEW"  if conf >= 0.50 else
                        "BLOCK"
                    )
                    return {
                        "executor":    executor,
                        "critic":      critic,
                        "verdict":     verdict,
                        "contradictions": [],
                        "second_pass": conf > 0.80 and blast > 0.20,
                    }
    except Exception:
        pass

    # Rule-based fallback — always available
    executor = _build_executor(ticket, trust)
    critic   = _build_critic(trust)
    verdict  = (
        "PROCEED" if conf >= 0.80 else
        "REVIEW"  if conf >= 0.50 else
        "BLOCK"
    )

    return {
        "executor":    executor,
        "critic":      critic,
        "verdict":     verdict,
        "contradictions": [],
        "second_pass": conf > 0.80 and blast > 0.20,
    }


def _build_executor(ticket: str, trust: Dict) -> str:
    conf = trust.get("confidence", 0.0)
    rev  = trust.get("reversibility", 0.5)
    return (
        f"Executor: operation is {'reversible' if rev > 0.60 else 'partially reversible'} "
        f"with confidence {conf:.2f}. "
        f"Intent clarity {trust.get('intent_score', 0):.2f} supports execution."
    )


def _build_critic(trust: Dict) -> str:
    blast  = trust.get("blast_radius", 0.0)
    policy = trust.get("policy_score", 1.0)
    rev    = trust.get("reversibility", 0.5)

    parts = []
    if blast > 0.30:
        parts.append(f"blast radius {blast:.2f} indicates downstream cascade risk")
    if policy < 0.50:
        parts.append(f"policy score {policy:.2f} signals compliance concern")
    if rev < 0.30:
        parts.append(f"reversibility {rev:.2f} — recovery will be difficult")

    if not parts:
        parts.append("no critical risk factors detected")

    return "Critic: " + "; ".join(parts) + "."
