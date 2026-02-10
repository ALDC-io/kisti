import { NodeDef, EdgeDef } from "./types";

/**
 * 10 nodes positioned on a 2014 Subaru STI schematic.
 * Coordinates are percentages (0-100) of the viewport.
 * Layout: car viewed from above, front at top.
 */
export const NODES: NodeDef[] = [
  // Brake sensors — four corners of the car
  {
    id: "brake-fl",
    label: "Brake FL",
    type: "sensor",
    x: 28,
    y: 22,
    unit: "°F",
    min: 150,
    max: 800,
    warnThreshold: 450,
    hotThreshold: 600,
    description: "Front-left brake rotor temperature sensor",
  },
  {
    id: "brake-fr",
    label: "Brake FR",
    type: "sensor",
    x: 72,
    y: 22,
    unit: "°F",
    min: 150,
    max: 800,
    warnThreshold: 450,
    hotThreshold: 600,
    description: "Front-right brake rotor temperature — running hotter than FL",
  },
  {
    id: "brake-rl",
    label: "Brake RL",
    type: "sensor",
    x: 28,
    y: 78,
    unit: "°F",
    min: 100,
    max: 600,
    warnThreshold: 350,
    hotThreshold: 500,
    description: "Rear-left brake rotor temperature sensor",
  },
  {
    id: "brake-rr",
    label: "Brake RR",
    type: "sensor",
    x: 72,
    y: 78,
    unit: "°F",
    min: 100,
    max: 600,
    warnThreshold: 350,
    hotThreshold: 500,
    description: "Rear-right brake rotor temperature sensor",
  },
  // Engine sensors — clustered around center-front
  {
    id: "egt",
    label: "EGT",
    type: "sensor",
    x: 50,
    y: 28,
    unit: "°F",
    min: 800,
    max: 1800,
    warnThreshold: 1500,
    hotThreshold: 1650,
    description: "Exhaust gas temperature probe — turbo health indicator",
  },
  {
    id: "boost",
    label: "Boost",
    type: "sensor",
    x: 40,
    y: 38,
    unit: "PSI",
    min: -14,
    max: 28,
    warnThreshold: 22,
    hotThreshold: 26,
    description: "Manifold boost pressure — turbo output",
  },
  {
    id: "oil-temp",
    label: "Oil Temp",
    type: "sensor",
    x: 60,
    y: 38,
    unit: "°F",
    min: 160,
    max: 300,
    warnThreshold: 250,
    hotThreshold: 280,
    description: "Engine oil temperature — lubrication health",
  },
  {
    id: "wideband",
    label: "Wideband O₂",
    type: "sensor",
    x: 50,
    y: 48,
    unit: "AFR",
    min: 10,
    max: 18,
    warnThreshold: 14.7,
    hotThreshold: 12,
    description: "Wideband oxygen sensor — air/fuel ratio monitoring",
  },
  // Link ECU G4X — center of car
  {
    id: "ecu",
    label: "Link G4X",
    type: "ecu",
    x: 50,
    y: 58,
    unit: "",
    min: 0,
    max: 100,
    warnThreshold: 80,
    hotThreshold: 95,
    description: "Link ECU G4X — central engine management, CAN bus hub",
  },
  // Jetson Orin — trunk area
  {
    id: "jetson",
    label: "Jetson Orin",
    type: "edge-compute",
    x: 50,
    y: 88,
    unit: "",
    min: 0,
    max: 100,
    warnThreshold: 75,
    hotThreshold: 90,
    description:
      "NVIDIA Jetson Orin — edge inference, telemetry aggregation, cloud sync",
  },
];

/**
 * 9 edges: 8 sensors → ECU (CAN bus), ECU → Jetson (USB)
 */
export const EDGES: EdgeDef[] = [
  {
    id: "brake-fl-ecu",
    source: "brake-fl",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "brake-fr-ecu",
    source: "brake-fr",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "brake-rl-ecu",
    source: "brake-rl",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "brake-rr-ecu",
    source: "brake-rr",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  { id: "egt-ecu", source: "egt", target: "ecu", type: "can", label: "CAN" },
  {
    id: "boost-ecu",
    source: "boost",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "oil-ecu",
    source: "oil-temp",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "wideband-ecu",
    source: "wideband",
    target: "ecu",
    type: "can",
    label: "CAN",
  },
  {
    id: "ecu-jetson",
    source: "ecu",
    target: "jetson",
    type: "usb",
    label: "USB 3.0",
  },
];

export function getNode(id: string): NodeDef | undefined {
  return NODES.find((n) => n.id === id);
}

export function getConnectedEdges(nodeId: string): EdgeDef[] {
  return EDGES.filter((e) => e.source === nodeId || e.target === nodeId);
}

export function getConnectedNodes(nodeId: string): string[] {
  const edges = getConnectedEdges(nodeId);
  const ids = new Set<string>();
  for (const e of edges) {
    if (e.source !== nodeId) ids.add(e.source);
    if (e.target !== nodeId) ids.add(e.target);
  }
  return Array.from(ids);
}
