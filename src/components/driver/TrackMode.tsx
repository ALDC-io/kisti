"use client";

import { useRef, useEffect, useCallback } from "react";
import { CornerTelemetry, DriverDisplayState, gt7TireColor } from "@/lib/driverTelemetry";
import { CIRCUIT, TURNS, getCircuitPosition } from "@/lib/lagunaSecaCircuit";
import VoiceTicker from "./VoiceTicker";

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

/** Driver POV forward-looking track view with vanishing point perspective */
function drawDriverPOV(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  progress: number,
  speedKph: number
) {
  // Sky/horizon gradient
  const skyGrad = ctx.createLinearGradient(0, 0, 0, h * 0.4);
  skyGrad.addColorStop(0, "#0A0F14");
  skyGrad.addColorStop(1, "#141E28");
  ctx.fillStyle = skyGrad;
  ctx.fillRect(0, 0, w, h * 0.4);

  // Ground
  const groundGrad = ctx.createLinearGradient(0, h * 0.4, 0, h);
  groundGrad.addColorStop(0, "#1A2818");
  groundGrad.addColorStop(1, "#0C1A0A");
  ctx.fillStyle = groundGrad;
  ctx.fillRect(0, h * 0.4, w, h * 0.6);

  // Vanishing point
  const vpX = w * 0.5;
  const vpY = h * 0.38;

  // Determine upcoming turn from circuit data
  const segCount = CIRCUIT.length - 1;
  const segFloat = (progress % 1) * segCount;
  const segIdx = Math.floor(segFloat) % segCount;
  const lookAhead1 = CIRCUIT[(segIdx + 1) % CIRCUIT.length];
  const lookAhead2 = CIRCUIT[(segIdx + 2) % CIRCUIT.length];
  const lookAhead3 = CIRCUIT[(segIdx + 3) % CIRCUIT.length];

  // Track curve direction from upcoming segments
  const curveDir = (lookAhead2.x - lookAhead1.x) * 3;
  const curveDir2 = (lookAhead3.x - lookAhead2.x) * 2;

  // Road edges with perspective — curve shifts the vanishing point
  const curveShift = curveDir * w * 0.3;
  const curveShift2 = (curveDir + curveDir2) * w * 0.2;
  const adjustedVpX = vpX + curveShift;

  // Track surface — trapezoidal road
  const roadBottomL = w * 0.1;
  const roadBottomR = w * 0.9;
  const roadTopL = adjustedVpX - w * 0.04;
  const roadTopR = adjustedVpX + w * 0.04;

  // Asphalt
  ctx.fillStyle = "#1E1E1E";
  ctx.beginPath();
  ctx.moveTo(roadBottomL, h);
  ctx.lineTo(roadTopL, vpY);
  ctx.lineTo(roadTopR, vpY);
  ctx.lineTo(roadBottomR, h);
  ctx.closePath();
  ctx.fill();

  // Track surface texture — subtle strips
  ctx.globalAlpha = 0.08;
  for (let i = 0; i < 8; i++) {
    const t = i / 8;
    const y = vpY + (h - vpY) * t;
    const lx = roadTopL + (roadBottomL - roadTopL) * t;
    const rx = roadTopR + (roadBottomR - roadTopR) * t;
    ctx.strokeStyle = i % 2 === 0 ? "#333" : "#111";
    ctx.lineWidth = 1 + t * 2;
    ctx.beginPath();
    ctx.moveTo(lx, y);
    ctx.lineTo(rx, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Curbs (red/white kerbing on edges)
  const kerbSegments = 12;
  for (let i = 0; i < kerbSegments; i++) {
    const t0 = i / kerbSegments;
    const t1 = (i + 1) / kerbSegments;

    const y0 = vpY + (h - vpY) * t0;
    const y1 = vpY + (h - vpY) * t1;

    // Left curb
    const lx0 = roadTopL + (roadBottomL - roadTopL) * t0;
    const lx1 = roadTopL + (roadBottomL - roadTopL) * t1;
    const curbW0 = (roadBottomR - roadBottomL) * 0.02 * (0.1 + t0 * 0.9);
    const curbW1 = (roadBottomR - roadBottomL) * 0.02 * (0.1 + t1 * 0.9);

    ctx.fillStyle = i % 2 === 0 ? HIGHLIGHT : WHITE;
    ctx.globalAlpha = 0.6 + t0 * 0.4;
    ctx.beginPath();
    ctx.moveTo(lx0 - curbW0, y0);
    ctx.lineTo(lx0, y0);
    ctx.lineTo(lx1, y1);
    ctx.lineTo(lx1 - curbW1, y1);
    ctx.closePath();
    ctx.fill();

    // Right curb
    const rx0 = roadTopR + (roadBottomR - roadTopR) * t0;
    const rx1 = roadTopR + (roadBottomR - roadTopR) * t1;
    ctx.beginPath();
    ctx.moveTo(rx0, y0);
    ctx.lineTo(rx0 + curbW0, y0);
    ctx.lineTo(rx1 + curbW1, y1);
    ctx.lineTo(rx1, y1);
    ctx.closePath();
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  // Center dashed line
  ctx.strokeStyle = "#444";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([8, 12]);
  ctx.beginPath();
  ctx.moveTo(w * 0.5, h);
  ctx.lineTo(adjustedVpX, vpY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Distant track curve hint (where the road bends)
  if (Math.abs(curveDir) > 0.02) {
    const bendX = adjustedVpX + curveShift2;
    const bendY = vpY - h * 0.06;
    ctx.strokeStyle = "#2A2A2A";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(roadTopL, vpY);
    ctx.quadraticCurveTo(adjustedVpX, vpY - 8, bendX - w * 0.03, bendY);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(roadTopR, vpY);
    ctx.quadraticCurveTo(adjustedVpX, vpY - 8, bendX + w * 0.03, bendY);
    ctx.stroke();
  }

  // Horizon glow
  const horizGlow = ctx.createRadialGradient(adjustedVpX, vpY, 0, adjustedVpX, vpY, w * 0.3);
  horizGlow.addColorStop(0, "rgba(230,0,0,0.06)");
  horizGlow.addColorStop(1, "rgba(230,0,0,0)");
  ctx.fillStyle = horizGlow;
  ctx.beginPath();
  ctx.arc(adjustedVpX, vpY, w * 0.3, 0, Math.PI * 2);
  ctx.fill();

  // Find nearest turn label
  const pos = getCircuitPosition(progress);
  let nearestTurn = "";
  let nearestDist = Infinity;
  for (const t of TURNS) {
    const dx = pos.x - t.x;
    const dy = pos.y - t.y;
    const d = Math.sqrt(dx * dx + dy * dy);
    if (d < nearestDist && d < 0.15) {
      nearestDist = d;
      nearestTurn = t.label;
    }
  }

  // Speed readout (bottom left)
  ctx.fillStyle = WHITE;
  ctx.font = "bold 20px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`${Math.round(speedKph)}`, 10, h - 10);
  ctx.fillStyle = GRAY;
  ctx.font = "9px Helvetica, sans-serif";
  ctx.fillText("km/h", 10 + ctx.measureText(`${Math.round(speedKph)}`).width + 4, h - 12);

  // Turn label (top center, if near a turn)
  if (nearestTurn) {
    ctx.fillStyle = HIGHLIGHT;
    ctx.font = "bold 11px Helvetica, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(nearestTurn, w * 0.5, 16);
    ctx.textAlign = "start";
  }

  // Track name
  ctx.fillStyle = DIM;
  ctx.font = "7px Helvetica, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("LAGUNA SECA", w - 8, h - 8);
  ctx.textAlign = "start";
}

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
  ctx.fillStyle = BG_DARK;
  ctx.fillRect(x, y, w, h);

  ctx.strokeStyle = isHottest ? HIGHLIGHT : CHROME_MID;
  ctx.lineWidth = isHottest ? 2 : 1;
  ctx.beginPath();
  ctx.roundRect(x + 1, y + 1, w - 2, h - 2, 4);
  ctx.stroke();

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

  ctx.fillStyle = WHITE;
  ctx.font = "bold 10px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(label, x + 6, y + 14);

  const wearColor = corner.tireWearPct > 50 ? GREEN : corner.tireWearPct > 25 ? YELLOW : RED;
  ctx.fillStyle = wearColor;
  ctx.font = "bold 9px Helvetica, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(corner.tireWearPct)}%`, x + w - 6, y + 14);
  ctx.textAlign = "left";

  const tireColor = gt7TireColor(corner.tireTempC);
  const tireX = x + w * 0.15;
  const tireY = y + 20;
  const tireW = w * 0.35;
  const tireH = h - 30;
  const r = Math.min(tireW, tireH) * 0.22;

  ctx.fillStyle = "#1A1A1A";
  ctx.beginPath();
  ctx.roundRect(tireX, tireY, tireW, tireH, r);
  ctx.fill();
  ctx.strokeStyle = "#3A3A3A";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(tireX, tireY, tireW, tireH, r);
  ctx.stroke();

  const fillH = tireH * (corner.tireWearPct / 100);
  const fillY = tireY + tireH - fillH;
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(tireX + 2, tireY + 2, tireW - 4, tireH - 4, r - 1);
  ctx.clip();

  const grad = ctx.createLinearGradient(tireX, fillY, tireX, tireY + tireH);
  grad.addColorStop(0, tireColor);
  grad.addColorStop(1, tireColor + "88");
  ctx.fillStyle = grad;
  ctx.fillRect(tireX + 2, fillY, tireW - 4, fillH);

  if (fillH > 4) {
    const glossGrad = ctx.createLinearGradient(tireX, fillY, tireX, fillY + 6);
    glossGrad.addColorStop(0, "rgba(255,255,255,0.3)");
    glossGrad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glossGrad;
    ctx.fillRect(tireX + 2, fillY, tireW - 4, Math.min(6, fillH));
  }

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

  ctx.strokeStyle = GRAY;
  ctx.lineWidth = 0.5;
  for (const pct of [25, 50, 75]) {
    const ny = tireY + tireH * (1 - pct / 100);
    ctx.beginPath();
    ctx.moveTo(tireX, ny);
    ctx.lineTo(tireX + 3, ny);
    ctx.stroke();
  }

  ctx.restore();

  const brakeX = tireX + tireW + 4;
  const brakeW = 6;
  const brakeColor = corner.brakeTempC > 316 ? RED : corner.brakeTempC > 232 ? YELLOW : GREEN;
  const brakeNorm = Math.max(0, Math.min(1, (corner.brakeTempC - 100) / 400));
  const brakeBarH = tireH * brakeNorm;

  ctx.fillStyle = "#1A1A1A";
  ctx.beginPath();
  ctx.roundRect(brakeX, tireY, brakeW, tireH, 2);
  ctx.fill();

  ctx.save();
  ctx.beginPath();
  ctx.roundRect(brakeX + 1, tireY + 1, brakeW - 2, tireH - 2, 1);
  ctx.clip();
  ctx.fillStyle = brakeColor;
  ctx.fillRect(brakeX + 1, tireY + tireH - brakeBarH, brakeW - 2, brakeBarH);
  ctx.restore();

  const textX = x + w * 0.62;

  ctx.fillStyle = tireColor;
  ctx.font = "bold 16px Helvetica, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`${Math.round(corner.tireTempC)}°`, textX, tireY + tireH * 0.35);

  ctx.fillStyle = GRAY;
  ctx.font = "8px Helvetica, sans-serif";
  ctx.fillText("TIRE", textX, tireY + tireH * 0.35 + 12);

  ctx.fillStyle = brakeColor;
  ctx.font = "bold 12px Helvetica, sans-serif";
  ctx.fillText(`${Math.round(corner.brakeTempC)}°`, textX, tireY + tireH * 0.7);

  ctx.fillStyle = GRAY;
  ctx.font = "8px Helvetica, sans-serif";
  ctx.fillText("BRAKE", textX, tireY + tireH * 0.7 + 12);

  ctx.textAlign = "start";
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

    // Layout: left 55% = driver POV, right 45% = GT7 tire gauges (same as street)
    const mapW = w * 0.55;
    const gaugeX = mapW + 4;
    const gaugeW = w - gaugeX;

    // Driver POV track view
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, mapW, h);
    ctx.clip();
    drawDriverPOV(ctx, mapW, h, state.gps.circuitProgress, state.gps.speedKph);
    ctx.restore();

    // Corner gauges (2x2 grid)
    const cornerH = (h - 4) * 0.5;
    const cornerW = (gaugeW - 4) * 0.5;
    const corners = [
      { key: "FL", x: gaugeX, y: 0, label: "FL" },
      { key: "FR", x: gaugeX + cornerW + 2, y: 0, label: "FR" },
      { key: "RL", x: gaugeX, y: cornerH + 2, label: "RL" },
      { key: "RR", x: gaugeX + cornerW + 2, y: cornerH + 2, label: "RR" },
    ];

    const hottestKey = Object.entries(state.corners).sort(
      ([, a], [, b]) => b.tireTempC - a.tireTempC
    )[0]?.[0];

    for (const c of corners) {
      const data = state.corners[c.key];
      if (data) {
        drawGT7Tire(ctx, c.x, c.y, cornerW, cornerH, data, c.label, c.key === hottestKey);
      }
    }
  }, [state]);

  useEffect(() => {
    const id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  }, [draw]);

  return (
    <div className="relative flex h-full w-full flex-col">
      {/* Compact session header bar */}
      <div
        className="flex shrink-0 items-center justify-between px-2"
        style={{
          height: 24,
          backgroundColor: "rgba(18,18,18,0.95)",
          borderBottom: `1px solid ${DIM}`,
        }}
      >
        <div className="flex items-center gap-3">
          <span className="text-[8px] font-bold" style={{ color: HIGHLIGHT }}>
            TRACK
          </span>
          <div className="flex items-center gap-1">
            <span className="text-[8px]" style={{ color: GRAY }}>SESSION</span>
            <span className="text-[10px] font-bold tabular-nums" style={{ color: WHITE }}>
              {fmtTime(state.session.sessionTimeS)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[8px]" style={{ color: GRAY }}>LAP</span>
            <span className="text-[10px] font-bold tabular-nums" style={{ color: WHITE }}>
              {state.session.lapCount}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="text-[8px]" style={{ color: GRAY }}>LAST</span>
            <span className="text-[10px] font-bold tabular-nums" style={{ color: WHITE }}>
              {fmtTime(state.session.lastLapS)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[8px]" style={{ color: GRAY }}>BEST</span>
            <span className="text-[10px] font-bold tabular-nums" style={{ color: HIGHLIGHT }}>
              {fmtTime(state.session.bestLapS)}
            </span>
          </div>
        </div>
      </div>

      {/* Canvas layer */}
      <div className="relative flex-1">
        <canvas
          ref={canvasRef}
          className="absolute inset-0 h-full w-full"
          aria-label="Track mode: driver POV and corner temperature gauges"
        />
      </div>

      {/* Voice ticker bar at bottom */}
      <VoiceTicker findings={state.findings} />
    </div>
  );
}
