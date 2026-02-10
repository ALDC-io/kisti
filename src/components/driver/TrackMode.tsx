"use client";

import { useRef, useEffect, useCallback } from "react";
import { DriverDisplayState, CornerTelemetry } from "@/lib/driverTelemetry";
import { CIRCUIT, TURNS, getCircuitPosition } from "@/lib/lagunaSecaCircuit";

const BG_DARK = "#0A0A0A";
const CHROME_DARK = "#606060";
const CHROME_MID = "#909090";
const RED = "#FF1A1A";
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

function fmtTime(seconds: number): string {
  if (seconds <= 0) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function drawThermalCorner(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  corner: CornerTelemetry,
  label: string,
  isHottest: boolean
) {
  // Background
  ctx.fillStyle = isHottest ? "#1A0505" : BG_DARK;
  ctx.fillRect(x, y, w, h);

  // Chrome bezel
  ctx.strokeStyle = isHottest ? HIGHLIGHT : CHROME_DARK;
  ctx.lineWidth = isHottest ? 2 : 1;
  ctx.beginPath();
  ctx.roundRect(x + 1, y + 1, w - 2, h - 2, 3);
  ctx.stroke();

  // Glow effect for hottest
  if (isHottest) {
    ctx.shadowColor = HIGHLIGHT;
    ctx.shadowBlur = 8;
    ctx.strokeStyle = HIGHLIGHT;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.roundRect(x + 2, y + 2, w - 4, h - 4, 2);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  // Corner name
  ctx.fillStyle = WHITE;
  ctx.font = "bold 10px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(label, x + 6, y + 14);

  // Tire temp (big number)
  const tireColor = tempColor(corner.tireTempC, 90, 105);
  ctx.fillStyle = tireColor;
  ctx.font = "bold 18px Helvetica, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`${Math.round(corner.tireTempC)}°`, x + w * 0.35, y + h * 0.55);

  // Brake temp
  const brakeColor = tempColor(corner.brakeTempC, 232, 316);
  ctx.fillStyle = brakeColor;
  ctx.font = "11px Helvetica, sans-serif";
  ctx.fillText(`BRK ${Math.round(corner.brakeTempC)}°`, x + w * 0.35, y + h * 0.75);
  ctx.textAlign = "start";

  // Sparkline (right side)
  const trend = corner.tireTrend;
  if (trend.length >= 2) {
    const sx = x + w * 0.6;
    const sy = y + 8;
    const sw = w * 0.35;
    const sh = h * 0.5;
    const mn = Math.min(...trend);
    const mx = Math.max(...trend);
    const rng = mx - mn || 1;

    ctx.beginPath();
    for (let i = 0; i < trend.length; i++) {
      const px = sx + (i / (trend.length - 1)) * sw;
      const py = sy + sh - ((trend[i] - mn) / rng) * sh;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.strokeStyle = tireColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  // Delta arrow
  if (trend.length >= 2) {
    const delta = trend[trend.length - 1] - trend[trend.length - 2];
    const arrow = delta > 0 ? "\u2191" : delta < 0 ? "\u2193" : "\u2192";
    const dColor = delta > 1 ? RED : delta < -1 ? GREEN : GRAY;
    ctx.fillStyle = dColor;
    ctx.font = "10px Helvetica, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${arrow}${Math.abs(delta).toFixed(1)}`, x + w - 4, y + h - 6);
    ctx.textAlign = "start";
  }
}

function drawTrackMap(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  progress: number
) {
  const m = 6;

  // Background
  ctx.fillStyle = BG_DARK;
  ctx.fillRect(x, y, w, h);

  // Chrome border
  ctx.strokeStyle = CHROME_DARK;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);

  const tx = (nx: number) => x + m + nx * (w - 2 * m);
  const ty = (ny: number) => y + m + ny * (h - 2 * m);

  // Build smooth track path
  ctx.beginPath();
  ctx.moveTo(tx(CIRCUIT[0].x), ty(CIRCUIT[0].y));
  for (let i = 1; i < CIRCUIT.length; i++) {
    const curr = CIRCUIT[i];
    if (i + 1 < CIRCUIT.length) {
      const nxt = CIRCUIT[i + 1];
      ctx.quadraticCurveTo(
        tx(curr.x),
        ty(curr.y),
        tx((curr.x + nxt.x) / 2),
        ty((curr.y + nxt.y) / 2)
      );
    } else {
      ctx.lineTo(tx(curr.x), ty(curr.y));
    }
  }

  // Track surface
  ctx.strokeStyle = "#282828";
  ctx.lineWidth = 8;
  ctx.stroke();

  // Track edge
  ctx.strokeStyle = CHROME_MID;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Start/finish line
  const sfX = tx(CIRCUIT[0].x);
  const sfY = ty(CIRCUIT[0].y);
  ctx.strokeStyle = HIGHLIGHT;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(sfX, sfY - 8);
  ctx.lineTo(sfX, sfY + 8);
  ctx.stroke();

  // Turn labels
  ctx.font = "7px Helvetica, sans-serif";
  for (const turn of TURNS) {
    ctx.fillStyle = GRAY;
    ctx.fillText(turn.label, tx(turn.x) + 6, ty(turn.y) - 2);
  }

  // CORKSCREW label
  ctx.fillStyle = "#666666";
  ctx.font = "6px Helvetica, sans-serif";
  ctx.fillText("CORKSCREW", tx(0.12), ty(0.14));

  // Track name
  ctx.fillStyle = GRAY;
  ctx.font = "7px Helvetica, sans-serif";
  ctx.fillText("LAGUNA SECA", x + m + 2, y + h - m - 2);

  // Car position
  const pos = getCircuitPosition(progress);
  const carX = tx(pos.x);
  const carY = ty(pos.y);

  // Glow
  ctx.beginPath();
  ctx.arc(carX, carY, 10, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255,0,0,0.15)";
  ctx.fill();

  ctx.beginPath();
  ctx.arc(carX, carY, 6, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255,0,0,0.3)";
  ctx.fill();

  // Car dot
  ctx.beginPath();
  ctx.arc(carX, carY, 4, 0, Math.PI * 2);
  ctx.fillStyle = HIGHLIGHT;
  ctx.fill();

  ctx.beginPath();
  ctx.arc(carX, carY, 1.5, 0, Math.PI * 2);
  ctx.fillStyle = WHITE;
  ctx.fill();
}

interface TrackModeProps {
  state: DriverDisplayState;
}

export default function TrackMode({ state }: TrackModeProps) {
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

    // Layout: left 55% = thermal quadrant, right 45% = track map + info
    const leftW = w * 0.55;
    const rightX = leftW + 2;
    const rightW = w - rightX;

    // 2x2 thermal corners
    const cornerW = (leftW - 4) / 2;
    const cornerH = (h - 4) / 2;

    // Find hottest corner
    const hottestKey = Object.entries(state.corners).sort(
      ([, a], [, b]) => b.tireTempC - a.tireTempC
    )[0]?.[0];

    const cornerPositions = [
      { key: "FL", x: 0, y: 0 },
      { key: "FR", x: cornerW + 2, y: 0 },
      { key: "RL", x: 0, y: cornerH + 2 },
      { key: "RR", x: cornerW + 2, y: cornerH + 2 },
    ];

    for (const c of cornerPositions) {
      const data = state.corners[c.key];
      if (data) {
        drawThermalCorner(ctx, c.x, c.y, cornerW, cornerH, data, c.key, c.key === hottestKey);
      }
    }

    // Track map (right, top portion)
    const trackH = h * 0.6;
    drawTrackMap(ctx, rightX, 0, rightW, trackH, state.gps.circuitProgress);

    // Oil + brake strip area (right, below track map)
    const infoY = trackH + 2;
    const infoH = h - infoY;

    // Oil gauge mini
    ctx.fillStyle = "#121212";
    ctx.fillRect(rightX, infoY, rightW, 30);
    ctx.strokeStyle = CHROME_DARK;
    ctx.lineWidth = 1;
    ctx.strokeRect(rightX, infoY, rightW, 30);

    ctx.fillStyle = HIGHLIGHT;
    ctx.font = "bold 9px Helvetica, sans-serif";
    ctx.fillText("OIL", rightX + 4, infoY + 12);

    const oilColor = state.oilStatus === "hot" ? RED : state.oilStatus === "warn" ? YELLOW : GREEN;
    ctx.fillStyle = oilColor;
    ctx.font = "bold 14px Helvetica, sans-serif";
    ctx.fillText(`${Math.round(state.oilPsi)}`, rightX + 4, infoY + 26);

    ctx.fillStyle = GRAY;
    ctx.font = "9px Helvetica, sans-serif";
    ctx.fillText("PSI", rightX + 36, infoY + 26);

    ctx.fillStyle = state.oilTempC > 130 ? RED : WHITE;
    ctx.font = "10px Helvetica, sans-serif";
    ctx.fillText(`${Math.round(state.oilTempC)}°C`, rightX + rightW - 45, infoY + 26);
  }, [state]);

  useEffect(() => {
    const id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  }, [draw]);

  return (
    <div className="relative flex h-full w-full">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full"
        aria-label="Track mode: thermal quadrant and Laguna Seca circuit map"
      />

      {/* HTML overlay: findings + session widget */}
      <div
        className="pointer-events-none absolute right-0 bottom-0 flex flex-col gap-1 p-1"
        style={{ width: "45%" }}
      >
        {/* Findings list */}
        {state.findings.length > 0 && (
          <div
            className="overflow-hidden rounded"
            style={{
              backgroundColor: "rgba(18,18,18,0.95)",
              border: `1px solid ${CHROME_DARK}`,
              maxHeight: "50%",
            }}
          >
            <div className="px-2 py-1" style={{ borderBottom: `1px solid ${DIM}` }}>
              <span className="text-[10px] font-bold" style={{ color: HIGHLIGHT }}>
                KiSTI FINDINGS
              </span>
            </div>
            <div className="space-y-0.5 overflow-y-auto p-1" style={{ maxHeight: 72 }}>
              {state.findings.slice(0, 3).map((f) => (
                <div key={f.id} className="flex items-start gap-1 px-1">
                  <span
                    className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor:
                        f.severity === "critical" ? RED : f.severity === "warning" ? YELLOW : GREEN,
                    }}
                  />
                  <span className="text-[8px] leading-tight" style={{ color: GRAY }}>
                    {f.title}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session widget */}
        <div
          className="rounded p-1.5"
          style={{
            backgroundColor: "rgba(18,18,18,0.95)",
            border: `1px solid ${CHROME_DARK}`,
          }}
        >
          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
            <div>
              <span className="text-[8px]" style={{ color: GRAY }}>
                SESSION
              </span>
              <div className="text-xs font-bold tabular-nums" style={{ color: WHITE }}>
                {fmtTime(state.session.sessionTimeS)}
              </div>
            </div>
            <div>
              <span className="text-[8px]" style={{ color: GRAY }}>
                LAP
              </span>
              <div className="text-xs font-bold tabular-nums" style={{ color: WHITE }}>
                {state.session.lapCount}
              </div>
            </div>
            <div>
              <span className="text-[8px]" style={{ color: GRAY }}>
                LAST
              </span>
              <div className="text-xs font-bold tabular-nums" style={{ color: WHITE }}>
                {fmtTime(state.session.lastLapS)}
              </div>
            </div>
            <div>
              <span className="text-[8px]" style={{ color: GRAY }}>
                BEST
              </span>
              <div className="text-xs font-bold tabular-nums" style={{ color: HIGHLIGHT }}>
                {fmtTime(state.session.bestLapS)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
