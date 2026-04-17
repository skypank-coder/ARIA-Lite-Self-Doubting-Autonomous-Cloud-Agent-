import { useState, useRef, useEffect } from "react";

interface TopbarProps {
  elapsedMs: number | null;
  memoryCount: number;
  memoryTooltip: string | null;
}

export function Topbar({ elapsedMs, memoryCount, memoryTooltip }: TopbarProps) {
  const [showMemoryTooltip, setShowMemoryTooltip] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (tooltipRef.current && !tooltipRef.current.contains(e.target as Node)) {
        setShowMemoryTooltip(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div
      className="flex items-center justify-between px-4"
      style={{
        height: 44,
        background: "var(--aria-panel)",
        borderBottom: "1px solid var(--aria-border)",
        flexShrink: 0,
      }}
      data-testid="topbar"
    >
      <div className="flex items-center gap-3">
        <span
          className="font-bold text-white"
          style={{ fontSize: 18, fontFamily: "Inter, sans-serif", letterSpacing: "-0.5px" }}
          data-testid="wordmark"
        >
          ARIA-LITE<span style={{ color: "var(--aria-cyan)" }}>++</span>
        </span>
        <PillBadge label="SDACA v2" color="cyan" />
        <PillBadge label="RISK INTELLIGENCE" color="blue" />
        <PillBadge label="AWS TRACK" color="aws" />
        {memoryCount > 0 && (
          <div ref={tooltipRef} className="relative">
            <button
              className="flex items-center gap-1 px-2 py-0.5 rounded cursor-pointer"
              style={{
                fontSize: 10,
                fontFamily: "var(--app-font-mono)",
                color: "var(--aria-cyan)",
                border: "1px solid var(--aria-cyan)",
                background: "rgba(0,180,216,0.08)",
                letterSpacing: "0.05em",
              }}
              onClick={() => setShowMemoryTooltip(!showMemoryTooltip)}
              data-testid="memory-badge"
            >
              <span>◉</span>
              <span>MEMORY: {memoryCount} INCIDENT</span>
            </button>
            {showMemoryTooltip && memoryTooltip && (
              <div
                className="absolute top-8 left-0 z-50 rounded px-3 py-2 text-xs mono whitespace-nowrap"
                style={{
                  background: "#0F1923",
                  border: "1px solid var(--aria-cyan)",
                  color: "var(--aria-text)",
                  fontSize: 11,
                }}
                data-testid="memory-tooltip"
              >
                {memoryTooltip}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <StepBadge />
        {elapsedMs !== null && (
          <span
            className="mono"
            style={{ fontSize: 12, color: "var(--aria-muted)" }}
            data-testid="elapsed-ms"
          >
            {elapsedMs} MS
          </span>
        )}
        <span style={{ fontSize: 11, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif" }}>INNOVITUS 1.0</span>
        <div className="flex items-center gap-1">
          <span style={{ fontSize: 11, color: "var(--aria-muted)" }}>AWS TRACK</span>
          <AwsSmile />
        </div>
      </div>
    </div>
  );
}

function PillBadge({ label, color }: { label: string; color: "cyan" | "blue" | "aws" }) {
  const colorMap = {
    cyan: { border: "#00B4D8", text: "#00B4D8" },
    blue: { border: "#2D7DD2", text: "#2D7DD2" },
    aws: { border: "#FF9900", text: "#FF9900" },
  };
  const c = colorMap[color];
  return (
    <span
      className="px-2 py-0.5 rounded-full"
      style={{
        fontSize: 10,
        fontFamily: "Inter, sans-serif",
        fontWeight: 500,
        letterSpacing: "0.05em",
        border: `1px solid ${c.border}`,
        color: c.text,
      }}
    >
      {label}
    </span>
  );
}

function StepBadge() {
  return (
    <span
      className="px-2.5 py-0.5 rounded"
      style={{
        fontSize: 11,
        fontFamily: "Inter, sans-serif",
        fontWeight: 700,
        background: "var(--aria-cyan)",
        color: "#0F1923",
        letterSpacing: "0.04em",
      }}
      data-testid="step-badge"
    >
      STEP 5/5
    </span>
  );
}

function AwsSmile() {
  return (
    <svg width="18" height="18" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M29 64 Q50 76 71 64" stroke="#FF9900" strokeWidth="7" fill="none" strokeLinecap="round"/>
      <path d="M20 64 L29 64 L25 72 Z" fill="#FF9900"/>
      <path d="M80 64 L71 64 L75 72 Z" fill="#FF9900"/>
    </svg>
  );
}
