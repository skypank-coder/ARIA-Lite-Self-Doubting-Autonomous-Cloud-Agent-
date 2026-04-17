"""
Incident Intelligence Memory: Tracks past failures and detects patterns.
Provides warnings based on similar past incidents.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class IncidentRecord:
    """Record of a past incident."""
    action: str
    target_resource: str
    timestamp: str
    outcome: str  # "success", "partial_failure", "full_failure"
    affected_services: List[str] = field(default_factory=list)
    duration_minutes: int = 0
    revenue_impact_usd: float = 0.0
    root_cause: str = ""
    lessons_learned: str = ""


class IncidentMemory:
    """Enhanced memory system with pattern detection."""
    
    def __init__(self):
        self.incidents: List[IncidentRecord] = []
        self.patterns: Dict = {}
    
    def record_incident(self, record: IncidentRecord):
        """Record a past incident."""
        self.incidents.append(record)
        self._update_patterns()
    
    def _update_patterns(self):
        """Detect patterns from incident history."""
        self.patterns = {
            "failure_prone_actions": self._detect_failure_prone_actions(),
            "cascade_patterns": self._detect_cascade_patterns(),
            "recurring_failures": self._detect_recurring_failures(),
            "regional_issues": self._detect_regional_issues(),
        }
    
    def _detect_failure_prone_actions(self) -> Dict:
        """Identify which action types have high failure rates."""
        action_stats = {}
        
        for incident in self.incidents:
            action = incident.action
            if action not in action_stats:
                action_stats[action] = {"total": 0, "failures": 0}
            
            action_stats[action]["total"] += 1
            if incident.outcome != "success":
                action_stats[action]["failures"] += 1
        
        failure_rates = {}
        for action, stats in action_stats.items():
            if stats["total"] > 0:
                failure_rates[action] = stats["failures"] / stats["total"]
        
        return failure_rates
    
    def _detect_cascade_patterns(self) -> List[Dict]:
        """Detect which failure combinations frequently cascade."""
        cascade_chains = []
        
        for i, incident in enumerate(self.incidents):
            if len(incident.affected_services) > 3:  # Multi-service failure
                cascade_pattern = {
                    "trigger": incident.target_resource,
                    "cascade_length": len(incident.affected_services),
                    "affected": incident.affected_services[:5],
                    "frequency": 1,
                }
                
                # Check if similar pattern exists
                for existing in cascade_chains:
                    if existing["trigger"] == cascade_pattern["trigger"]:
                        existing["frequency"] += 1
                        break
                else:
                    cascade_chains.append(cascade_pattern)
        
        # Sort by frequency
        return sorted(cascade_chains, key=lambda x: x["frequency"], reverse=True)
    
    def _detect_recurring_failures(self) -> List[Dict]:
        """Identify resources that fail repeatedly."""
        resource_failures = {}
        
        for incident in self.incidents:
            res = incident.target_resource
            if res not in resource_failures:
                resource_failures[res] = 0
            if incident.outcome != "success":
                resource_failures[res] += 1
        
        recurring = [
            {"resource": res, "failure_count": count}
            for res, count in resource_failures.items() if count >= 2
        ]
        
        return sorted(recurring, key=lambda x: x["failure_count"], reverse=True)
    
    def _detect_regional_issues(self) -> List[str]:
        """Identify regions with higher failure rates."""
        regional_stats = {}
        
        for incident in self.incidents:
            # Extract region from resource metadata if available
            # For now, just track by resource name pattern
            if "us-east-1" in incident.target_resource.lower():
                region = "us-east-1"
            elif "us-west" in incident.target_resource.lower():
                region = "us-west-2"
            else:
                region = "other"
            
            if region not in regional_stats:
                regional_stats[region] = 0
            if incident.outcome != "success":
                regional_stats[region] += 1
        
        return [r for r, count in sorted(regional_stats.items(), 
                                        key=lambda x: x[1], reverse=True) 
                if count > 0]
    
    def find_similar_incidents(self, action: str, target: str) -> List[Dict]:
        """Find past incidents similar to current request."""
        similar = []
        
        for incident in self.incidents:
            similarity_score = 0.0
            
            # Exact action match
            if incident.action == action:
                similarity_score += 0.5
            
            # Resource type match
            target_type = target.split("-")[0].lower()
            incident_type = incident.target_resource.split("-")[0].lower()
            if target_type == incident_type:
                similarity_score += 0.3
            
            # If failed before
            if incident.outcome != "success":
                similarity_score += 0.2
            
            if similarity_score >= 0.5:
                similar.append({
                    "incident": incident,
                    "similarity_score": similarity_score,
                    "outcome": incident.outcome,
                    "warning": self._generate_warning(incident),
                })
        
        return sorted(similar, key=lambda x: x["similarity_score"], reverse=True)
    
    def _generate_warning(self, incident: IncidentRecord) -> str:
        """Generate human-readable warning from incident."""
        if incident.outcome == "full_failure":
            warning = f"⚠ Earlier {incident.action} on {incident.target_resource} caused full outage"
            if incident.affected_services:
                warning += f" affecting {len(incident.affected_services)} services"
            if incident.revenue_impact_usd > 0:
                warning += f" (${int(incident.revenue_impact_usd)} impact)"
            return warning
        
        elif incident.outcome == "partial_failure":
            warning = f"⚠ Earlier {incident.action} caused cascade to {incident.affected_services[:3]}"
            if incident.duration_minutes > 30:
                warning += f" - recovery took {incident.duration_minutes} min"
            return warning
        
        else:
            return f"ℹ Past {incident.action} on similar resource succeeded"
    
    def get_warnings_for_action(self, action: str, target: str, blast_radius: Dict) -> List[str]:
        """Get all relevant warnings for the current action."""
        warnings = []
        
        # Check failure patterns
        failure_rates = self.patterns.get("failure_prone_actions", {})
        if action in failure_rates and failure_rates[action] > 0.5:
            warnings.append(f"⚠ {action.upper()} actions have {int(failure_rates[action]*100)}% historical failure rate")
        
        # Check cascade patterns
        cascade_patterns = self.patterns.get("cascade_patterns", [])
        for pattern in cascade_patterns:
            if pattern["trigger"] in target:
                warnings.append(f"⚠ Cascading failure detected {pattern['frequency']} times: "
                              f"{pattern['trigger']} → {pattern['cascade_length']} services")
        
        # Check similar incidents
        similar = self.find_similar_incidents(action, target)
        for sim in similar[:2]:  # Top 2 similar incidents
            warnings.append(sim["warning"])
        
        return warnings
    
    def to_dict(self) -> Dict:
        """Export memory as dict for API."""
        return {
            "incident_count": len(self.incidents),
            "patterns": self.patterns,
            "recent_incidents": [
                {
                    "action": inc.action,
                    "target": inc.target_resource,
                    "outcome": inc.outcome,
                    "timestamp": inc.timestamp,
                }
                for inc in self.incidents[-10:]  # Last 10
            ],
        }


# Pre-populate with demo incidents
def create_demo_memory() -> IncidentMemory:
    """Create memory with realistic demo incidents."""
    memory = IncidentMemory()
    
    incidents = [
        IncidentRecord(
            action="delete",
            target_resource="iam-role-app",
            timestamp="2026-04-16T10:23:00Z",
            outcome="full_failure",
            affected_services=["ec2-app-1", "ec2-app-2", "lambda-workers"],
            duration_minutes=45,
            revenue_impact_usd=3500,
            root_cause="IAM role deletion cascaded to all dependent services",
            lessons_learned="Always audit IAM dependencies before deletion",
        ),
        IncidentRecord(
            action="scale",
            target_resource="ec2-app-1",
            timestamp="2026-04-15T14:10:00Z",
            outcome="partial_failure",
            affected_services=["rds-primary"],
            duration_minutes=12,
            revenue_impact_usd=800,
            root_cause="RDS connection pooling exhausted during scale",
            lessons_learned="Pre-test connection pools before scaling",
        ),
        IncidentRecord(
            action="modify",
            target_resource="rds-primary",
            timestamp="2026-04-10T09:45:00Z",
            outcome="full_failure",
            affected_services=["ec2-app-1", "ec2-app-2", "elasticsearch", "lambda-workers"],
            duration_minutes=120,
            revenue_impact_usd=15000,
            root_cause="Zone exhaustion during RDS modification in eu-west-1",
            lessons_learned="Always use multi-AZ during peak hours",
        ),
        IncidentRecord(
            action="attach_policy",
            target_resource="iam-role-lambda",
            timestamp="2026-04-14T16:30:00Z",
            outcome="success",
            affected_services=[],
            duration_minutes=1,
            revenue_impact_usd=0,
        ),
        IncidentRecord(
            action="create",
            target_resource="s3-bucket",
            timestamp="2026-04-12T11:00:00Z",
            outcome="success",
            affected_services=[],
            duration_minutes=0,
            revenue_impact_usd=0,
        ),
    ]
    
    for incident in incidents:
        memory.record_incident(incident)
    
    return memory
