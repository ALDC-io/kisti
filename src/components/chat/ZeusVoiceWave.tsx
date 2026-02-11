"use client";

import { useEffect, useRef, useState } from "react";

const BAR_COUNT = 3;
const UPDATE_MS = 80;

function randomHeights(): number[] {
  // KITT-style 3-bar VU meter: center = overall volume, sides = L/R channels
  const center = 0.4 + Math.random() * 0.6; // 40-100%
  const left = center * (0.5 + Math.random() * 0.5); // proportional to center
  const right = center * (0.5 + Math.random() * 0.5);
  return [left, center, right];
}

function idleHeights(): number[] {
  return [0.06, 0.06, 0.06];
}

export default function ZeusVoiceWave({ active }: { active: boolean }) {
  const [heights, setHeights] = useState<number[]>(idleHeights);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      setHeights(randomHeights());
      intervalRef.current = setInterval(() => {
        setHeights(randomHeights());
      }, UPDATE_MS);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setHeights(idleHeights());
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [active]);

  return (
    <div className="flex h-10 items-end justify-center gap-1 px-4 py-1">
      {heights.map((h, i) => (
        <div
          key={i}
          className="w-3 rounded-sm"
          style={{
            height: `${h * 100}%`,
            background: active
              ? "linear-gradient(to top, #990000, #CC0000, #E60000, #FF1A1A)"
              : "#CC000025",
            transition: "height 70ms ease-out",
            boxShadow: active
              ? `0 0 ${6 + h * 10}px #E6000080, 0 0 ${2 + h * 4}px #FF1A1A60`
              : "none",
          }}
        />
      ))}
    </div>
  );
}
