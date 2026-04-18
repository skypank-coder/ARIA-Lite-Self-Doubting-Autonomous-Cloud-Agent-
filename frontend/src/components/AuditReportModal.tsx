import { useState, useCallback } from "react";

interface AuditReport {
  ticket: string;
  header: {
    action: string; service: string; environment: string;
    urgency: string; risk_level: string; timestamp: string;
  };
  decision: {
    verdict: string; confidence: number;
    binding_constraint: string; reason: string;
  };
  risk_factors: {
    blast_radius: string; affected: string[]; reversibility: string;
    policy: string; environment: string; risk_signals: string[];
    contradictions: string[];
  };
  impact: {
    primary_service: string; paths: string[];
    summary: string; node_count: number;
  };
  premortem: { failures: string[]; likelihood: number };
  debate: {
    executor: string; critic: string; conclusion: string;
    exec_score?: number; crit_score?: number;
  };
  recommendation: string[];
  final_call: { recommendation: string; symbol: string; color: string; note: string };
  memory: { prior_incidents: number; penalty_applied: number; pattern: string | null };
  scores: {
    intent_score: number; reversibility: number;
    blast_radius: number; policy_score: number; confidence: number;
  };
}

interface AuditReportModalProps {
  ticket: string;
  onClose: () => void;
}

const FINAL_COLORS: Record<string, string> = {
  green: "#1DB87A",
  amber: "#E07B2A",
  red:   "#CF3A3A",
};

