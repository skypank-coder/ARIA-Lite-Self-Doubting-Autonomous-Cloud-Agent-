export type NodeType = "source" | "compute" | "critical" | "active";

export interface GraphNode {
  id: string;
  label: string;
  service: string;
  type: NodeType;
  x: number;
  y: number;
  wave: 1 | 2 | 3;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface GraphConfig {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const GRAPH_CONFIGS: Record<string, GraphConfig> = {
  s3_create: {
    nodes: [
      { id: "s3", label: "S3", service: "s3", type: "source", x: 80, y: 160, wave: 1 },
      { id: "cloudfront", label: "CloudFront", service: "cloudfront", type: "compute", x: 310, y: 80, wave: 2 },
      { id: "lambda", label: "Lambda", service: "lambda", type: "active", x: 310, y: 240, wave: 3 },
    ],
    edges: [
      { from: "s3", to: "cloudfront" },
      { from: "s3", to: "lambda" },
    ],
  },
  iam_delete: {
    nodes: [
      { id: "iam", label: "IAM Role", service: "iam", type: "source", x: 70, y: 190, wave: 1 },
      { id: "ec2", label: "EC2", service: "ec2", type: "critical", x: 250, y: 50, wave: 2 },
      { id: "rds", label: "RDS", service: "rds", type: "critical", x: 250, y: 110, wave: 2 },
      { id: "lambda", label: "Lambda", service: "lambda", type: "critical", x: 250, y: 170, wave: 2 },
      { id: "alb", label: "ALB", service: "elb", type: "critical", x: 250, y: 230, wave: 3 },
      { id: "cw", label: "CloudWatch", service: "cloudwatch", type: "critical", x: 250, y: 290, wave: 3 },
      { id: "sm", label: "Secrets Mgr", service: "secretsmanager", type: "critical", x: 250, y: 350, wave: 3 },
    ],
    edges: [
      { from: "iam", to: "ec2" },
      { from: "iam", to: "rds" },
      { from: "iam", to: "lambda" },
      { from: "iam", to: "alb" },
      { from: "iam", to: "cw" },
      { from: "iam", to: "sm" },
    ],
  },
  iam_attach: {
    nodes: [
      { id: "iam", label: "IAM Role", service: "iam", type: "source", x: 80, y: 160, wave: 1 },
      { id: "ec2", label: "Dev EC2", service: "ec2", type: "compute", x: 290, y: 80, wave: 2 },
      { id: "s3dev", label: "S3-Dev", service: "s3", type: "active", x: 290, y: 180, wave: 2 },
      { id: "lambda", label: "Dev Lambda", service: "lambda", type: "active", x: 290, y: 280, wave: 3 },
    ],
    edges: [
      { from: "iam", to: "ec2" },
      { from: "iam", to: "s3dev" },
      { from: "iam", to: "lambda" },
    ],
  },
  ec2_scale: {
    nodes: [
      { id: "ec2", label: "EC2 Fleet", service: "ec2", type: "source", x: 60, y: 160, wave: 1 },
      { id: "alb", label: "ALB", service: "elb", type: "compute", x: 190, y: 160, wave: 2 },
      { id: "rds", label: "RDS Primary", service: "rds", type: "critical", x: 320, y: 100, wave: 2 },
      { id: "cache", label: "ElastiCache", service: "elasticache", type: "active", x: 320, y: 220, wave: 3 },
      { id: "cw", label: "CloudWatch", service: "cloudwatch", type: "active", x: 420, y: 160, wave: 3 },
    ],
    edges: [
      { from: "ec2", to: "alb" },
      { from: "alb", to: "rds" },
      { from: "alb", to: "cache" },
      { from: "rds", to: "cw" },
    ],
  },
  rds_modify: {
    nodes: [
      { id: "rds", label: "RDS Primary", service: "rds", type: "source", x: 80, y: 160, wave: 1 },
      { id: "app", label: "App Server", service: "ec2", type: "compute", x: 240, y: 100, wave: 2 },
      { id: "reports", label: "Lambda Reports", service: "lambda", type: "active", x: 240, y: 240, wave: 2 },
      { id: "cw", label: "CloudWatch", service: "cloudwatch", type: "active", x: 390, y: 160, wave: 3 },
    ],
    edges: [
      { from: "rds", to: "app" },
      { from: "rds", to: "reports" },
      { from: "app", to: "cw" },
    ],
  },
  lambda_deploy: {
    nodes: [
      { id: "lambda", label: "Lambda", service: "lambda", type: "source", x: 80, y: 160, wave: 1 },
      { id: "apigw", label: "API Gateway", service: "apigateway", type: "compute", x: 240, y: 160, wave: 2 },
      { id: "dynamo", label: "DynamoDB", service: "dynamodb", type: "active", x: 390, y: 100, wave: 3 },
      { id: "cw", label: "CloudWatch", service: "cloudwatch", type: "active", x: 390, y: 240, wave: 3 },
    ],
    edges: [
      { from: "lambda", to: "apigw" },
      { from: "apigw", to: "dynamo" },
      { from: "apigw", to: "cw" },
    ],
  },
};

export const NODE_COLORS: Record<NodeType, string> = {
  source: "#00B4D8",
  compute: "#2D7DD2",
  critical: "#CF3A3A",
  active: "#1DB87A",
};
