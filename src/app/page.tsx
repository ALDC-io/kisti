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

        {/* Car Schematic with Link Hardware */}
        <section className="relative mx-auto max-w-7xl px-4 pb-8">
          <div className="flex flex-col gap-6 lg:flex-row">
            {/* Link Hardware — left panel */}
            <div className="shrink-0 lg:w-56">
              <div className="flex items-center gap-2 mb-4">
                <img
                  src="/assets/link_logo.svg"
                  alt="Link Engine Management"
                  className="h-4"
                  draggable={false}
                />
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
                  Sponsored Hardware
                </span>
              </div>
              <div className="flex gap-3 overflow-x-auto pb-2 lg:flex-col lg:gap-4 lg:overflow-visible lg:pb-0">
                {[
                  {
                    src: "/assets/link_g5_neo4.jpg",
                    name: "G5 Neo 4",
                    role: "ECU",
                    spec: "6-cyl, WiFi, 1GB log",
                    url: "https://dealers.linkecu.com/G5-Voodoo-Neo-4",
                  },
                  {
                    src: "/assets/link_strada_dash.jpg",
                    name: "Strada 7\" Street",
                    role: "Dash Display",
                    spec: "800x480, 10 RGB shift LEDs",
                    url: "https://dealers.linkecu.com/LINK-MXG-Strada-7-Dash-Street-Edition",
                  },
                  {
                    src: "/assets/link_can_keypad.jpg",
                    name: "CAN Keypad 8",
                    role: "Driver Controls",
                    spec: "IP67, 3M operations rated",
                    url: "https://dealers.linkecu.com/CANKeypad8",
                  },
                ].map((product) => (
                  <a
                    key={product.name}
                    href={product.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex min-w-[10rem] flex-col overflow-hidden rounded-xl border border-white/10 bg-white/5 transition-colors hover:border-ecu/30 hover:bg-white/[0.08] lg:min-w-0"
                  >
                    <div className="relative aspect-square overflow-hidden bg-white">
                      <img
                        src={product.src}
                        alt={product.name}
                        className="h-full w-full object-contain p-2 transition-transform group-hover:scale-105"
                        draggable={false}
                      />
                    </div>
                    <div className="p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-ecu/80">
                        {product.role}
                      </div>
                      <p className="mt-0.5 text-sm font-semibold text-foreground">
                        {product.name}
                      </p>
                      <p className="mt-0.5 text-[11px] text-foreground/40">
                        {product.spec}
                      </p>
                    </div>
                  </a>
                ))}
              </div>
            </div>

            {/* Car Schematic */}
            <div
              className={`min-w-0 flex-1 transition-all duration-300 ${
                selectedNodeId ? "mr-0 lg:mr-96" : ""
              }`}
            >
              <KistiAthenaOverlay
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                streams={state.streams}
              />
            </div>
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
