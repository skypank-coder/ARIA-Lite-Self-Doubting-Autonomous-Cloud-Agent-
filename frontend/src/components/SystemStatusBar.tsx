import type { ARIAResponse } from "@/lib/presets";

interface SystemStatusBarProps {
  data: ARIAResponse | null;
  elapsedMs: number | null;
}

function Dot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: color,
        marginRight: 5,
        flexShrink: 0,
      }}
    />
  );
}

export function SystemStatusBar({ data, elapsedMs }: SystemStatusBarProps) {
  const sdCount    = data?.self_doubt_flags?.length ?? 0;
  const memCount   = data?.memory?.total_count ?? 0;
  const nodeCount  = data?.graph?.nodes?.length ?? 0;
  const ms         = elapsedMs != null ? elapsedMs : "—";

  const sdColor =
    sdCount === 0 ? "#1DB87A" :
    sdCount <= 2  ? "#E07B2A" : "#CF3A3A";

  const items = [
    { dot: "#1DB87A", label: "trust engine v3 · active" },
    { dot: "#1DB87A", label: `memory · ${memCount} entries` },
    { dot: sdColor,   label: `self-doubt · ${sdCount} flags active` },
    { dot: "#1DB87A", label: `ai layer · ${ms}ms` },
    { dot: "#1DB87A", label: `graph · ${nodeCount} nodes` },
  ];

  return (
    <div
      className="mono"
      style={{
        height: 28,
        background: "rgba(8,16,24,0.85)",
        borderTop: "1px solid var(--aria-border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-around",
        padding: "0 16px",
        flexShrink: 0,
      }}
    >
      {items.map(({ dot, label }) => (
        <span
          key={label}
          style={{
            fontSize: 10,
            color: "var(--aria-muted)",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Dot color={dot} />
          {label}
        </span>
      ))}
    </div>
  );
}
