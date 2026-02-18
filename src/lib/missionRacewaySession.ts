/**
 * Mission Raceway track day session data.
 * 6 laps: 1 warm-up, 3 hot, 2 cool-down.
 * Full Link G4X ECU telemetry per lap.
 */

export interface LapTelemetry {
  /** Lap number (1-based) */
  lap: number;
  /** Session phase */
  phase: "warm-up" | "hot" | "cool-down";
  /** Lap time in seconds */
  lapTimeS: number;
  /** Formatted lap time string */
  lapTimeStr: string;
  /** Sector times in seconds [S1, S2, S3] */
  sectors: [number, number, number];
  /** Min speed in km/h */
  minSpeedKph: number;
  /** Max speed in km/h */
  maxSpeedKph: number;
  /** Peak braking G force */
  peakBrakingG: number;
  /** Peak lateral G */
  peakLateralG: number;
  /** Link ECU channel data */
  ecu: LinkECUData;
}

export interface LinkECUData {
  /** Brake temps in °F [FL, FR, RL, RR] */
  brakeTemps: [number, number, number, number];
  /** Tire temps in °F [FL, FR, RL, RR] */
  tireTemps: [number, number, number, number];
  /** Peak exhaust gas temperature °F */
  egtPeak: number;
  /** Average EGT °F */
  egtAvg: number;
  /** Peak boost PSI */
  boostPeak: number;
  /** Average boost PSI */
  boostAvg: number;
  /** Oil temperature °F */
  oilTemp: number;
  /** Oil pressure PSI */
  oilPressure: number;
  /** Wideband AFR under boost */
  afrBoost: number;
  /** Wideband AFR at cruise/lift */
  afrCruise: number;
}

function formatLapTime(s: number): string {
  const min = Math.floor(s / 60);
  const sec = s % 60;
  return `${min}:${sec.toFixed(1).padStart(4, "0")}`;
}

