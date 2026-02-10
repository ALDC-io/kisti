export type NodeType = "sensor" | "ecu" | "edge-compute";

export type ConnectionType = "can" | "usb" | "wifi";

export type SeverityLevel = "info" | "warning" | "critical";

export type CloudSyncStatus = "ONLINE" | "QUEUED" | "OFFLINE";

export type TelemetryStatus = "ok" | "warn" | "hot";

export interface NodeDef {
  id: string;
  label: string;
  type: NodeType;
  /** Percentage-based coordinates (0-100) for responsive SVG overlay */
  x: number;
  y: number;
  unit: string;
  min: number;
  max: number;
  warnThreshold: number;
  hotThreshold: number;
  description: string;
}

export interface EdgeDef {
  id: string;
  source: string;
  target: string;
  type: ConnectionType;
  label: string;
}

export interface TelemetryPoint {
  value: number;
  timestamp: number;
  status: TelemetryStatus;
}

export interface TelemetryStream {
  nodeId: string;
  current: TelemetryPoint;
  history: TelemetryPoint[];
}

export interface ZeusFinding {
  id: string;
  title: string;
  severity: SeverityLevel;
  description: string;
  relatedNodes: string[];
  timestamp: number;
}

export interface CloudSync {
  status: CloudSyncStatus;
  lastSync: number;
  pendingCount: number;
}
