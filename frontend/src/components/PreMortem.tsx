import { useEffect, useState } from "react";
import type { ARIAResponse } from "@/lib/presets";

interface PreMortemProps {
  data: ARIAResponse | null;
  loading: boolean;
}

function sevColor(sev: number): string {
  if (sev >= 5) return "#CF3A3A";
  if (sev >= 4) return "#CF3A3A";
  if (sev >= 3) return "#E07B2A";
  if (sev >= 2) return "#E07B2A";
  return "#1DB87A";
}

export function PreMortem({ data, loading }: PreMortemProps) {
  const [visible, setVisible] = useState<number[]>([]);

  useEffect(() => {
    setVisible([]);
    if (loading || !data) return;

    const timers = [0, 150, 300].map((d, i) =>
      setTimeout(() => setVisible(prev => [...prev, i]), d)
    );
    return () => timers.forEach(clearTimeout);
  }, [data, loading]);

  const premortem = data?.premortem ?? [];

  return (
    <div
      className="flex flex-col h-full"
      style={{
        background: "var(--aria-panel)",
        border: "1px solid var(--aria-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
      data-testid="pre-mortem"
    >
      <div
        className="px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}
      >
        <span className="panel-header">Pre-Mortem Analysis</span>
      </div>
      <div className="flex flex-col gap-2 px-3 py-2 overflow-y-auto flex-1">
        {loading ? (
          <>
            {[0, 1, 2].map(i => (
              <div key={i} className="skeleton" style={{ height: 72, borderRadius: 6 }} />
            ))}
          </>
        ) : (
          premortem.map((item, i) => (
            <FailureCard
              key={i}
              item={item}
              visible={visible.includes(i)}
            />
          ))
        )}
      </div>
    </div>
  );
}

interface FailureCardItem {
  severity: number;
  title: string;
  probability: number;
  mitigation: string;
  impacted_deps: number;
}

function FailureCard({ item, visible }: { item: FailureCardItem; visible: boolean }) {
  const color = sevColor(item.severity);

  return (
    <div
      className="rounded p-2.5"
      style={{
        border: `1px solid var(--aria-border)`,
        background: "rgba(15,25,35,0.5)",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateX(0)" : "translateX(30px)",
        transition: "opacity 0.35s ease, transform 0.35s ease",
        borderRadius: 6,
      }}
      data-testid="failure-card"
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span
            className="px-1.5 py-0.5 rounded flex-shrink-0"
            style={{
              fontSize: 9,
              fontWeight: 700,
              fontFamily: "Inter, sans-serif",
              background: color,
              color: "#fff",
              letterSpacing: "0.05em",
            }}
          >
            SEV{item.severity}
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--aria-text)",
              fontFamily: "Inter, sans-serif",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            data-testid="failure-title"
          >
            {item.title}
          </span>
        </div>
        <span
          className="flex-shrink-0"
          style={{ fontSize: 10, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif" }}
        >
          {item.probability}% likely
        </span>
      </div>
      <div
        style={{ fontSize: 10, color: "var(--aria-muted)", fontFamily: "Inter, sans-serif", lineHeight: 1.4, marginBottom: 6 }}
      >
        — {item.mitigation}
      </div>
      <div
        style={{ fontSize: 10, color: "rgba(90,112,128,0.6)", fontFamily: "Inter, sans-serif" }}
      >
        Impacted dependency count: {item.impacted_deps}
      </div>
    </div>
  );
}
