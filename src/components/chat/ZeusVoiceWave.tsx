"use client";

import { useEffect, useRef, useState } from "react";

const COLUMNS = 3;
const SEGMENTS = 7; // segments per half (top + bottom = 14 total per column)
const UPDATE_MS = 80;

function randomLevels(): number[] {
  // KITT 3-bar: center = overall, sides = L/R channels
  const center = Math.floor(2 + Math.random() * (SEGMENTS - 1)); // 2-7 segments lit
  const left = Math.floor(center * (0.4 + Math.random() * 0.6));
  const right = Math.floor(center * (0.4 + Math.random() * 0.6));
  return [Math.max(1, left), center, Math.max(1, right)];
}

function idleLevels(): number[] {
  return [0, 0, 0];
}

export default function ZeusVoiceWave({ active }: { active: boolean }) {
  const [levels, setLevels] = useState<number[]>(idleLevels);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      setLevels(randomLevels());
      intervalRef.current = setInterval(() => {
        setLevels(randomLevels());
      }, UPDATE_MS);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setLevels(idleLevels());
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [active]);

  return (
    <div className="flex h-14 items-center justify-center gap-1.5 px-4 py-1">
      {levels.map((level, col) => (
        <div key={col} className="flex flex-col items-center gap-[2px]">
          {/* Top half — segments grow upward from center */}
          {Array.from({ length: SEGMENTS }, (_, seg) => {
            const fromCenter = SEGMENTS - seg; // 7 at top, 1 at center
            const lit = active && fromCenter <= level;
            const intensity = lit ? 1 - (fromCenter - 1) / SEGMENTS : 0;
            return (
              <div
                key={`t${seg}`}
                className="rounded-[1px]"
                style={{
                  width: 10,
                  height: 3,
                  background: lit
                    ? `rgba(200, 10, 51, ${0.4 + intensity * 0.6})`
                    : "rgba(200, 10, 51, 0.08)",
                  boxShadow: lit
                    ? `0 0 ${3 + intensity * 5}px rgba(200, 10, 51, ${0.3 + intensity * 0.4})`
                    : "none",
                  transition: "all 70ms ease-out",
                }}
              />
            );
          })}
          {/* Bottom half — mirror of top */}
          {Array.from({ length: SEGMENTS }, (_, seg) => {
            const fromCenter = seg + 1; // 1 at center, 7 at bottom
            const lit = active && fromCenter <= level;
            const intensity = lit ? 1 - (fromCenter - 1) / SEGMENTS : 0;
            return (
              <div
                key={`b${seg}`}
                className="rounded-[1px]"
                style={{
                  width: 10,
                  height: 3,
                  background: lit
                    ? `rgba(200, 10, 51, ${0.4 + intensity * 0.6})`
                    : "rgba(200, 10, 51, 0.08)",
                  boxShadow: lit
                    ? `0 0 ${3 + intensity * 5}px rgba(200, 10, 51, ${0.3 + intensity * 0.4})`
                    : "none",
                  transition: "all 70ms ease-out",
                }}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
