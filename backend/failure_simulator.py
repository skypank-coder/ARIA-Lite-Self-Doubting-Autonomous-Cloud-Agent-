"""
Failure Propagation Simulator: Models cascading failures across cloud infrastructure.
Generates best-case, degraded, and worst-case scenarios.
"""

import random
from typing import Dict, List, Tuple
from dataclasses import dataclass
from dependency_graph import DependencyGraphEngine

@dataclass
class FailureScenario:
    """Represents a failure propagation scenario."""
    name: str
    probability: float
    affected_services: List[str]
    recovery_time_minutes: int
    revenue_impact_usd: float
    severity: str  # "critical", "high", "medium", "low"
    description: str


class FailureSimulator:
    """Simulates cascading failures and generates scenarios."""
    
    def __init__(self, graph_engine: DependencyGraphEngine):
        self.engine = graph_engine
    
    def generate_scenarios(self, failed_resource: str, action_type: str) -> List[FailureScenario]:
        """
        Generate best-case, degraded, and worst-case failure scenarios.
        
        action_type: "create", "delete", "modify", "scale", "update"
        """
        blast_radius = self.engine.compute_blast_radius(failed_resource)
        affected_nodes = blast_radius["affected_nodes"]
        
        scenarios = []
        
        # Best case: Quick failover, no user impact
        scenarios.append(FailureScenario(
            name="Best Case: Graceful Failover",
            probability=0.15,
            affected_services=[],
            recovery_time_minutes=0,
            revenue_impact_usd=0,
            severity="low",
            description="Resource creates/modifies successfully, all dependencies handled gracefully.",
        ))
        
        # Degraded: Partial impact, quick recovery
        degraded_affected = affected_nodes[:max(1, len(affected_nodes) // 3)]
        degraded_recovery = 5
        degraded_impact = self._estimate_revenue_impact(degraded_affected, degraded_recovery)
        scenarios.append(FailureScenario(
            name="Degraded: Partial Service Impact",
            probability=0.35,
            affected_services=degraded_affected,
            recovery_time_minutes=degraded_recovery,
            revenue_impact_usd=degraded_impact,
            severity="medium",
            description=f"~{len(degraded_affected)} downstream services affected. Automatic failover triggers within 5 minutes.",
        ))
        
        # Cascading: Multiple service failures
        cascading_affected = affected_nodes[:max(1, len(affected_nodes) // 2)]
        cascading_recovery = 15
        cascading_impact = self._estimate_revenue_impact(cascading_affected, cascading_recovery)
        scenarios.append(FailureScenario(
            name="Cascading: Multi-Service Outage",
            probability=0.35,
            affected_services=cascading_affected,
            recovery_time_minutes=cascading_recovery,
            revenue_impact_usd=cascading_impact,
            severity="high",
            description=f"~{len(cascading_affected)} services fail sequentially. Manual intervention required.",
        ))
        
        # Worst case: Full cascade
        if blast_radius["user_facing_impact"]:
            worst_affected = affected_nodes
            worst_recovery = 60
            worst_impact = self._estimate_revenue_impact(worst_affected, worst_recovery)
            scenarios.append(FailureScenario(
                name="Worst Case: Full Service Cascade",
                probability=0.15,
                affected_services=worst_affected,
                recovery_time_minutes=worst_recovery,
                revenue_impact_usd=worst_impact,
                severity="critical",
                description=f"All {len(worst_affected)} dependent services cascade. User-facing outage ~1 hour.",
            ))
        
        return scenarios
    
    def _estimate_revenue_impact(self, affected_services: List[str], recovery_minutes: int) -> float:
        """Estimate revenue loss based on affected services and recovery time."""
        total_cost_per_hour = sum(
            self.engine.resources.get(svc, type('', (), {'cost_per_hour': 0})()).cost_per_hour
            for svc in affected_services
        )
        user_facing_count = sum(
            1 for svc in affected_services
            if self.engine.resources.get(svc, type('', (), {'user_facing': False})()).user_facing
        )
        
        # Rough estimation: $5-20 per minute of downtime per user-facing service
        revenue_per_minute = user_facing_count * random.uniform(5, 20)
        return revenue_per_minute * recovery_minutes
    
    def simulate_propagation(self, initial_failure: str) -> Dict:
        """
        Simulate step-by-step failure propagation.
        Returns a timeline of cascading failures.
        """
        timeline = []
        timeline.append({
            "time_ms": 0,
            "event": "initial_failure",
            "service": initial_failure,
            "reason": "Action triggered resource failure",
        })
        
        # Simulate propagation wave
        current_failed = {initial_failure}
        wave = 1
        time_offset = 100
        
        for step in range(3):  # 3 propagation waves
            next_failed = set()
            for service in current_failed:
                downstream = self.engine.get_affected_nodes(service, direction="downstream")
                # Only ~30% propagate to avoid full cascade
                propagated = random.sample(downstream, max(0, len(downstream) // 3))
                next_failed.update(propagated)
                
                for affected in propagated:
                    timeline.append({
                        "time_ms": time_offset + (step * 500),
                        "event": "cascade",
                        "service": affected,
                        "triggered_by": service,
                        "reason": "Dependency failed",
                    })
            
            current_failed = next_failed
            wave += 1
            if not current_failed:
                break
        
        return {
            "total_affected": len(set(ev["service"] for ev in timeline)),
            "timeline": timeline,
            "duration_ms": timeline[-1]["time_ms"] if timeline else 0,
        }
