"use client";

import { useRef, useEffect, useCallback, useState } from "react";

/**
 * Zeus Voice Waveform — Reusable audio-synced visualizer.
 *
 * Renders a 3-column mirrored bar waveform driven by real audio amplitude.
 * Center column leads, outer bars follow. Gradient from bright core to
 * dim edges. Configurable colors, size, and urgency.
 *
 * Usage:
 *   <VoiceWaveform
 *     envelope={amplitudeArray}
 *     isPlaying={true}
 *     palette="rose"
 *     width={240}
 *     height={140}
 *   />
 */

export type WaveformPalette = "rose" | "blue" | "green" | "amber" | "custom";

interface PaletteColors {
  core: [number, number, number];    // RGB at horizontal center
  mid: [number, number, number];     // RGB at mid segments
  outer: [number, number, number];   // RGB at outermost segments
  dark: [number, number, number];    // RGB when unlit
}

const PALETTES: Record<string, PaletteColors> = {
  rose: {
    core: [240, 100, 120],
    mid: [230, 40, 70],
    outer: [200, 10, 51],
    dark: [20, 5, 0],
  },
  blue: {
    core: [100, 180, 255],
    mid: [40, 120, 230],
    outer: [10, 60, 180],
    dark: [0, 5, 20],
  },
  green: {
    core: [100, 240, 140],
    mid: [40, 200, 80],
    outer: [10, 150, 50],
    dark: [0, 15, 5],
  },
  amber: {
    core: [255, 200, 80],
    mid: [240, 140, 40],
    outer: [200, 80, 10],
    dark: [20, 10, 0],
  },
};

interface VoiceWaveformProps {
  /** Amplitude envelope array (0.0-1.0 per frame) */
  envelope?: number[];
  /** Whether audio is currently playing */
  isPlaying?: boolean;
  /** Current amplitude for real-time mode (0.0-1.0) */
  amplitude?: number;
  /** Color palette name or custom colors */
  palette?: WaveformPalette;
  /** Custom palette colors (when palette="custom") */
  customColors?: PaletteColors;
  /** Canvas width */
  width?: number;
  /** Canvas height */
  height?: number;
  /** Number of vertical segments per column (each side of center) */
  segments?: number;
  /** Background color */
  bgColor?: string;
  /** Frames per second for envelope playback */
  fps?: number;
}

