/**
 * Laguna Seca circuit path data.
 * Normalized 0-1 coordinates matching the PySide6 track_map_widget.
 */

export interface CircuitPoint {
  x: number;
  y: number;
}

export interface TurnLabel {
  x: number;
  y: number;
  label: string;
}

/** 22-point bezier-compatible circuit (last point closes the loop) */
export const CIRCUIT: CircuitPoint[] = [
  { x: 0.85, y: 0.75 }, // Start/finish
  { x: 0.70, y: 0.78 }, // T1 approach
  { x: 0.55, y: 0.82 }, // T2 Andretti hairpin entry
  { x: 0.48, y: 0.78 }, // Hairpin apex
  { x: 0.45, y: 0.70 }, // Hairpin exit
  { x: 0.50, y: 0.60 }, // Short straight
  { x: 0.55, y: 0.52 }, // T3
  { x: 0.58, y: 0.45 }, // T4
  { x: 0.55, y: 0.38 }, // T5 entry (esses)
  { x: 0.48, y: 0.32 }, // T5 exit
  { x: 0.40, y: 0.28 }, // T6
  { x: 0.32, y: 0.22 }, // Corkscrew approach
  { x: 0.28, y: 0.18 }, // Corkscrew top (T8)
  { x: 0.25, y: 0.25 }, // Corkscrew drop
  { x: 0.22, y: 0.35 }, // Corkscrew exit
  { x: 0.25, y: 0.45 }, // Downhill
  { x: 0.30, y: 0.55 }, // T9 Rainey curve entry
  { x: 0.38, y: 0.62 }, // Rainey apex
  { x: 0.48, y: 0.65 }, // Rainey exit
  { x: 0.58, y: 0.68 }, // Back straight entry
  { x: 0.70, y: 0.70 }, // Back straight
  { x: 0.85, y: 0.75 }, // Start/finish (close loop)
];

export const TURNS: TurnLabel[] = [
  { x: 0.52, y: 0.83, label: "T2" },
  { x: 0.56, y: 0.48, label: "T4" },
  { x: 0.42, y: 0.30, label: "T6" },
  { x: 0.24, y: 0.16, label: "T8" },
  { x: 0.34, y: 0.60, label: "T9" },
];

/** Interpolate position along circuit at progress 0-1 */
export function getCircuitPosition(progress: number): CircuitPoint {
  const p = ((progress % 1) + 1) % 1;
  const n = CIRCUIT.length;
  const total = n - 1;
  const segFloat = p * total;
  const segIdx = Math.floor(segFloat) % total;
  const segFrac = segFloat - Math.floor(segFloat);

  const p0 = CIRCUIT[segIdx];
  const p1 = CIRCUIT[(segIdx + 1) % n];

  return {
    x: p0.x + (p1.x - p0.x) * segFrac,
    y: p0.y + (p1.y - p0.y) * segFrac,
  };
}
