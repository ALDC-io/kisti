"use client";

import { useRef, useEffect, useCallback } from "react";
import { DriverDisplayState } from "@/lib/driverTelemetry";

const BG_DARK = "#0A0A0A";
const WHITE = "#FFFFFF";
const RED = "#FF1A1A";
const GRAY = "#808080";

function drawLabel(ctx: CanvasRenderingContext2D, w: number, label: string, frame: number) {
  ctx.fillStyle = "rgba(0,0,0,0.6)";
  ctx.fillRect(0, 0, w, 14);
  ctx.fillStyle = WHITE;
  ctx.font = "bold 8px Helvetica, sans-serif";
  ctx.fillText(label, 4, 10);

  // REC indicator
  if (frame % 20 < 15) {
    ctx.beginPath();
    ctx.arc(w - 12, 7, 3, 0, Math.PI * 2);
    ctx.fillStyle = RED;
    ctx.fill();
  }
  ctx.fillStyle = WHITE;
  ctx.font = "7px Helvetica, sans-serif";
  ctx.fillText("REC", w - 32, 10);
}

function drawRGBCamera(ctx: CanvasRenderingContext2D, w: number, h: number, frame: number) {
  // Sky gradient
  const sky = ctx.createLinearGradient(0, 0, 0, h * 0.45);
  sky.addColorStop(0, "#6688AA");
  sky.addColorStop(0.5, "#8899AA");
  sky.addColorStop(1, "#99AABB");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h * 0.45);

  // Mountains
  ctx.beginPath();
  ctx.moveTo(0, h * 0.4);
  const peaks = [
    [0, 0.38], [0.08, 0.32], [0.15, 0.35], [0.22, 0.28],
    [0.32, 0.33], [0.4, 0.26], [0.48, 0.3], [0.55, 0.24],
    [0.62, 0.29], [0.7, 0.25], [0.78, 0.31], [0.85, 0.27],
    [0.92, 0.34], [1, 0.3],
  ];
  for (const [px, py] of peaks) ctx.lineTo(px * w, py * h);
  ctx.lineTo(w, h * 0.45);
  ctx.lineTo(0, h * 0.45);
  ctx.fillStyle = "#445566";
  ctx.fill();

  // Hillside
  const hill = ctx.createLinearGradient(0, h * 0.35, 0, h * 0.55);
  hill.addColorStop(0, "#664422");
  hill.addColorStop(1, "#553311");
  ctx.fillStyle = hill;
  ctx.fillRect(0, h * 0.4, w, h * 0.15);

  // Trees (simplified)
  const seed = 42;
  for (let i = 0; i < 20; i++) {
    const tx = ((seed + i * 37) % 100) / 100;
    const ty = 0.3 + ((seed + i * 53) % 35) / 100;
    const colors = ["#CC4400", "#DD6600", "#BB2200", "#EE8800", "#996600"];
    const cx = tx * w;
    const cy = ty * h;
    const sz = 6 + (1 - ty) * 12;
    ctx.fillStyle = "#3D2B1F";
    ctx.fillRect(cx - 1, cy, 2, sz / 2);
    ctx.beginPath();
    ctx.arc(cx, cy - sz / 4, sz / 2, 0, Math.PI * 2);
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
  }

  // Road surface
  const vx = w * 0.48;
  const vy = h * 0.42;
  const curve = Math.sin(frame * 0.02) * w * 0.03;

  ctx.beginPath();
  ctx.moveTo(w * 0.15, h);
  ctx.quadraticCurveTo(w * 0.3 + curve, h * 0.6, vx + curve * 0.5, vy);
  ctx.quadraticCurveTo(w * 0.65 - curve, h * 0.6, w * 0.85, h);
  ctx.fillStyle = "#3A3A3A";
  ctx.fill();

  // Center line
  ctx.setLineDash([8, 12]);
  ctx.strokeStyle = "#AA8800";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(w * 0.49, h);
  ctx.quadraticCurveTo(w * 0.48 + curve * 0.5, h * 0.65, vx, vy + 10);
  ctx.stroke();
  ctx.setLineDash([]);

  // Guardrails
  ctx.strokeStyle = "#888888";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(w * 0.18, h);
  ctx.quadraticCurveTo(w * 0.32 + curve, h * 0.62, vx + curve * 0.3, vy + 5);
  ctx.stroke();

  drawLabel(ctx, w, "RGB  1920x1080  60fps", frame);
}

