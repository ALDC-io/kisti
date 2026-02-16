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

/**
 * Sample the circuit ahead of the current position, returning
 * lateral offsets (positive = right, negative = left) for N slices
 * of road stretching into the distance.
 */
function sampleRoadAhead(progress: number, slices: number): number[] {
  const cur = getCircuitPosition(progress);
  const offsets: number[] = [];
  // heading from current to next point
  const tiny = getCircuitPosition((progress + 0.005) % 1);
  const headX = tiny.x - cur.x;
  const headY = tiny.y - cur.y;
  const headLen = Math.sqrt(headX * headX + headY * headY) || 0.001;
  // unit heading
  const hx = headX / headLen;
  const hy = headY / headLen;
  // perpendicular (right-hand)
  const px = -hy;
  const py = hx;

  for (let i = 0; i < slices; i++) {
    // look further ahead for each slice (exponential spacing for perspective)
    const lookDist = 0.005 + (i / slices) * 0.18;
    const ahead = getCircuitPosition((progress + lookDist) % 1);
    // vector from car to lookahead point
    const dx = ahead.x - cur.x;
    const dy = ahead.y - cur.y;
    // project onto perpendicular axis → lateral offset
    const lateral = dx * px + dy * py;
    offsets.push(lateral);
  }
  return offsets;
}

