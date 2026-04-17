import { useEffect, useRef, useState } from "react";
import { GRAPH_CONFIGS, NODE_COLORS, type GraphNode, type GraphEdge } from "@/lib/graph-configs";
import { AwsServiceIconSvg } from "@/lib/aws-icons";

interface DependencyGraphProps {
  scenario: string;
  loading: boolean;
  viewMode: "graph" | "simulation";
  onViewChange: (v: "graph" | "simulation") => void;
  simulation: ARIASim[];
}

interface ARIASim {
  scenario: string;
  probability: number;
  detail: string;
}

function Arrow({ from, to, nodes }: { from: string; to: string; nodes: GraphNode[] }) {
  const fromNode = nodes.find(n => n.id === from);
  const toNode = nodes.find(n => n.id === to);
  if (!fromNode || !toNode) return null;

  const fr = fromNode.type === "source" ? 34 : 28;
  const tr = toNode.type === "source" ? 34 : 28;

  const dx = toNode.x - fromNode.x;
  const dy = toNode.y - fromNode.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist === 0) return null;

  const nx = dx / dist;
  const ny = dy / dist;
  const x1 = fromNode.x + nx * (fr + 2);
  const y1 = fromNode.y + ny * (fr + 2);
  const x2 = toNode.x - nx * (tr + 2);
  const y2 = toNode.y - ny * (tr + 2);

  const arrowSize = 7;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const ax1 = x2 - arrowSize * Math.cos(angle - Math.PI / 6);
  const ay1 = y2 - arrowSize * Math.sin(angle - Math.PI / 6);
  const ax2 = x2 - arrowSize * Math.cos(angle + Math.PI / 6);
  const ay2 = y2 - arrowSize * Math.sin(angle + Math.PI / 6);

  return (
    <g opacity={0.6}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2D4A5E" strokeWidth={1.5} />
      <polygon points={`${x2},${y2} ${ax1},${ay1} ${ax2},${ay2}`} fill="#2D4A5E" />
    </g>
  );
}

function NodeCircle({ node, visible }: { node: GraphNode; visible: boolean }) {
  const r = node.type === "source" ? 34 : 28;
  const color = NODE_COLORS[node.type];
  const isCritical = node.type === "critical";
  const iconSize = r === 34 ? 22 : 18;

  return (
    <g
      style={{
        opacity: visible ? 1 : 0,
        transition: "opacity 0.5s ease",
      }}
    >
      {isCritical && (
        <circle
          cx={node.x}
          cy={node.y}
          r={r + 10}
          fill="none"
          stroke={color}
          strokeWidth={0.8}
          opacity={0.25}
          className="pulse-red"
        />
      )}
      <circle
        cx={node.x}
        cy={node.y}
        r={r}
        fill="#16202B"
        stroke={color}
        strokeWidth={node.type === "source" ? 2.5 : 1.8}
      />
      <AwsServiceIconSvg service={node.service} cx={node.x} cy={node.y} size={iconSize} />
      <text
        x={node.x}
        y={node.y + r + 14}
        textAnchor="middle"
        fill="#5A7080"
        fontSize={9}
        fontFamily="'JetBrains Mono', monospace"
        fontWeight="500"
      >
        {node.label}
      </text>
    </g>
  );
}

