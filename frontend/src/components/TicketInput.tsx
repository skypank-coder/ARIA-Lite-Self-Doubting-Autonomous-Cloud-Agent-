interface TicketInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function TicketInput({ value, onChange, onSubmit, loading }: TicketInputProps) {
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      onSubmit();
    }
  }

  return (
    <div
      className="flex items-center gap-0"
      style={{
        height: 52,
        background: "#1C2A38",
        borderTop: "1px solid var(--aria-border)",
        flexShrink: 0,
      }}
      data-testid="ticket-input-area"
    >
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe the cloud operation in plain English..."
        rows={1}
        className="flex-1 bg-transparent outline-none resize-none px-4 py-3"
        style={{
          fontFamily: "var(--app-font-mono)",
          fontSize: 12,
          color: "var(--aria-text)",
          border: "none",
          lineHeight: 1.6,
          height: "100%",
        }}
        data-testid="ticket-input"
        disabled={loading}
      />
      <button
        onClick={onSubmit}
        disabled={loading || !value.trim()}
        className="flex items-center gap-2 h-full px-6 font-bold transition-opacity"
        style={{
          fontFamily: "Inter, sans-serif",
          fontSize: 13,
          fontWeight: 700,
          background: loading ? "rgba(0,180,216,0.6)" : "var(--aria-cyan)",
          color: "#0F1923",
          border: "none",
          cursor: loading || !value.trim() ? "not-allowed" : "pointer",
          flexShrink: 0,
          letterSpacing: "0.04em",
          opacity: !value.trim() && !loading ? 0.5 : 1,
        }}
        data-testid="analyze-button"
      >
        {loading ? (
          <>
            <Spinner />
            ANALYZING...
          </>
        ) : (
          <>
            <span style={{ fontSize: 14 }}>⚡</span>
            ANALYZE →
          </>
        )}
      </button>
    </div>
  );
}

function Spinner() {
  return (
    <div
      style={{
        width: 12,
        height: 12,
        border: "2px solid rgba(15,25,35,0.3)",
        borderTop: "2px solid #0F1923",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite",
      }}
    />
  );
}
