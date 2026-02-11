"use client";

import { useEffect, useRef, useState } from "react";

const BAR_COUNT = 24;
const UPDATE_MS = 70;

function randomHeights(): number[] {
  // Generate speech-like random heights — center bars tend taller, edges shorter
  const center = (BAR_COUNT - 1) / 2;
  return Array.from({ length: BAR_COUNT }, (_, i) => {
    const dist = Math.abs(i - center) / center;
    const ceiling = 1 - dist * 0.5; // center: 1.0, edges: 0.5
    const floor = 0.1;
    // Random with bias toward mid-range for natural speech feel
    const r1 = Math.random();
    const r2 = Math.random();
    const biased = (r1 + r2) / 2; // averages two randoms — clusters toward middle
    return floor + biased * (ceiling - floor);
  });
}

function idleHeights(): number[] {
  return Array.from({ length: BAR_COUNT }, () => 0.06);
}

export default function ZeusVoiceWave({ active }: { active: boolean }) {
  const [heights, setHeights] = useState<number[]>(idleHeights);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      // Immediately show activity
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
    <div className="flex h-8 items-end justify-center gap-[2px] px-4 py-1">
      {heights.map((h, i) => (
        <div
          key={i}
          className="w-[3px] rounded-full"
          style={{
            height: `${h * 100}%`,
            background: active
              ? "linear-gradient(to top, #CC0000, #E60000, #FF1A1A)"
              : "#CC000040",
            transition: "height 60ms ease-out",
            boxShadow: active && h > 0.4
              ? `0 0 ${h * 8}px #E6000060`
              : "none",
          }}
        />
      ))}
    </div>
  );
}
