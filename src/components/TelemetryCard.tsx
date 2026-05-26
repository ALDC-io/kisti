"use client";

import { TelemetryStream } from "@/lib/types";
import { NodeDef } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  ok: "#10b981",
  warn: "#f59e0b",
  hot: "#ef4444",
};

const STATUS_LABELS: Record<string, string> = {
  ok: "Normal",
  warn: "Warning",
  hot: "Critical",
};

function Sparkline({
  history,
  min,
  max,
  color,
}: {
  history: { value: number }[];
  min: number;
  max: number;
  color: string;
}) {
  if (history.length < 2) return null;

  const width = 200;
  const height = 40;
  const padding = 2;

  const range = max - min || 1;
  const points = history.map((p, i) => {
    const x = padding + (i / (history.length - 1)) * (width - padding * 2);
    const y =
      height - padding - ((p.value - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-10 w-full"
      role="img"
      aria-label="Telemetry sparkline"
    >
      <polyline
        points={points.join(" ")}
        className="sparkline-path"
        stroke={color}
      />
    </svg>
  );
}

interface TelemetryCardProps {
  node: NodeDef;
  stream: TelemetryStream;
}

export default function TelemetryCard({ node, stream }: TelemetryCardProps) {
  const color = STATUS_COLORS[stream.current.status];
  const label = STATUS_LABELS[stream.current.status];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: color }}
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-gray-900">
            {node.label}
          </span>
        </div>
        <span className="text-xs font-medium" style={{ color }}>
          {label}
        </span>
      </div>

      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold tabular-nums text-gray-900">
          {stream.current.value}
        </span>
        <span className="text-sm text-gray-500">{node.unit}</span>
      </div>

      <div className="mt-2">
        <Sparkline
          history={stream.history}
          min={node.min}
          max={node.max}
          color={color}
        />
      </div>

      <div className="mt-2 flex justify-between text-xs text-gray-400">
        <span>
          Range: {node.min}–{node.max} {node.unit}
        </span>
        <span>Warn: {node.warnThreshold}</span>
      </div>
    </div>
  );
}
