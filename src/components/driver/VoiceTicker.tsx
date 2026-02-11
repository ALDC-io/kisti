"use client";

import { useState, useEffect, useRef } from "react";
import { ZeusFinding } from "@/lib/types";

const KISTI_RED = "#E60000";
const KISTI_RED_DIM = "#4A0000";
const TYPE_INTERVAL_MS = 30;
const COOLDOWN_MS = 4000;
const MAX_VISIBLE = 3;

interface TickerLine {
  id: string;
  text: string;
  complete: boolean;
}

function formatFinding(f: ZeusFinding): string {
  switch (f.severity) {
    case "critical":
      return `Watch it — ${f.title}`;
    case "warning":
      return `Heads up. ${f.title}`;
    default:
      return f.title;
  }
}

interface VoiceTickerProps {
  findings: ZeusFinding[];
}

export default function VoiceTicker({ findings }: VoiceTickerProps) {
  const [lines, setLines] = useState<TickerLine[]>([]);
  const [charIndex, setCharIndex] = useState(0);
  const seenRef = useRef<Set<string>>(new Set());
  const cooldownRef = useRef(0);

  // Detect new findings and queue ticker lines
  useEffect(() => {
    for (const f of findings) {
      if (seenRef.current.has(f.id)) continue;
      seenRef.current.add(f.id);

      const now = Date.now();
      if (now - cooldownRef.current < COOLDOWN_MS) continue;
      cooldownRef.current = now;

      const text = formatFinding(f);
      setLines((prev) => {
        const next: TickerLine[] = [{ id: f.id, text, complete: false }, ...prev];
        return next.slice(0, MAX_VISIBLE + 2);
      });
      setCharIndex(0);
    }
  }, [findings]);

  // Typewriter effect on the newest incomplete line
  useEffect(() => {
    const activeLine = lines.find((l) => !l.complete);
    if (!activeLine) return;

    if (charIndex >= activeLine.text.length) {
      setLines((prev) =>
        prev.map((l) => (l.id === activeLine.id ? { ...l, complete: true } : l))
      );
      return;
    }

    const timer = setInterval(() => {
      setCharIndex((prev) => prev + 1);
    }, TYPE_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [lines, charIndex]);

  const isTyping = lines.some((l) => !l.complete);
  const visibleLines = lines.slice(0, MAX_VISIBLE);

  return (
    <div
      className="flex w-full items-center gap-2 px-2"
      style={{
        height: 45,
        backgroundColor: "rgba(10,10,10,0.95)",
        borderTop: "1px solid #333",
      }}
    >
      {/* Mini 3-bar KITT waveform */}
      <div className="flex shrink-0 items-end gap-[2px]" style={{ height: 18 }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={isTyping ? `animate-ticker-bar${i > 0 ? ` animate-ticker-bar-${i}` : ""}` : ""}
            style={{
              width: 3,
              height: isTyping ? undefined : 4,
              minHeight: 4,
              backgroundColor: isTyping ? KISTI_RED : KISTI_RED_DIM,
              borderRadius: 1,
            }}
          />
        ))}
      </div>

      {/* Ticker lines */}
      <div className="flex min-w-0 flex-1 flex-col justify-center overflow-hidden">
        {visibleLines.length === 0 ? (
          <span className="text-[9px] italic" style={{ color: "#555" }}>
            KiSTI standing by…
          </span>
        ) : (
          visibleLines.map((line, idx) => {
            const isActive = idx === 0 && !line.complete;
            const displayText = isActive
              ? line.text.slice(0, charIndex)
              : line.text;
            return (
              <div
                key={line.id}
                className="truncate leading-tight"
                style={{
                  fontSize: idx === 0 ? 10 : 9,
                  color: idx === 0 ? "#FFFFFF" : "#666",
                  opacity: idx === 0 ? 1 : 0.6,
                }}
              >
                {displayText}
                {isActive && (
                  <span
                    className="animate-cursor-blink inline-block"
                    style={{
                      width: 5,
                      height: 10,
                      backgroundColor: KISTI_RED,
                      marginLeft: 1,
                    }}
                  />
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
