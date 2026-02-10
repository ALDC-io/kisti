"use client";

import { NODES, EDGES, getConnectedEdges } from "@/lib/kistiGraph";
import { NodeDef, EdgeDef, TelemetryStream } from "@/lib/types";

const NODE_COLORS: Record<string, string> = {
  sensor: "#10b981",
  ecu: "#f59e0b",
  "edge-compute": "#8b5cf6",
};

const EDGE_COLORS: Record<string, string> = {
  can: "#3b82f6",
  usb: "#ec4899",
  wifi: "#06b6d4",
};

const STATUS_COLORS: Record<string, string> = {
  ok: "#10b981",
  warn: "#f59e0b",
  hot: "#ef4444",
};

interface OverlayProps {
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  streams: Map<string, TelemetryStream>;
}

export default function KistiAthenaOverlay({
  selectedNodeId,
  onSelectNode,
  streams,
}: OverlayProps) {
  const connectedEdgeIds = selectedNodeId
    ? new Set(getConnectedEdges(selectedNodeId).map((e) => e.id))
    : null;

  function getNodeOpacity(node: NodeDef): number {
    if (!selectedNodeId) return 1;
    if (node.id === selectedNodeId) return 1;
    const edges = getConnectedEdges(selectedNodeId);
    const connectedNodeIds = new Set(
      edges.flatMap((e) => [e.source, e.target])
    );
    if (connectedNodeIds.has(node.id)) return 0.8;
    return 0.25;
  }

  function getEdgeOpacity(edge: EdgeDef): number {
    if (!connectedEdgeIds) return 0.5;
    return connectedEdgeIds.has(edge.id) ? 1 : 0.1;
  }

  function getNodeStatusColor(nodeId: string): string {
    const stream = streams.get(nodeId);
    if (!stream) return NODE_COLORS["sensor"];
    return STATUS_COLORS[stream.current.status] || NODE_COLORS["sensor"];
  }

  return (
    <div id="schematic" className="relative mx-auto w-full max-w-4xl">
      {/* STI schematic background */}
      <img
        src="/assets/sti_schematic.svg"
        alt="2014 Subaru STI schematic — top-down view"
        className="w-full opacity-40"
        draggable={false}
      />

      {/* SVG overlay */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 h-full w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Interactive sensor node overlay on STI schematic"
      >
        {/* Edges */}
        {EDGES.map((edge) => {
          const source = NODES.find((n) => n.id === edge.source);
          const target = NODES.find((n) => n.id === edge.target);
          if (!source || !target) return null;

          const isActive = connectedEdgeIds?.has(edge.id);
          return (
            <line
              key={edge.id}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke={EDGE_COLORS[edge.type]}
              strokeWidth={isActive ? 0.4 : 0.2}
              opacity={getEdgeOpacity(edge)}
              className={isActive ? "animate-edge-pulse" : ""}
            />
          );
        })}

        {/* Nodes */}
        {NODES.map((node) => {
          const isSelected = node.id === selectedNodeId;
          const radius = node.type === "ecu" ? 3.5 : node.type === "edge-compute" ? 3.2 : 2.5;
          const color = isSelected
            ? getNodeStatusColor(node.id)
            : NODE_COLORS[node.type];
          const stream = streams.get(node.id);

          return (
            <g
              key={node.id}
              onClick={() =>
                onSelectNode(isSelected ? null : node.id)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectNode(isSelected ? null : node.id);
                }
              }}
              role="button"
              tabIndex={0}
              aria-label={`${node.label}: ${stream ? `${stream.current.value} ${node.unit}` : "loading"}`}
              className="cursor-pointer"
              style={{ opacity: getNodeOpacity(node) }}
            >
              {/* Glow ring */}
              <circle
                cx={node.x}
                cy={node.y}
                r={radius + 1}
                fill="none"
                stroke={color}
                strokeWidth={0.3}
                opacity={isSelected ? 0.6 : 0.2}
                className={isSelected ? "animate-node-glow" : ""}
                style={{ color }}
              />

              {node.type === "ecu" || node.type === "edge-compute" ? (
                <>
                  {/* Logo background */}
                  <rect
                    x={node.x - 5}
                    y={node.y - 2.5}
                    width={10}
                    height={5}
                    rx={1}
                    fill={`${color}15`}
                    stroke={color}
                    strokeWidth={isSelected ? 0.4 : 0.25}
                  />
                  {/* Embedded logo */}
                  <image
                    href={node.type === "ecu" ? "/assets/link_logo.svg" : "/assets/jetson_orin_logo.svg"}
                    x={node.x - 4.5}
                    y={node.y - 2}
                    width={9}
                    height={4}
                    style={{ pointerEvents: "none" }}
                  />
                </>
              ) : (
                /* Sensor node circle */
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={radius}
                  fill={`${color}20`}
                  stroke={color}
                  strokeWidth={isSelected ? 0.5 : 0.3}
                />
              )}

              {/* Label */}
              <text
                x={node.x}
                y={node.y - (node.type === "ecu" || node.type === "edge-compute" ? 4 : radius + 1.5)}
                textAnchor="middle"
                fontSize="2.2"
                fill={color}
                fontWeight={isSelected ? "bold" : "normal"}
                style={{ pointerEvents: "none" }}
              >
                {node.label}
              </text>

              {/* Live value */}
              {stream && (
                <text
                  x={node.x}
                  y={node.y + (node.type === "ecu" || node.type === "edge-compute" ? 4.5 : 0.8)}
                  textAnchor="middle"
                  fontSize="2"
                  fill={STATUS_COLORS[stream.current.status]}
                  fontFamily="monospace"
                  style={{ pointerEvents: "none" }}
                >
                  {node.unit
                    ? `${stream.current.value}${node.unit}`
                    : `${stream.current.value}%`}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Click-away to deselect */}
      {selectedNodeId && (
        <button
          className="absolute inset-0 -z-10"
          onClick={() => onSelectNode(null)}
          aria-label="Deselect node"
        />
      )}
    </div>
  );
}
