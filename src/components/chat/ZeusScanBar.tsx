"use client";

export default function ZeusScanBar({ active }: { active: boolean }) {
  if (!active) return null;

  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-white/5">
      <div
        className="animate-kitt-scan h-full w-1/3 rounded-full"
        style={{ background: "linear-gradient(to right, transparent, #C80A33, transparent)" }}
      />
    </div>
  );
}
