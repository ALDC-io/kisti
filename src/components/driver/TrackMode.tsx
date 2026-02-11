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

function fmtTime(seconds: number): string {
  if (seconds <= 0) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function tireHeatColor(tempC: number): string {
  // cold=blue → green → yellow → red
  if (tempC < 60) return "#50B4FF";
  if (tempC < 80) return "#00CC66";
  if (tempC < 100) return "#FFAA00";
  return "#FF2222";
}

function drawStiHeatmap(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  corners: Record<string, CornerTelemetry>,
  oilTempC: number
) {
  // Background
  ctx.fillStyle = BG_DARK;
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = CHROME_DARK;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);

  // Car dimensions within panel
  const carW = w * 0.5;
  const carH = h * 0.82;
  const carX = x + (w - carW) / 2;
  const carY = y + (h - carH) / 2;

  // --- Draw simplified STI silhouette (top-down 5-door hatchback) ---
  const cx = carX + carW / 2;

  ctx.beginPath();
  // Front bumper — rounded nose
  ctx.moveTo(carX + carW * 0.25, carY);
  ctx.quadraticCurveTo(cx, carY - carH * 0.02, carX + carW * 0.75, carY);
  // Right side — front fender to rear
  ctx.lineTo(carX + carW * 0.82, carY + carH * 0.08);
  ctx.lineTo(carX + carW * 0.85, carY + carH * 0.18);
  ctx.lineTo(carX + carW * 0.83, carY + carH * 0.35);
  // Right door indent
  ctx.lineTo(carX + carW * 0.82, carY + carH * 0.50);
  ctx.lineTo(carX + carW * 0.84, carY + carH * 0.65);
  // Rear fender flare
  ctx.lineTo(carX + carW * 0.86, carY + carH * 0.78);
  ctx.lineTo(carX + carW * 0.82, carY + carH * 0.90);
  // Rear bumper
  ctx.quadraticCurveTo(cx, carY + carH * 1.02, carX + carW * 0.18, carY + carH * 0.90);
  // Left side — rear to front (mirror)
  ctx.lineTo(carX + carW * 0.14, carY + carH * 0.78);
  ctx.lineTo(carX + carW * 0.16, carY + carH * 0.65);
  ctx.lineTo(carX + carW * 0.18, carY + carH * 0.50);
  ctx.lineTo(carX + carW * 0.17, carY + carH * 0.35);
  ctx.lineTo(carX + carW * 0.15, carY + carH * 0.18);
  ctx.lineTo(carX + carW * 0.18, carY + carH * 0.08);
  ctx.closePath();

  ctx.fillStyle = "#1A1A1A";
  ctx.fill();
  ctx.strokeStyle = "#606060";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Hood scoop (STI signature)
  ctx.fillStyle = "#222222";
  ctx.beginPath();
  ctx.roundRect(cx - carW * 0.1, carY + carH * 0.08, carW * 0.2, carH * 0.12, 2);
  ctx.fill();
  ctx.strokeStyle = "#444444";
  ctx.lineWidth = 0.5;
  ctx.stroke();

  // Windshield line
  ctx.strokeStyle = "#404040";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(carX + carW * 0.22, carY + carH * 0.25);
  ctx.lineTo(carX + carW * 0.78, carY + carH * 0.25);
  ctx.stroke();

  // Rear window line
  ctx.beginPath();
  ctx.moveTo(carX + carW * 0.25, carY + carH * 0.72);
  ctx.lineTo(carX + carW * 0.75, carY + carH * 0.72);
  ctx.stroke();

  // Wing (rear spoiler)
  ctx.fillStyle = "#252525";
  ctx.beginPath();
  ctx.roundRect(carX + carW * 0.12, carY + carH * 0.88, carW * 0.76, carH * 0.03, 1);
  ctx.fill();
  ctx.strokeStyle = "#505050";
  ctx.lineWidth = 0.5;
  ctx.stroke();

  // --- Wheel positions (relative to car) ---
  const wheels = [
    { key: "FL", wx: carX + carW * 0.15, wy: carY + carH * 0.15 },
    { key: "FR", wx: carX + carW * 0.85, wy: carY + carH * 0.15 },
    { key: "RL", wx: carX + carW * 0.15, wy: carY + carH * 0.80 },
    { key: "RR", wx: carX + carW * 0.85, wy: carY + carH * 0.80 },
  ];

  const heatRadius = carW * 0.22;
  const brakeRadius = heatRadius * 0.35;

  for (const wh of wheels) {
    const corner = corners[wh.key];
    if (!corner) continue;

    // Tire thermal radial gradient
    const heatColor = tireHeatColor(corner.tireTempC);
    const grad = ctx.createRadialGradient(wh.wx, wh.wy, 0, wh.wx, wh.wy, heatRadius);
    grad.addColorStop(0, heatColor + "CC");
    grad.addColorStop(0.5, heatColor + "66");
    grad.addColorStop(1, heatColor + "00");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(wh.wx, wh.wy, heatRadius, 0, Math.PI * 2);
    ctx.fill();

    // Brake disc indicator
    const brakeColor = corner.brakeTempC > 316 ? RED : corner.brakeTempC > 232 ? YELLOW : GREEN;
    ctx.fillStyle = brakeColor;
    ctx.beginPath();
    ctx.arc(wh.wx, wh.wy, brakeRadius, 0, Math.PI * 2);
    ctx.fill();

    // Small dark center dot
    ctx.fillStyle = "#111111";
    ctx.beginPath();
    ctx.arc(wh.wx, wh.wy, brakeRadius * 0.35, 0, Math.PI * 2);
    ctx.fill();
  }

  // Engine bay heat zone (front-center)
  const engX = cx;
  const engY = carY + carH * 0.12;
  const engRadius = carW * 0.18;
  const oilNorm = Math.max(0, Math.min(1, (oilTempC - 80) / 80));
  const engAlpha = Math.round(0x33 + oilNorm * 0x99).toString(16).padStart(2, "0");
  const engGrad = ctx.createRadialGradient(engX, engY, 0, engX, engY, engRadius);
  engGrad.addColorStop(0, `#FF4400${engAlpha}`);
  engGrad.addColorStop(0.6, `#FF220044`);
  engGrad.addColorStop(1, "#FF220000");
  ctx.fillStyle = engGrad;
  ctx.beginPath();
  ctx.arc(engX, engY, engRadius, 0, Math.PI * 2);
  ctx.fill();

  // Pure visual heatmap — no corner labels
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

    // Layout: left 55% = STI heatmap, right 45% = track map + info
    const leftW = w * 0.55;
    const rightX = leftW + 2;
    const rightW = w - rightX;

    // STI silhouette heatmap
    drawStiHeatmap(ctx, 0, 0, leftW, h, state.corners, state.oilTempC);

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
