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

  const debate   = data?.debate;
  const meta     = data?.parsed_meta;
  const sdFlags  = data?.self_doubt_flags ?? [];

  const envColor = (env?: string) =>
    env === "production" ? "#CF3A3A" :
    env === "dev"        ? "#1DB87A" : "#E07B2A";

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

      {/* Parsed metadata row */}
      {!loading && meta && (
        <div
          className="flex items-center gap-2 px-3 py-1.5 flex-wrap"
          style={{ borderBottom: "1px solid var(--aria-border)", background: "rgba(0,0,0,0.15)" }}
        >
          {([
            { label: "VERB",    val: meta.verb_class },
            { label: "SERVICE", val: meta.service },
            { label: "ENV",     val: meta.environment, color: envColor(meta.environment) },
            { label: "URGENCY", val: meta.urgency },
          ] as Array<{ label: string; val: string; color?: string }>).map(({ label, val, color }) => (
            <span
              key={label}
              className="mono"
              style={{
                fontSize: 9,
                letterSpacing: "0.05em",
                color: color ?? "var(--aria-muted)",
                background: "var(--aria-border)",
                padding: "1px 5px",
                borderRadius: 3,
              }}
            >
              {label}: {val}
            </span>
          ))}
        </div>
      )}
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

        {/* Self-Doubt Flags */}
        {!loading && sdFlags.length > 0 && (
          <div style={{ borderTop: "1px solid var(--aria-border)", marginTop: 6, paddingTop: 6 }}>
            <span className="panel-header" style={{ fontSize: 9, display: "block", marginBottom: 4 }}>
              Self-Doubt Signals
            </span>
            {sdFlags.map((f, i) => {
              const isCritical = ["PROD_RISK", "CONTRADICTION", "EXTREME_SCALE"].includes(f.type);
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 fade-in"
                  style={{ marginBottom: 3 }}
                >
                  <span
                    className="mono"
                    style={{
                      fontSize: 8,
                      letterSpacing: "0.05em",
                      padding: "1px 4px",
                      borderRadius: 3,
                      flexShrink: 0,
                      background: isCritical ? "#CF3A3A" : "rgba(224,123,42,0.2)",
                      color: isCritical ? "#fff" : "#E07B2A",
                      border: isCritical ? "none" : "1px solid #E07B2A",
                    }}
                  >
                    {f.type}
                  </span>
                  <span style={{ fontSize: 10, color: "var(--aria-text)", flex: 1, fontFamily: "Inter, sans-serif" }}>
                    {f.msg}
                  </span>
                  <span className="mono" style={{ fontSize: 9, color: "var(--aria-muted)", flexShrink: 0 }}>
                    {f.impact}
                  </span>
                </div>
              );
            })}
          </div>
        )}
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
