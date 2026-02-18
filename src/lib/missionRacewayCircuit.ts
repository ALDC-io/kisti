/**
 * Mission Raceway circuit path data.
 * 2.25 km, 9 turns, counter-clockwise layout.
 * Normalized 0-1 coordinates.
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

/** 24-point circuit path (last point closes the loop) */
export const CIRCUIT: CircuitPoint[] = [
  { x: 0.82, y: 0.60 }, // Start/finish straight
  { x: 0.75, y: 0.55 }, // S/F approach to T1
  { x: 0.68, y: 0.48 }, // T1 entry (right-hander)
  { x: 0.63, y: 0.40 }, // T1 apex
  { x: 0.60, y: 0.32 }, // T1 exit
  { x: 0.55, y: 0.25 }, // Short straight to T2
  { x: 0.48, y: 0.20 }, // T2 entry (left kink)
  { x: 0.40, y: 0.18 }, // T2 apex
  { x: 0.32, y: 0.20 }, // T3 entry (right-hander)
  { x: 0.26, y: 0.25 }, // T3 apex
  { x: 0.22, y: 0.32 }, // T3 exit, back straight entry
  { x: 0.20, y: 0.42 }, // Back straight
  { x: 0.22, y: 0.52 }, // T4 entry (left-hander)
  { x: 0.25, y: 0.58 }, // T4 apex
  { x: 0.28, y: 0.64 }, // T5 entry (right)
  { x: 0.32, y: 0.70 }, // T5 apex
  { x: 0.38, y: 0.74 }, // T6 entry (left kink)
  { x: 0.45, y: 0.76 }, // T6 apex
  { x: 0.52, y: 0.78 }, // T7A entry (chicane)
  { x: 0.58, y: 0.75 }, // T7A apex
  { x: 0.62, y: 0.72 }, // T7B exit
  { x: 0.68, y: 0.70 }, // T8/T9 complex entry
  { x: 0.75, y: 0.66 }, // T9 apex, onto main straight
  { x: 0.82, y: 0.60 }, // Start/finish (close loop)
];

export const TURNS: TurnLabel[] = [
  { x: 0.65, y: 0.38, label: "T1" },
  { x: 0.42, y: 0.16, label: "T2" },
  { x: 0.23, y: 0.23, label: "T3" },
  { x: 0.22, y: 0.56, label: "T4" },
  { x: 0.30, y: 0.72, label: "T5" },
  { x: 0.43, y: 0.78, label: "T6" },
  { x: 0.56, y: 0.80, label: "T7" },
  { x: 0.72, y: 0.68, label: "T9" },
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
