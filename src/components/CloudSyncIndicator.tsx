"use client";

import { CloudSync } from "@/lib/types";

const STATUS_CONFIG: Record<
  string,
  { color: string; label: string; description: string }
> = {
  ONLINE: {
    color: "#10b981",
    label: "Eclipse Sync Active",
    description: "Telemetry streaming to ALDC Eclipse in real-time",
  },
  QUEUED: {
    color: "#f59e0b",
    label: "Queued",
    description: "Data buffered on Jetson, uploading to Eclipse when bandwidth allows",
  },
  OFFLINE: {
    color: "#ef4444",
    label: "Offline",
    description: "No cloud connection — data stored locally on Jetson",
  },
};

interface CloudSyncIndicatorProps {
  cloudSync: CloudSync;
}

export default function CloudSyncIndicator({
  cloudSync,
}: CloudSyncIndicatorProps) {
  const config = STATUS_CONFIG[cloudSync.status];
  const elapsed = Math.round((Date.now() - cloudSync.lastSync) / 1000);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: config.color }}
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-gray-900">
            {config.label}
          </span>
        </div>
        {cloudSync.pendingCount > 0 && (
          <span className="text-xs text-gray-500">
            {cloudSync.pendingCount} pending
          </span>
        )}
      </div>
      <p className="mt-1.5 text-xs text-gray-500">{config.description}</p>
      <p className="mt-1 text-xs text-gray-400">
        Last sync: {elapsed}s ago
      </p>
    </div>
  );
}
