import { useEffect, useRef, useState, useMemo } from "react";
import { NODE_COLORS } from "@/lib/graph-configs";
import { AwsServiceIconSvg } from "@/lib/aws-icons";
import type { ARIAResponse } from "@/lib/presets";

interface DependencyGraphProps {
  data: ARIAResponse | null;
  loading: boolean;
  viewMode: "graph" | "simulation";
  onViewChange: (v: "graph" | "simulation") => void;
}

interface ARIASim {
  scenario: string;
  probability: number;
  detail: string;
  type?: string;
  color?: string;
}

// ── Dynamic layout ────────────────────────────────────────────────────────────

interface LayoutNode {
  id: string;
  label: string;
  service: string;
  type: string;
  wave: number;
  x: number;
  y: number;
}

const NODE_TYPE_MAP: Record<string, string> = {
  core:       "source",
  network:    "compute",
  gateway:    "compute",
  compute:    "compute",
  storage:    "active",
  database:   "critical",
  edge:       "active",
  monitoring: "active",
  messaging:  "active",
  system:     "compute",
};

const SERVICE_LABELS: Record<string, string> = {
  s3: "S3", ec2: "EC2", iam: "IAM", rds: "RDS", lambda: "Lambda",
  alb: "ALB", cloudwatch: "CloudWatch", cloudfront: "CloudFront",
  sns: "SNS", api: "API GW", autoscaling: "AutoScale",
  lambda_fn: "Lambda", secrets: "Secrets Mgr", vpc: "VPC", kms: "KMS",
};

function buildLayout(
  nodes: Array<{ id: string; type: string; wave?: number }>,
  _edges: Array<{ from: string; to: string }>,
  W: number,
  H: number,
): { layoutNodes: LayoutNode[]; viewBox: string } {
  if (!nodes.length) return { layoutNodes: [], viewBox: "0 0 400 260" };

  // Hard cap at 5 nodes
  const capped = nodes.slice(0, 5);

  // Group by wave for top-bottom layout
  const waveMap: Record<number, string[]> = {};
  for (const n of capped) {
    const w = n.wave ?? 2;
    (waveMap[w] = waveMap[w] ?? []).push(n.id);
  }
  const waves = Object.keys(waveMap).map(Number).sort();

  const PAD   = 48;
  const nodeR = 28;
  const xGap  = 90;   // horizontal spacing between siblings
  const yGap  = 100;  // vertical spacing between waves

  const positions: Record<string, { x: number; y: number }> = {};

  waves.forEach((wave, wi) => {
    const ids = waveMap[wave];
    const totalW = (ids.length - 1) * xGap;
    const startX = W / 2 - totalW / 2;
    const y = PAD + wi * yGap;
    ids.forEach((id, i) => {
      positions[id] = { x: startX + i * xGap, y };
    });
  });

  const layoutNodes: LayoutNode[] = capped.map(n => ({
    id:      n.id,
    label:   SERVICE_LABELS[n.id] ?? n.id.toUpperCase(),
    service: n.id,
    type:    NODE_TYPE_MAP[n.type] ?? "active",
    wave:    n.wave ?? 2,
    x:       positions[n.id]?.x ?? W / 2,
    y:       positions[n.id]?.y ?? H / 2,
  }));

  const allX = layoutNodes.map(n => n.x);
  const allY = layoutNodes.map(n => n.y);
  const minX = Math.min(...allX) - PAD;
  const maxX = Math.max(...allX) + PAD;
  const minY = Math.min(...allY) - PAD;
  const maxY = Math.max(...allY) + nodeR + PAD + 16;

  const vbW = Math.max(maxX - minX, 280);
  const vbH = Math.max(maxY - minY, 180);

  return { layoutNodes, viewBox: `${minX} ${minY} ${vbW} ${vbH}` };
}

// ── Arrow ─────────────────────────────────────────────────────────────────────