/** Complete 6-lap Mission Raceway session */
export const SESSION_LAPS: LapTelemetry[] = [
  // Lap 1 — Warm-up: 60-70% pace, building temps
  {
    lap: 1,
    phase: "warm-up",
    lapTimeS: 105.2,
    lapTimeStr: formatLapTime(105.2),
    sectors: [36.8, 35.1, 33.3],
    minSpeedKph: 48,
    maxSpeedKph: 145,
    peakBrakingG: 0.7,
    peakLateralG: 0.8,
    ecu: {
      brakeTemps: [280, 305, 210, 205],
      tireTemps: [138, 145, 125, 122],
      egtPeak: 1180,
      egtAvg: 1050,
      boostPeak: 14,
      boostAvg: 10,
      oilTemp: 192,
      oilPressure: 58,
      afrBoost: 11.4,
      afrCruise: 14.7,
    },
  },
  // Lap 2 — Hot 1: full pace, aggressive
  {
    lap: 2,
    phase: "hot",
    lapTimeS: 82.4,
    lapTimeStr: formatLapTime(82.4),
    sectors: [28.2, 27.8, 26.4],
    minSpeedKph: 62,
    maxSpeedKph: 178,
    peakBrakingG: 1.1,
    peakLateralG: 1.2,
    ecu: {
      brakeTemps: [365, 405, 268, 262],
      tireTemps: [162, 176, 145, 142],
      egtPeak: 1520,
      egtAvg: 1380,
      boostPeak: 19,
      boostAvg: 16,
      oilTemp: 222,
      oilPressure: 54,
      afrBoost: 11.2,
      afrCruise: 14.7,
    },
  },
  // Lap 3 — Hot 2: BEST LAP, peak everything, tires optimal
  {
    lap: 3,
    phase: "hot",
    lapTimeS: 79.4,
    lapTimeStr: formatLapTime(79.4),
    sectors: [27.1, 26.5, 25.8],
    minSpeedKph: 65,
    maxSpeedKph: 182,
    peakBrakingG: 1.2,
    peakLateralG: 1.3,
    ecu: {
      brakeTemps: [388, 428, 275, 270],
      tireTemps: [168, 182, 150, 148],
      egtPeak: 1580,
      egtAvg: 1420,
      boostPeak: 20,
      boostAvg: 17,
      oilTemp: 235,
      oilPressure: 52,
      afrBoost: 11.2,
      afrCruise: 14.7,
    },
  },
  // Lap 4 — Hot 3: slight degradation, higher EGT, tires climbing
  {
    lap: 4,
    phase: "hot",
    lapTimeS: 81.3,
    lapTimeStr: formatLapTime(81.3),
    sectors: [27.8, 27.2, 26.3],
    minSpeedKph: 63,
    maxSpeedKph: 180,
    peakBrakingG: 1.1,
    peakLateralG: 1.25,
    ecu: {
      brakeTemps: [395, 435, 282, 278],
      tireTemps: [175, 190, 155, 152],
      egtPeak: 1565,
      egtAvg: 1410,
      boostPeak: 19,
      boostAvg: 16,
      oilTemp: 238,
      oilPressure: 51,
      afrBoost: 11.3,
      afrCruise: 14.7,
    },
  },
  // Lap 5 — Cool-down 1: 50-60% pace, temps dropping
  {
    lap: 5,
    phase: "cool-down",
    lapTimeS: 98.5,
    lapTimeStr: formatLapTime(98.5),
    sectors: [34.2, 33.0, 31.3],
    minSpeedKph: 45,
    maxSpeedKph: 138,
    peakBrakingG: 0.6,
    peakLateralG: 0.7,
    ecu: {
      brakeTemps: [310, 340, 235, 230],
      tireTemps: [155, 165, 140, 138],
      egtPeak: 1220,
      egtAvg: 1080,
      boostPeak: 10,
      boostAvg: 7,
      oilTemp: 225,
      oilPressure: 54,
      afrBoost: 11.5,
      afrCruise: 14.7,
    },
  },
  // Lap 6 — Cool-down 2: parade pace, everything cooling
  {
    lap: 6,
    phase: "cool-down",
    lapTimeS: 102.8,
    lapTimeStr: formatLapTime(102.8),
    sectors: [35.5, 34.8, 32.5],
    minSpeedKph: 42,
    maxSpeedKph: 130,
    peakBrakingG: 0.5,
    peakLateralG: 0.6,
    ecu: {
      brakeTemps: [260, 285, 210, 208],
      tireTemps: [142, 150, 130, 128],
      egtPeak: 1080,
      egtAvg: 960,
      boostPeak: 8,
      boostAvg: 5,
      oilTemp: 212,
      oilPressure: 56,
      afrBoost: 11.6,
      afrCruise: 14.7,
    },
  },
];

/** Best lap from the session */
export const BEST_LAP = SESSION_LAPS.reduce((best, lap) =>
  lap.lapTimeS < best.lapTimeS ? lap : best
);

/** Session summary stats */
export const SESSION_SUMMARY = {
  track: "Mission Raceway",
  location: "Mission, BC, Canada",
  totalLaps: SESSION_LAPS.length,
  bestLapTime: BEST_LAP.lapTimeStr,
  bestLapNumber: BEST_LAP.lap,
  totalSessionTime: SESSION_LAPS.reduce((sum, l) => sum + l.lapTimeS, 0),
  peakEGT: Math.max(...SESSION_LAPS.map((l) => l.ecu.egtPeak)),
  peakBoost: Math.max(...SESSION_LAPS.map((l) => l.ecu.boostPeak)),
  peakOilTemp: Math.max(...SESSION_LAPS.map((l) => l.ecu.oilTemp)),
  maxFRBrakeDelta: Math.max(
    ...SESSION_LAPS.map((l) => l.ecu.brakeTemps[1] - l.ecu.brakeTemps[0])
  ),
};
