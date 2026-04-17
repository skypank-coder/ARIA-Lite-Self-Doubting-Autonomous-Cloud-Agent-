export function AwsServiceIconSvg({ service, cx, cy, size = 18 }: { service: string; cx: number; cy: number; size?: number }) {
  const h = size / 2;
  const x = cx - h;
  const y = cy - h;

  switch (service) {
    case "s3":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <polygon points={`0,${-h} ${h},${-h*0.4} ${h},${h*0.4} 0,${h} ${-h},${h*0.4} ${-h},${-h*0.4}`} fill="#3F8624" opacity="0.25"/>
          <polygon points={`0,${-h} ${h},${-h*0.4} 0,0 ${-h},${-h*0.4}`} fill="#5AB333"/>
          <polygon points={`${-h},${-h*0.4} 0,0 0,${h} ${-h},${h*0.4}`} fill="#277C1A"/>
          <polygon points={`${h},${-h*0.4} 0,0 0,${h} ${h},${h*0.4}`} fill="#3F8624"/>
          <text textAnchor="middle" dy="3" fill="white" fontSize={size * 0.32} fontWeight="700" fontFamily="Inter, sans-serif">S3</text>
        </g>
      );
    case "ec2":
      return (
        <g transform={`translate(${x}, ${y})`}>
          <rect x="1" y="1" width={size - 2} height={size - 2} rx="2.5" fill="#ED7100" opacity="0.2" stroke="#ED7100" strokeWidth="1.2"/>
          <text x={h} y={h + 3} textAnchor="middle" fill="#ED7100" fontSize={size * 0.32} fontWeight="700" fontFamily="Inter, sans-serif">EC2</text>
        </g>
      );
    case "iam":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <circle cx={0} cy={-h * 0.35} r={h * 0.42} fill="#DD344C" opacity="0.9"/>
          <path d={`M${-h} ${h*0.6} Q${-h} 0 0 0 Q${h} 0 ${h} ${h*0.6}`} stroke="#DD344C" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </g>
      );
    case "rds":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <ellipse cx={0} cy={-h * 0.5} rx={h} ry={h * 0.3} fill="#527FFF" opacity="0.25" stroke="#527FFF" strokeWidth="1.2"/>
          <line x1={-h} y1={-h * 0.5} x2={-h} y2={h * 0.5} stroke="#527FFF" strokeWidth="1.2"/>
          <line x1={h} y1={-h * 0.5} x2={h} y2={h * 0.5} stroke="#527FFF" strokeWidth="1.2"/>
          <ellipse cx={0} cy={h * 0.5} rx={h} ry={h * 0.3} fill="#527FFF" opacity="0.25" stroke="#527FFF" strokeWidth="1.2"/>
          <ellipse cx={0} cy={0} rx={h} ry={h * 0.3} fill="#16202B" stroke="#527FFF" strokeWidth="1.2"/>
          <text textAnchor="middle" dy="3" fill="#527FFF" fontSize={size * 0.3} fontWeight="700" fontFamily="Inter, sans-serif">RDS</text>
        </g>
      );
    case "lambda":
      return (
        <g transform={`translate(${x}, ${y})`}>
          <rect x="1" y="1" width={size - 2} height={size - 2} rx="3" fill="#FF9900" opacity="0.15"/>
          <text x={h} y={h * 1.1} textAnchor="middle" fill="#FF9900" fontSize={size * 0.55} fontWeight="700" fontFamily="serif">λ</text>
        </g>
      );
    case "elb":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <rect x={-h} y={-h * 0.25} width={size} height={h * 0.5} rx={h * 0.25} fill="#8C4FFF" opacity="0.2" stroke="#8C4FFF" strokeWidth="1.2"/>
          <circle cx={-h * 0.55} cy={0} r={h * 0.2} fill="#8C4FFF"/>
          <circle cx={0} cy={0} r={h * 0.2} fill="#8C4FFF"/>
          <circle cx={h * 0.55} cy={0} r={h * 0.2} fill="#8C4FFF"/>
          <text textAnchor="middle" dy={h * 0.65} fill="#8C4FFF" fontSize={size * 0.27} fontWeight="700" fontFamily="Inter, sans-serif">ALB</text>
        </g>
      );
    case "cloudwatch":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <circle cx={0} cy={0} r={h} fill="none" stroke="#FF4F8B" strokeWidth="1.2" opacity="0.4"/>
          <polyline points={`${-h*0.65},${h*0.2} ${-h*0.3},${-h*0.2} 0,${h*0.1} ${h*0.3},${-h*0.4} ${h*0.65},0`} stroke="#FF4F8B" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </g>
      );
    case "secretsmanager":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <rect x={-h * 0.7} y={-h * 0.1} width={h * 1.4} height={h * 0.9} rx={2} fill="#DD344C" opacity="0.2" stroke="#DD344C" strokeWidth="1.2"/>
          <path d={`M${-h*0.45} ${-h*0.1} V${-h*0.5} a${h*0.45} ${h*0.45} 0 0 1 ${h*0.9} 0 V${-h*0.1}`} stroke="#DD344C" strokeWidth="1.2" fill="none" strokeLinecap="round"/>
          <circle cx={0} cy={h * 0.3} r={h * 0.18} fill="#DD344C"/>
        </g>
      );
    case "cloudfront":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <circle cx={0} cy={0} r={h} fill="none" stroke="#8C4FFF" strokeWidth="1.2" opacity="0.5"/>
          <ellipse cx={0} cy={0} rx={h * 0.42} ry={h} fill="none" stroke="#8C4FFF" strokeWidth="1.2"/>
          <line x1={-h} y1={0} x2={h} y2={0} stroke="#8C4FFF" strokeWidth="1.2" opacity="0.6"/>
        </g>
      );
    case "elasticache":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <ellipse cx={0} cy={-h * 0.4} rx={h * 0.8} ry={h * 0.28} fill="#3F8624" opacity="0.2" stroke="#3F8624" strokeWidth="1.2"/>
          <line x1={-h * 0.8} y1={-h * 0.4} x2={-h * 0.8} y2={h * 0.4} stroke="#3F8624" strokeWidth="1.2"/>
          <line x1={h * 0.8} y1={-h * 0.4} x2={h * 0.8} y2={h * 0.4} stroke="#3F8624" strokeWidth="1.2"/>
          <ellipse cx={0} cy={h * 0.4} rx={h * 0.8} ry={h * 0.28} fill="#3F8624" opacity="0.2" stroke="#3F8624" strokeWidth="1.2"/>
        </g>
      );
    case "apigateway":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <rect x={-h} y={-h * 0.7} width={size} height={h * 1.4} rx={2.5} fill="#FF4F8B" opacity="0.12" stroke="#FF4F8B" strokeWidth="1.2"/>
          <text textAnchor="middle" dy="2" fill="#FF4F8B" fontSize={size * 0.28} fontWeight="700" fontFamily="Inter, sans-serif">API</text>
          <text textAnchor="middle" dy={h * 0.65} fill="#FF4F8B" fontSize={size * 0.24} fontWeight="600" fontFamily="Inter, sans-serif">GW</text>
        </g>
      );
    case "dynamodb":
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <ellipse cx={0} cy={-h * 0.5} rx={h * 0.75} ry={h * 0.28} fill="#527FFF" opacity="0.25" stroke="#527FFF" strokeWidth="1.2"/>
          <line x1={-h * 0.75} y1={-h * 0.5} x2={-h * 0.75} y2={h * 0.5} stroke="#527FFF" strokeWidth="1.2"/>
          <line x1={h * 0.75} y1={-h * 0.5} x2={h * 0.75} y2={h * 0.5} stroke="#527FFF" strokeWidth="1.2"/>
          <ellipse cx={0} cy={h * 0.5} rx={h * 0.75} ry={h * 0.28} fill="#527FFF" opacity="0.25" stroke="#527FFF" strokeWidth="1.2"/>
          <ellipse cx={0} cy={0} rx={h * 0.75} ry={h * 0.28} fill="#16202B" stroke="#527FFF" strokeWidth="1.2"/>
          <text textAnchor="middle" dy="3" fill="#527FFF" fontSize={size * 0.3} fontWeight="700" fontFamily="Inter, sans-serif">DDB</text>
        </g>
      );
    default:
      return (
        <g transform={`translate(${cx}, ${cy})`}>
          <rect x={-h} y={-h} width={size} height={size} rx={2} fill="#5A7080" opacity="0.2" stroke="#5A7080" strokeWidth="1"/>
          <text textAnchor="middle" dy="3" fill="#5A7080" fontSize={size * 0.32} fontWeight="700" fontFamily="Inter, sans-serif">
            {service.substring(0, 3).toUpperCase()}
          </text>
        </g>
      );
  }
}
