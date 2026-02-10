"use client";

import { NodeDef, TelemetryStream, ZeusFinding, CloudSync } from "@/lib/types";
import { getNode } from "@/lib/kistiGraph";
import TelemetryCard from "./TelemetryCard";
import ZeusFindingsCard from "./ZeusFindingsCard";
import CloudSyncIndicator from "./CloudSyncIndicator";

const TYPE_LABELS: Record<string, string> = {
  sensor: "Sensor Node",
  ecu: "Engine Control Unit",
  "edge-compute": "Edge Compute",
};

interface NodeSidebarProps {
  selectedNodeId: string | null;
  streams: Map<string, TelemetryStream>;
  findings: ZeusFinding[];
  cloudSync: CloudSync;
  onSelectNode: (id: string | null) => void;
  onClose: () => void;
}

export default function NodeSidebar({
  selectedNodeId,
  streams,
  findings,
  cloudSync,
  onSelectNode,
  onClose,
}: NodeSidebarProps) {
  if (!selectedNodeId) return null;

  const node = getNode(selectedNodeId);
  if (!node) return null;

  const stream = streams.get(selectedNodeId);

  // Filter findings relevant to this node
  const relevantFindings = findings.filter((f) =>
    f.relatedNodes.includes(selectedNodeId)
  );

  // For ECU/Jetson, show all connected sensor streams
  const showMultipleStreams =
    node.type === "ecu" || node.type === "edge-compute";

  return (
    <aside
      className="fixed right-0 top-14 bottom-0 z-40 w-full max-w-sm overflow-y-auto border-l border-gray-200 bg-sidebar animate-slide-in"
      role="complementary"
      aria-label={`Telemetry details for ${node.label}`}
    >
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-gray-200 bg-gradient-to-r from-kisti-accent/10 to-transparent p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-sidebar-text">
              {node.label}
            </h2>
            <p className="text-xs text-gray-500">{TYPE_LABELS[node.type]}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4.293 4.293a1 1 0 011.414 0L8 6.586l2.293-2.293a1 1 0 111.414 1.414L9.414 8l2.293 2.293a1 1 0 01-1.414 1.414L8 9.414l-2.293 2.293a1 1 0 01-1.414-1.414L6.586 8 4.293 5.707a1 1 0 010-1.414z" />
            </svg>
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">{node.description}</p>
      </div>

      {/* Content */}
      <div className="space-y-4 p-4">
        {/* Single sensor telemetry */}
        {!showMultipleStreams && stream && (
          <TelemetryCard node={node} stream={stream} />
        )}

        {/* ECU/Jetson: show all connected streams */}
        {showMultipleStreams && (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Connected Channels
            </h3>
            {Array.from(streams.entries())
              .filter(([id]) => {
                if (node.type === "edge-compute") return true; // Jetson sees all
                return id !== selectedNodeId;
              })
              .map(([id, s]) => {
                const n = getNode(id);
                if (!n || n.type !== "sensor") return null;
                return <TelemetryCard key={id} node={n} stream={s} />;
              })}
          </div>
        )}

        {/* Zeus Findings */}
        {relevantFindings.length > 0 && (
          <ZeusFindingsCard
            findings={relevantFindings}
            onSelectNode={(id) => onSelectNode(id)}
          />
        )}

        {/* All findings for ECU/Jetson */}
        {showMultipleStreams && findings.length > 0 && (
          <ZeusFindingsCard
            findings={findings}
            onSelectNode={(id) => onSelectNode(id)}
          />
        )}

        {/* Cloud sync for Jetson */}
        {node.type === "edge-compute" && (
          <CloudSyncIndicator cloudSync={cloudSync} />
        )}
      </div>
    </aside>
  );
}
