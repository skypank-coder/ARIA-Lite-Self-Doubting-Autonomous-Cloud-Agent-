import { PRESETS } from "@/lib/presets";

interface PresetTabsProps {
  activeId: string;
  onSelect: (id: string, ticket: string) => void;
}

export function PresetTabs({ activeId, onSelect }: PresetTabsProps) {
  return (
    <div
      className="flex items-center gap-2 overflow-x-auto px-4"
      style={{
        height: 40,
        background: "var(--aria-panel)",
        borderBottom: "1px solid var(--aria-border)",
        flexShrink: 0,
        scrollbarWidth: "none",
      }}
      data-testid="preset-tabs"
    >
      {PRESETS.map((p) => {
        const isActive = activeId === p.id;
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p.id, p.ticket)}
            className="flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-all"
            style={{
              fontFamily: "Inter, sans-serif",
              fontSize: 11,
              fontWeight: isActive ? 700 : 400,
              background: isActive ? "var(--aria-cyan)" : "transparent",
              color: isActive ? "#0F1923" : "var(--aria-muted)",
              border: isActive ? "1px solid var(--aria-cyan)" : "1px solid var(--aria-border)",
              whiteSpace: "nowrap",
              maxWidth: 220,
              overflow: "hidden",
              textOverflow: "ellipsis",
              cursor: "pointer",
            }}
            title={p.ticket}
            data-testid={`preset-tab-${p.id}`}
          >
            {p.ticket}
          </button>
        );
      })}
    </div>
  );
}
