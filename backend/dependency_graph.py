"""
Dependency Graph Engine: Models cloud resources and their relationships.
Uses NetworkX for efficient graph operations.
"""

import networkx as nx
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

@dataclass
class CloudResource:
    """Represents a cloud resource in the dependency graph."""
    id: str
    type: str  # IAM, EC2, RDS, Lambda, S3, ALB, etc.
    criticality: float  # 0-1, impact if goes down
    region: str
    cost_per_hour: float
    user_facing: bool  # Does users interact with this?
    dependencies: List[str] = field(default_factory=list)
    dependent_services: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "criticality": self.criticality,
            "region": self.region,
            "cost_per_hour": self.cost_per_hour,
            "user_facing": self.user_facing,
            "metadata": self.metadata,
        }


class DependencyGraphEngine:
    """Manages cloud resource dependency graph and traversal."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.resources: Dict[str, CloudResource] = {}
    
    def add_resource(self, resource: CloudResource):
        """Add a resource node to the graph."""
        self.resources[resource.id] = resource
        self.graph.add_node(
            resource.id,
            type=resource.type,
            criticality=resource.criticality,
            region=resource.region,
            cost_per_hour=resource.cost_per_hour,
            user_facing=resource.user_facing,
        )
    
    def add_dependency(self, source_id: str, target_id: str, weight: float = 1.0):
        """Add a directed edge: source depends on target."""
        if source_id in self.resources and target_id in self.resources:
            self.graph.add_edge(source_id, target_id, weight=weight)
            self.resources[source_id].dependencies.append(target_id)
            self.resources[target_id].dependent_services.append(source_id)
    
    def get_affected_nodes(self, failed_node: str, direction: str = "downstream") -> List[str]:
        """
        Get all nodes affected if `failed_node` fails.
        
        direction="downstream": Services that depend on failed_node (cascade down)
        direction="upstream": Services that failed_node depends on (cascade up)
        """
        if direction == "downstream":
            # Find all nodes that depend on failed_node (reverse graph)
            reverse_graph = self.graph.reverse()
            affected = list(nx.descendants(reverse_graph, failed_node))
        else:  # upstream
            affected = list(nx.descendants(self.graph, failed_node))
        
        return affected
    
    def compute_blast_radius(self, failed_node: str) -> Dict:
        """
        Compute the blast radius of a single resource failure.
        Returns criticality-weighted impact across regions.
        """
        downstream = self.get_affected_nodes(failed_node, direction="downstream")
        
        impact = {
            "affected_count": len(downstream),
            "affected_nodes": downstream,
            "critical_services": [],
            "user_facing_impact": False,
            "regions_affected": set(),
            "total_cost_per_hour": 0.0,
            "criticality_score": 0.0,
        }
        
        for node_id in downstream:
            res = self.resources.get(node_id)
            if res:
                impact["regions_affected"].add(res.region)
                impact["total_cost_per_hour"] += res.cost_per_hour
                impact["criticality_score"] += res.criticality
                if res.criticality >= 0.8:
                    impact["critical_services"].append(node_id)
                if res.user_facing:
                    impact["user_facing_impact"] = True
        
        # Normalize criticality score
        if downstream:
            impact["criticality_score"] /= len(downstream)
        
        impact["regions_affected"] = list(impact["regions_affected"])
        return impact
    
    def get_recovery_path(self, failed_node: str) -> Dict:
        """
        Compute recovery dependencies.
        What must be recovered first to get failed_node back online?
        """
        upstream_deps = self.get_affected_nodes(failed_node, direction="upstream")
        recovery_order = []
        
        # Topological sort of upstream dependencies
        subgraph = self.graph.subgraph([failed_node] + upstream_deps).copy()
        try:
            recovery_order = list(nx.topological_sort(subgraph.reverse()))
        except nx.NetworkXError:
            recovery_order = upstream_deps
        
        return {
            "recovery_order": recovery_order,
            "critical_path_length": len(recovery_order),
            "parallel_recoverable": self._find_parallel_branches(failed_node),
        }
    
    def _find_parallel_branches(self, node_id: str) -> List[List[str]]:
        """
        Find independent dependency branches that can be recovered in parallel.
        """
        upstream_deps = self.get_affected_nodes(node_id, direction="upstream")
        branches = []
        visited = set()
        
        for dep in upstream_deps:
            if dep not in visited:
                branch = list(nx.ancestors(self.graph, dep))
                branches.append(branch)
                visited.update(branch)
        
        return branches
    
    def to_dict(self) -> Dict:
        """Export graph as dictionary for frontend visualization."""
        nodes = []
        edges = []
        
        for node_id, resource in self.resources.items():
            nodes.append({
                "id": node_id,
                **resource.to_dict(),
            })
        
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "weight": data.get("weight", 1.0),
            })
        
        return {"nodes": nodes, "edges": edges}


# Pre-defined cloud architecture for demo
def create_demo_architecture() -> DependencyGraphEngine:
    """Create a realistic AWS architecture for testing."""
    engine = DependencyGraphEngine()
    
    # Add resources
    resources = [
        # Frontend
        CloudResource("alb-primary", "ALB", 0.9, "us-east-1", 16.0, True),
        CloudResource("cdn", "CloudFront", 0.85, "global", 0.0, True),
        
        # Compute
        CloudResource("ec2-app-1", "EC2", 0.8, "us-east-1", 10.0, True),
        CloudResource("ec2-app-2", "EC2", 0.8, "us-east-1", 10.0, True),
        CloudResource("lambda-workers", "Lambda", 0.7, "us-east-1", 2.0, False),
        
        # Data
        CloudResource("rds-primary", "RDS", 0.95, "us-east-1", 45.0, True),
        CloudResource("rds-replica", "RDS", 0.7, "us-west-2", 45.0, False),
        CloudResource("elasticsearch", "Elasticsearch", 0.6, "us-east-1", 30.0, False),
        CloudResource("redis-cache", "ElastiCache", 0.75, "us-east-1", 5.0, False),
        CloudResource("s3-main", "S3", 0.8, "us-east-1", 1.0, True),
        
        # IAM & Security
        CloudResource("iam-role-app", "IAM", 0.95, "global", 0.0, False),
        CloudResource("iam-role-lambda", "IAM", 0.7, "global", 0.0, False),
        CloudResource("secrets-manager", "SecretsManager", 0.85, "us-east-1", 0.5, False),
        
        # Observability
        CloudResource("cloudwatch", "CloudWatch", 0.6, "global", 5.0, False),
        CloudResource("sns-alerts", "SNS", 0.65, "us-east-1", 1.0, False),
    ]
    
    for res in resources:
        engine.add_resource(res)
    
    # Add dependencies (source depends on target)
    dependencies = [
        ("cdn", "alb-primary"),
        ("alb-primary", "ec2-app-1"),
        ("alb-primary", "ec2-app-2"),
        ("alb-primary", "redis-cache"),
        ("alb-primary", "secrets-manager"),
        
        ("ec2-app-1", "rds-primary"),
        ("ec2-app-2", "rds-primary"),
        ("ec2-app-1", "elasticsearch"),
        ("ec2-app-1", "secrets-manager"),
        ("ec2-app-1", "iam-role-app"),
        
        ("lambda-workers", "rds-primary"),
        ("lambda-workers", "elasticsearch"),
        ("lambda-workers", "s3-main"),
        ("lambda-workers", "iam-role-lambda"),
        
        ("rds-replica", "rds-primary"),
        ("elasticsearch", "s3-main"),
        ("redis-cache", "secrets-manager"),
        
        ("cloudwatch", "ec2-app-1"),
        ("cloudwatch", "ec2-app-2"),
        ("cloudwatch", "rds-primary"),
        ("sns-alerts", "cloudwatch"),
    ]
    
    for source, target in dependencies:
        engine.add_dependency(source, target, weight=1.0)
    
    return engine
"""
Wrapper functions for dependency_graph to work with scenario structures.
Append this to the end of dependency_graph.py
"""

def build_graph(scenario):
    """
    Build a dependency graph from a scenario definition.
    """
    engine = DependencyGraphEngine()
    
    # Add resources from scenario definition
    resources_def = scenario.get("resources", {})
    for name, metadata in resources_def.items():
        res = CloudResource(
            id=name,
            type=metadata.get("type", "Unknown"),
            criticality=metadata.get("criticality", 0.5),
            region=metadata.get("region", "us-east-1"),
            cost_per_hour=metadata.get("cost_per_hour", 0.0),
            user_facing=metadata.get("user_facing", False),
        )
        engine.add_resource(res)
    
    # Add hardcoded demo architecture dependencies
    demo_engine = create_demo_architecture()
    for source, target, data in demo_engine.graph.edges(data=True):
        try:
            engine.add_dependency(source, target, weight=data.get("weight", 1.0))
        except KeyError:
            pass
    
    return engine


def compute_blast_radius(graph, entry_nodes):
    """
    Compute total blast radius across multiple entry points.
    
    FIXED FORMULA: blast_radius = (affected_nodes / total_nodes) * average_criticality
    (Removed max_criticality dominator)
    """
    all_affected = set()
    criticality_scores = []
    user_facing_count = 0
    critical_services = []
    
    for node in entry_nodes:
        if node in graph.resources:
            blast = graph.compute_blast_radius(node)
            all_affected.update(blast.get("affected_nodes", []))
            criticality_scores.append(blast.get("criticality_score", 0.0))
            user_facing_count += 1 if blast.get("user_facing_impact", False) else 0
            critical_services.extend(blast.get("critical_services", []))
    
    total_resources = len(graph.resources)
    affected_fraction = len(all_affected) / max(total_resources, 1)
    
    # Use AVERAGE criticality instead of MAX (prevents inflation)
    avg_criticality = sum(criticality_scores) / len(criticality_scores) if criticality_scores else 0.0
    weighted_impact = round(affected_fraction * avg_criticality, 2)
    
    return {
        "affected_nodes": list(all_affected),
        "weighted_impact": min(1.0, weighted_impact),
        "user_facing_count": user_facing_count,
        "critical_services": list(set(critical_services)),
    }


def serialize_graph(graph, blast, entry_nodes):
    """
    Serialize graph for frontend visualization.
    """
    nodes = []
    affected = set(blast.get("affected_nodes", []))
    
    for node_id, resource in graph.resources.items():
        node_data = resource.to_dict()
        node_data["id"] = node_id
        node_data["is_entry"] = node_id in entry_nodes
        node_data["is_affected"] = node_id in affected
        nodes.append(node_data)
    
    edges = []
    for source, target, data in graph.graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "weight": data.get("weight", 1.0),
            "is_blast_path": (source in affected or target in affected),
        })
    
    return {"nodes": nodes, "edges": edges}


def propagation_summary(blast, graph):
    """
    Summarize blast radius propagation in waves.
    """
    waves = []
    affected = set(blast.get("affected_nodes", []))
    
    if not affected:
        return []
    
    wave1_count = len([n for n in affected if graph.resources[n].criticality < 0.8])
    waves.append({"wave": 1, "affected_count": wave1_count, "severity": "high"})
    
    wave2_count = len(blast.get("critical_services", []))
    if wave2_count > 0:
        waves.append({"wave": 2, "affected_count": wave2_count, "severity": "critical"})
    
    if blast.get("user_facing_count", 0) > 0:
        waves.append({"wave": 3, "affected_count": 1, "severity": "user_impact"})
    
    return waves
