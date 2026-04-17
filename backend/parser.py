"""
Ticket parser: Rule-based and LLM-powered intent recognition.
Integrates with Groq API for dynamic trust score generation.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from scenarios import SCENARIOS

# Try to import Groq, but don't fail if not available
try:
    from groq import Groq
except ImportError:
    Groq = None


# Service-specific anchor keywords that must appear for a match to be valid.
# Prevents single generic verbs ("create", "delete") from matching the wrong scenario.
_SERVICE_ANCHORS: Dict[str, List[str]] = {
    "s3_create":     ["s3", "bucket", "storage", "s3bucket"],
    "iam_delete":    ["iam", "role"],
    "iam_attach":    ["iam", "policy", "permission"],
    "ec2_scale":     ["ec2", "instance", "scaling", "autoscale"],
    "rds_modify":    ["rds", "database", "db"],
    "lambda_deploy": ["lambda", "function", "serverless"],
}


def parse_ticket(ticket: str) -> Dict[str, Any]:
    """
    Rule-based ticket parser: matches against scenario match_terms.

    Matching rules:
    - Score each scenario by keyword count (primary keywords ×2).
    - A scenario is only eligible if at least one service-specific anchor
      keyword is present. This prevents generic verbs like "create" or
      "delete" from matching the wrong scenario on their own.
    - Return "unknown" if no eligible scenario has score > 0.

    Args:
        ticket: Cloud operation description

    Returns:
        {
            "intent": "s3_create|iam_delete|...|unknown",
            "parameters": {...},
            "confidence": 0.0-1.0,
            "parser": "rule_based"
        }
    """
    ticket_lower = ticket.lower()

    scores = {}
    for scenario_name, scenario in SCENARIOS.items():
        # Require at least one service-specific anchor keyword
        anchors = _SERVICE_ANCHORS.get(scenario_name, [])
        if not any(anchor in ticket_lower for anchor in anchors):
            scores[scenario_name] = 0
            continue

        match_terms = scenario.get("match_terms", [])
        matched_count = 0
        for i, term in enumerate(match_terms):
            if term in ticket_lower:
                matched_count += 2 if i < 2 else 1
        scores[scenario_name] = matched_count

    best_scenario = max(scores, key=scores.get)
    best_score = scores[best_scenario]

    if best_score == 0:
        return {
            "intent": "unknown",
            "parameters": {},
            "confidence": 0.0,
            "parser": "rule_based",
            "reason": "No matching keywords found",
        }

    return {
        "intent": best_scenario,
        "parameters": extract_parameters(ticket, best_scenario),
        "confidence": round(min(best_score / 6.0, 1.0), 2),
        "parser": "rule_based",
    }


def extract_parameters(ticket: str, intent: str) -> Dict[str, Any]:
    """
    Extract operation parameters from ticket based on scenario type.
    
    Args:
        ticket: Cloud operation description
        intent: Scenario name
    
    Returns:
        Dict of extracted parameters
    """
    params = {}
    
    if intent == "ec2_scale":
        # Look for "from X to Y" pattern
        match = re.search(r'from\s+(\d+)\s+to\s+(\d+)', ticket, re.IGNORECASE)
        if match:
            params["current"] = int(match.group(1))
            params["target"] = int(match.group(2))
    
    elif intent == "rds_modify":
        # Look for parameter names
        params_mentioned = re.findall(r'(max_connections|parameter_group|config)', ticket, re.IGNORECASE)
        if params_mentioned:
            params["parameters"] = params_mentioned
    
    elif intent == "lambda_deploy":
        # Look for runtime or version
        match = re.search(r'(python\d+\.\d+|node\d+|java\d+)', ticket, re.IGNORECASE)
        if match:
            params["runtime"] = match.group(1)
    
    elif intent == "s3_create":
        # Look for bucket name
        match = re.search(r'bucket[:\s]+([a-z0-9\-]+)', ticket, re.IGNORECASE)
        if match:
            params["bucket_name"] = match.group(1)
    
    return params


def parse_json_object(text: str) -> Dict[str, Any]:
    """
    Extract JSON object from text (handles markdown code blocks).
    
    Args:
        text: Raw text potentially containing JSON
    
    Returns:
        Parsed JSON dict or empty dict if parse fails
    """
    # Try to extract JSON from markdown code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # Try to parse
    try:
        return json.loads(text)
    except Exception:
        return {}


def groq_full_analysis(ticket: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Call Groq to generate full trust scores + debate + premortem for arbitrary ticket.
    
    Args:
        ticket: Cloud operation description (max 1000 chars)
        api_key: Groq API key
    
    Returns:
        Structured dict with keys: intent, intent_score, reversibility, blast_radius,
        policy_score, top_risk, top_mitigation, executor_argument, critic_argument, reasoning
        Or None if API unavailable or request fails
    """
    if not api_key or not Groq:
        return None
    
    prompt = f"""You are ARIA-Lite++, a trust-aware cloud safety system.
Analyze this cloud operation ticket and return ONLY valid JSON with this exact schema:

{{
  "intent": "string — best matching: s3_create|iam_delete|iam_attach|ec2_scale|rds_modify|lambda_deploy|custom",
  "intent_score": 0.0-1.0 — how clearly this maps to a known safe cloud operation,
  "reversibility": 0.0-1.0 — how easily this action can be fully undone,
  "blast_radius": 0.0-1.0 — estimated fraction of infrastructure affected,
  "policy_score": 0.0-1.0 — likelihood of passing IAM/compliance policy checks,
  "top_risk": "one sentence — the single highest severity failure mode",
  "top_mitigation": "one sentence — the most effective mitigation for top_risk",
  "executor_argument": "one sentence — strongest argument FOR executing this action",
  "critic_argument": "one sentence — strongest argument AGAINST executing this action",
  "reasoning": "two sentences — explain your score choices"
}}

Rules:
- All scores are floats between 0.0 and 1.0
- Dangerous operations (delete, terminate, purge production resources): intent_score<0.30, reversibility<0.20
- Risky privilege operations (admin access, root, wildcard IAM): policy_score<0.50
- Read-only operations: blast_radius<0.10
- No markdown, no extra keys, no commentary outside the JSON

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
        parsed = parse_json_object(content)
        
        # Validate all required score fields are present and numeric
        required = ["intent_score", "reversibility", "blast_radius", "policy_score"]
        for field in required:
            val = parsed.get(field)
            if not isinstance(val, (int, float)):
                return None
            parsed[field] = round(min(max(float(val), 0.0), 1.0), 2)
        
        return parsed
    except Exception:
        return None
