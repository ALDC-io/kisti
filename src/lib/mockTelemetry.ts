"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  TelemetryPoint,
  TelemetryStream,
  TelemetryStatus,
  ZeusFinding,
  CloudSync,
  CloudSyncStatus,
} from "./types";
import { NODES } from "./kistiGraph";

const HISTORY_LENGTH = 30;

/**
 * Session-phase baselines for Mission Raceway simulation.
 * Warm-up (~0-105s): 60-70% pace, building temps
 * Hot laps (~105-350s): full pace, peak telemetry
 * Cool-down (~350s+): 50-60% pace, temps dropping
 */
type PhaseBaselines = Record<string, number>;

const WARM_UP_BASELINES: PhaseBaselines = {
  "brake-fl": 280,
  "brake-fr": 305,
  "brake-rl": 210,
  "brake-rr": 205,
  "tire-fl": 138,
  "tire-fr": 145,
  "tire-rl": 125,
  "tire-rr": 122,
  egt: 1050,
  boost: 12,
  "oil-temp": 192,
  "oil-pressure": 58,
  wideband: 14.5,
  "teledyne-ir": 30,
  lidar: 20,
  "rgb-cam": 60,
  "weather-cam": 15,
  ecu: 45,
  jetson: 62,
};

const HOT_LAP_BASELINES: PhaseBaselines = {
  "brake-fl": 388,
  "brake-fr": 428, // +40°F bias — the "story"
  "brake-rl": 275,
  "brake-rr": 270,
  "tire-fl": 168,
  "tire-fr": 182, // Hotter from brake heat soak
  "tire-rl": 150,
  "tire-rr": 148,
  egt: 1420,
  boost: 19,
  "oil-temp": 235,
  "oil-pressure": 52,
  wideband: 14.0,
  "teledyne-ir": 30,
  lidar: 20,
  "rgb-cam": 60,
  "weather-cam": 15,
  ecu: 45,
  jetson: 62,
};

const COOL_DOWN_BASELINES: PhaseBaselines = {
  "brake-fl": 285,
  "brake-fr": 312,
  "brake-rl": 222,
  "brake-rr": 218,
  "tire-fl": 148,
  "tire-fr": 157,
  "tire-rl": 135,
  "tire-rr": 132,
  egt: 1020,
  boost: 9,
  "oil-temp": 218,
  "oil-pressure": 55,
  wideband: 14.6,
  "teledyne-ir": 30,
  lidar: 20,
  "rgb-cam": 60,
  "weather-cam": 15,
  ecu: 45,
  jetson: 62,
};

/** Session start timestamp — set on first tick */
let sessionStartMs: number | null = null;

/** Get session-phase-aware baselines based on elapsed time */
function getPhaseBaselines(): PhaseBaselines {
  if (sessionStartMs === null) {
    sessionStartMs = Date.now();
    return WARM_UP_BASELINES;
  }
  const elapsedS = (Date.now() - sessionStartMs) / 1000;
  if (elapsedS < 105) return WARM_UP_BASELINES;   // Warm-up lap
  if (elapsedS < 350) return HOT_LAP_BASELINES;    // 3 hot laps
  return COOL_DOWN_BASELINES;                        // Cool-down laps
}

/** Noise magnitude per sensor */
const NOISE: Record<string, number> = {
  "brake-fl": 12,
  "brake-fr": 18, // More volatile too
  "brake-rl": 8,
  "brake-rr": 8,
  "tire-fl": 6,
  "tire-fr": 8,
  "tire-rl": 5,
  "tire-rr": 5,
  egt: 40,
  boost: 2,
  "oil-temp": 5,
  "oil-pressure": 4,
  wideband: 0.3,
  "teledyne-ir": 2,
  lidar: 1.5,
  "rgb-cam": 3,
  "weather-cam": 1,
  ecu: 8,
  jetson: 6,
};

