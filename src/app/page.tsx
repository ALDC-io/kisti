"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Nav from "@/components/Nav";
import HeroSection from "@/components/HeroSection";
import DriverDisplay from "@/components/driver/DriverDisplay";
import PitEngineerView from "@/components/pit/PitEngineerView";
import KistiAthenaOverlay from "@/components/KistiAthenaOverlay";
import NodeSidebar from "@/components/NodeSidebar";
import { useDriverTelemetry } from "@/lib/driverTelemetry";

/* ------------------------------------------------------------------ */
/*  Link hardware — ordered top-to-bottom matching car position (y)   */
/*  Real dimensions drive both card aspect ratios and relative widths  */
/* ------------------------------------------------------------------ */
const LINK_PRODUCTS = [
  {
    id: "strada",
    src: "/assets/link_strada_dash.jpg",
    name: 'Strada 7" Street',
    role: "Dash Display",
    spec: "800x480, 10 RGB shift LEDs",
    url: "https://dealers.linkecu.com/LINK-MXG-Strada-7-Dash-Street-Edition",
    widthMm: 237,
    heightMm: 128,
    targetX: 50, // dashboard center
    targetY: 46,
    sizeClass: "w-40 lg:w-full", // widest product = full panel
  },
  {
    id: "keypad",
    src: "/assets/link_can_keypad.jpg",
    name: "CAN Keypad 8",
    role: "Driver Controls",
    spec: "IP67, 3M operations rated",
    url: "https://dealers.linkecu.com/CANKeypad8",
    widthMm: 123.5,
    heightMm: 70,
    targetX: 44, // center console
    targetY: 52,
    sizeClass: "w-40 lg:w-[52%]", // 123.5/237 ≈ 52%
  },
  {
    id: "g5-neo",
    src: "/assets/link_g5_neo4.jpg",
    name: "G5 Neo 4",
    role: "ECU",
    spec: "6-cyl, WiFi, 1GB log",
    url: "https://dealers.linkecu.com/G5-Voodoo-Neo-4",
    widthMm: 107,
    heightMm: 158,
    targetX: 50, // existing ECU node position
    targetY: 58,
    sizeClass: "w-40 lg:w-[45%]", // 107/237 ≈ 45%
  },
];

/* ------------------------------------------------------------------ */

interface LeaderLine {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export default function Home() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const state = useDriverTelemetry();

