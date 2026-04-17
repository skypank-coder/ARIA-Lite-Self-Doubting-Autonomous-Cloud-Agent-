"""
Risk Analyzer: Computes multi-dimensional risk scores.
Replaces single confidence with: availability_risk, security_risk, cost_risk, reversibility_score
"""

from typing import Dict
from dataclasses import dataclass
from dependency_graph import DependencyGraphEngine, CloudResource


@dataclass
class RiskProfile:
    """Multi-dimensional risk assessment."""
    availability_risk: float  # 0-1, probability of outage
    security_risk: float  # 0-1, vulnerability exposure
    cost_risk: float  # 0-1, financial exposure
    reversibility_score: float  # 0-1, ease of undo
    data_loss_risk: float  # 0-1, potential data corruption
    recovery_time_minutes: int  # Estimated full recovery
    
    # Composite scores
    overall_risk: float  # Weighted combination
    action_recommended: str  # AUTO, APPROVE, or BLOCK
    
    def to_dict(self):
        return {
            "availability_risk": round(self.availability_risk, 2),
            "security_risk": round(self.security_risk, 2),
            "cost_risk": round(self.cost_risk, 2),
            "reversibility_score": round(self.reversibility_score, 2),
            "data_loss_risk": round(self.data_loss_risk, 2),
            "recovery_time_minutes": self.recovery_time_minutes,
            "overall_risk": round(self.overall_risk, 2),
            "action_recommended": self.action_recommended,
        }


