import { useEffect, useState } from "react";
import type { ARIAResponse } from "@/lib/presets";

interface DebateEngineProps {
  data: ARIAResponse | null;
  loading: boolean;
}

export function DebateEngine({ data, loading }: DebateEngineProps) {
  const [visible, setVisible] = useState<number[]>([]);

  useEffect(() => {
    setVisible([]);
    if (loading || !data) return;

    const delays = [0, 200, 500];
    const timers = delays.map((d, i) =>
      setTimeout(() => setVisible(prev => [...prev, i]), d)
    );
    return () => timers.forEach(clearTimeout);
  }, [data, loading]);

  const debate = data?.debate;

  return (
    <div
      className="flex flex-col"
      style={{
        background: "var(--aria-panel)",
        border: "1px solid var(--aria-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
      data-testid="debate-engine"
    >
      <div
        className="px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)" }}
      >
        <span className="panel-header">Debate Engine</span>
      </div>
      <div className="flex flex-col gap-0 px-3 py-2 overflow-y-auto flex-1">
        {loading ? (
          <>
            <div className="skeleton mb-2" style={{ height: 36, borderRadius: 4 }} />
            <div className="skeleton mb-2" style={{ height: 36, borderRadius: 4 }} />
            <div className="skeleton" style={{ height: 36, borderRadius: 4 }} />
          </>
        ) : debate ? (
          <>
            <DebateRow
              pill="EXEC"
              pillColor="#1DB87A"
              pillTextColor="#000"
              text={debate.executor}
              visible={visible.includes(0)}
            />
            <DebateRow
              pill="CRIT"
              pillColor="#CF3A3A"
              pillTextColor="#fff"
              text={debate.critic}
              visible={visible.includes(1)}
            />
            <DebateRow
              isVerdict
              text={debate.verdict}
              visible={visible.includes(2)}
            />
          </>
        ) : null}
      </div>
    </div>
  );
}

interface DebateRowProps {
  pill?: string;
  pillColor?: string;
  pillTextColor?: string;
  text: string;
  visible: boolean;
  isVerdict?: boolean;
}

function DebateRow({ pill, pillColor, pillTextColor, text, visible, isVerdict }: DebateRowProps) {
  if (!visible) return null;

  const hasPriorIncident = text.startsWith("⚠ PRIOR INCIDENT:");

  return (
    <div
      className="flex items-start gap-2 py-2 fade-in"
      style={{ borderBottom: "1px solid rgba(31,48,64,0.5)" }}
    >
      {isVerdict ? (
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "#7B5CF0",
            fontFamily: "Inter, sans-serif",
            flexShrink: 0,
            paddingTop: 1,
            minWidth: 52,
          }}
          data-testid="verdict-label"
        >
          VERDICT
        </span>
      ) : (
        <span
          className="px-1.5 py-0.5 rounded flex-shrink-0"
          style={{
            fontSize: 9,
            fontWeight: 700,
            fontFamily: "Inter, sans-serif",
            letterSpacing: "0.06em",
            background: pillColor,
            color: pillTextColor,
            marginTop: 2,
            minWidth: 40,
            textAlign: "center",
          }}
        >
          {pill}
        </span>
      )}
      <p
        style={{
          fontSize: 12,
          fontStyle: "italic",
          color: isVerdict ? "#7B5CF0" : "rgba(212,221,232,0.85)",
          fontFamily: "Inter, sans-serif",
          lineHeight: 1.5,
          margin: 0,
        }}
        data-testid={isVerdict ? "verdict-text" : undefined}
      >
        {hasPriorIncident ? (
          <>
            <span style={{ color: "#E07B2A", fontStyle: "italic" }}>
              {text.slice(0, text.indexOf(":") + 1)}
            </span>
            {text.slice(text.indexOf(":") + 1)}
          </>
        ) : (
          text
        )}
      </p>
    </div>
  );
}
