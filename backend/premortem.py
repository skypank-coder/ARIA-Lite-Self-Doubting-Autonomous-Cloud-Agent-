"""
Pre-mortem analysis: 3 failure modes per scenario with severity 1-5 and mitigation.
"""

from scenarios import PREMORTEM_ANALYSIS


def get_premortem(scenario_name: str) -> list:
    """
    Fetch pre-mortem for a scenario.

    Returns:
        [
            {
                "failure": str,
                "severity": int (1-5),
                "mitigation": str,
            },
            ...
        ]
    """
    return PREMORTEM_ANALYSIS.get(scenario_name, [])
