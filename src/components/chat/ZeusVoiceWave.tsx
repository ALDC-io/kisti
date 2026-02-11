"use client";

const BAR_COUNT = 24;

export default function ZeusVoiceWave({ active }: { active: boolean }) {
  return (
    <div className="flex h-8 items-center justify-center gap-[2px] px-4">
      {Array.from({ length: BAR_COUNT }, (_, i) => {
        // Create a natural-looking wave pattern with varied delays and heights
        const center = BAR_COUNT / 2;
        const dist = Math.abs(i - center) / center; // 0 at center, 1 at edges
        const maxScale = 1 - dist * 0.6; // taller in center, shorter at edges

        return (
          <div
            key={i}
            className="w-[3px] rounded-full transition-all duration-300"
            style={{
              height: active ? `${maxScale * 100}%` : "8%",
              background: active
                ? "linear-gradient(to top, #CC0000, #E60000, #FF1A1A)"
                : "#CC000040",
              animation: active
                ? `zeusVoiceBar 0.4s ease-in-out ${i * 0.03}s infinite alternate`
                : "none",
              boxShadow: active
                ? `0 0 ${4 + maxScale * 4}px #E6000060`
                : "none",
            }}
          />
        );
      })}
    </div>
  );
}
