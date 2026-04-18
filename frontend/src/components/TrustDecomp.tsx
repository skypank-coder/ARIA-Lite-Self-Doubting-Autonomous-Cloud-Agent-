import { useEffect, useState, useRef } from "react";
import type { ARIAResponse } from "@/lib/presets";

interface TrustDecompProps {
  data: ARIAResponse | null;
  loading: boolean;
}

function valueColor(v: number): string {
  if (v >= 0.70) return "#1DB87A";
  if (v >= 0.40) return "#E07B2A";
  return "#CF3A3A";
}

function confidenceColor(v: number): string {
  if (v >= 0.80) return "#1DB87A";
  if (v >= 0.50) return "#E07B2A";
  return "#CF3A3A";
}

interface AnimatedBarProps {
  value: number;
  color: string;
  loading: boolean;
  delay?: number;
}

function AnimatedBar({ value, color, loading, delay = 0 }: AnimatedBarProps) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (loading) { setWidth(0); return; }
    const t = setTimeout(() => setWidth(value * 100), delay);
    return () => clearTimeout(t);
  }, [value, loading, delay]);

  if (loading) {
    return <div className="skeleton" style={{ height: 4, borderRadius: 2, width: "100%" }} />;
  }

  return (
    <div style={{ height: 4, borderRadius: 2, background: "var(--aria-border)", overflow: "hidden" }}>
      <div
        style={{
          height: "100%",
          width: `${width}%`,
          background: color,
          borderRadius: 2,
          transition: "width 1.2s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        }}
      />
    </div>
  );
}

interface CountUpProps {
  target: number;
  loading: boolean;
  color: string;
}

function CountUp({ target, loading, color }: CountUpProps) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (loading) { setDisplay(0); return; }
    const start = performance.now();
    const duration = 1000;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      setDisplay(progress * target);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(target);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, loading]);

  return (
    <span
      className="mono"
      style={{ fontSize: 56, fontWeight: 700, color, lineHeight: 1, letterSpacing: "-2px" }}
      data-testid="confidence-value"
    >
      {display.toFixed(2)}
    </span>
  );
}