export function AuditReportModal({ ticket, onClose }: AuditReportModalProps) {
  const [report, setReport]   = useState<AuditReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/audit/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket }),
      });
      const json = await resp.json();
      if (json.error) { setError(json.error); return; }
      setReport(json as AuditReport);
    } catch {
      setError("Failed to fetch audit report — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [ticket]);

  // Trigger fetch on mount
  useState(() => { fetchReport(); });

  const handleDownload = () => {
    if (!report) return;
    const el = document.getElementById("aria-audit-printable");
    if (!el) return;

    const win = window.open("", "_blank");
    if (!win) return;
    win.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>ARIA-Lite++ Audit Report — ${report.header.service} ${report.header.action}</title>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px;
                 color: #1a1a2e; background: #fff; padding: 32px; }
          .header-band { background: #0f1923; color: #fff; padding: 20px 24px;
                         border-radius: 6px; margin-bottom: 20px; }
          .header-band h1 { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
          .header-band .meta { font-size: 11px; color: #8899aa; }
          .verdict-banner { padding: 14px 20px; border-radius: 6px; margin-bottom: 20px;
                            border-left: 4px solid; }
          .section { margin-bottom: 18px; }
          .section h2 { font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
                        text-transform: uppercase; color: #5a7080; margin-bottom: 8px;
                        padding-bottom: 4px; border-bottom: 1px solid #e0e8f0; }
          .score-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
          .score-box { background: #f5f8fc; border-radius: 4px; padding: 8px 10px; }
          .score-box .label { font-size: 9px; color: #5a7080; text-transform: uppercase;
                              letter-spacing: 0.1em; }
          .score-box .value { font-size: 18px; font-weight: 700; font-family: monospace; }
          .path { font-family: monospace; font-size: 11px; color: #1a1a2e;
                  background: #f0f4f8; padding: 3px 8px; border-radius: 3px;
                  display: inline-block; margin: 2px 0; }
          .failure { padding: 6px 10px; background: #fff5f5; border-left: 3px solid #cf3a3a;
                     border-radius: 0 4px 4px 0; margin-bottom: 4px; font-size: 11px; }
          .step { padding: 5px 0; font-size: 11px; border-bottom: 1px solid #f0f4f8; }
          .step::before { content: "☐ "; color: #5a7080; }
          .debate-box { background: #f8fafc; border-radius: 4px; padding: 10px 12px;
                        margin-bottom: 8px; font-size: 11px; font-style: italic; }
          .debate-label { font-size: 9px; font-weight: 700; letter-spacing: 0.1em;
                          text-transform: uppercase; margin-bottom: 4px; }
          .final-box { padding: 16px 20px; border-radius: 6px; text-align: center; }
          .final-box .symbol { font-size: 28px; }
          .final-box .rec { font-size: 16px; font-weight: 700; margin: 4px 0; }
          .final-box .note { font-size: 11px; color: #5a7080; }
          .tag { display: inline-block; font-size: 9px; padding: 2px 6px; border-radius: 3px;
                 font-weight: 600; letter-spacing: 0.08em; margin: 2px; }
          .footer { margin-top: 24px; padding-top: 12px; border-top: 1px solid #e0e8f0;
                    font-size: 10px; color: #8899aa; text-align: center; }
          @media print {
            body { padding: 16px; }
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>${el.innerHTML}</body>
      </html>
    `);
    win.document.close();
    setTimeout(() => { win.print(); }, 400);
  };

  const fc    = report?.final_call;
  const fcCol = fc ? (FINAL_COLORS[fc.color] ?? "#E07B2A") : "#E07B2A";

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 10000,
        background: "rgba(0,0,0,0.75)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: "var(--aria-panel)",
          border: "1px solid var(--aria-border)",
          borderRadius: 8,
          width: "100%", maxWidth: 760,
          maxHeight: "90vh",
          display: "flex", flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-5 py-3"
          style={{ borderBottom: "1px solid var(--aria-border)", flexShrink: 0 }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--aria-cyan)", letterSpacing: "0.12em" }}>
            ARIA-LITE++ · AUDIT REPORT
          </span>
          <div className="flex items-center gap-2">
            {report && (
              <button onClick={handleDownload}
                className="mono"
                style={{
                  fontSize: 10, padding: "3px 10px", borderRadius: 4,
                  border: "1px solid var(--aria-cyan)", color: "var(--aria-cyan)",
                  background: "transparent", cursor: "pointer",
                }}>
                ↓ DOWNLOAD PDF
              </button>
            )}
            <button onClick={onClose}
              style={{
                fontSize: 14, color: "var(--aria-muted)", background: "transparent",
                border: "none", cursor: "pointer", lineHeight: 1,
              }}>✕</button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-5 py-4" id="aria-audit-printable">
          {loading && (
            <div className="flex items-center justify-center" style={{ height: 200 }}>
              <span className="mono" style={{ color: "var(--aria-muted)", fontSize: 12 }}>
                GENERATING REPORT...
              </span>
            </div>
          )}

          {error && (
            <div style={{ color: "#CF3A3A", fontFamily: "Inter, sans-serif", fontSize: 13, padding: 16 }}>
              {error}
            </div>
          )}

          {report && (
            <div style={{ fontFamily: "Inter, sans-serif", color: "var(--aria-text)" }}>

              {/* 1. HEADER */}
              <div style={{
                background: "#0F1923", borderRadius: 6, padding: "16px 20px",
                marginBottom: 16, border: "1px solid var(--aria-border)",
              }}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="mono" style={{ fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 4 }}>
                      {report.header.action} · {report.header.service}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--aria-muted)" }}>
                      ENV: {report.header.environment} &nbsp;·&nbsp;
                      URGENCY: {report.header.urgency} &nbsp;·&nbsp;
                      {report.header.timestamp}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 4,
                    background: report.header.risk_level === "CRITICAL" ? "rgba(207,58,58,0.2)"
                      : report.header.risk_level === "HIGH" ? "rgba(207,58,58,0.15)"
                      : "rgba(224,123,42,0.15)",
                    color: report.header.risk_level === "LOW" ? "#1DB87A" : "#CF3A3A",
                    border: `1px solid ${report.header.risk_level === "LOW" ? "#1DB87A" : "#CF3A3A"}`,
                    fontFamily: "monospace",
                  }}>
                    {report.header.risk_level}
                  </span>
                </div>
              </div>

              {/* 2. DECISION SNAPSHOT */}
              <Section title="Decision Snapshot">
                <div style={{
                  padding: "12px 16px", borderRadius: 6, marginBottom: 8,
                  border: "1px solid #E07B2A", background: "rgba(224,123,42,0.06)",
                }}>
                  <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: "#E07B2A", marginBottom: 4 }}>
                    {report.decision.verdict}
                    <span style={{ fontSize: 12, fontWeight: 400, marginLeft: 12, color: "var(--aria-muted)" }}>
                      Confidence: {report.decision.confidence.toFixed(3)}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--aria-text)" }}>
                    {report.decision.reason}
                  </div>
                </div>
                <ScoreGrid scores={report.scores} />
              </Section>

              {/* 3. KEY RISK FACTORS */}
              <Section title="Key Risk Factors">
                <RiskRow label="Blast Radius"   value={report.risk_factors.blast_radius} />
                <RiskRow label="Reversibility"  value={report.risk_factors.reversibility} />
                <RiskRow label="Policy"         value={report.risk_factors.policy} />
                <RiskRow label="Environment"    value={report.risk_factors.environment} />
                {report.risk_factors.contradictions.length > 0 && (
                  <RiskRow label="Contradictions"
                    value={report.risk_factors.contradictions.join(", ")}
                    warn />
                )}
              </Section>

              {/* 4. IMPACT SUMMARY */}
              <Section title="Impact Summary">
                <div style={{ fontSize: 12, color: "var(--aria-muted)", marginBottom: 8, fontStyle: "italic" }}>
                  {report.impact.summary}
                </div>
                <div className="flex flex-col gap-1">
                  {report.impact.paths.map((p, i) => (
                    <span key={i} className="mono" style={{
                      fontSize: 11, background: "rgba(0,180,216,0.08)",
                      color: "var(--aria-cyan)", padding: "3px 8px",
                      borderRadius: 3, display: "inline-block",
                    }}>{p}</span>
                  ))}
                </div>
              </Section>

              {/* 5. PRE-MORTEM */}
              <Section title={`Pre-Mortem Analysis · Likelihood ${report.premortem.likelihood}%`}>
                {report.premortem.failures.map((f, i) => (
                  <div key={i} style={{
                    padding: "7px 10px", marginBottom: 4,
                    background: "rgba(207,58,58,0.06)",
                    borderLeft: "3px solid #CF3A3A", borderRadius: "0 4px 4px 0",
                    fontSize: 12,
                  }}>
                    {i + 1}. {f}
                  </div>
                ))}
              </Section>

              {/* 6. DEBATE */}
              <Section title="Executor vs Critic">
                <DebateBox label="EXEC" color="#1DB87A" text={report.debate.executor}
                  score={report.debate.exec_score} />
                <DebateBox label="CRIT" color="#CF3A3A" text={report.debate.critic}
                  score={report.debate.crit_score} />
                <div style={{
                  fontSize: 12, fontStyle: "italic", color: "var(--aria-muted)",
                  padding: "8px 12px", background: "rgba(123,92,240,0.06)",
                  borderRadius: 4, borderLeft: "3px solid #7B5CF0",
                }}>
                  Conclusion: {report.debate.conclusion}
                </div>
              </Section>

              {/* 7. RECOMMENDED ACTIONS */}
              <Section title="Recommended Next Steps">
                {report.recommendation.map((step, i) => (
                  <div key={i} style={{
                    padding: "6px 0", fontSize: 12,
                    borderBottom: "1px solid var(--aria-border)",
                    display: "flex", gap: 8, alignItems: "flex-start",
                  }}>
                    <span className="mono" style={{ color: "var(--aria-cyan)", flexShrink: 0 }}>
                      {i + 1}.
                    </span>
                    {step}
                  </div>
                ))}
                {report.memory.prior_incidents > 0 && (
                  <div style={{ fontSize: 11, color: "#E07B2A", marginTop: 8 }}>
                    ⚠ {report.memory.prior_incidents} prior incident(s) on record —
                    memory penalty ×{report.memory.penalty_applied.toFixed(2)} applied
                  </div>
                )}
              </Section>

              {/* 8. FINAL CALL */}
              <div style={{
                padding: "16px 20px", borderRadius: 6, textAlign: "center",
                border: `2px solid ${fcCol}`,
                background: `${fcCol}10`,
                marginTop: 4,
              }}>
                <div style={{ fontSize: 24, marginBottom: 4 }}>{fc?.symbol}</div>
                <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: fcCol, marginBottom: 4 }}>
                  {fc?.recommendation}
                </div>
                <div style={{ fontSize: 12, color: "var(--aria-muted)" }}>{fc?.note}</div>
              </div>

              <div style={{ fontSize: 10, color: "var(--aria-muted)", textAlign: "center", marginTop: 12 }}>
                ARIA-LITE++ · engine=trust_engine_v3 · confidence={report.scores.confidence.toFixed(4)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
        textTransform: "uppercase", color: "var(--aria-muted)",
        paddingBottom: 6, marginBottom: 8,
        borderBottom: "1px solid var(--aria-border)",
        fontFamily: "Inter, sans-serif",
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function RiskRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex items-start gap-3" style={{ marginBottom: 5, fontSize: 12 }}>
      <span style={{ color: "var(--aria-muted)", minWidth: 110, flexShrink: 0, fontFamily: "Inter, sans-serif" }}>
        {label}
      </span>
      <span style={{ color: warn ? "#E07B2A" : "var(--aria-text)" }}>{value}</span>
    </div>
  );
}

function ScoreGrid({ scores }: { scores: AuditReport["scores"] }) {
  const items = [
    { label: "Intent",       val: scores.intent_score },
    { label: "Reversibility",val: scores.reversibility },
    { label: "Blast Radius", val: scores.blast_radius },
    { label: "Policy",       val: scores.policy_score },
  ];
  const color = (v: number, isBlast = false) => {
    const eff = isBlast ? 1 - v : v;
    return eff >= 0.70 ? "#1DB87A" : eff >= 0.40 ? "#E07B2A" : "#CF3A3A";
  };
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, marginTop: 8 }}>
      {items.map(({ label, val }) => (
        <div key={label} style={{
          background: "rgba(0,0,0,0.2)", borderRadius: 4, padding: "8px 10px",
          border: "1px solid var(--aria-border)",
        }}>
          <div style={{ fontSize: 9, color: "var(--aria-muted)", textTransform: "uppercase",
            letterSpacing: "0.1em", marginBottom: 2 }}>{label}</div>
          <div className="mono" style={{
            fontSize: 20, fontWeight: 700,
            color: color(val, label === "Blast Radius"),
          }}>{val.toFixed(2)}</div>
        </div>
      ))}
    </div>
  );
}

function DebateBox({ label, color, text, score }: {
  label: string; color: string; text: string; score?: number | null;
}) {
  return (
    <div style={{
      padding: "8px 12px", marginBottom: 6, borderRadius: 4,
      background: "rgba(0,0,0,0.15)", borderLeft: `3px solid ${color}`,
    }}>
      <div className="flex items-center gap-2 mb-1">
        <span style={{
          fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3,
          background: color, color: label === "EXEC" ? "#000" : "#fff",
          fontFamily: "monospace",
        }}>{label}</span>
        {score != null && (
          <span className="mono" style={{ fontSize: 9, color: "var(--aria-muted)" }}>
            strength: {score.toFixed(2)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "var(--aria-text)", fontStyle: "italic" }}>{text}</div>
    </div>
  );
}
