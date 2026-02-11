"use client";

export type DriverMode = "KISTI" | "STREET" | "TRACK" | "VIDEO" | "LOG" | "SETTINGS";

const MODES: { key: DriverMode; label: string; shortcut: string }[] = [
  { key: "KISTI", label: "KISTI", shortcut: "1" },
  { key: "STREET", label: "STREET", shortcut: "2" },
  { key: "TRACK", label: "TRACK", shortcut: "3" },
  { key: "VIDEO", label: "VIDEO", shortcut: "4" },
  { key: "LOG", label: "LOG", shortcut: "5" },
  { key: "SETTINGS", label: "SET", shortcut: "6" },
];

interface DriverSoftkeyBarProps {
  activeMode: DriverMode;
  onModeChange: (mode: DriverMode) => void;
}

export default function DriverSoftkeyBar({
  activeMode,
  onModeChange,
}: DriverSoftkeyBarProps) {
  return (
    <div
      className="flex h-[52px] items-stretch"
      style={{
        backgroundColor: "var(--driver-panel)",
        borderTop: "1px solid var(--driver-chrome-dark)",
      }}
    >
      {MODES.map((m) => {
        const isActive = activeMode === m.key;
        return (
          <button
            key={m.key}
            onClick={() => onModeChange(m.key)}
            className="flex flex-1 items-center justify-center text-xs font-bold tracking-wider transition-colors"
            style={{
              backgroundColor: isActive ? "var(--driver-cherry)" : "transparent",
              color: isActive ? "var(--driver-white)" : "var(--driver-silver)",
              borderLeft: "1px solid var(--driver-chrome-dark)",
              borderRight: "none",
            }}
            aria-label={`Switch to ${m.key} mode`}
            aria-pressed={isActive}
          >
            {m.key === "KISTI" ? (
              <img
                src="/assets/kisti_logo.png"
                alt="KiSTI"
                style={{
                  height: 28,
                  filter: isActive ? "brightness(0) invert(1)" : "none",
                }}
                draggable={false}
              />
            ) : (
              m.label
            )}
          </button>
        );
      })}
    </div>
  );
}
