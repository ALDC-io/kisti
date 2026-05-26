"use client";

import { SESSION_LAPS, BEST_LAP, SESSION_SUMMARY, LapTelemetry } from "@/lib/missionRacewaySession";

const BG_DARK = "#0A0A0A";
const HIGHLIGHT = "#E60000";
const CYAN = "#00DDFF";
const GREEN = "#00CC66";
const YELLOW = "#FFAA00";
const GRAY = "#808080";
const CHROME_DARK = "#606060";
const DIM = "#444444";

function phaseColor(phase: LapTelemetry["phase"]): string {
  if (phase === "warm-up") return YELLOW;
  if (phase === "hot") return HIGHLIGHT;
  return CYAN;
}

function phaseLabel(phase: LapTelemetry["phase"]): string {
  if (phase === "warm-up") return "WARM";
  if (phase === "hot") return "HOT";
  return "COOL";
}

function formatTime(s: number): string {
  const min = Math.floor(s / 60);
  const sec = s % 60;
  return `${min}:${sec.toFixed(1).padStart(4, "0")}`;
}

/** Bar width as % of the slowest lap */
function barPct(lapTime: number): number {
  const slowest = Math.max(...SESSION_LAPS.map((l) => l.lapTimeS));
  return (lapTime / slowest) * 100;
}

export default function LogMode() {
  return (
    <div
      className="flex h-full w-full flex-col overflow-hidden"
      style={{ backgroundColor: BG_DARK }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-1"
        style={{ borderBottom: `1px solid ${CHROME_DARK}` }}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-bold" style={{ color: HIGHLIGHT }}>
            SESSION LOG
          </span>
          <span className="text-[10px]" style={{ color: GRAY }}>
            {SESSION_SUMMARY.track} — {SESSION_SUMMARY.location}
          </span>
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-[10px]" style={{ color: GRAY }}>
            BEST
          </span>
          <span className="text-xs font-bold" style={{ color: GREEN }}>
            {SESSION_SUMMARY.bestLapTime}
          </span>
          <span className="text-[10px]" style={{ color: GRAY }}>
            L{SESSION_SUMMARY.bestLapNumber}
          </span>
        </div>
      </div>

      {/* Lap list */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {SESSION_LAPS.map((lap) => {
          const isBest = lap.lap === BEST_LAP.lap;
          const frDelta = lap.ecu.brakeTemps[1] - lap.ecu.brakeTemps[0];
          return (
            <div
              key={lap.lap}
              className="mb-1 rounded px-2 py-1"
              style={{
                border: isBest ? `1px solid ${GREEN}` : `1px solid ${DIM}`,
                backgroundColor: isBest ? "rgba(0,204,102,0.06)" : "transparent",
              }}
            >
              {/* Lap header row */}
              <div className="flex items-center gap-2">
                <span
                  className="w-5 text-center text-[10px] font-bold"
                  style={{ color: phaseColor(lap.phase) }}
                >
                  {lap.lap}
                </span>
                <span
                  className="rounded px-1 text-[9px] font-bold"
                  style={{
                    color: BG_DARK,
                    backgroundColor: phaseColor(lap.phase),
                  }}
                >
                  {phaseLabel(lap.phase)}
                </span>
                <span
                  className="font-mono text-xs font-bold"
                  style={{ color: isBest ? GREEN : "#CCCCCC" }}
                >
                  {formatTime(lap.lapTimeS)}
                </span>
                {isBest && (
                  <span className="text-[9px] font-bold" style={{ color: GREEN }}>
                    BEST
                  </span>
                )}
                {/* Lap time bar */}
                <div className="relative ml-auto h-2 flex-1 overflow-hidden rounded" style={{ backgroundColor: DIM }}>
                  <div
                    className="absolute left-0 top-0 h-full rounded"
                    style={{
                      width: `${barPct(lap.lapTimeS)}%`,
                      backgroundColor: isBest ? GREEN : phaseColor(lap.phase),
                      opacity: 0.6,
                    }}
                  />
                </div>
              </div>

              {/* Telemetry detail row */}
              <div className="mt-0.5 flex gap-3 pl-7 text-[9px]" style={{ color: GRAY }}>
                <span>
                  S: {lap.sectors[0].toFixed(1)} / {lap.sectors[1].toFixed(1)} / {lap.sectors[2].toFixed(1)}
                </span>
                <span>
                  {lap.minSpeedKph}-{lap.maxSpeedKph} km/h
                </span>
                <span>
                  {lap.peakBrakingG}G brk
                </span>
                <span>
                  {lap.peakLateralG}G lat
                </span>
              </div>

              {/* ECU row */}
              <div className="flex gap-3 pl-7 text-[9px]" style={{ color: GRAY }}>
                <span>
                  EGT <span style={{ color: lap.ecu.egtPeak > 1500 ? YELLOW : GRAY }}>{lap.ecu.egtPeak}°F</span>
                </span>
                <span>
                  Boost {lap.ecu.boostPeak} PSI
                </span>
                <span>
                  Oil {lap.ecu.oilTemp}°F / {lap.ecu.oilPressure} PSI
                </span>
                <span style={{ color: frDelta > 35 ? YELLOW : GRAY }}>
                  FR+ {frDelta}°F
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Session summary footer */}
      <div
        className="flex items-center justify-between px-3 py-1 text-[9px]"
        style={{ borderTop: `1px solid ${CHROME_DARK}`, color: GRAY }}
      >
        <span>{SESSION_SUMMARY.totalLaps} laps — {formatTime(SESSION_SUMMARY.totalSessionTime)} total</span>
        <span>Peak EGT {SESSION_SUMMARY.peakEGT}°F — Boost {SESSION_SUMMARY.peakBoost} PSI — Oil {SESSION_SUMMARY.peakOilTemp}°F</span>
        <span>FR delta max +{SESSION_SUMMARY.maxFRBrakeDelta}°F</span>
      </div>
    </div>
  );
}
