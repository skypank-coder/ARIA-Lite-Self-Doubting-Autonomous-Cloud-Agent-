"""
V2 Intent Analyzer: Pure structured extraction, NO keyword shortcuts.

Converts raw ticket text into structured parameters that drive risk computation.
No scenario-based lookup. Pure NLP + regex analysis.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Action(Enum):
    """Infrastructure actions."""
    CREATE = "create"
    DELETE = "delete"
    MODIFY = "modify"
    SCALE = "scale"
    ATTACH = "attach"
    DETACH = "detach"
    DEPLOY = "deploy"
    STOP = "stop"
    START = "start"
    UNKNOWN = "unknown"


class Resource(Enum):
    """AWS resources."""
    S3 = "s3"
    EC2 = "ec2"
    RDS = "rds"
    IAM = "iam"
    LAMBDA = "lambda"
    EKS = "eks"
    VPC = "vpc"
    UNKNOWN = "unknown"


class Environment(Enum):
    """Deployment environment."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


@dataclass
class OperationContext:
    """Qualitative context from ticket text."""
    is_temporary: bool = False          # "temporary", "test", "poc"
    is_unused: bool = False             # "unused", "orphaned", "dead"
    is_low_traffic: bool = False        # "low traffic", "minimal", "unused"
    is_read_only: bool = False          # "read", "list", "describe only"
    is_admin_access: bool = False       # "admin", "root", "administratoraccess"
    has_backup: bool = False            # "backup", "snapshot", "replicated"
    is_critical_path: bool = False      # "critical", "prod-facing", "data-sensitive"
    is_immediate: bool = False          # "now", "asap", "immediately"
    has_rollback_plan: bool = False     # "rollback", "revert", "downtime acceptable"


@dataclass
class IntentAnalysis:
    """Structured intent extracted from raw ticket."""
    raw_text: str = ""
    
    # Primary extraction
    action: Action = Action.UNKNOWN
    resource: Resource = Resource.UNKNOWN
    environment: Environment = Environment.UNKNOWN
    
    # Quantitative parameters
    scale_factor: float = 1.0           # target/current for scaling operations
    source_count: Optional[int] = None  # current count (e.g., 2 instances)
    target_count: Optional[int] = None  # desired count (e.g., 8 instances)
    
    # Context
    context: OperationContext = field(default_factory=OperationContext)
    region: Optional[str] = None
    
    # Quality metrics
    extraction_confidence: float = 0.5  # 0-1: how well did we parse?
    is_valid: bool = False              # If action/resource could be determined


def detect_action(text: str) -> Action:
    """Detect primary action from text."""
    lower = text.lower()
    
    if re.search(r'\b(delete|drop|remove|destroy)\b', lower):
        return Action.DELETE
    elif re.search(r'\b(scale|increase|add|expand|grow)\b', lower):
        return Action.SCALE
    elif re.search(r'\b(modify|update|change|patch|reconfigure)\b', lower):
        return Action.MODIFY
    elif re.search(r'\b(attach|grant|add.*policy)\b', lower):
        return Action.ATTACH
    elif re.search(r'\b(detach|revoke|remove.*policy)\b', lower):
        return Action.DETACH
    elif re.search(r'\b(deploy|publish|release|promote)\b', lower):
        return Action.DEPLOY
    elif re.search(r'\b(stop|shutdown|halt)\b', lower):
        return Action.STOP
    elif re.search(r'\b(start|restart|boot|launch)\b', lower):
        return Action.START
    elif re.search(r'\b(create|provision|new|setup|build)\b', lower):
        return Action.CREATE
    
    return Action.UNKNOWN


def detect_resource(text: str) -> Resource:
    """Detect primary resource from text."""
    lower = text.lower()
    
    if re.search(r'\b(s3|bucket|object.*storage)\b', lower):
        return Resource.S3
    elif re.search(r'\b(ec2|instance|ami|autoscal|compute)\b', lower):
        return Resource.EC2
    elif re.search(r'\b(rds|database|db|sql|postgres|mysql)\b', lower):
        return Resource.RDS
    elif re.search(r'\b(iam|role|policy|permission|iam\.)\b', lower):
        return Resource.IAM
    elif re.search(r'\b(lambda|function|serverless|code)\b', lower):
        return Resource.LAMBDA
    elif re.search(r'\b(eks|kubernetes|k8s|kube|container)\b', lower):
        return Resource.EKS
    elif re.search(r'\b(vpc|subnet|security.*group|network|vpc\.)\b', lower):
        return Resource.VPC
    
    return Resource.UNKNOWN


