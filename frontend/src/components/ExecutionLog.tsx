import { useEffect, useState, useRef } from "react";
import type { ARIAResponse } from "@/lib/presets";
import { AuditReportModal } from "@/components/AuditReportModal";

interface ExecutionLogProps {
  data: ARIAResponse | null;
  loading: boolean;
  ticket?: string;
}

const STATUS_SYMBOL: Record<string, { symbol: string; color: string }> = {
  ok:       { symbol: "●", color: "#1DB87A" },
  warn:     { symbol: "▲", color: "#E07B2A" },
  fail:     { symbol: "■", color: "#CF3A3A" },
  rollback: { symbol: "↩", color: "#7B5CF0" },
  memory:   { symbol: "◉", color: "#00B4D8" },
};

function getTimestamp(): string {
  const now = new Date();
  return [
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join(":") + "." + String(now.getMilliseconds()).padStart(3, "0");
}

function isPhaseHeader(msg: string): boolean {
  return /PHASE \d/.test(msg);
}

type ApprovalState = "pending" | "approved" | "rejected" | null;

export function ExecutionLog({ data, loading, ticket = "" }: ExecutionLogProps) {
  const [visibleLines, setVisibleLines]     = useState<number>(0);
  const [timestamps, setTimestamps]         = useState<string[]>([]);
  const [approvalState, setApprovalState]   = useState<ApprovalState>(null);
  const [pausedAt, setPausedAt]             = useState<number>(-1);
  const [extraLines, setExtraLines]         = useState<ARIAResponse["execution_log"]>([]);
  const [showAudit, setShowAudit]           = useState(false);
  const scrollRef  = useRef<HTMLDivElement>(null);
  const timersRef  = useRef<ReturnType<typeof setTimeout>[]>([]);

  const logs        = data?.execution_log ?? [];
  const hasRollback = data?.has_rollback ?? false;
  const isApprove   = data?.gate === "APPROVE";

  // Find the index of the first warn line (for APPROVE pause point)
  const firstWarnIdx = logs.findIndex(l => l.status === "warn");
  const pauseAfter   = firstWarnIdx >= 0 ? firstWarnIdx : -1;

  useEffect(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    setVisibleLines(0);
    setTimestamps([]);
    setApprovalState(null);
    setPausedAt(-1);
    setExtraLines([]);

    if (loading || !data) return;

    setTimestamps(logs.map(() => getTimestamp()));

    // For APPROVE gate: stream up to and including the first warn line, then pause
    const streamLimit = (isApprove && pauseAfter >= 0) ? pauseAfter + 1 : logs.length;

    for (let i = 0; i < streamLimit; i++) {
      const t = setTimeout(
        () => setVisibleLines(prev => prev + 1),
        i * 200
      );
      timersRef.current.push(t);
    }

    // After streaming up to pause point, set pending state
    if (isApprove && pauseAfter >= 0 && pauseAfter < logs.length - 1) {
      const pauseDelay = (pauseAfter + 1) * 200 + 50;
      const pt = setTimeout(() => {
        setApprovalState("pending");
        setPausedAt(pauseAfter + 1);
      }, pauseDelay);
      timersRef.current.push(pt);
    }

    return () => timersRef.current.forEach(clearTimeout);
  }, [data, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Resume streaming remaining lines after approval
  useEffect(() => {
    if (approvalState !== "approved" || pausedAt < 0) return;
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    const remaining = logs.slice(pausedAt);
    remaining.forEach((_, i) => {
      const t = setTimeout(
        () => setVisibleLines(prev => prev + 1),
        i * 200
      );
      timersRef.current.push(t);
    });
    return () => timersRef.current.forEach(clearTimeout);
  }, [approvalState]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visibleLines, approvalState, extraLines]);

  const handleApprove = () => {
    setApprovalState("approved");
  };

  const handleReject = () => {
    setApprovalState("rejected");
    setExtraLines([{ msg: "Operation rejected by operator. No AWS calls made.", status: "fail" }]);
  };

  // Lines to display: base visible lines + any extra (rejection line)
  const displayLogs = [
    ...logs.slice(0, visibleLines),
    ...extraLines,
  ];

  return (
    <>
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
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}
      >
        <span className="panel-header">Execution Log</span>
        <div className="flex items-center gap-2">
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
          {isApprove && !loading && (
            <button
              onClick={() => setShowAudit(true)}
              className="mono"
              style={{
                fontSize: 9, padding: "2px 8px", borderRadius: 3,
                border: "1px solid #E07B2A", color: "#E07B2A",
                background: "transparent", cursor: "pointer",
              }}
            >
              ↗ AUDIT REPORT
            </button>
          )}
          {!loading && logs.length > 0 && (
            <span
              className="mono"
              style={{ fontSize: 9, color: "var(--aria-muted)" }}
            >
              {visibleLines}/{logs.length}
            </span>
          )}
        </div>
      </div>

      {/* Log body */}
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
            {displayLogs.map((line, i) => {
              const sym        = STATUS_SYMBOL[line.status] || STATUS_SYMBOL.ok;
              const isPhase    = isPhaseHeader(line.msg);
              const isRollback = line.status === "rollback";

              return (
                <div
                  key={i}
                  className="fade-in mono"
                  style={{
                    fontSize: 11,
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 6,
                    marginTop: isPhase ? 6 : 0,
                    borderLeft: isRollback ? "2px solid #7B5CF0" : "2px solid transparent",
                    paddingLeft: isRollback ? 6 : 0,
                    background: isRollback ? "rgba(123,92,240,0.04)" : "transparent",
                  }}
                  data-testid={`log-line-${i}`}
                >
                  <span style={{ color: "var(--aria-muted)", flexShrink: 0, fontSize: 10 }}>
                    [{timestamps[i] ?? getTimestamp()}]
                  </span>
                  <span style={{ color: sym.color, flexShrink: 0 }}>{sym.symbol}</span>
                  <span
                    style={{
                      color: isPhase
                        ? "var(--aria-cyan)"
                        : line.status === "fail"
                        ? "#CF3A3A"
                        : line.status === "rollback"
                        ? "#7B5CF0"
                        : "var(--aria-text)",
                      wordBreak: "break-word",
                      fontWeight: isPhase ? 600 : 400,
                    }}
                  >
                    {line.msg}
                  </span>
                </div>
              );
            })}

            {/* APPROVE pause — human decision buttons */}
            {approvalState === "pending" && (
              <div className="fade-in flex items-center gap-3 mt-2 pt-2" style={{ borderTop: "1px solid var(--aria-border)" }}>
                <span className="mono" style={{ fontSize: 10, color: "#E07B2A" }}>⊙ awaiting operator decision</span>
                <button
                  onClick={handleApprove}
                  className="mono"
                  style={{
                    fontSize: 10,
                    padding: "2px 8px",
                    borderRadius: 3,
                    border: "1px solid #1DB87A",
                    color: "#1DB87A",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  ✓ APPROVE EXECUTION
                </button>
                <button
                  onClick={handleReject}
                  className="mono"
                  style={{
                    fontSize: 10,
                    padding: "2px 8px",
                    borderRadius: 3,
                    border: "1px solid #CF3A3A",
                    color: "#CF3A3A",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  ✗ REJECT
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
    {showAudit && (
      <AuditReportModal
        ticket={ticket}
        onClose={() => setShowAudit(false)}
      />
    )}
  </>
  );
}
