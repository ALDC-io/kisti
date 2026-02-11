"use client";

import { useRef, useEffect, useCallback } from "react";
import { CornerTelemetry, CameraInfo, DriverDisplayState, gt7TireColor, GT7_COLORS } from "@/lib/driverTelemetry";

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

function drawGT7Tire(
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

  // Glow for hottest
  if (isHottest) {
    ctx.shadowColor = HIGHLIGHT;
    ctx.shadowBlur = 6;
    ctx.strokeStyle = HIGHLIGHT;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.roundRect(x + 2, y + 2, w - 4, h - 4, 3);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  // Corner name
  ctx.fillStyle = WHITE;
  ctx.font = "bold 10px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(label, x + 6, y + 14);

  // Wear % (top right)
  const wearColor = corner.tireWearPct > 50 ? GREEN : corner.tireWearPct > 25 ? YELLOW : RED;
  ctx.fillStyle = wearColor;
  ctx.font = "bold 9px Helvetica, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(corner.tireWearPct)}%`, x + w - 6, y + 14);
  ctx.textAlign = "left";

  // --- GT7 Rounded Tire Shape ---
  const tireColor = gt7TireColor(corner.tireTempC);
  const tireX = x + w * 0.15;
  const tireY = y + 20;
  const tireW = w * 0.35;
  const tireH = h - 30;
  const r = Math.min(tireW, tireH) * 0.22; // corner radius

  // Tire outline (dark rubber)
  ctx.fillStyle = "#1A1A1A";
  ctx.beginPath();
  ctx.roundRect(tireX, tireY, tireW, tireH, r);
  ctx.fill();
  ctx.strokeStyle = "#3A3A3A";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(tireX, tireY, tireW, tireH, r);
  ctx.stroke();

  // Wear fill bar (fills from bottom up based on wearPct)
  const fillH = tireH * (corner.tireWearPct / 100);
  const fillY = tireY + tireH - fillH;
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(tireX + 2, tireY + 2, tireW - 4, tireH - 4, r - 1);
  ctx.clip();

  // Gradient fill matching tire temp color
  const grad = ctx.createLinearGradient(tireX, fillY, tireX, tireY + tireH);
  grad.addColorStop(0, tireColor);
  grad.addColorStop(1, tireColor + "88");
  ctx.fillStyle = grad;
  ctx.fillRect(tireX + 2, fillY, tireW - 4, fillH);

  // Glossy highlight (top of fill)
  if (fillH > 4) {
    const glossGrad = ctx.createLinearGradient(tireX, fillY, tireX, fillY + 6);
    glossGrad.addColorStop(0, "rgba(255,255,255,0.3)");
    glossGrad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glossGrad;
    ctx.fillRect(tireX + 2, fillY, tireW - 4, Math.min(6, fillH));
  }

  // Tread lines (horizontal grooves)
  ctx.strokeStyle = "rgba(0,0,0,0.3)";
  ctx.lineWidth = 1;
  const treadCount = 5;
  for (let i = 1; i < treadCount; i++) {
    const ly = tireY + (tireH * i) / treadCount;
    ctx.beginPath();
    ctx.moveTo(tireX + 4, ly);
    ctx.lineTo(tireX + tireW - 4, ly);
    ctx.stroke();
  }

  // Wear notch marks (left side)
  ctx.strokeStyle = GRAY;
  ctx.lineWidth = 0.5;
  for (let pct of [25, 50, 75]) {
    const ny = tireY + tireH * (1 - pct / 100);
    ctx.beginPath();
    ctx.moveTo(tireX, ny);
    ctx.lineTo(tireX + 3, ny);
    ctx.stroke();
  }

  ctx.restore();

  // --- Brake Temperature Strip ---
  const brakeX = tireX + tireW + 4;
  const brakeW = 6;
  const brakeColor = corner.brakeTempC > 316 ? RED : corner.brakeTempC > 232 ? YELLOW : GREEN;
  const brakeNorm = Math.max(0, Math.min(1, (corner.brakeTempC - 100) / 400));
  const brakeBarH = tireH * brakeNorm;

  // Brake strip background
  ctx.fillStyle = "#1A1A1A";
  ctx.beginPath();
  ctx.roundRect(brakeX, tireY, brakeW, tireH, 2);
  ctx.fill();

  // Brake fill (from bottom)
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(brakeX + 1, tireY + 1, brakeW - 2, tireH - 2, 1);
  ctx.clip();
  ctx.fillStyle = brakeColor;
  ctx.fillRect(brakeX + 1, tireY + tireH - brakeBarH, brakeW - 2, brakeBarH);
  ctx.restore();

  // --- Temperature Readouts (right side) ---
  const textX = x + w * 0.62;

  // Tire temp (big)
  ctx.fillStyle = tireColor;
  ctx.font = "bold 16px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`${Math.round(corner.tireTempC)}°`, textX, tireY + tireH * 0.35);

  // "TIRE" label
  ctx.fillStyle = GRAY;
  ctx.font = "8px Helvetica, sans-serif";
  ctx.fillText("TIRE", textX, tireY + tireH * 0.35 + 12);

  // Brake temp
  ctx.fillStyle = brakeColor;
  ctx.font = "bold 12px Helvetica, sans-serif";
  ctx.fillText(`${Math.round(corner.brakeTempC)}°`, textX, tireY + tireH * 0.7);

  // "BRAKE" label
  ctx.fillStyle = GRAY;
  ctx.font = "8px Helvetica, sans-serif";
  ctx.fillText("BRAKE", textX, tireY + tireH * 0.7 + 12);

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
      ([, a], [, b]) => b.tireTempC - a.tireTempC
    )[0]?.[0];

    for (const c of corners) {
      const data = state.corners[c.key];
      if (data) {
        drawGT7Tire(
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