function drawIRCamera(ctx: CanvasRenderingContext2D, w: number, h: number, frame: number) {
  // Thermal gradient background (cold to hot)
  const bg = ctx.createLinearGradient(0, 0, 0, h);
  bg.addColorStop(0, "#1A0033");
  bg.addColorStop(0.3, "#330066");
  bg.addColorStop(0.5, "#660099");
  bg.addColorStop(0.7, "#CC3300");
  bg.addColorStop(1, "#FF6600");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Heat blobs
  for (let i = 0; i < 8; i++) {
    const bx = ((i * 47 + frame) % 100) / 100 * w;
    const by = h * 0.3 + ((i * 31) % 50) / 100 * h * 0.5;
    const grad = ctx.createRadialGradient(bx, by, 0, bx, by, 20 + i * 5);
    grad.addColorStop(0, `rgba(255,${100 + i * 20},0,0.6)`);
    grad.addColorStop(1, "rgba(255,100,0,0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(bx, by, 20 + i * 5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Crosshair
  const cx = w / 2;
  const cy = h / 2;
  ctx.strokeStyle = "rgba(255,255,255,0.4)";
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(cx - 15, cy);
  ctx.lineTo(cx + 15, cy);
  ctx.moveTo(cx, cy - 15);
  ctx.lineTo(cx, cy + 15);
  ctx.stroke();

  // Temp scale
  ctx.fillStyle = WHITE;
  ctx.font = "7px monospace";
  ctx.fillText("35°C", w - 30, 24);
  ctx.fillText("-5°C", w - 30, h - 6);

  drawLabel(ctx, w, "Teledyne IR  640x480  30fps", frame);
}

function drawLiDARCamera(ctx: CanvasRenderingContext2D, w: number, h: number, frame: number) {
  ctx.fillStyle = "#050808";
  ctx.fillRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h * 0.6;

  // Distance rings
  ctx.strokeStyle = "rgba(0,255,100,0.15)";
  ctx.lineWidth = 0.5;
  const rings = [10, 25, 50];
  for (let i = 0; i < rings.length; i++) {
    const r = (i + 1) * Math.min(w, h) * 0.15;
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI, 0);
    ctx.stroke();

    ctx.fillStyle = "rgba(0,255,100,0.3)";
    ctx.font = "6px monospace";
    ctx.fillText(`${rings[i]}m`, cx + r - 14, cy - 2);
  }

  // Point cloud
  ctx.fillStyle = "#00FF66";
  const seed = frame * 7;
  for (let i = 0; i < 150; i++) {
    const angle = Math.PI + ((i * 137.5 + seed) % 180) * (Math.PI / 180);
    const dist = ((i * 73 + seed * 3) % 100) / 100;
    const r = dist * Math.min(w, h) * 0.45;
    const jitterX = (Math.sin(i + frame * 0.1) * 2);
    const jitterY = (Math.cos(i * 1.3 + frame * 0.1) * 2);
    const px = cx + Math.cos(angle) * r + jitterX;
    const py = cy + Math.sin(angle) * r + jitterY;

    if (py < h && px > 0 && px < w) {
      const brightness = 0.3 + dist * 0.7;
      ctx.globalAlpha = brightness;
      ctx.fillRect(px, py, 2, 2);
    }
  }
  ctx.globalAlpha = 1;

  drawLabel(ctx, w, "LiDAR  1024x64  10fps", frame);
}

function drawWeatherCamera(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  frame: number,
  weather: { tempC: number; windDir: string; windKph: number; humidity: number; elevation: number }
) {
  // Overcast sky
  const bg = ctx.createLinearGradient(0, 0, 0, h);
  bg.addColorStop(0, "#667788");
  bg.addColorStop(1, "#889999");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Ground
  ctx.fillStyle = "#556655";
  ctx.fillRect(0, h * 0.65, w, h * 0.35);

  // Conditions overlay
  ctx.fillStyle = "rgba(0,0,0,0.7)";
  ctx.fillRect(8, h * 0.25, w - 16, h * 0.55);

  const lx = 16;
  let ly = h * 0.35;
  const lineH = 16;

  ctx.fillStyle = WHITE;
  ctx.font = "bold 12px Helvetica, sans-serif";
  ctx.fillText(`${Math.round(weather.tempC)}°C`, lx, ly);
  ly += lineH;

  ctx.font = "10px Helvetica, sans-serif";
  ctx.fillStyle = "#CCCCCC";
  ctx.fillText(`${weather.windDir} ${Math.round(weather.windKph)} km/h`, lx, ly);
  ly += lineH;

  ctx.fillText(`${Math.round(weather.humidity)}% humidity`, lx, ly);
  ly += lineH;

  ctx.fillText("Dry road", lx, ly);
  ly += lineH;

  ctx.fillText(`${weather.elevation}m elev`, lx, ly);

  drawLabel(ctx, w, "Weather  1280x720  15fps", frame);
}

interface VideoModeProps {
  state: DriverDisplayState;
}

export default function VideoMode({ state }: VideoModeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef(0);
  const animRef = useRef<number>(0);

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
    const halfW = (w - 2) / 2;
    const halfH = (h - 2) / 2;

    frameRef.current += 1;
    const frame = frameRef.current;

    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, w, h);

    // Top-left: RGB
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, halfW, halfH);
    ctx.clip();
    drawRGBCamera(ctx, halfW, halfH, frame);
    ctx.restore();

    // Top-right: IR
    ctx.save();
    ctx.translate(halfW + 2, 0);
    ctx.beginPath();
    ctx.rect(0, 0, halfW, halfH);
    ctx.clip();
    drawIRCamera(ctx, halfW, halfH, frame);
    ctx.restore();

    // Bottom-left: LiDAR
    ctx.save();
    ctx.translate(0, halfH + 2);
    ctx.beginPath();
    ctx.rect(0, 0, halfW, halfH);
    ctx.clip();
    drawLiDARCamera(ctx, halfW, halfH, frame);
    ctx.restore();

    // Bottom-right: Weather
    ctx.save();
    ctx.translate(halfW + 2, halfH + 2);
    ctx.beginPath();
    ctx.rect(0, 0, halfW, halfH);
    ctx.clip();
    drawWeatherCamera(ctx, halfW, halfH, frame, state.weather);
    ctx.restore();

    animRef.current = requestAnimationFrame(draw);
  }, [state.weather]);

  useEffect(() => {
    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full"
      aria-label="Video mode: four camera feeds showing RGB, thermal, LiDAR, and weather views"
    />
  );
}
