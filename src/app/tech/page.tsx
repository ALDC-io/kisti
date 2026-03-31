import Nav from "@/components/Nav";

const PIPELINE_STAGES = [
  {
    title: "1. Sensor Layer",
    description:
      "13 high-frequency sensors (brake temps, tire temps, EGT, boost, oil temp/pressure, wideband O₂) sample at 4-10Hz via analog/CAN interfaces.",
    detail: "Brake FL/FR/RL/RR thermocouples, tire FL/FR/RL/RR infrared sensors, K-type EGT probe, Cobb 4 Bar MAP sensor, GM IAT sensor, 150 PSI oil pressure sensor, flex fuel sensor, Bosch LSU 4.9 wideband.",
  },
  {
    title: "2. Vision Layer",
    description:
      "4 front-mounted cameras feed directly to the Jetson AGX Thor via USB 3.0 and CSI — thermal, depth, visual, and weather sensing.",
    detail: "Teledyne FLIR thermal IR, 3D LiDAR point cloud, high-speed RGB camera, Yoctopuce Yocto-Spruce weather station.",
  },
  {
    title: "3. ECU Aggregation",
    description:
      "Link G5 Neo 4 ECU receives all sensor data via CAN bus, applies calibration tables, and streams merged telemetry over USB.",
    detail: "500Kbps CAN, 100+ channels available, configurable output rates, real-time fuel/ignition corrections.",
  },
  {
    title: "4. Edge Inference",
    description:
      "NVIDIA Jetson AGX Thor processes telemetry and vision data at the edge — anomaly detection, pattern matching, and predictive diagnostics in <50ms.",
    detail: "1,000+ TOPS AI performance (128GB LPDDR5X), TensorRT optimized models, 16 camera inputs, local data buffering when offline.",
  },
  {
    title: "5. Cloud Sync",
    description:
      "Zeus ingests telemetry via WiFi/cellular with store-and-forward. AI findings surface in real-time dashboards.",
    detail: "pgvector semantic search, 3.5M+ memories, automatic embedding via Voyage AI, Slack/email alerts.",
  },
];

