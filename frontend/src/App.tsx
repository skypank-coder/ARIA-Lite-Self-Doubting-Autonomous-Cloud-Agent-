import { useState, useCallback, useEffect, useRef } from "react";
import { Topbar } from "@/components/Topbar";
import { PresetTabs } from "@/components/PresetTabs";
import { TrustDecomp } from "@/components/TrustDecomp";
import { DependencyGraph } from "@/components/DependencyGraph";
import { DebateEngine } from "@/components/DebateEngine";
import { PreMortem } from "@/components/PreMortem";
import { ExecutionLog } from "@/components/ExecutionLog";
import { TicketInput } from "@/components/TicketInput";
import { getMockResponse, PRESETS, type ARIAResponse } from "@/lib/presets";

interface Toast {
  id: number;
  message: string;
}

interface AnalysisHistory {
  id: string;
  ticket: string;
  scenario: string;
  data: ARIAResponse;
  timestamp: number;
}

let toastCounter = 0;

export default function App() {
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [ticket, setTicket] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<ARIAResponse | null>(null);
  const [currentScenario, setCurrentScenario] = useState<string>("");
  const [viewMode, setViewMode] = useState<"graph" | "simulation">("graph");
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [memoryCount, setMemoryCount] = useState(0);
  const [memoryTooltip, setMemoryTooltip] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [history, setHistory] = useState<AnalysisHistory[]>([]);
  const [useRealBackend, setUseRealBackend] = useState<boolean>(true);
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
      const resp = await fetch("/api/process_ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket: ticketText }),
        signal: abortRef.current.signal,
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const json: ARIAResponse = await resp.json();
      const elapsed = Date.now() - startTime;
      
      setElapsedMs(elapsed);
      setData(json);
      const scenario = json.scenario || "unknown";
      setCurrentScenario(scenario);

      // Add to history
      const historyItem: AnalysisHistory = {
        id: `${Date.now()}`,
        ticket: ticketText,
        scenario,
        data: json,
        timestamp: Date.now(),
      };
      setHistory(prev => [historyItem, ...prev].slice(0, 20)); // Keep last 20

      if (json.rollback_active) {
        setMemoryCount(prev => prev + 1);
        setMemoryTooltip("ec2_scale — RDS pool exhaustion — eu-west-1");
      }

      addToast(`Analysis complete: ${scenario}`);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      
      const elapsed = Date.now() - startTime;
      setElapsedMs(elapsed);

      const isNetworkError =
        (err as Error).message.includes("fetch") ||
        (err as Error).message.includes("Failed") ||
        (err as Error).message.includes("NetworkError");

      if (isNetworkError) {
        addToast("❌ Backend unreachable — ensure server is running on port 8001");
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
        height: "100dvh",
        width: "100vw",
        background: "var(--aria-bg)",
        overflow: "hidden",
      }}
    >
      <Topbar elapsedMs={elapsedMs} memoryCount={memoryCount} memoryTooltip={memoryTooltip} />
      <PresetTabs activeId={activePreset} onSelect={handlePresetSelect} />

      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "22% 46% 32%",
          gridTemplateRows: "58% 42%",
          gap: 8,
          padding: 8,
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        <div style={{ gridColumn: "1", gridRow: "1 / 3", minHeight: 0 }}>
          <TrustDecomp data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "2", gridRow: "1", minHeight: 0 }}>
          <DependencyGraph
            scenario={currentScenario}
            loading={loading}
            viewMode={viewMode}
            onViewChange={setViewMode}
            simulation={data?.simulation ?? []}
          />
        </div>

        <div style={{ gridColumn: "2", gridRow: "2", minHeight: 0 }}>
          <DebateEngine data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "3", gridRow: "1", minHeight: 0 }}>
          <PreMortem data={data} loading={loading} />
        </div>

        <div style={{ gridColumn: "3", gridRow: "2", minHeight: 0 }}>
          <ExecutionLog data={data} loading={loading} />
        </div>
      </div>

      <TicketInput
        value={ticket}
        onChange={setTicket}
        onSubmit={handleAnalyze}
        loading={loading}
      />

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