export function DependencyGraph({ scenario, loading, viewMode, onViewChange, simulation }: DependencyGraphProps) {
  const [visibleWaves, setVisibleWaves] = useState<number[]>([]);
  const [waveCounter, setWaveCounter] = useState(0);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const config = GRAPH_CONFIGS[scenario] || GRAPH_CONFIGS.s3_create;

  useEffect(() => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    setVisibleWaves([]);
    setWaveCounter(0);

    if (loading) return;

    let count = 0;
    const schedule = (wave: number, delay: number) => {
      const t = setTimeout(() => {
        setVisibleWaves(prev => [...prev, wave]);
        count++;
        setWaveCounter(count);
      }, delay);
      timeoutsRef.current.push(t);
    };

    schedule(1, 100);
    schedule(2, 500);
    schedule(3, 900);

    return () => timeoutsRef.current.forEach(clearTimeout);
  }, [scenario, loading]);

  const nodePad = 52;
  const minX = Math.min(...config.nodes.map(n => n.x)) - nodePad;
  const maxX = Math.max(...config.nodes.map(n => n.x)) + nodePad;
  const minY = Math.min(...config.nodes.map(n => n.y)) - nodePad;
  const maxY = Math.max(...config.nodes.map(n => n.y)) + nodePad + 16;

  const viewBoxW = Math.max(maxX - minX, 400);
  const viewBoxH = Math.max(maxY - minY, 220);
  const viewBox = `${minX} ${minY} ${viewBoxW} ${viewBoxH}`;

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
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}
      >
        <div className="flex items-center gap-3">
          <span className="panel-header">Dependency Graph — Execution Propagation</span>
          {!loading && (
            <span className="mono" style={{ fontSize: 9, color: "var(--aria-cyan)", letterSpacing: "0.12em" }}>
              WAVE {Math.min(waveCounter, 3)}/3
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {(["graph", "simulation"] as const).map(v => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              style={{
                fontSize: 9,
                fontFamily: "Inter, sans-serif",
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: viewMode === v ? "#0F1923" : "var(--aria-muted)",
                background: viewMode === v ? "var(--aria-cyan)" : "transparent",
                border: `1px solid ${viewMode === v ? "var(--aria-cyan)" : "var(--aria-border)"}`,
                borderRadius: 4,
                padding: "2px 8px",
                cursor: "pointer",
              }}
              data-testid={`view-${v}`}
            >
              {v === "graph" ? "Graph View" : "Simulation View"}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {loading ? (
          <div className="flex items-center justify-center flex-1">
            <span className="mono" style={{ fontSize: 12, color: "var(--aria-muted)", letterSpacing: "0.15em" }}>
              COMPUTING...
            </span>
          </div>
        ) : viewMode === "graph" ? (
          <>
            <div style={{ flex: 1, minHeight: 0 }}>
              <svg
                width="100%"
                height="100%"
                viewBox={viewBox}
                preserveAspectRatio="xMidYMid meet"
              >
                {config.edges.map((e: GraphEdge, i: number) => (
                  <Arrow key={i} from={e.from} to={e.to} nodes={config.nodes} />
                ))}
                {config.nodes.map((n: GraphNode) => (
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

function GraphLegend() {
  const items = [
    { color: "#00B4D8", label: "SOURCE" },
    { color: "#2D7DD2", label: "COMPUTE" },
    { color: "#CF3A3A", label: "CRITICAL" },
    { color: "#1DB87A", label: "ACTIVE" },
  ];
  return (
    <div
      className="flex items-center gap-5 px-4 py-2"
      style={{ borderTop: "1px solid var(--aria-border)", flexShrink: 0 }}
    >
      {items.map(({ color, label }) => (
        <div key={label} className="flex items-center gap-1.5">
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{
            fontSize: 9,
            color: "var(--aria-muted)",
            fontFamily: "Inter, sans-serif",
            fontWeight: 500,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

function SimulationView({ simulations }: { simulations: ARIASim[] }) {
  const colors = ["#1DB87A", "#1DB87A", "#E07B2A", "#E07B2A", "#CF3A3A"];
  const [widths, setWidths] = useState<number[]>(simulations.map(() => 0));

  useEffect(() => {
    setWidths(simulations.map(() => 0));
    const t = setTimeout(() => setWidths(simulations.map(s => s.probability)), 150);
    return () => clearTimeout(t);
  }, [simulations]);

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
      {simulations.map((sim, i) => (
        <div key={i} className="fade-in" style={{ animationDelay: `${i * 80}ms` }}>
          <div className="flex items-center justify-between mb-1.5">
            <span
              className="mono"
              style={{
                fontSize: 10,
                color: "var(--aria-text)",
                flex: 1,
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                paddingRight: 10,
              }}
            >
              {sim.scenario}
            </span>
            <span className="mono flex-shrink-0" style={{ fontSize: 11, color: colors[i] || "#5A7080", fontWeight: 700 }}>
              {sim.probability}%
            </span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: "var(--aria-border)", overflow: "hidden", marginBottom: 5 }}>
            <div
              style={{
                height: "100%",
                width: `${widths[i]}%`,
                background: colors[i] || "#5A7080",
                borderRadius: 2,
                transition: "width 0.9s cubic-bezier(0.25,0.46,0.45,0.94)",
              }}
            />
          </div>
          <span style={{ fontSize: 10, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif" }}>
            {sim.detail}
          </span>
        </div>
      ))}
    </div>
  );
}