  /* Leader-line state */
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map());
  const [lines, setLines] = useState<LeaderLine[]>([]);
  const [svgSize, setSvgSize] = useState({ w: 0, h: 0 });

  const updateLines = useCallback(() => {
    const section = sectionRef.current;
    if (!section) return;

    const schematic = section.querySelector("#schematic");
    const svgEl = schematic?.querySelector("svg");
    if (!schematic || !svgEl) return;

    const sectionRect = section.getBoundingClientRect();
    const svgRect = svgEl.getBoundingClientRect();
    setSvgSize({ w: sectionRect.width, h: sectionRect.height });

    /* Map schematic viewBox (0 0 100 100, xMidYMid meet) to px */
    const aspect = svgRect.width / svgRect.height;
    let rW: number, rH: number, oX: number, oY: number;
    if (aspect > 1) {
      rH = svgRect.height;
      rW = rH;
      oX = (svgRect.width - rW) / 2;
      oY = 0;
    } else {
      rW = svgRect.width;
      rH = rW;
      oX = 0;
      oY = (svgRect.height - rH) / 2;
    }

    const next: LeaderLine[] = [];
    for (const p of LINK_PRODUCTS) {
      const card = cardRefs.current.get(p.id);
      if (!card) continue;
      const cr = card.getBoundingClientRect();

      next.push({
        id: p.id,
        x1: cr.right - sectionRect.left,
        y1: cr.top + cr.height / 2 - sectionRect.top,
        x2:
          svgRect.left + oX + (p.targetX / 100) * rW - sectionRect.left,
        y2:
          svgRect.top + oY + (p.targetY / 100) * rH - sectionRect.top,
      });
    }
    setLines(next);
  }, []);

  /* Recalculate on mount, resize, and when sidebar changes layout */
  useEffect(() => {
    const t = setTimeout(updateLines, 120);
    const obs = new ResizeObserver(updateLines);
    if (sectionRef.current) obs.observe(sectionRef.current);
    window.addEventListener("resize", updateLines);
    return () => {
      clearTimeout(t);
      obs.disconnect();
      window.removeEventListener("resize", updateLines);
    };
  }, [updateLines]);

  useEffect(() => {
    const t = setTimeout(updateLines, 350); // after CSS transition
    return () => clearTimeout(t);
  }, [selectedNodeId, updateLines]);

  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <HeroSection />

        {/* Car Schematic with Link Hardware + Leader Lines */}
        <section
          ref={sectionRef}
          className="relative mx-auto max-w-7xl px-4 pb-8"
        >
          <div className="flex flex-col gap-6 lg:flex-row">
            {/* Link Hardware — left panel, proportionally sized */}
            <div className="shrink-0 lg:w-56">
              <div className="mb-4 flex items-center gap-2">
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

              <div className="flex gap-3 overflow-x-auto pb-2 lg:flex-col lg:items-center lg:gap-4 lg:overflow-visible lg:pb-0">
                {LINK_PRODUCTS.map((product) => (
                  <a
                    key={product.id}
                    ref={(el) => {
                      if (el) cardRefs.current.set(product.id, el);
                      else cardRefs.current.delete(product.id);
                    }}
                    href={product.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`group flex flex-col overflow-hidden rounded-xl border border-white/10 bg-white/5 transition-colors hover:border-ecu/30 hover:bg-white/[0.08] lg:min-w-0 ${product.sizeClass}`}
                  >
                    <div
                      className="overflow-hidden bg-white"
                      style={{
                        aspectRatio: `${product.widthMm} / ${product.heightMm}`,
                      }}
                    >
                      <img
                        src={product.src}
                        alt={product.name}
                        className="h-full w-full object-contain p-2 transition-transform group-hover:scale-105"
                        draggable={false}
                      />
                    </div>
                    <div className="p-2.5">
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

          {/* Leader lines overlay — desktop only */}
          {svgSize.w > 0 && (
            <svg
              className="pointer-events-none absolute inset-0 hidden lg:block"
              viewBox={`0 0 ${svgSize.w} ${svgSize.h}`}
              style={{ zIndex: 5 }}
            >
              <defs>
                <marker
                  id="leader-dot"
                  viewBox="0 0 10 10"
                  refX="5"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                >
                  <circle cx="5" cy="5" r="4" fill="#f59e0b" opacity="0.8" />
                </marker>
              </defs>
              {lines.map((l) => {
                const dx = l.x2 - l.x1;
                // Control points: leave card horizontally, arrive at target horizontally
                const cx1 = l.x1 + dx * 0.45;
                const cx2 = l.x2 - dx * 0.25;
                return (
                  <g key={l.id}>
                    {/* Shadow for contrast on dark bg */}
                    <path
                      d={`M${l.x1},${l.y1} C${cx1},${l.y1} ${cx2},${l.y2} ${l.x2},${l.y2}`}
                      stroke="black"
                      strokeWidth={2.5}
                      fill="none"
                      opacity={0.15}
                    />
                    {/* Dashed leader */}
                    <path
                      d={`M${l.x1},${l.y1} C${cx1},${l.y1} ${cx2},${l.y2} ${l.x2},${l.y2}`}
                      stroke="#f59e0b"
                      strokeWidth={1.5}
                      strokeDasharray="8 5"
                      fill="none"
                      opacity={0.5}
                      markerEnd="url(#leader-dot)"
                      className="animate-leader-dash"
                    />
                    {/* Source dot */}
                    <circle
                      cx={l.x1}
                      cy={l.y1}
                      r={3}
                      fill="#f59e0b"
                      opacity={0.6}
                    />
                    {/* Target pulse ring */}
                    <circle
                      cx={l.x2}
                      cy={l.y2}
                      r={6}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth={1}
                      opacity={0.25}
                      className="animate-node-glow"
                      style={{ color: "#f59e0b" }}
                    />
                  </g>
                );
              })}
            </svg>
          )}

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
              Driver gauge cluster (left) and pit engineer dashboard (right) —
              same data, different perspectives
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
