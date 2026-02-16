"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useTelemetryStream } from "./mockTelemetry";
import { TelemetryStream, ZeusFinding, CloudSync } from "./types";
import { getCircuitPosition, CircuitPoint } from "./lagunaSecaCircuit";

// --- Types ---

export interface CornerTelemetry {
  tireTempC: number;
  brakeTempC: number;
  tireStatus: "ok" | "warn" | "hot";
  brakeStatus: "ok" | "warn" | "hot";
  tireTrend: number[]; // last 30 values in C
  brakeTrend: number[]; // last 30 values in C
  tireWearPct: number; // 0-100, degrades over time
}

// GT7-style tire color thresholds (°C)
export const GT7_COLORS = {
  BLUE: "#0077DD",   // < 75°C (cold)
  GREEN: "#00CC66",  // 75-90°C (optimal)
  YELLOW: "#FFAA00", // 90-105°C (warm)
  RED: "#FF2222",    // > 105°C (overheating)
} as const;

export function gt7TireColor(tempC: number): string {
  if (tempC < 75) return GT7_COLORS.BLUE;
  if (tempC < 90) return GT7_COLORS.GREEN;
  if (tempC < 105) return GT7_COLORS.YELLOW;
  return GT7_COLORS.RED;
}

export interface GPSPosition {
  lat: number;
  lon: number;
  speedKph: number;
  heading: number;
  circuitProgress: number;
  position: CircuitPoint;
}

export interface SessionData {
  sessionTimeS: number;
  lapCount: number;
  lastLapS: number;
  bestLapS: number;
  lapTimes: number[];
}

export interface CameraInfo {
  name: string;
  connected: boolean;
  fps: number;
  resolution: string;
}

export interface WeatherData {
  tempC: number;
  windDir: string;
  windKph: number;
  humidity: number;
  condition: string;
  elevation: number;
}

export interface DriverDisplayState {
  corners: Record<string, CornerTelemetry>;
  gps: GPSPosition;
  oilPsi: number;
  oilTempC: number;
  oilTrend: number[];
  oilStatus: "ok" | "warn" | "hot";
  egt: number;
  boost: number;
  wideband: number;
  cameras: CameraInfo[];
  session: SessionData;
  weather: WeatherData;
  findings: ZeusFinding[];
  cloudSync: CloudSync;
  streams: Map<string, TelemetryStream>;
}

// --- Helpers ---

function fToC(f: number): number {
  return (f - 32) * (5 / 9);
}

function getStatusFromC(tempC: number, warnC: number, hotC: number): "ok" | "warn" | "hot" {
  if (tempC >= hotC) return "hot";
  if (tempC >= warnC) return "warn";
  return "ok";
}

// --- Hook ---

const LAP_DURATION_S = 92;
const CIRCUIT_SPEED = 1 / (LAP_DURATION_S * (1000 / 150)); // per tick at 150ms

