import Nav from "@/components/Nav";

const PARTNERS = [
  {
    name: "Boost Barn",
    role: "Build Partner",
    description:
      "Custom STI build, turbo installation, brake system, and sensor integration. The hands that built KiSTI.",
    color: "#ef4444",
    logo: "/assets/boost_barn_logo.png",
  },
  {
    name: "Link Engine Management",
    role: "ECU Platform",
    description:
      "Link G4X provides the CAN bus backbone — 100+ configurable channels with real-time calibration and logging.",
    color: "#f59e0b",
    logo: "/assets/link_logo.svg",
  },
  {
    name: "NVIDIA",
    role: "Edge Compute",
    description:
      "Jetson Orin delivers 40 TOPS of AI performance at the edge for real-time anomaly detection and inference.",
    color: "#76b900",
    logo: "/assets/jetson_orin_logo.svg",
  },
  {
    name: "ALDC",
    role: "Platform & Intelligence",
    description:
      "Edge telemetry platform architecture, Zeus cloud intelligence, and AI-powered diagnostics.",
    color: "#6366f1",
    logo: "/assets/aldc_logo.svg",
  },
];

export default function PartnersPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <section className="mx-auto max-w-4xl px-4 py-16">
          <h1 className="text-3xl font-bold sm:text-4xl">
            <span className="text-kisti-accent">Partners</span> &amp;
            Integration
          </h1>
          <p className="mt-4 text-foreground/60">
            KiSTI is built on proven platforms from industry leaders in
            motorsport ECU, edge AI, and cloud intelligence.
          </p>

          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {PARTNERS.map((partner) => (
              <div
                key={partner.name}
                className="rounded-xl border border-white/10 bg-white/5 p-6"
              >
                {partner.logo && (
                  <img
                    src={partner.logo}
                    alt={`${partner.name} logo`}
                    className="mb-4 h-8"
                    draggable={false}
                  />
                )}
                <div
                  className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
                  style={{
                    backgroundColor: `${partner.color}20`,
                    color: partner.color,
                  }}
                >
                  {partner.role}
                </div>
                <h3 className="text-lg font-bold text-foreground">
                  {partner.name}
                </h3>
                <p className="mt-2 text-sm text-foreground/60">
                  {partner.description}
                </p>
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className="mt-16 rounded-xl border border-kisti-accent/30 bg-kisti-accent/5 p-8 text-center">
            <h2 className="text-2xl font-bold text-foreground">
              Interested in KiSTI?
            </h2>
            <p className="mt-3 text-foreground/60">
              Whether you&apos;re a racing team, OEM, or tech partner — we&apos;d love to
              talk about edge telemetry.
            </p>
            <a
              href="mailto:contact@analyticlabs.io"
              className="mt-6 inline-block rounded-lg bg-kisti-accent px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-kisti-glow"
            >
              Get in Touch
            </a>
          </div>
        </section>
      </main>
    </>
  );
}
