"use client";

import { useRef } from "react";
import {
  DriverDisplayState,
  CornerTelemetry,
} from "@/lib/driverTelemetry";
import { TelemetryStream, ZeusFinding } from "@/lib/types";

function fmtTime(seconds: number): string {
  if (seconds <= 0) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function StatusDot({ status }: { status: "ok" | "warn" | "hot" }) {
  const colors = { ok: "#10b981", warn: "#f59e0b", hot: "#ef4444" };
  return (
    <span
      className="inline-block h-2 w-2 rounded-full"
      style={{ backgroundColor: colors[status] }}
    />
  );
}

function MiniSparkline({
  data,
  color,
  width = 80,
  height = 24,
}: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  if (data.length < 2) return null;
  const mn = Math.min(...data);
  const mx = Math.max(...data);
  const rng = mx - mn || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - 2 - ((v - mn) / rng) * (height - 4);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CornerCard({
  label,
  corner,
}: {
  label: string;
  corner: CornerTelemetry;
}) {
  const tireColor =
    corner.tireStatus === "hot"
      ? "#ef4444"
      : corner.tireStatus === "warn"
        ? "#f59e0b"
        : "#10b981";
  const brakeColor =
    corner.brakeStatus === "hot"
      ? "#ef4444"
      : corner.brakeStatus === "warn"
        ? "#f59e0b"
        : "#10b981";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <StatusDot status={corner.tireStatus} />
          <span className="text-xs font-semibold text-gray-900">{label}</span>
        </div>
      </div>
      <div className="mt-1.5 flex items-end gap-3">
        <div>
          <div className="text-[10px] text-gray-500">Tire</div>
          <div className="text-sm font-bold tabular-nums" style={{ color: tireColor }}>
            {Math.round(corner.tireTempC)}°C
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500">Brake</div>
          <div className="text-sm font-bold tabular-nums" style={{ color: brakeColor }}>
            {Math.round(corner.brakeTempC)}°C
          </div>
        </div>
        <div className="ml-auto">
          <MiniSparkline data={corner.tireTrend} color={tireColor} width={60} height={20} />
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, { bg: string; text: string }> = {
    info: { bg: "bg-blue-100", text: "text-blue-700" },
    warning: { bg: "bg-amber-100", text: "text-amber-700" },
    critical: { bg: "bg-red-100", text: "text-red-700" },
  };
  const s = styles[severity] || styles.info;
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.bg} ${s.text}`}>
      {severity.toUpperCase()}
    </span>
  );
}

interface PitEngineerViewProps {
  state: DriverDisplayState;
}

export default function PitEngineerView({ state }: PitEngineerViewProps) {
  const syncColor =
    state.cloudSync.status === "ONLINE"
      ? "#10b981"
      : state.cloudSync.status === "QUEUED"
        ? "#f59e0b"
        : "#ef4444";

  const oilStream = state.streams.get("oil-pressure");
  const oilTempStream = state.streams.get("oil-temp");
  const egtStream = state.streams.get("egt");
  const boostStream = state.streams.get("boost");
  const wbStream = state.streams.get("wideband");

  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-200 bg-gray-50"
      role="region"
      aria-label="Pit engineer monitoring dashboard"
    >
      {/* Session header */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[10px] font-medium text-gray-500">SESSION</div>
            <div className="text-sm font-bold tabular-nums text-gray-900">
              {fmtTime(state.session.sessionTimeS)}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-medium text-gray-500">LAP</div>
            <div className="text-sm font-bold tabular-nums text-gray-900">
              {state.session.lapCount}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-medium text-gray-500">BEST</div>
            <div className="text-sm font-bold tabular-nums text-purple-600">
              {fmtTime(state.session.bestLapS)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: syncColor }}
          />
          <span className="text-[10px] font-medium text-gray-500">
            {state.cloudSync.status}
          </span>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {/* Telemetry grid: 4 corner cards */}
        <div className="grid grid-cols-2 gap-1.5">
          <CornerCard label="Front Left" corner={state.corners.FL} />
          <CornerCard label="Front Right" corner={state.corners.FR} />
          <CornerCard label="Rear Left" corner={state.corners.RL} />
          <CornerCard label="Rear Right" corner={state.corners.RR} />
        </div>

        {/* Engine row */}
        <div className="grid grid-cols-4 gap-1.5">
          {[
            {
              label: "Oil PSI",
              value: Math.round(state.oilPsi),
              unit: "PSI",
              status: state.oilStatus,
              stream: oilStream,
            },
            {
              label: "Oil Temp",
              value: oilTempStream ? Math.round(oilTempStream.current.value) : "—",
              unit: "°F",
              status: (oilTempStream?.current.status || "ok") as "ok" | "warn" | "hot",
              stream: oilTempStream,
            },
            {
              label: "EGT",
              value: egtStream ? Math.round(egtStream.current.value) : "—",
              unit: "°F",
              status: (egtStream?.current.status || "ok") as "ok" | "warn" | "hot",
              stream: egtStream,
            },
            {
              label: "Boost",
              value: boostStream ? boostStream.current.value.toFixed(1) : "—",
              unit: "PSI",
              status: (boostStream?.current.status || "ok") as "ok" | "warn" | "hot",
              stream: boostStream,
            },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-gray-200 bg-white p-2"
            >
              <div className="flex items-center gap-1">
                <StatusDot status={item.status} />
                <span className="text-[10px] text-gray-500">{item.label}</span>
              </div>
              <div className="mt-0.5 text-sm font-bold tabular-nums text-gray-900">
                {item.value}
                <span className="text-[10px] font-normal text-gray-400"> {item.unit}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Zeus Findings feed */}
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-1.5">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-purple-500">
              <path d="M8 1L1 14h14L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <path d="M8 6v4M8 12h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="text-xs font-semibold text-gray-900">Zeus Findings</span>
          </div>
          <div className="max-h-28 space-y-1 overflow-y-auto p-2">
            {state.findings.map((f) => (
              <div key={f.id} className="flex items-start gap-2 rounded p-1.5">
                <SeverityBadge severity={f.severity} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-gray-900">{f.title}</div>
                  <div className="text-[10px] leading-tight text-gray-500">
                    {f.description}
                  </div>
                </div>
              </div>
            ))}

          </div>
        </div>

        {/* Weather + Cloud sync */}
        <div className="grid grid-cols-2 gap-1.5">
          <div className="rounded-lg border border-gray-200 bg-white p-2">
            <div className="text-[10px] font-medium text-gray-500">WEATHER</div>
            <div className="mt-0.5 text-xs text-gray-900">
              {Math.round(state.weather.tempC)}°C · {state.weather.condition}
            </div>
            <div className="text-[10px] text-gray-500">
              {state.weather.windDir} {Math.round(state.weather.windKph)} km/h ·{" "}
              {Math.round(state.weather.humidity)}%
            </div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-2">
            <div className="flex items-center gap-1.5">
              <img
                src="/assets/aldc_logo.svg"
                alt="ALDC"
                className="h-3"
                draggable={false}
              />
              <div className="text-[10px] font-medium text-gray-500">ECLIPSE SYNC</div>
            </div>
            <div className="mt-0.5 flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: syncColor }}
              />
              <span className="text-xs font-medium text-gray-900">
                {state.cloudSync.status}
              </span>
            </div>
            <div className="text-[10px] text-gray-500">
              {state.cloudSync.pendingCount > 0
                ? `${state.cloudSync.pendingCount} pending uploads`
                : "Streaming to Eclipse"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
