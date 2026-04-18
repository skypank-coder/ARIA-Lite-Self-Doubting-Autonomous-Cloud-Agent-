"""
simulation_engine.py — ARIA-Lite++
Monte Carlo probabilistic simulation (200 runs).
Outcomes vary per confidence, reversibility, blast_radius, node_count.
"""

import random
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from parser import ParsedIntent

_COLORS = {
    "success":           "#1DB87A",
    "degraded":          "#E07B2A",
    "cascading_failure": "#CF3A3A",
    "rollback":          "#7B5CF0",
}

_RUNS = 200


def run_simulation(parsed: "ParsedIntent", trust: Dict) -> List[Dict]:
    conf  = max(0.0, min(1.0, trust["confidence"]))
    blast = max(0.0, min(1.0, trust["blast_radius"]))
    rev   = max(0.0, min(1.0, trust["reversibility"]))
    count = max(trust.get("affected_count", 1), 1)
    svc   = parsed.service.upper()

    # Cascade threshold scales with blast and node count
    cascade_threshold = blast * min(1.0, count / 6.0)

    outcomes = {"success": 0, "degraded": 0, "cascade": 0, "rollback": 0}

    for _ in range(_RUNS):
        r = random.random()

        if r < conf * rev:
            outcomes["success"] += 1
        elif r < conf * rev + cascade_threshold:
            outcomes["cascade"] += 1
        elif r < 0.6 + blast * 0.2:
            outcomes["degraded"] += 1
        else:
            outcomes["rollback"] += 1

    total = sum(outcomes.values()) or 1

    s = round(outcomes["success"]  / total * 100)
    d = round(outcomes["degraded"] / total * 100)
    c = round(outcomes["cascade"]  / total * 100)
    r = round(outcomes["rollback"] / total * 100)

    # Fix rounding drift
    drift = 100 - (s + d + c + r)
    # Add drift to largest bucket
    buckets = [("success", s), ("degraded", d), ("cascade", c), ("rollback", r)]
    buckets.sort(key=lambda x: x[1], reverse=True)
    name_map = {"success": 0, "degraded": 1, "cascade": 2, "rollback": 3}
    vals = [s, d, c, r]
    vals[name_map[buckets[0][0]]] += drift

    s, d, c, r = vals

    scenarios = [
        {
            "scenario":    "Successful execution",
            "probability": max(s, 0),
            "detail":      f"{svc} state matches intent. conf={conf:.2f} × rev={rev:.2f}.",
            "type":        "success",
            "color":       _COLORS["success"],
            "driver":      f"conf {conf:.2f} × rev {rev:.2f}",
        },
        {
            "scenario":    "Degraded execution",
            "probability": max(d, 0),
            "detail":      f"Partial completion — reversibility {rev:.2f} limits clean recovery.",
            "type":        "degraded",
            "color":       _COLORS["degraded"],
            "driver":      f"rev {rev:.2f}, blast {blast:.2f}",
        },
        {
            "scenario":    "Cascade failure",
            "probability": max(c, 0),
            "detail":      f"Blast {blast:.2f} across {count} service(s) — cascade threshold {cascade_threshold:.2f}.",
            "type":        "cascading_failure",
            "color":       _COLORS["cascading_failure"],
            "driver":      f"blast {blast:.2f} × nodes {count}",
        },
        {
            "scenario":    "Rollback triggered",
            "probability": max(r, 0),
            "detail":      f"Low confidence ({conf:.2f}) elevates rollback probability.",
            "type":        "rollback",
            "color":       _COLORS["rollback"],
            "driver":      f"1 - conf {conf:.2f}",
        },
    ]

    return [s for s in scenarios if s["probability"] > 0]