function Arrow({ from, to, nodes }: { from: string; to: string; nodes: LayoutNode[] }) {
  const fn = nodes.find(n => n.id === from);
  const tn = nodes.find(n => n.id === to);
  if (!fn || !tn) return null;

  const fr = fn.type === "source" ? 34 : 28;
  const tr = tn.type === "source" ? 34 : 28;
  const dx = tn.x - fn.x, dy = tn.y - fn.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist === 0) return null;

  const nx = dx / dist, ny = dy / dist;
  const x1 = fn.x + nx * (fr + 2), y1 = fn.y + ny * (fr + 2);
  const x2 = tn.x - nx * (tr + 2), y2 = tn.y - ny * (tr + 2);
  const sz = 7, angle = Math.atan2(y2 - y1, x2 - x1);
  const ax1 = x2 - sz * Math.cos(angle - Math.PI / 6);
  const ay1 = y2 - sz * Math.sin(angle - Math.PI / 6);
  const ax2 = x2 - sz * Math.cos(angle + Math.PI / 6);
  const ay2 = y2 - sz * Math.sin(angle + Math.PI / 6);

  return (
    <g opacity={0.6}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2D4A5E" strokeWidth={1.5} />
      <polygon points={`${x2},${y2} ${ax1},${ay1} ${ax2},${ay2}`} fill="#2D4A5E" />
    </g>
  );
}

// ── Node ──────────────────────────────────────────────────────────────────────

