"use client";

import { useRef, useEffect, useCallback } from "react";
import { CornerTelemetry, CameraInfo, DriverDisplayState } from "@/lib/driverTelemetry";

// Theme constants matching PySide6
const BG_DARK = "#0A0A0A";
const CHROME_DARK = "#606060";
const CHROME_MID = "#909090";
const RED = "#FF1A1A";
const CHERRY = "#CC0000";
const GREEN = "#00CC66";
const YELLOW = "#FFAA00";
const WHITE = "#FFFFFF";
const GRAY = "#808080";
const DIM = "#333333";
const HIGHLIGHT = "#E60000";

function tempColor(c: number, greenMax: number, yellowMax: number): string {
  if (c < greenMax) return GREEN;
  if (c < yellowMax) return YELLOW;
  return RED;
}

function drawCornerGauge(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  corner: CornerTelemetry,
  label: string,
  isHottest: boolean
) {
  // Black gauge face
  ctx.fillStyle = BG_DARK;
  ctx.fillRect(x, y, w, h);

  // Chrome bezel
  ctx.strokeStyle = isHottest ? HIGHLIGHT : CHROME_MID;
  ctx.lineWidth = isHottest ? 2 : 1;
  ctx.beginPath();
  ctx.roundRect(x + 1, y + 1, w - 2, h - 2, 4);
  ctx.stroke();

  // Inner chrome line
  ctx.strokeStyle = CHROME_DARK;
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.roundRect(x + 3, y + 3, w - 6, h - 6, 3);
  ctx.stroke();

  // Corner name
  ctx.fillStyle = WHITE;
  ctx.font = "bold 10px Helvetica, sans-serif";
  ctx.fillText(label, x + 6, y + 15);

  // Gauge arc for tire temp
  const cx = x + w * 0.5;
  const cy = y + h * 0.52;
  const radius = Math.min(w, h) * 0.28;
  const startAngle = (225 * Math.PI) / 180;
  const sweepAngle = (270 * Math.PI) / 180;

  // Background arc
  ctx.beginPath();
  ctx.arc(cx, cy, radius, startAngle, startAngle + sweepAngle);
  ctx.strokeStyle = DIM;
  ctx.lineWidth = 3;
  ctx.stroke();

  // Normalize tire temp: 60-130C range
  const tireNorm = Math.max(0, Math.min(1, (corner.tireTempC - 60) / 70));
  const tireAngle = startAngle + tireNorm * sweepAngle;

  // Colored arc segment
  ctx.beginPath();
  ctx.arc(cx, cy, radius, startAngle, tireAngle);
  ctx.strokeStyle = tempColor(corner.tireTempC, 90, 105);
  ctx.lineWidth = 3;
  ctx.stroke();

  // Tick marks
  for (let i = 0; i <= 10; i++) {
    const angle = startAngle + (i / 10) * sweepAngle;
    const inner = radius - 4;
    const outer = radius + 2;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
    ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
    ctx.strokeStyle = i % 5 === 0 ? GRAY : DIM;
    ctx.lineWidth = i % 5 === 0 ? 1 : 0.5;
    ctx.stroke();
  }

  // Needle
  const needleLen = radius - 2;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + Math.cos(tireAngle) * needleLen, cy + Math.sin(tireAngle) * needleLen);
  ctx.strokeStyle = RED;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Center dot
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fillStyle = CHROME_MID;
  ctx.fill();

  // Tire temp value
  const tireColor = tempColor(corner.tireTempC, 90, 105);
  ctx.fillStyle = tireColor;
  ctx.font = "bold 14px Helvetica, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`${Math.round(corner.tireTempC)}°C`, cx, cy + radius + 16);

  // Brake temp (below tire)
  const brakeColor = tempColor(corner.brakeTempC, 232, 316);
  ctx.fillStyle = brakeColor;
  ctx.font = "10px Helvetica, sans-serif";
  ctx.fillText(`BRK ${Math.round(corner.brakeTempC)}°C`, cx, cy + radius + 30);
  ctx.textAlign = "start";
}