export function TrustDecomp({ data, loading }: TrustDecompProps) {
  const bars = [
    { label: "INTENT SCORE", key: "intent_score", color: "#1DB87A" },
    { label: "REVERSIBILITY", key: "reversibility", color: "#2D7DD2" },
    { label: "BLAST RADIUS", key: "blast_radius", color: "#E07B2A" },
    { label: "POLICY SCORE", key: "policy_score", color: "#7B5CF0" },
  ] as const;

  const trust = data?.trust;
  const gate = data?.gate;

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{
        background: "var(--aria-panel)",
        border: "1px solid var(--aria-border)",
        borderRadius: 6,
      }}
      data-testid="trust-decomp"
    >
      <div className="px-3 pt-3 pb-2" style={{ borderBottom: "1px solid var(--aria-border)" }}>
        <span className="panel-header">Trust Decomposition</span>
      </div>

      <div className="flex flex-col gap-3 px-3 pt-3">
        {bars.map(({ label, key, color }, i) => {
          const val = trust ? (trust as Record<string, number>)[key] : 0;
          return (
            <div key={label}>
              <div className="flex justify-between items-center mb-1">
                <span className="panel-header">{label}</span>
                {loading ? (
                  <div className="skeleton" style={{ width: 36, height: 12 }} />
                ) : (
                  <span
                    className="mono"
                    style={{ fontSize: 12, color: key === "blast_radius" ? valueColor(1 - val) : valueColor(val) }}
                  >
                    {val.toFixed(2)}
                  </span>
                )}
              </div>
              <AnimatedBar value={val} color={color} loading={loading} delay={i * 150} />
            </div>
          );
        })}
      </div>

      <div className="px-3 pt-3" style={{ borderTop: "1px solid var(--aria-border)", marginTop: 12 }}>
        <span className="panel-header">Confidence</span>
        <div className="mt-1">
          {loading ? (
            <div className="skeleton" style={{ width: 100, height: 56 }} />
          ) : (
            <CountUp
              target={trust?.confidence ?? 0}
              loading={loading}
              color={confidenceColor(trust?.confidence ?? 0)}
            />
          )}
        </div>
        <div className="mt-1">
          <span
            className="mono"
            style={{ fontSize: 10, color: "var(--aria-cyan)" }}
            data-testid="confidence-formula"
          >
            C = I × R × (1-B) × P
          </span>
        </div>
      </div>

      {/* Confidence Timeline */}
      {!loading && data?.memory_timeline && (
        <ConfidenceTimeline
          timeline={data.memory_timeline
            .flatMap(e => e.history)
            .slice(-8)}
          penalty={data.memory?.penalty ?? 1.0}
        />
      )}

      <div className="px-3 pt-3 pb-3 flex-1">
        <span className="panel-header">Decision Gate</span>
        <div className="mt-2">
          {loading ? (
            <div className="skeleton" style={{ height: 72, borderRadius: 6 }} />
          ) : (
            <GateCard gate={gate ?? null} confidence={trust?.confidence ?? 0} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Confidence Timeline ──────────────────────────────────────────────────────

interface TimelineEntry {
  confidence: number;
  gate:       string;
  timestamp:  string;
}

function ConfidenceTimeline({ timeline, penalty }: { timeline: TimelineEntry[]; penalty: number }) {
  if (timeline.length < 2) return null;

  const W = 200, H = 72;
  const PAD = { t: 8, b: 16, l: 4, r: 4 };
  const iW = W - PAD.l - PAD.r;
  const iH = H - PAD.t - PAD.b;

  const GATE_COLOR: Record<string, string> = {
    AUTO:    "#1DB87A",
    APPROVE: "#E07B2A",
    BLOCK:   "#CF3A3A",
  };

  const xOf = (i: number) => PAD.l + (i / Math.max(timeline.length - 1, 1)) * iW;
  const yOf = (c: number) => PAD.t + (1 - c) * iH;

  const pts = timeline.map((e, i) => `${xOf(i)},${yOf(e.confidence)}`).join(" ");

  const y80 = yOf(0.80);
  const y50 = yOf(0.50);

  return (
    <div className="px-3 pb-2" style={{ borderTop: "1px solid var(--aria-border)", paddingTop: 8 }}>
      <div className="flex justify-between items-center mb-1">
        <span className="panel-header" style={{ fontSize: 9 }}>CONFIDENCE HISTORY</span>
        <span className="mono" style={{ fontSize: 9, color: "var(--aria-muted)" }}>
          {timeline.length} runs
        </span>
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
        {/* threshold lines */}
        <line x1={PAD.l} y1={y80} x2={W - PAD.r} y2={y80}
          stroke="#1DB87A" strokeWidth={0.5} strokeDasharray="3,3" opacity={0.4} />
        <line x1={PAD.l} y1={y50} x2={W - PAD.r} y2={y50}
          stroke="#E07B2A" strokeWidth={0.5} strokeDasharray="3,3" opacity={0.4} />
        {/* line */}
        <polyline points={pts} fill="none" stroke="#2D4A5E" strokeWidth={1.5} />
        {/* dots */}
        {timeline.map((e, i) => (
          <circle
            key={i}
            cx={xOf(i)} cy={yOf(e.confidence)}
            r={i === timeline.length - 1 ? 5 : 3}
            fill={GATE_COLOR[e.gate] ?? "#5A7080"}
          />
        ))}
        {/* latest value label */}
        <text
          x={W - PAD.r} y={yOf(timeline[timeline.length - 1].confidence) - 6}
          textAnchor="end" fill="#C9D6E3" fontSize={8}
          fontFamily="'JetBrains Mono', monospace"
        >
          {timeline[timeline.length - 1].confidence.toFixed(3)}
        </text>
      </svg>
      <div className="mono" style={{ fontSize: 9, color: "var(--aria-muted)", marginTop: 2 }}>
        memory penalty: ×{penalty.toFixed(2)}
      </div>
    </div>
  );
}


function GateCard({ gate, confidence }: { gate: "AUTO" | "APPROVE" | "BLOCK" | null; confidence: number }) {
  if (!gate) return null;

  const configs = {
    AUTO: {
      border: "#1DB87A",
      bg: "rgba(29,184,122,0.07)",
      label: "AUTO-EXECUTE",
      subtitle: "TRUST ≥ 0.80 — EXECUTING WITHOUT HUMAN APPROVAL",
      color: "#1DB87A",
      className: "",
    },
    APPROVE: {
      border: "#E07B2A",
      bg: "rgba(224,123,42,0.07)",
      label: "HUMAN APPROVAL REQUIRED",
      subtitle: "TRUST 0.50–0.79 — ROUTED TO 1-CLICK APPROVER",
      color: "#E07B2A",
      className: "",
    },
    BLOCK: {
      border: "#CF3A3A",
      bg: "rgba(207,58,58,0.07)",
      label: "HARD BLOCK",
      subtitle: "TRUST < 0.50 — REFUSED WITH STRUCTURED EXPLANATION",
      color: "#CF3A3A",
      className: "pulse-red",
    },
  };

  const c = configs[gate];

  return (
    <div
      className={`rounded p-3 fade-in ${c.className}`}
      style={{
        border: `1.5px solid ${c.border}`,
        background: c.bg,
        borderRadius: 6,
      }}
      data-testid="gate-card"
    >
      <div className="flex items-center gap-1">
        <span
          className="mono"
          style={{ fontSize: 15, fontWeight: 700, color: c.color }}
          data-testid="gate-label"
        >
          {c.label}
          {gate === "BLOCK" && <span className="blink ml-1">|</span>}
        </span>
      </div>
      <div
        className="mt-1"
        style={{ fontSize: 9, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif", letterSpacing: "0.05em" }}
        data-testid="gate-subtitle"
      >
        {c.subtitle}
      </div>
      <div className="mt-2">
        <span
          className="mono"
          style={{ fontSize: 11, color: c.color, opacity: 0.8 }}
        >
          CONF: {confidence.toFixed(2)}
        </span>
      </div>
    </div>
  );
}