export default function TechPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <section className="mx-auto max-w-4xl px-4 py-16">
          <h1 className="text-3xl font-bold sm:text-4xl">
            <span className="text-kisti-accent">Technology</span> Overview
          </h1>
          <p className="mt-4 text-foreground/60">
            KiSTI combines motorsport-grade sensors, a production ECU, and edge
            AI into a unified telemetry platform. Here&apos;s how data flows from
            sensor to insight.
          </p>

          {/* Architecture diagram placeholder */}
          <div className="mt-8 rounded-xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-lg font-semibold text-foreground/80">
              System Architecture
            </h2>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              {/* Sensors → CAN → Link → Jetson Orin → branches */}
              <span className="rounded-md bg-kisti-accent/15 px-3 py-1.5 text-sm font-medium text-kisti-accent">
                Sensors
              </span>
              <span className="text-foreground/30">→</span>
              <span className="rounded-md bg-kisti-accent/15 px-3 py-1.5 text-sm font-medium text-kisti-accent">
                CAN
              </span>
              <span className="text-foreground/30">→</span>
              <span className="flex items-center rounded-md bg-kisti-accent/15 px-2 py-1">
                <img src="/assets/link_logo.svg" alt="Link" className="h-5" draggable={false} />
              </span>
              <span className="text-foreground/30">→</span>
              <span className="flex items-center rounded-md bg-kisti-accent/15 px-2 py-1">
                <img src="/assets/jetson_orin_logo.svg" alt="Jetson AGX Thor" className="h-5" draggable={false} />
              </span>
              <span className="text-foreground/30">→</span>
              {/* Branch: Driver View / Zeus → Pit Engineer */}
              <div className="flex flex-col items-start gap-1">
                <span className="rounded-md bg-kisti-accent/15 px-3 py-1 text-sm font-medium text-kisti-accent">
                  Driver View
                </span>
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1.5 rounded-md bg-kisti-accent/15 px-2 py-1">
                    <img src="/assets/aldc_logo.svg" alt="ALDC" className="h-4" draggable={false} />
                    <span className="text-sm font-medium text-kisti-accent">Zeus</span>
                  </span>
                  <span className="text-foreground/30">→</span>
                  <span className="rounded-md bg-kisti-accent/15 px-3 py-1 text-sm font-medium text-kisti-accent">
                    Pit Engineer
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Pipeline stages */}
          <div className="mt-12 space-y-8">
            <h2 className="text-xl font-semibold text-foreground/80">
              Data Pipeline
            </h2>
            {PIPELINE_STAGES.map((stage) => (
              <div
                key={stage.title}
                className="rounded-lg border border-white/10 bg-white/5 p-5"
              >
                <h3 className="text-lg font-semibold text-kisti-accent">
                  {stage.title}
                </h3>
                <p className="mt-2 text-sm text-foreground/70">
                  {stage.description}
                </p>
                <p className="mt-2 text-xs text-foreground/40">
                  {stage.detail}
                </p>
              </div>
            ))}
          </div>

          {/* Voice AI Pipeline */}
          <div className="mt-12 space-y-4">
            <h2 className="text-xl font-semibold text-foreground/80">
              Voice AI Pipeline
            </h2>
            <p className="text-sm text-foreground/60">
              Fully offline conversational AI — no cloud dependency, no cellular required. The entire voice stack runs on-device on the Jetson AGX Thor.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  title: "Speech-to-Text",
                  desc: "whisper.cpp with CUDA acceleration",
                  detail: "~130ms for 3-second utterances. Custom wake word detection with barge-in echo cancellation.",
                },
                {
                  title: "Text-to-Speech",
                  desc: "Piper TTS — sub-200ms conversational responses",
                  detail: "Three voice modes: Informal (personality), Standard (clinical data), Safety-Critical (emergency only).",
                },
                {
                  title: "Edge Memory",
                  desc: "DuckDB + ONNX embeddings on-device",
                  detail: "Persistent knowledge across sessions. Voice-activated 'remember' commands. Cloud sync when WiFi available.",
                },
                {
                  title: "Anomaly Detection",
                  desc: "Real-time pattern matching on telemetry streams",
                  detail: "Threshold-based alerts sourced from build baselines. Predictive diagnostics with spoken warnings.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-lg border border-white/10 bg-white/5 p-5"
                >
                  <h3 className="text-sm font-semibold text-kisti-accent">
                    {item.title}
                  </h3>
                  <p className="mt-1 text-sm text-foreground/70">
                    {item.desc}
                  </p>
                  <p className="mt-1 text-xs text-foreground/40">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* The Vehicle */}
          <div className="mt-12 rounded-xl border border-kisti-accent/20 bg-kisti-accent/5 p-6">
            <h2 className="text-xl font-semibold text-foreground/80">
              The Vehicle
            </h2>
            <p className="mt-3 text-sm text-foreground/60">
              2014 Subaru WRX STI Hatch. IAG 750 Closed Deck short block (rated 750 BHP), BCP X400 turbo, ID1300 injectors, COBB front-mount intercooler. Full standalone flex fuel tune by Boost Barn Motorsports. Track-tested at Mission Raceway, BC.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                "E85 Corn Ethanol",
                "IAG 750 Block",
                "BCP X400 Turbo",
                "360-390 WHP",
                "Link G5 Neo 4 ECU",
                "Fortune Auto Coilovers",
                "Competition Clutch Stage 2",
              ].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-kisti-accent/20 bg-kisti-accent/10 px-3 py-1 text-xs font-medium text-kisti-accent"
                >
                  {tag}
                </span>
              ))}
            </div>
            <p className="mt-4 text-xs text-foreground/40">
              Runs exclusively on E85 — corn-derived ethanol. One of the few edge AI automotive platforms powered by renewable fuel.
            </p>
          </div>

          {/* Specs */}
          <div className="mt-12 grid gap-4 sm:grid-cols-3">
            {[
              { label: "Sensor Channels", value: "17" },
              { label: "Sample Rate", value: "4-10 Hz" },
              { label: "Edge Latency", value: "<50ms" },
              { label: "CAN Speed", value: "500 Kbps" },
              { label: "AI Performance", value: "1,000+ TOPS" },
              { label: "Cloud Memories", value: "3.5M+" },
            ].map((spec) => (
              <div
                key={spec.label}
                className="rounded-lg border border-white/10 bg-white/5 p-4 text-center"
              >
                <p className="text-2xl font-bold text-kisti-accent">
                  {spec.value}
                </p>
                <p className="mt-1 text-xs text-foreground/50">{spec.label}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