/** Driver POV forward-looking track view with animated road flow */
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

  const vpY = h * 0.38;
  const roadH = h - vpY; // height of road area

  // --- Build curved road from circuit data ---
  const SLICES = 24;
  const laterals = sampleRoadAhead(progress, SLICES);
  const curveMagnitude = 2.8; // how dramatically turns show

  // For each depth slice, compute screen-space center and width
  // Perspective: depth t=0 is far (VP), t=1 is near (bottom of screen)
  const roadPts: { y: number; cx: number; halfW: number }[] = [];
  for (let i = 0; i < SLICES; i++) {
    // t goes from 0 (far/horizon) to 1 (near/camera)
    const t = i / (SLICES - 1);
    // Exponential depth — more detail near camera
    const depth = t * t;
    const y = vpY + roadH * depth;
    // Road width grows with perspective
    const halfW = w * (0.03 + 0.38 * depth);
    // Lateral offset from circuit curvature (scaled by screen width, stronger near camera)
    const lateralIdx = SLICES - 1 - i; // far slices use far lookahead
    const lateral = laterals[lateralIdx] || 0;
    const cx = w * 0.5 - lateral * curveMagnitude * w * (0.3 + depth * 0.7);
    roadPts.push({ y, cx, halfW });
  }

  // --- Draw asphalt as filled trapezoid strips ---
  for (let i = 0; i < roadPts.length - 1; i++) {
    const a = roadPts[i];
    const b = roadPts[i + 1];
    // Slightly lighter asphalt near camera for depth
    const shade = Math.round(0x1a + (b.y - vpY) / roadH * 0x0e);
    ctx.fillStyle = `rgb(${shade},${shade},${shade})`;
    ctx.beginPath();
    ctx.moveTo(a.cx - a.halfW, a.y);
    ctx.lineTo(a.cx + a.halfW, a.y);
    ctx.lineTo(b.cx + b.halfW, b.y);
    ctx.lineTo(b.cx - b.halfW, b.y);
    ctx.closePath();
    ctx.fill();
  }

  // --- Scrolling road stripes (perspective-correct, flow toward camera) ---
  const stripePhase = (progress * 400) % 1; // fast scroll
  ctx.globalAlpha = 0.07;
  const stripeCount = 16;
  for (let i = 0; i < stripeCount; i++) {
    const rawT = (i / stripeCount + stripePhase) % 1;
    const depth = rawT * rawT;
    const y = vpY + roadH * depth;
    // Interpolate road center/width at this y
    const idx = rawT * (SLICES - 1);
    const lo = Math.floor(idx);
    const hi = Math.min(lo + 1, SLICES - 1);
    const frac = idx - lo;
    const cx = roadPts[lo].cx + (roadPts[hi].cx - roadPts[lo].cx) * frac;
    const hw = roadPts[lo].halfW + (roadPts[hi].halfW - roadPts[lo].halfW) * frac;
    ctx.strokeStyle = i % 2 === 0 ? "#444" : "#222";
    ctx.lineWidth = 1 + depth * 3;
    ctx.beginPath();
    ctx.moveTo(cx - hw * 0.95, y);
    ctx.lineTo(cx + hw * 0.95, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // --- Scrolling curbs (red/white kerbing) ---
  const kerbCount = 18;
  const kerbPhase = (progress * 300) % 1;
  for (let i = 0; i < kerbCount; i++) {
    const rawT0 = (i / kerbCount + kerbPhase) % 1;
    const rawT1 = ((i + 1) / kerbCount + kerbPhase) % 1;
    if (rawT1 < rawT0) continue; // skip wrap-around segment

    const depth0 = rawT0 * rawT0;
    const depth1 = rawT1 * rawT1;
    const y0 = vpY + roadH * depth0;
    const y1 = vpY + roadH * depth1;

    // Interpolate road edges
    const idx0 = rawT0 * (SLICES - 1);
    const lo0 = Math.floor(idx0);
    const hi0 = Math.min(lo0 + 1, SLICES - 1);
    const f0 = idx0 - lo0;
    const cx0 = roadPts[lo0].cx + (roadPts[hi0].cx - roadPts[lo0].cx) * f0;
    const hw0 = roadPts[lo0].halfW + (roadPts[hi0].halfW - roadPts[lo0].halfW) * f0;

    const idx1 = rawT1 * (SLICES - 1);
    const lo1 = Math.floor(idx1);
    const hi1 = Math.min(lo1 + 1, SLICES - 1);
    const f1 = idx1 - lo1;
    const cx1 = roadPts[lo1].cx + (roadPts[hi1].cx - roadPts[lo1].cx) * f1;
    const hw1 = roadPts[lo1].halfW + (roadPts[hi1].halfW - roadPts[lo1].halfW) * f1;

    const curbW0 = hw0 * 0.06;
    const curbW1 = hw1 * 0.06;

    ctx.fillStyle = i % 2 === 0 ? HIGHLIGHT : WHITE;
    ctx.globalAlpha = 0.5 + depth0 * 0.5;

    // Left curb
    ctx.beginPath();
    ctx.moveTo(cx0 - hw0 - curbW0, y0);
    ctx.lineTo(cx0 - hw0, y0);
    ctx.lineTo(cx1 - hw1, y1);
    ctx.lineTo(cx1 - hw1 - curbW1, y1);
    ctx.closePath();
    ctx.fill();

    // Right curb
    ctx.beginPath();
    ctx.moveTo(cx0 + hw0, y0);
    ctx.lineTo(cx0 + hw0 + curbW0, y0);
    ctx.lineTo(cx1 + hw1 + curbW1, y1);
    ctx.lineTo(cx1 + hw1, y1);
    ctx.closePath();
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  // --- Scrolling center dashes ---
  const dashCount = 14;
  const dashPhase = (progress * 350) % 1;
  ctx.strokeStyle = "#555";
  for (let i = 0; i < dashCount; i++) {
    const rawT = (i / dashCount + dashPhase) % 1;
    const depth = rawT * rawT;
    const idx = rawT * (SLICES - 1);
    const lo = Math.floor(idx);
    const hi = Math.min(lo + 1, SLICES - 1);
    const frac = idx - lo;
    const cx = roadPts[lo].cx + (roadPts[hi].cx - roadPts[lo].cx) * frac;
    const y = vpY + roadH * depth;

    if (i % 2 === 0) {
      ctx.lineWidth = 1 + depth * 1.5;
      ctx.globalAlpha = 0.3 + depth * 0.5;
      const nextT = ((i + 0.4) / dashCount + dashPhase) % 1;
      const nextDepth = nextT * nextT;
      const nextIdx = nextT * (SLICES - 1);
      const nlo = Math.floor(nextIdx);
      const nhi = Math.min(nlo + 1, SLICES - 1);
      const nf = nextIdx - nlo;
      const ncx = roadPts[nlo].cx + (roadPts[nhi].cx - roadPts[nlo].cx) * nf;
      const ny = vpY + roadH * nextDepth;
      ctx.beginPath();
      ctx.moveTo(cx, y);
      ctx.lineTo(ncx, ny);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;

  // --- Horizon glow ---
  const vpCx = roadPts[0].cx;
  const horizGlow = ctx.createRadialGradient(vpCx, vpY, 0, vpCx, vpY, w * 0.25);
  horizGlow.addColorStop(0, "rgba(230,0,0,0.06)");
  horizGlow.addColorStop(1, "rgba(230,0,0,0)");
  ctx.fillStyle = horizGlow;
  ctx.beginPath();
  ctx.arc(vpCx, vpY, w * 0.25, 0, Math.PI * 2);
  ctx.fill();

  // --- Find nearest turn label ---
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
