"use client";

import { useState } from "react";
import Nav from "@/components/Nav";
import HeroSection from "@/components/HeroSection";
import KistiAthenaOverlay from "@/components/KistiAthenaOverlay";
import NodeSidebar from "@/components/NodeSidebar";
import { useTelemetryStream } from "@/lib/mockTelemetry";

export default function Home() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const { streams, findings, cloudSync } = useTelemetryStream();

  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <HeroSection />

        <section className="relative mx-auto max-w-7xl px-4 pb-16">
          <div
            className={`transition-all duration-300 ${
              selectedNodeId ? "mr-0 lg:mr-96" : ""
            }`}
          >
            <KistiAthenaOverlay
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              streams={streams}
            />
          </div>

          {/* Legend */}
          <div className="mt-6 flex flex-wrap justify-center gap-4 text-xs text-foreground/50">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-sensor" />
              Sensor
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-ecu" />
              ECU
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-edge-compute" />
              Edge Compute
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 border-t-2 border-can" />
              CAN Bus
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 border-t-2 border-usb" />
              USB 3.0
            </div>
          </div>
        </section>

        <NodeSidebar
          selectedNodeId={selectedNodeId}
          streams={streams}
          findings={findings}
          cloudSync={cloudSync}
          onSelectNode={setSelectedNodeId}
          onClose={() => setSelectedNodeId(null)}
        />
      </main>
    </>
  );
}
