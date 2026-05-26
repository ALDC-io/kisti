"use client";

import { ZeusFinding } from "@/lib/types";

const SEVERITY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  info: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  warning: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  critical: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
};

interface ZeusFindingsCardProps {
  findings: ZeusFinding[];
  onSelectNode: (id: string) => void;
}

export default function ZeusFindingsCard({
  findings,
  onSelectNode,
}: ZeusFindingsCardProps) {
  if (findings.length === 0) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className="text-kisti-accent"
        >
          <path
            d="M8 1L1 14h14L8 1z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M8 6v4M8 12h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <span className="text-sm font-semibold text-gray-900">
          Zeus Findings
        </span>
      </div>

      <div className="space-y-3">
        {findings.map((finding) => {
          const style = SEVERITY_STYLES[finding.severity];
          return (
            <div key={finding.id} className={`rounded-md p-3 ${style.bg}`}>
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${style.dot}`}
                  aria-hidden="true"
                />
                <span className={`text-sm font-medium ${style.text}`}>
                  {finding.title}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-600">
                {finding.description}
              </p>
              {finding.relatedNodes.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {finding.relatedNodes.map((nodeId) => (
                    <button
                      key={nodeId}
                      onClick={() => onSelectNode(nodeId)}
                      className="rounded-full bg-white/80 px-2 py-0.5 text-xs font-medium text-gray-700 transition-colors hover:bg-kisti-accent/10 hover:text-kisti-accent border border-gray-200"
                    >
                      {nodeId}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