def detect_environment(text: str) -> Environment:
    """Detect target environment from text."""
    lower = text.lower()
    
    if re.search(r'\b(prod|production|prd|live|customer-facing)\b', lower):
        return Environment.PRODUCTION
    elif re.search(r'\b(staging|stage|stg|pre-prod)\b', lower):
        return Environment.STAGING
    elif re.search(r'\b(dev|development|test|qa|sandbox|poc)\b', lower):
        return Environment.DEVELOPMENT
    
    return Environment.UNKNOWN


def extract_scale_parameters(text: str) -> tuple[Optional[int], Optional[int], float]:
    """
    Extract source/target counts from scale operations.
    Returns: (source_count, target_count, scale_factor)
    """
    lower = text.lower()
    
    # Pattern: "from X to Y" or "X -> Y" or "X to Y"
    match = re.search(r'from\s+(\d+)\s+to\s+(\d+)', lower)
    if match:
        source = int(match.group(1))
        target = int(match.group(2))
        if source > 0:
            return source, target, target / source
    
    # Pattern: "X -> Y" or "X→Y"
    match = re.search(r'(\d+)\s*[-–→>]+\s*(\d+)', lower)
    if match:
        source = int(match.group(1))
        target = int(match.group(2))
        if source > 0:
            return source, target, target / source
    
    # Pattern: "scale to X" or "up to X"
    match = re.search(r'(?:scale|up)\s+to\s+(\d+)', lower)
    if match:
        target = int(match.group(1))
        return None, target, 1.0  # We don't know source
    
    return None, None, 1.0


def extract_context(text: str) -> OperationContext:
    """Extract qualitative context from ticket text."""
    lower = text.lower()
    
    ctx = OperationContext()
    ctx.is_temporary = bool(re.search(r'\b(temporary|temp|testing|poc)\b', lower))
    ctx.is_unused = bool(re.search(r'\b(unused|orphan|dead|legacy)\b', lower))
    ctx.is_low_traffic = bool(re.search(r'\b(low traffic|minimal|light|unused)\b', lower))
    ctx.is_read_only = bool(re.search(r'\b(read|list|describe|query|get)\b', lower))
    ctx.is_admin_access = bool(re.search(r'\b(admin|root|administratoraccess|full.*access)\b', lower))
    ctx.has_backup = bool(re.search(r'\b(backup|snapshot|replicated|replica|rto|rpo)\b', lower))
    ctx.is_critical_path = bool(re.search(r'\b(critical|prod-facing|data|compliance|sensitive)\b', lower))
    ctx.is_immediate = bool(re.search(r'\b(now|asap|immediately|urgent|right away)\b', lower))
    ctx.has_rollback_plan = bool(re.search(r'\b(rollback|revert|undo|downtime.*acceptable)\b', lower))
    
    return ctx


def extract_region(text: str) -> Optional[str]:
    """Extract AWS region if present."""
    regions = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-central-1",
        "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
    ]
    lower = text.lower()
    for region in regions:
        if region in lower:
            return region
    return None


def analyze_intent(ticket: str) -> IntentAnalysis:
    """
    Main entry point: Convert ticket to structured IntentAnalysis.
    
    NO KEYWORD SHORTCUTS. Every component extracted independently.
    """
    analysis = IntentAnalysis(raw_text=ticket)
    
    # Extract components independently
    analysis.action = detect_action(ticket)
    analysis.resource = detect_resource(ticket)
    analysis.environment = detect_environment(ticket)
    analysis.context = extract_context(ticket)
    analysis.region = extract_region(ticket)
    
    # For scale operations, extract parameters
    if analysis.action == Action.SCALE:
        source, target, factor = extract_scale_parameters(ticket)
        analysis.source_count = source
        analysis.target_count = target
        analysis.scale_factor = factor
    
    # Compute extraction confidence
    confidence = 0.0
    if analysis.action != Action.UNKNOWN:
        confidence += 0.35
    if analysis.resource != Resource.UNKNOWN:
        confidence += 0.35
    if analysis.environment != Environment.UNKNOWN:
        confidence += 0.20
    if analysis.scale_factor != 1.0:
        confidence += 0.10
    
    analysis.extraction_confidence = min(1.0, confidence)
    analysis.is_valid = (
        analysis.action != Action.UNKNOWN and 
        analysis.resource != Resource.UNKNOWN
    )
    
    return analysis