function NodeCircle({ node, visible }: { node: LayoutNode; visible: boolean }) {
  const r = node.type === "source" ? 34 : 28;
  const color = (NODE_COLORS as Record<string, string>)[node.type] ?? "#5A7080";
  const isCritical = node.type === "critical";

  return (
    <g style={{ opacity: visible ? 1 : 0, transition: "opacity 0.5s ease" }}>
      {isCritical && (
        <circle cx={node.x} cy={node.y} r={r + 10}
          fill="none" stroke={color} strokeWidth={0.8} opacity={0.25} className="pulse-red" />
      )}
      <circle cx={node.x} cy={node.y} r={r}
        fill="#16202B" stroke={color} strokeWidth={node.type === "source" ? 2.5 : 1.8} />
      <AwsServiceIconSvg service={node.service} cx={node.x} cy={node.y} size={node.type === "source" ? 22 : 18} />
      <text x={node.x} y={node.y + r + 14} textAnchor="middle"
        fill="#5A7080" fontSize={9} fontFamily="'JetBrains Mono', monospace" fontWeight="500">
        {node.label}
      </text>
    </g>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function DependencyGraph({ data, loading, viewMode, onViewChange }: DependencyGraphProps) {
  const [visibleWaves, setVisibleWaves] = useState<number[]>([]);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 480, h: 320 });

  // Measure container
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDims({ w: width, h: height });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Build layout from live graph data
  const rawNodes = data?.graph?.nodes ?? [];
  const rawEdges = data?.graph?.edges ?? [];

  const { layoutNodes, viewBox } = useMemo(
    () => buildLayout(rawNodes, rawEdges, dims.w, dims.h),
    [rawNodes, rawEdges, dims.w, dims.h],
  );

  // Wave animation — re-trigger when graph changes
  const graphKey = rawNodes.map(n => n.id).join(",");
  useEffect(() => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    setVisibleWaves([]);
    setWaveCounter(0);
    if (loading || !rawNodes.length) return;

    let count = 0;
    [1, 2, 3].forEach((wave, i) => {
      const t = setTimeout(() => {
        setVisibleWaves(prev => [...prev, wave]);
        count++;
      }, i * 400 + 100);
      timeoutsRef.current.push(t);
    });
    return () => timeoutsRef.current.forEach(clearTimeout);
  }, [graphKey, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const simulation: ARIASim[] = data?.simulation ?? [];
  const nodeCount = layoutNodes.length;

  return (
    <div
      className="flex flex-col h-full"
      style={{
        background: "var(--aria-panel)",
        border: "1px solid var(--aria-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
      data-testid="dependency-graph"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}>
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-3">
            <span className="panel-header">Impact Propagation Graph</span>
            {!loading && nodeCount > 0 && (
              <span className="mono" style={{ fontSize: 9, color: "var(--aria-cyan)", letterSpacing: "0.12em" }}>
                {nodeCount} NODES
              </span>
            )}
          </div>
          {!loading && data?.graph?.explanation && (
            <span style={{ fontSize: 10, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif", fontStyle: "italic" }}>
              {data.graph.explanation}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {(["graph", "simulation"] as const).map(v => (
            <button key={v} onClick={() => onViewChange(v)}
              style={{
                fontSize: 9, fontFamily: "Inter, sans-serif", fontWeight: 600,
                letterSpacing: "0.08em", textTransform: "uppercase",
                color: viewMode === v ? "#0F1923" : "var(--aria-muted)",
                background: viewMode === v ? "var(--aria-cyan)" : "transparent",
                border: `1px solid ${viewMode === v ? "var(--aria-cyan)" : "var(--aria-border)"}`,
                borderRadius: 4, padding: "2px 8px", cursor: "pointer",
              }}
              data-testid={`view-${v}`}
            >
              {v === "graph" ? "Graph View" : "Simulation"}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {loading ? (
          <div className="flex items-center justify-center flex-1">
            <span className="mono" style={{ fontSize: 12, color: "var(--aria-muted)", letterSpacing: "0.15em" }}>
              COMPUTING...
            </span>
          </div>
        ) : viewMode === "graph" ? (
          <>
            <div ref={containerRef} style={{ flex: 1, minHeight: 0, display: "flex", justifyContent: "center" }}>
              <svg
                width="100%"
                height="100%"
                viewBox={viewBox}
                preserveAspectRatio="xMidYMid meet"
                style={{ maxWidth: 500 }}
              >
                {rawEdges.map((e, i) => (
                  <Arrow key={i} from={e.from} to={e.to} nodes={layoutNodes} />
                ))}
                {layoutNodes.map(n => (
                  <NodeCircle key={n.id} node={n} visible={visibleWaves.includes(n.wave)} />
                ))}
              </svg>
            </div>
            <GraphLegend />
          </>
        ) : (
          <SimulationView simulations={simulation} />
        )}
      </div>
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function GraphLegend() {
  return (
    <div className="flex items-center gap-5 px-4 py-2"
      style={{ borderTop: "1px solid var(--aria-border)", flexShrink: 0 }}>
      {[
        { color: "#00B4D8", label: "SOURCE" },
        { color: "#2D7DD2", label: "COMPUTE" },
        { color: "#CF3A3A", label: "CRITICAL" },
        { color: "#1DB87A", label: "ACTIVE" },
      ].map(({ color, label }) => (
        <div key={label} className="flex items-center gap-1.5">
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{ fontSize: 9, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif",
            fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Simulation view ───────────────────────────────────────────────────────────

const SIM_COLORS: Record<string, string> = {
  success:           "#1DB87A",
  degraded:          "#E07B2A",
  cascading_failure: "#CF3A3A",
  rollback:          "#7B5CF0",
};

function SimulationView({ simulations }: { simulations: ARIASim[] }) {
  const [widths, setWidths] = useState<number[]>(simulations.map(() => 0));

  useEffect(() => {
    setWidths(simulations.map(() => 0));
    const t = setTimeout(() => setWidths(simulations.map(s => s.probability)), 150);
    return () => clearTimeout(t);
  }, [simulations]);

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
      {simulations.map((sim, i) => {
        const color = sim.color ?? SIM_COLORS[sim.type ?? ""] ?? "#5A7080";
        return (
          <div key={i} className="fade-in" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="mono" style={{ fontSize: 11, color: "var(--aria-text)", flex: 1,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 10 }}>
                {sim.scenario}
              </span>
              <span className="mono flex-shrink-0" style={{ fontSize: 13, color, fontWeight: 700 }}>
                {sim.probability}%
              </span>
            </div>
            <div style={{ height: 5, borderRadius: 3, background: "var(--aria-border)",
              overflow: "hidden", marginBottom: 5 }}>
              <div style={{
                height: "100%", width: `${widths[i]}%`, background: color,
                borderRadius: 3, transition: "width 0.9s cubic-bezier(0.25,0.46,0.45,0.94)",
              }} />
            </div>
            <span style={{ fontSize: 11, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif" }}>
              {sim.detail}
            </span>
          </div>
        );
      })}
    </div>
  );
}
