import { useEffect, useState, useRef } from "react";
import type { ARIAResponse } from "@/lib/presets";

interface ExecutionLogProps {
  data: ARIAResponse | null;
  loading: boolean;
}

const STATUS_SYMBOL: Record<string, { symbol: string; color: string }> = {
  ok: { symbol: "●", color: "#1DB87A" },
  warn: { symbol: "▲", color: "#E07B2A" },
  fail: { symbol: "■", color: "#CF3A3A" },
  rollback: { symbol: "↩", color: "#7B5CF0" },
  memory: { symbol: "◉", color: "#00B4D8" },
};

function getTimestamp(): string {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  const ms = String(now.getMilliseconds()).padStart(3, "0");
  return `${h}:${m}:${s}.${ms}`;
}

export function ExecutionLog({ data, loading }: ExecutionLogProps) {
  const [visibleLines, setVisibleLines] = useState<number>(0);
  const [timestamps, setTimestamps] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const logs = data?.execution_log ?? [];
  const hasRollback = data?.has_rollback ?? false;

  useEffect(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    setVisibleLines(0);
    setTimestamps([]);

    if (loading || !data) return;

    const ts: string[] = logs.map(() => getTimestamp());
    setTimestamps(ts);

    logs.forEach((_, i) => {
      const t = setTimeout(() => {
        setVisibleLines(prev => prev + 1);
      }, i * 350);
      timersRef.current.push(t);
    });

    return () => timersRef.current.forEach(clearTimeout);
  }, [data, loading]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visibleLines]);

  return (
    <div
      className="flex flex-col h-full"
      style={{
        background: "var(--aria-panel)",
        border: "1px solid var(--aria-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
      data-testid="execution-log"
    >
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}
      >
        <span className="panel-header">Execution Log</span>
        {hasRollback && !loading && (
          <span
            className="px-2 py-0.5 rounded"
            style={{
              fontSize: 9,
              fontFamily: "Inter, sans-serif",
              fontWeight: 600,
              letterSpacing: "0.08em",
              color: "#7B5CF0",
              border: "1px solid #7B5CF0",
              background: "rgba(123,92,240,0.08)",
            }}
          >
            ROLLBACK ACTIVE
          </span>
        )}
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-2"
        style={{ minHeight: 0 }}
      >
        {loading ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3].map(i => (
              <div key={i} className="skeleton" style={{ height: 14, borderRadius: 3 }} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {logs.slice(0, visibleLines).map((line, i) => {
              const sym = STATUS_SYMBOL[line.status] || STATUS_SYMBOL.ok;
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 fade-in mono"
                  style={{ fontSize: 11 }}
                  data-testid={`log-line-${i}`}
                >
                  <span style={{ color: "var(--aria-muted)", flexShrink: 0 }}>
                    [{timestamps[i] ?? "00:00:00.000"}]
                  </span>
                  <span style={{ color: sym.color, flexShrink: 0 }}>{sym.symbol}</span>
                  <span style={{ color: "var(--aria-text)", wordBreak: "break-word" }}>{line.msg}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
