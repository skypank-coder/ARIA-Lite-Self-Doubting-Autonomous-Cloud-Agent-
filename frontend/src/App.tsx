import { useState, useCallback, useRef } from "react";
import { Topbar } from "@/components/Topbar";
import { PresetTabs } from "@/components/PresetTabs";
import { TrustDecomp } from "@/components/TrustDecomp";
import { DependencyGraph } from "@/components/DependencyGraph";
import { DebateEngine } from "@/components/DebateEngine";
import { PreMortem } from "@/components/PreMortem";
import { ExecutionLog } from "@/components/ExecutionLog";
import { TicketInput } from "@/components/TicketInput";
import { SystemStatusBar } from "@/components/SystemStatusBar";
import { type ARIAResponse } from "@/lib/presets";

interface Toast {
  id: number;
  message: string;
}

let toastCounter = 0;

// Resolve backend URL: env var in production, /api proxy in local dev
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const apiUrl = (path: string) =>
  API_BASE ? `${API_BASE}${path}` : `/api${path}`;

export default function App() {
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [ticket, setTicket] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<ARIAResponse | null>(null);
  const [viewMode, setViewMode] = useState<"graph" | "simulation">("graph");
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [memoryCount, setMemoryCount] = useState(0);
  const [memoryTooltip, setMemoryTooltip] = useState<string | undefined>(undefined);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const addToast = useCallback((message: string) => {
    const id = ++toastCounter;
    setToasts(prev => [...prev, { id, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  }, []);

  const submitTicket = useCallback(async (ticketText: string) => {
    if (!ticketText.trim()) {
      addToast("Enter a cloud operation request");
      return;
    }
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setData(null);
    setViewMode("graph");

    const startTime = Date.now();

    try {
      const resp = await fetch(apiUrl("/process_ticket"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket: ticketText }),
        signal: abortRef.current!.signal,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json() as ARIAResponse;
      const elapsed = Date.now() - startTime;

      setElapsedMs(elapsed);
      setData(json);

      if (json.has_rollback) {
        setMemoryCount(prev => prev + 1);
        setMemoryTooltip("ec2_scale — RDS pool exhaustion — eu-west-1");
      }

      addToast(`Analysis complete: ${json.gate} — ${json.scenario ?? json.parsed?.service ?? "unknown"}`);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;

      const elapsed = Date.now() - startTime;
      setElapsedMs(elapsed);

      const isNetworkError =
        (err as Error).message.includes("fetch") ||
        (err as Error).message.includes("Failed") ||
        (err as Error).message.includes("NetworkError");

      if (isNetworkError) {
        addToast("❌ Backend unreachable — ensure server is running or check VITE_API_URL");
      } else {
        addToast(`❌ Error: ${(err as Error).message}`);
      }
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  const handlePresetSelect = useCallback((id: string, ticketText: string) => {
    setActivePreset(id);
    setTicket(ticketText);
    submitTicket(ticketText);
  }, [submitTicket]);

  const handleAnalyze = useCallback(() => {
    submitTicket(ticket);
  }, [ticket, submitTicket]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100dvh",
        width: "100vw",
        background: "var(--aria-bg)",
        overflowY: "auto",
      }}
    >
      <Topbar elapsedMs={elapsedMs} memoryCount={memoryCount} memoryTooltip={memoryTooltip} />
      <PresetTabs activeId={activePreset} onSelect={handlePresetSelect} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "22% 46% 32%",
          gridTemplateRows: "auto auto",
          gap: 10,
          padding: 10,
        }}
      >
        <div style={{ gridColumn: "1", gridRow: "1 / 3", minHeight: 0 }}>
          <TrustDecomp data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "2", gridRow: "1", minHeight: 380 }}>
          <DependencyGraph
            data={data}
            loading={loading}
            viewMode={viewMode}
            onViewChange={setViewMode}
          />
        </div>

        <div style={{ gridColumn: "2", gridRow: "2", minHeight: 280 }}>
          <DebateEngine data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "3", gridRow: "1", minHeight: 460 }}>
          <PreMortem data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "3", gridRow: "2", minHeight: 280 }}>
          <ExecutionLog data={data} loading={loading} ticket={ticket} />
        </div>
      </div>

      <TicketInput
        value={ticket}
        onChange={setTicket}
        onSubmit={handleAnalyze}
        loading={loading}
      />

      <SystemStatusBar data={data} elapsedMs={elapsedMs} />

      <div
        style={{
          position: "fixed",
          bottom: 64,
          right: 16,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          zIndex: 9999,
        }}
      >
        {toasts.map(t => (
          <div
            key={t.id}
            className="fade-in"
            style={{
              background: "var(--aria-panel)",
              border: "1px solid var(--aria-red)",
              borderRadius: 6,
              padding: "10px 16px",
              fontSize: 12,
              fontFamily: "Inter, sans-serif",
              color: "var(--aria-text)",
              maxWidth: 320,
              boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            }}
            data-testid="toast"
          >
            {t.message}
          </div>
        ))}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