class RiskAnalyzer:
    """Computes multi-dimensional risk scores."""
    
    def __init__(self, graph_engine: DependencyGraphEngine):
        self.engine = graph_engine
    
    def analyze_action(self, action_type: str, target_resource: str, 
                      affected_resources: Dict) -> RiskProfile:
        """
        Analyze risk of an action on a specific resource.
        
        action_type: "create", "delete", "modify", "scale", "update", "attach_policy"
        target_resource: Resource being modified
        affected_resources: Dict of resources affected by the action
        """
        
        # Get blast radius info
        blast_radius = self.engine.compute_blast_radius(target_resource)
        affected_count = len(blast_radius["affected_nodes"])
        
        # Compute each risk dimension
        availability_risk = self._compute_availability_risk(
            action_type, target_resource, affected_count, blast_radius
        )
        
        security_risk = self._compute_security_risk(
            action_type, target_resource, affected_resources
        )
        
        cost_risk = self._compute_cost_risk(
            action_type, target_resource, blast_radius
        )
        
        reversibility_score = self._compute_reversibility(
            action_type, target_resource
        )
        
        data_loss_risk = self._compute_data_loss_risk(
            action_type, target_resource
        )
        
        recovery_time = self._estimate_recovery_time(
            action_type, affected_count, blast_radius
        )
        
        # Compute overall risk (weighted combination)
        # Lower is safer
        overall_risk = (
            0.35 * availability_risk +     # Availability is critical
            0.25 * security_risk +          # Security matters
            0.15 * cost_risk +              # Cost impact
            0.15 * data_loss_risk +         # Data integrity
            -0.10 * reversibility_score     # Higher reversibility = lower risk
        )
        overall_risk = max(0.0, min(1.0, overall_risk))
        
        # Determine action
        if overall_risk < 0.30 and reversibility_score > 0.7:
            action = "AUTO"
        elif overall_risk < 0.60 or reversibility_score > 0.85:
            action = "APPROVE"
        else:
            action = "BLOCK"
        
        return RiskProfile(
            availability_risk=availability_risk,
            security_risk=security_risk,
            cost_risk=cost_risk,
            reversibility_score=reversibility_score,
            data_loss_risk=data_loss_risk,
            recovery_time_minutes=recovery_time,
            overall_risk=overall_risk,
            action_recommended=action,
        )
    
    def _compute_availability_risk(self, action_type: str, target: str, 
                                   affected_count: int, blast_radius: Dict) -> float:
        """Compute probability of service unavailability."""
        target_res = self.engine.resources.get(target)
        if not target_res:
            return 0.2
        
        # Base risk by action type
        base_risk = {
            "create": 0.05,   # Usually safe
            "update": 0.15,   # Medium risk
            "scale": 0.10,    # Usually handled well
            "modify": 0.20,   # Dangerous
            "delete": 0.70,   # Very dangerous
            "attach_policy": 0.08,  # Safe if correct
        }.get(action_type, 0.15)
        
        # Increase by blast radius
        blast_multiplier = 1.0 + (affected_count * 0.05)  # +5% per affected service
        if blast_radius.get("user_facing_impact"):
            blast_multiplier *= 1.5
        
        # Increase by target criticality
        criticality_multiplier = 1.0 + (target_res.criticality * 0.3)
        
        risk = base_risk * blast_multiplier * criticality_multiplier
        return min(1.0, risk)
    
    def _compute_security_risk(self, action_type: str, target: str, 
                               affected_resources: Dict) -> float:
        """Compute security exposure (privilege escalation, exposure, etc)."""
        
        if action_type == "attach_policy":
            # Check if admin policy
            if "Administrator" in str(affected_resources.get("policy", "")):
                return 0.75  # High risk
            if "Write" in str(affected_resources.get("policy", "")):
                return 0.50
            if "Read" in str(affected_resources.get("policy", "")):
                return 0.15
            return 0.30
        
        elif action_type == "delete":
            if "iam" in target.lower():
                return 0.50  # Risk of access lockout
            return 0.10
        
        elif action_type == "update":
            return 0.10
        
        else:
            return 0.05
    
    def _compute_cost_risk(self, action_type: str, target: str, 
                           blast_radius: Dict) -> float:
        """Compute financial exposure."""
        total_cost = blast_radius.get("total_cost_per_hour", 0.0)
        
        if action_type == "delete":
            return 0.0  # Deleting saves money
        elif action_type == "scale":
            # Scaling up increases hourly cost
            cost_multiplier = min(1.0, total_cost / 100.0)  # Normalize to 0-1
            return cost_multiplier * 0.4
        else:
            return min(0.3, total_cost / 100.0)
    
    def _compute_reversibility(self, action_type: str, target: str) -> float:
        """
        Compute how easily can we undo this action?
        1.0 = fully reversible, 0.0 = irreversible
        """
        reversibility_map = {
            "create": 0.95,  # Can delete
            "delete": 0.05,  # Very hard to restore
            "scale": 0.90,   # Can scale back
            "update": 0.80,  # Can roll back
            "modify": 0.70,  # Harder to undo
            "attach_policy": 0.85,  # Can detach
        }
        return reversibility_map.get(action_type, 0.60)
    
    def _compute_data_loss_risk(self, action_type: str, target: str) -> float:
        """Compute risk of data corruption or loss."""
        if action_type == "delete":
            if "db" in target.lower() or "rds" in target.lower():
                return 0.95  # Database deletion = total loss
            if "s3" in target.lower():
                return 0.90
            return 0.50
        
        elif action_type == "modify":
            if "db" in target.lower():
                return 0.60
            return 0.20
        
        else:
            return 0.05
    
    def _estimate_recovery_time(self, action_type: str, affected_count: int, 
                               blast_radius: Dict) -> int:
        """Estimate recovery time in minutes."""
        base_recovery = {
            "create": 1,
            "scale": 5,
            "update": 10,
            "modify": 20,
            "attach_policy": 2,
            "delete": 120,  # Long recovery
        }.get(action_type, 15)
        
        # Increase by affected services
        cascade_multiplier = 1.0 + (affected_count * 0.5)
        
        # Increase if DB affected
        if blast_radius.get("critical_services"):
            cascade_multiplier *= 1.5
        
        recovery_time = int(base_recovery * cascade_multiplier)
        return min(360, recovery_time)  # Cap at 6 hours
