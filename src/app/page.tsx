"use client";

import { useState } from "react";
import Nav from "@/components/Nav";
import HeroSection from "@/components/HeroSection";
import DriverDisplay from "@/components/driver/DriverDisplay";
import PitEngineerView from "@/components/pit/PitEngineerView";
import KistiAthenaOverlay from "@/components/KistiAthenaOverlay";
import NodeSidebar from "@/components/NodeSidebar";
import { useDriverTelemetry } from "@/lib/driverTelemetry";

export default function Home() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const state = useDriverTelemetry();

  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <HeroSection />

        {/* Car Schematic */}
        <section className="relative mx-auto max-w-7xl px-4 pb-8">
          <div
            className={`transition-all duration-300 ${
              selectedNodeId ? "mr-0 lg:mr-96" : ""
            }`}
          >
            <KistiAthenaOverlay
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              streams={state.streams}
            />
          </div>

          {/* Legend */}
          <div className="mt-6 flex flex-wrap justify-center gap-4 text-xs text-foreground/50">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-sensor" />
              Sensor
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-camera" />
              Camera
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
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 border-t-2 border-csi" />
              CSI
            </div>
          </div>
        </section>

        {/* Driver View + Pit Engineer View — side by side */}
        <section className="relative mx-auto max-w-7xl px-4 pb-16">
          <div className="mb-6 text-center">
            <h2 className="text-lg font-bold tracking-tight text-foreground sm:text-xl">
              Live Telemetry Views
            </h2>
            <p className="mt-1 text-sm text-foreground/50">
              Driver gauge cluster (left) and pit engineer dashboard (right) — same data, different perspectives
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Driver View */}
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground/40">
                Driver View
              </div>
              <DriverDisplay state={state} />
            </div>

            {/* Pit Engineer View */}
            <div className="flex flex-col">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-foreground/40">
                Pit Engineer — Cloud Monitor
              </div>
              <div className="flex-1" style={{ minHeight: 320 }}>
                <PitEngineerView state={state} />
              </div>
            </div>
          </div>
        </section>

        <NodeSidebar
          selectedNodeId={selectedNodeId}
          streams={state.streams}
          findings={state.findings}
          cloudSync={state.cloudSync}
          onSelectNode={setSelectedNodeId}
          onClose={() => setSelectedNodeId(null)}
        />
      </main>
    </>
  );
}
