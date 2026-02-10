import Nav from "@/components/Nav";

const PIPELINE_STAGES = [
  {
    title: "1. Sensor Layer",
    description:
      "12 high-frequency sensors (brake temps, tire temps, EGT, boost, oil temp, wideband O₂) sample at 4-10Hz via analog/CAN interfaces.",
    detail: "Brake FL/FR/RL/RR thermocouples, tire FL/FR/RL/RR infrared sensors, K-type EGT probe, MAP sensor, NTC thermistor, Bosch LSU 4.9 wideband.",
  },
  {
    title: "2. ECU Aggregation",
    description:
      "Link G4X ECU receives all sensor data via CAN bus, applies calibration tables, and streams merged telemetry over USB.",
    detail: "500Kbps CAN, 100+ channels available, configurable output rates, real-time fuel/ignition corrections.",
  },
  {
    title: "3. Edge Inference",
    description:
      "NVIDIA Jetson Orin processes telemetry at the edge — anomaly detection, pattern matching, and predictive diagnostics in <50ms.",
    detail: "40 TOPS AI performance, TensorRT optimized models, local data buffering when offline.",
  },
  {
    title: "4. Cloud Sync",
    description:
      "Zeus Memory ingests telemetry via WiFi/cellular with store-and-forward. AI findings surface in real-time dashboards.",
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
            <div className="mt-4 flex flex-col items-center gap-2 sm:flex-row sm:justify-center sm:gap-4">
              {["Sensors", "CAN Bus", "Link G4X", "USB", "Jetson Orin", "WiFi", "Zeus Cloud"].map(
                (stage, i) => (
                  <div key={stage} className="flex items-center gap-2">
                    <span className="rounded-md bg-kisti-accent/15 px-3 py-1.5 text-sm font-medium text-kisti-accent">
                      {stage}
                    </span>
                    {i < 6 && (
                      <span className="hidden text-foreground/30 sm:inline">
                        →
                      </span>
                    )}
                  </div>
                )
              )}
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

          {/* Specs */}
          <div className="mt-12 grid gap-4 sm:grid-cols-3">
            {[
              { label: "Sensor Channels", value: "12" },
              { label: "Sample Rate", value: "4-10 Hz" },
              { label: "Edge Latency", value: "<50ms" },
              { label: "CAN Speed", value: "500 Kbps" },
              { label: "AI Performance", value: "40 TOPS" },
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