function lerpColor(
  a: [number, number, number],
  b: [number, number, number],
  t: number,
): [number, number, number] {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

export default function VoiceWaveform({
  envelope,
  isPlaying = false,
  amplitude: externalAmplitude,
  palette = "rose",
  customColors,
  width = 240,
  height = 140,
  segments = 7,
  bgColor = "#0a0a0a",
  fps = 40,
}: VoiceWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef(0);
  const animRef = useRef<number>(0);
  const prevCenterRef = useRef(0);
  const intensityRef = useRef(1.0);
  const lastFrameTimeRef = useRef(0);

  const colors = customColors || PALETTES[palette] || PALETTES.rose;

  const getSegmentColor = useCallback(
    (segIdx: number, colIdx: number, intensity: number): string => {
      const t = segIdx / Math.max(1, segments - 1); // 0.0 → 1.0
      const hFade = colIdx === 1 ? 1.0 : 0.6; // Center full, outer 60%

      let rgb: [number, number, number];
      if (t < 0.3) {
        rgb = lerpColor(colors.core, colors.mid, t / 0.3);
      } else if (t < 0.6) {
        rgb = lerpColor(colors.mid, colors.outer, (t - 0.3) / 0.3);
      } else {
        rgb = lerpColor(colors.outer, colors.dark, (t - 0.6) / 0.4);
      }

      const combined = hFade * intensity;
      const r = Math.round(rgb[0] * combined);
      const g = Math.round(rgb[1] * combined);
      const b = Math.round(rgb[2] * combined);
      const a = Math.max(0.15, combined * (1.0 - t * 0.5));

      return `rgba(${r},${g},${b},${a})`;
    },
    [colors, segments],
  );

  const draw = useCallback(
    (amp: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Update intensity (dims during pauses)
      if (amp > 0.1) {
        intensityRef.current = Math.min(1.0, intensityRef.current + 0.15);
      } else {
        intensityRef.current = Math.max(0.3, intensityRef.current - 0.08);
      }
      const intensity = intensityRef.current;

      // Compute levels
      let center = Math.round(amp * segments);

      // Decay: step down 1 per frame during pauses
      if (center < prevCenterRef.current) {
        center = Math.max(0, prevCenterRef.current - 1);
      }
      // Minimum 1 while playing
      if (isPlaying) {
        center = Math.max(1, center);
      }
      prevCenterRef.current = center;

      // Outer bars: lockstep at 60%, only when center >= 2
      let outer = 0;
      if (center >= 2) {
        outer = Math.max(0, Math.round(center * 0.6));
      }

      const levels = [outer, center, outer];

      // Clear
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, width, height);

      // Layout
      const numCols = 3;
      const segGap = 4;
      const colGap = 10;
      const outerShrink = 1;

      const colWidth = (width - (numCols + 1) * colGap) / numCols;
      const segH = Math.max(3, (height / 2 - segments * segGap) / segments);
      const centerY = height / 2;

      for (let col = 0; col < numCols; col++) {
        const level = levels[col];
        const colX = colGap + col * (colWidth + colGap);
        const isOuter = col !== 1;
        const sh = isOuter ? segH - outerShrink : segH;
        const sw = isOuter ? colWidth - 2 : colWidth;
        const sx = isOuter ? colX + 1 : colX;

        for (let seg = 0; seg < segments; seg++) {
          const lit = seg < level;

          if (lit) {
            ctx.fillStyle = getSegmentColor(seg, col, intensity);
          } else {
            const [dr, dg, db] = colors.dark;
            ctx.fillStyle = `rgba(${dr},${dg},${db},0.04)`;
          }

          // Glow on inner lit segments
          if (lit && seg < 3) {
            const glowAlpha = Math.max(0, 0.35 - seg * 0.12);
            if (glowAlpha > 0) {
              ctx.fillStyle = getSegmentColor(seg, col, intensity);
              const ge = 2;
              // Top glow
              const gyTop = centerY - (seg + 1) * (segH + segGap) - ge;
              ctx.globalAlpha = glowAlpha;
              ctx.fillRect(sx - ge, gyTop, sw + ge * 2, sh + ge * 2);
              // Bottom glow
              const gyBot = centerY + seg * (segH + segGap) - ge;
              ctx.fillRect(sx - ge, gyBot, sw + ge * 2, sh + ge * 2);
              ctx.globalAlpha = 1.0;
            }
          }

          // Segment fill
          ctx.fillStyle = lit
            ? getSegmentColor(seg, col, intensity)
            : `rgba(${colors.dark[0]},${colors.dark[1]},${colors.dark[2]},0.04)`;

          const yTop = centerY - (seg + 1) * (segH + segGap);
          ctx.fillRect(sx, yTop, sw, sh);
          const yBot = centerY + seg * (segH + segGap);
          ctx.fillRect(sx, yBot, sw, sh);
        }
      }
    },
    [
      width,
      height,
      segments,
      bgColor,
      colors,
      isPlaying,
      getSegmentColor,
    ],
  );

  // Envelope playback mode
  useEffect(() => {
    if (!envelope || !isPlaying) {
      frameRef.current = 0;
      return;
    }

    const interval = 1000 / fps;
    let idx = 0;

    const tick = () => {
      const now = performance.now();
      if (now - lastFrameTimeRef.current >= interval) {
        lastFrameTimeRef.current = now;
        if (idx < envelope.length) {
          draw(envelope[idx]);
          idx++;
        } else {
          draw(0);
        }
      }
      if (isPlaying && idx <= envelope.length) {
        animRef.current = requestAnimationFrame(tick);
      }
    };

    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [envelope, isPlaying, fps, draw]);

  // External amplitude mode (real-time, no envelope)
  useEffect(() => {
    if (envelope || externalAmplitude === undefined) return;

    draw(externalAmplitude);
  }, [externalAmplitude, envelope, draw]);

  // Idle state (not playing, no amplitude)
  useEffect(() => {
    if (!isPlaying && !externalAmplitude) {
      prevCenterRef.current = 0;
      intensityRef.current = 1.0;
      draw(0);
    }
  }, [isPlaying, externalAmplitude, draw]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width, height, borderRadius: 4 }}
    />
  );
}