function gaussianRandom(): number {
  let u = 0,
    v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function getStatus(
  value: number,
  warnThreshold: number,
  hotThreshold: number
): TelemetryStatus {
  // For wideband, "hot" means too rich (below threshold)
  if (hotThreshold < warnThreshold) {
    if (value <= hotThreshold) return "hot";
    if (value >= warnThreshold || value <= hotThreshold + 1) return "warn";
    return "ok";
  }
  if (value >= hotThreshold) return "hot";
  if (value >= warnThreshold) return "warn";
  return "ok";
}

function generatePoint(
  nodeId: string,
  prevValue: number | null
): TelemetryPoint {
  const node = NODES.find((n) => n.id === nodeId);
  if (!node) return { value: 0, timestamp: Date.now(), status: "ok" };

  const baselines = getPhaseBaselines();
  const baseline = baselines[nodeId] ?? (node.min + node.max) / 2;
  const noise = NOISE[nodeId] ?? 5;

  let value: number;
  if (prevValue !== null) {
    // Random walk from previous value, mean-reverting toward baseline
    const drift = (baseline - prevValue) * 0.05;
    value = prevValue + drift + gaussianRandom() * noise;
  } else {
    value = baseline + gaussianRandom() * noise;
  }

  // Clamp to sensor range
  value = Math.max(node.min, Math.min(node.max, value));

  // Brake FR: add extra bias to ensure it's consistently hotter
  if (nodeId === "brake-fr") {
    const flBase = baselines["brake-fl"];
    const minDelta = 15;
    if (value < flBase + minDelta) {
      value = flBase + minDelta + Math.random() * 25;
    }
  }

  // Tire FR: heat soak from hot FR brake
  if (nodeId === "tire-fr") {
    const flBase = baselines["tire-fl"];
    const minDelta = 10;
    if (value < flBase + minDelta) {
      value = flBase + minDelta + Math.random() * 5;
    }
  }

  return {
    value: Math.round(value * 10) / 10,
    timestamp: Date.now(),
    status: getStatus(value, node.warnThreshold, node.hotThreshold),
  };
}

/** Zeus findings that rotate on a timer */
const FINDINGS_POOL: Omit<ZeusFinding, "timestamp">[] = [
  {
    id: "finding-brake-asymmetry",
    title: "Brake Asymmetry Detected",
    severity: "warning",
    description:
      "Front-right brake rotor is consistently 15-40°F hotter than front-left. Possible caliper drag or pad glazing on FR.",
    relatedNodes: ["brake-fr", "brake-fl"],
  },
  {
    id: "finding-egt-trend",
    title: "EGT Upward Trend",
    severity: "info",
    description:
      "Exhaust gas temperature trending 3% higher over last 20 minutes. Within normal range but monitoring.",
    relatedNodes: ["egt"],
  },
  {
    id: "finding-boost-stability",
    title: "Boost Pressure Stable",
    severity: "info",
    description:
      "Turbo boost holding steady at target. No wastegate oscillation detected.",
    relatedNodes: ["boost", "ecu"],
  },
  {
    id: "finding-oil-temp-nominal",
    title: "Oil Temp in Range",
    severity: "info",
    description:
      "Engine oil at optimal operating temperature. Viscosity profile nominal.",
    relatedNodes: ["oil-temp"],
  },
  {
    id: "finding-tire-heat-soak",
    title: "FR Tire Heat Soak",
    severity: "warning",
    description:
      "Front-right tire running 10-15°F hotter than front-left due to brake heat transfer. Monitor for accelerated wear.",
    relatedNodes: ["tire-fr", "tire-fl", "brake-fr"],
  },
];

export function useTelemetryStream(): {
  streams: Map<string, TelemetryStream>;
  findings: ZeusFinding[];
  cloudSync: CloudSync;
} {
  const [streams, setStreams] = useState<Map<string, TelemetryStream>>(
    new Map()
  );
  const [findings, setFindings] = useState<ZeusFinding[]>([]);
  const [cloudSync, setCloudSync] = useState<CloudSync>({
    status: "ONLINE",
    lastSync: Date.now(),
    pendingCount: 0,
  });

  const streamsRef = useRef(streams);
  streamsRef.current = streams;

  const tick = useCallback(() => {
    setStreams((prev) => {
      const next = new Map(prev);
      for (const node of NODES) {
        const existing = prev.get(node.id);
        const prevValue = existing?.current.value ?? null;
        const point = generatePoint(node.id, prevValue);
        const history = existing
          ? [...existing.history, point].slice(-HISTORY_LENGTH)
          : [point];
        next.set(node.id, { nodeId: node.id, current: point, history });
      }
      return next;
    });
  }, []);

  useEffect(() => {
    // Initialize
    tick();

    // Sensor update interval: ~150ms (6-7 Hz)
    const sensorInterval = setInterval(tick, 150);

    // Findings rotation: every 8 seconds
    const findingsInterval = setInterval(() => {
      const count = 2 + Math.floor(Math.random() * 2); // 2-3 findings
      const shuffled = [...FINDINGS_POOL].sort(() => Math.random() - 0.5);
      setFindings(
        shuffled.slice(0, count).map((f) => ({ ...f, timestamp: Date.now() }))
      );
    }, 8000);

    // Initial findings
    setFindings(
      FINDINGS_POOL.slice(0, 3).map((f) => ({ ...f, timestamp: Date.now() }))
    );

    // Cloud sync status cycling
    const cloudInterval = setInterval(() => {
      const roll = Math.random();
      let status: CloudSyncStatus;
      let pendingCount: number;
      if (roll < 0.8) {
        status = "ONLINE";
        pendingCount = 0;
      } else if (roll < 0.95) {
        status = "QUEUED";
        pendingCount = Math.floor(Math.random() * 12) + 1;
      } else {
        status = "OFFLINE";
        pendingCount = Math.floor(Math.random() * 30) + 5;
      }
      setCloudSync({ status, lastSync: Date.now(), pendingCount });
    }, 5000);

    return () => {
      clearInterval(sensorInterval);
      clearInterval(findingsInterval);
      clearInterval(cloudInterval);
    };
  }, [tick]);

  return { streams, findings, cloudSync };
}