export function useDriverTelemetry(): DriverDisplayState {
  const { streams, findings, cloudSync } = useTelemetryStream();

  const progressRef = useRef(0);
  const sessionStartRef = useRef(Date.now());
  const lapStartRef = useRef(Date.now());
  const wearRef = useRef<Record<string, number>>({
    FL: 100, FR: 100, RL: 100, RR: 100,
  });
  const [session, setSession] = useState<SessionData>({
    sessionTimeS: 0,
    lapCount: 0,
    lastLapS: 0,
    bestLapS: 0,
    lapTimes: [],
  });
  const [gps, setGps] = useState<GPSPosition>({
    lat: 36.5725,
    lon: -121.9486,
    speedKph: 0,
    heading: 0,
    circuitProgress: 0,
    position: { x: 0.85, y: 0.75 },
  });

  const sessionRef = useRef(session);
  sessionRef.current = session;

  // GPS + session tick
  useEffect(() => {
    const interval = setInterval(() => {
      progressRef.current = (progressRef.current + CIRCUIT_SPEED) % 1;
      const pos = getCircuitPosition(progressRef.current);

      // Speed varies by position (slower in corners, faster on straights)
      const speedBase = 120 + Math.sin(progressRef.current * Math.PI * 6) * 40;
      const speed = speedBase + (Math.random() - 0.5) * 10;

      setGps({
        lat: 36.5725 + (pos.y - 0.5) * 0.005,
        lon: -121.9486 + (pos.x - 0.5) * 0.005,
        speedKph: Math.max(40, speed),
        heading: Math.atan2(pos.y - 0.5, pos.x - 0.5) * (180 / Math.PI),
        circuitProgress: progressRef.current,
        position: pos,
      });

      // Tire wear degradation (~0.015% per tick, faster in corners)
      const cornerLoad = Math.abs(Math.sin(progressRef.current * Math.PI * 6));
      const wearRate = 0.012 + cornerLoad * 0.008;
      for (const k of ["FL", "FR", "RL", "RR"]) {
        wearRef.current[k] = Math.max(0, wearRef.current[k] - wearRate);
        // Auto pit-stop reset at 15%
        if (wearRef.current[k] <= 15) {
          wearRef.current[k] = 100;
        }
      }

      // Session timing
      const now = Date.now();
      const sessionTimeS = (now - sessionStartRef.current) / 1000;
      const lapElapsed = (now - lapStartRef.current) / 1000;

      // Check for lap completion (when progress wraps)
      if (progressRef.current < 0.02 && lapElapsed > 30) {
        const lapTime = lapElapsed + (Math.random() - 0.5) * 4;
        setSession((prev) => {
          const newTimes = [...prev.lapTimes, lapTime];
          return {
            sessionTimeS,
            lapCount: prev.lapCount + 1,
            lastLapS: lapTime,
            bestLapS: prev.bestLapS === 0 ? lapTime : Math.min(prev.bestLapS, lapTime),
            lapTimes: newTimes.slice(-20),
          };
        });
        lapStartRef.current = now;
      } else {
        setSession((prev) => ({ ...prev, sessionTimeS }));
      }
    }, 150);

    return () => clearInterval(interval);
  }, []);

  // Build driver state from streams
  const buildCorner = useCallback(
    (tireId: string, brakeId: string, cornerKey: string): CornerTelemetry => {
      const tire = streams.get(tireId);
      const brake = streams.get(brakeId);
      const tireTempC = tire ? fToC(tire.current.value) : 85;
      const brakeTempC = brake ? fToC(brake.current.value) : 250;
      return {
        tireTempC,
        brakeTempC,
        tireStatus: getStatusFromC(tireTempC, 88, 110), // ~190F, ~230F
        brakeStatus: getStatusFromC(brakeTempC, 232, 316), // ~450F, ~600F
        tireTrend: (tire?.history || []).map((p) => fToC(p.value)),
        brakeTrend: (brake?.history || []).map((p) => fToC(p.value)),
        tireWearPct: wearRef.current[cornerKey] ?? 100,
      };
    },
    [streams]
  );

  const oilPressure = streams.get("oil-pressure");
  const oilTemp = streams.get("oil-temp");
  const egtStream = streams.get("egt");
  const boostStream = streams.get("boost");
  const widebandStream = streams.get("wideband");

  const oilPsi = oilPressure?.current.value ?? 55;
  const oilTempF = oilTemp?.current.value ?? 215;
  const oilTempC = fToC(oilTempF);

  const weather: WeatherData = {
    tempC: 8 + Math.sin(Date.now() / 60000) * 0.5,
    windDir: "NW",
    windKph: 15 + Math.sin(Date.now() / 30000) * 3,
    humidity: 72 + Math.sin(Date.now() / 45000) * 5,
    condition: "Overcast",
    elevation: 1147,
  };

  const cameras: CameraInfo[] = [
    {
      name: "Teledyne IR",
      connected: true,
      fps: streams.get("teledyne-ir")?.current.value ?? 30,
      resolution: "640x480",
    },
    {
      name: "LiDAR",
      connected: true,
      fps: streams.get("lidar")?.current.value ?? 10,
      resolution: "1024x64",
    },
    {
      name: "RGB",
      connected: true,
      fps: streams.get("rgb-cam")?.current.value ?? 60,
      resolution: "1920x1080",
    },
    {
      name: "Weather",
      connected: true,
      fps: streams.get("weather-cam")?.current.value ?? 15,
      resolution: "1280x720",
    },
  ];

  return {
    corners: {
      FL: buildCorner("tire-fl", "brake-fl", "FL"),
      FR: buildCorner("tire-fr", "brake-fr", "FR"),
      RL: buildCorner("tire-rl", "brake-rl", "RL"),
      RR: buildCorner("tire-rr", "brake-rr", "RR"),
    },
    gps,
    oilPsi,
    oilTempC,
    oilTrend: (oilPressure?.history || []).map((p) => p.value),
    oilStatus: oilPsi < 15 ? "hot" : oilPsi < 25 ? "warn" : "ok",
    egt: egtStream?.current.value ?? 1350,
    boost: boostStream?.current.value ?? 18,
    wideband: widebandStream?.current.value ?? 14.2,
    cameras,
    session,
    weather,
    findings,
    cloudSync,
    streams,
  };
}