function drawRoadMap(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  speedKph: number,
  heading: number
) {
  const m = 8;

  // Dark terrain background
  ctx.fillStyle = "#0C1210";
  ctx.fillRect(0, 0, w, h);

  // Chrome border
  ctx.strokeStyle = CHROME_DARK;
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 0, w, h);

  // Main highway (Hwy 68)
  ctx.strokeStyle = "#2A2A2A";
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(m, h * 0.7);
  ctx.lineTo(w - m, h * 0.3);
  ctx.stroke();

  ctx.strokeStyle = "#444444";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(m, h * 0.7);
  ctx.lineTo(w - m, h * 0.3);
  ctx.stroke();

  // Center line (dashed yellow)
  ctx.strokeStyle = "#665500";
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(m, h * 0.7);
  ctx.lineTo(w - m, h * 0.3);
  ctx.stroke();
  ctx.setLineDash([]);

  // Secondary road (Laureles Grade)
  ctx.strokeStyle = "#333333";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(w * 0.3, m);
  ctx.quadraticCurveTo(w * 0.35, h * 0.3, w * 0.45, h * 0.45);
  ctx.quadraticCurveTo(w * 0.55, h * 0.6, w * 0.5, h - m);
  ctx.stroke();

  // Side road (York Rd)
  ctx.strokeStyle = "#2A2A2A";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(w * 0.6, m);
  ctx.quadraticCurveTo(w * 0.65, h * 0.2, w * 0.55, h * 0.4);
  ctx.stroke();

  // Connector
  ctx.beginPath();
  ctx.moveTo(w * 0.2, h * 0.5);
  ctx.lineTo(w * 0.4, h * 0.35);
  ctx.stroke();

  // Track access road
  ctx.strokeStyle = "#333333";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(w * 0.55, h * 0.4);
  ctx.lineTo(w * 0.75, h * 0.35);
  ctx.quadraticCurveTo(w * 0.85, h * 0.3, w * 0.8, h * 0.2);
  ctx.stroke();

  // Terrain contour hints
  ctx.strokeStyle = "#141A18";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const yOff = h * (0.15 + i * 0.15);
    ctx.beginPath();
    ctx.moveTo(m, yOff);
    ctx.quadraticCurveTo(w * 0.3, yOff - 10 - i * 3, w * 0.6, yOff + 5);
    ctx.stroke();
  }

  // Position dot with glow
  const dotX = w * 0.5;
  const dotY = h * 0.48;

  // Outer glow
  const glow = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 18);
  glow.addColorStop(0, "rgba(230, 0, 0, 0.4)");
  glow.addColorStop(1, "rgba(230, 0, 0, 0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(dotX, dotY, 18, 0, Math.PI * 2);
  ctx.fill();

  // Inner dot
  ctx.fillStyle = HIGHLIGHT;
  ctx.beginPath();
  ctx.arc(dotX, dotY, 5, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = WHITE;
  ctx.beginPath();
  ctx.arc(dotX, dotY, 2, 0, Math.PI * 2);
  ctx.fill();

  // Speed readout
  ctx.fillStyle = WHITE;
  ctx.font = "bold 16px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`${Math.round(speedKph)} km/h`, m + 4, h - m - 6);

  // Compass
  const compassDirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round(((heading + 360) % 360) / 45) % 8;
  ctx.fillStyle = GRAY;
  ctx.font = "10px Helvetica, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(compassDirs[idx], w - m - 4, h - m - 6);
  ctx.textAlign = "start";
}

interface StreetModeProps {
  state: DriverDisplayState;
}

export default function StreetMode({ state }: StreetModeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;

    ctx.fillStyle = BG_DARK;
    ctx.fillRect(0, 0, w, h);

    // Layout: left 55% = road map, right 45% = gauge stack
    const mapW = w * 0.55;
    const gaugeX = mapW + 4;
    const gaugeW = w - gaugeX;

    // Road map
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, mapW, h);
    ctx.clip();
    drawRoadMap(ctx, mapW, h, state.gps.speedKph, state.gps.heading);
    ctx.restore();

    // Corner gauges (2x2 grid in the right panel)
    const cornerH = (h - 4) * 0.5;
    const cornerW = (gaugeW - 4) * 0.5;
    const corners = [
      { key: "FL", x: gaugeX, y: 0, label: "FL" },
      { key: "FR", x: gaugeX + cornerW + 2, y: 0, label: "FR" },
      { key: "RL", x: gaugeX, y: cornerH + 2, label: "RL" },
      { key: "RR", x: gaugeX + cornerW + 2, y: cornerH + 2, label: "RR" },
    ];

    // Find hottest corner
    const hottestKey = Object.entries(state.corners).sort(
      ([, a], [, b]) => b.brakeTempC - a.brakeTempC
    )[0]?.[0];

    for (const c of corners) {
      const data = state.corners[c.key];
      if (data) {
        drawCornerGauge(
          ctx,
          c.x,
          c.y,
          cornerW,
          cornerH,
          data,
          c.label,
          c.key === hottestKey
        );
      }
    }
  }, [state]);

  useEffect(() => {
    const id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  }, [draw]);

  return (
    <div className="relative flex h-full w-full">
      {/* Canvas layer for gauges + map */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full"
        aria-label="Street mode: road map and corner temperature gauges"
      />

      {/* HTML overlay: oil gauge + sensor status + alerts */}
      <div
        className="pointer-events-none absolute bottom-0 left-0 flex flex-col gap-1 p-1"
        style={{ width: "55%" }}
      >
        {/* Oil gauge overlay */}
        <div
          className="rounded px-2 py-1"
          style={{ backgroundColor: "rgba(18,18,18,0.9)", border: `1px solid ${CHROME_DARK}` }}
        >
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold" style={{ color: HIGHLIGHT }}>
              OIL
            </span>
            <span
              className="text-base font-bold tabular-nums"
              style={{
                color: state.oilStatus === "hot" ? RED : state.oilStatus === "warn" ? YELLOW : GREEN,
              }}
            >
              {Math.round(state.oilPsi)}
            </span>
            <span className="text-[10px]" style={{ color: GRAY }}>
              PSI
            </span>
            <span
              className="text-[10px]"
              style={{ color: state.oilTempC > 130 ? RED : WHITE }}
            >
              {Math.round(state.oilTempC)}°C
            </span>
          </div>
        </div>
      </div>

      {/* Sensor status (bottom right) */}
      <div
        className="pointer-events-none absolute right-0 bottom-0 flex flex-col gap-0.5 p-1"
        style={{ width: "45%" }}
      >
        {state.cameras.map((cam) => (
          <div
            key={cam.name}
            className="flex items-center justify-between rounded px-1.5 py-0.5"
            style={{ backgroundColor: "rgba(18,18,18,0.85)" }}
          >
            <div className="flex items-center gap-1">
              <span
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: cam.connected ? GREEN : RED }}
              />
              <span className="text-[9px]" style={{ color: GRAY }}>
                {cam.name}
              </span>
            </div>
            <span className="text-[9px] tabular-nums" style={{ color: WHITE }}>
              {Math.round(cam.fps)}fps
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
