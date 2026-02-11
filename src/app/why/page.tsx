import Nav from "@/components/Nav";

export default function WhyPage() {
  return (
    <>
      <Nav />
      <main className="relative min-h-screen overflow-hidden pt-14">
        {/* Ki watermark */}
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 flex items-center justify-center select-none"
        >
          <span className="text-[20rem] font-bold leading-none text-white/[0.02]">
            気
          </span>
        </div>

        <article className="relative mx-auto max-w-3xl px-4 py-16">
          {/* Hero */}
          <header>
            <h1 className="text-4xl font-bold sm:text-5xl">
              Why <span className="text-kisti-accent">KiSTI</span>?
            </h1>
            <p className="mt-4 text-xl text-foreground/60">
              Making Data Speak Racer
            </p>
          </header>

          {/* Divider — KITT scanner line */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Section 1 — The Concept */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Knight Industries STI
            </h2>
            <div className="mt-4 space-y-4 text-foreground/70">
              <p>
                We grew up as fans of Knight Rider. The idea of a talking car
                that understood its driver was science fiction in the 80s.
              </p>
              <p>
                KiSTI &mdash; the{" "}
                <span className="font-semibold text-kisti-accent">K</span>
                nowledge-
                <span className="font-semibold text-kisti-accent">I</span>
                ntegrated{" "}
                <span className="font-semibold text-kisti-accent">S</span>mart{" "}
                <span className="font-semibold text-kisti-accent">T</span>
                elemetry{" "}
                <span className="font-semibold text-kisti-accent">I</span>
                nterface &mdash; is our love letter to that idea, built on a
                2014 Subaru STI.
              </p>
              <p>
                Where KITT had an AI that could talk, KiSTI has 19 sensors, 4
                cameras, an edge AI, and a memory system called Zeus that turns
                raw telemetry into plain English.{" "}
                <span className="text-kisti-accent">
                  Oh, and it talks too.
                </span>
              </p>
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Section 2 — Ki */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Ki <span className="text-kisti-accent">(気)</span> &mdash; The
              Energy Within
            </h2>
            <div className="mt-4 space-y-4 text-foreground/70">
              <p>
                In Japanese philosophy,{" "}
                <span className="font-semibold text-kisti-accent">Ki (気)</span>{" "}
                is the vital energy or life force that flows through all living
                things.
              </p>
              <p>
                In a race car, data IS that vital energy &mdash; flowing through
                CAN buses, sensor wires, WiFi links, and cloud pipelines.
              </p>
              <p>
                KiSTI channels that data-ki into something meaningful: the car
                literally speaks to its driver and crew.
              </p>
              <p>
                The name captures both:{" "}
                <span className="font-semibold text-kisti-accent">Ki</span>{" "}
                (data energy) +{" "}
                <span className="font-semibold text-kisti-accent">STI</span>{" "}
                (the platform).
              </p>
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Section 3 — The Real Purpose */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Data Speaking Human
            </h2>
            <div className="mt-4 space-y-4 text-foreground/70">
              <p>
                KiSTI is a vehicle{" "}
                <span className="text-foreground/40">(pun intended)</span> built
                by{" "}
                <a
                  href="https://www.aldc.io"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-kisti-accent hover:underline"
                >
                  Analytic Labs
                </a>{" "}
                in collaboration with Boost Barn, to showcase what happens when
                you bring multiple technologies together, each with their own
                set of data.
              </p>
              <p>
                Our mission is to{" "}
                <span className="font-semibold text-kisti-accent">
                  make data speak human
                </span>
                . KiSTI shows off our ability to gather, analyze, and share data
                in novel and fun ways &mdash; while making all of it as easy to
                interact with as having a conversation.
              </p>
              <p className="font-mono text-sm text-kisti-accent/80">
                19 sensors &times; 4 cameras &times; 1 ECU &times; 1 edge
                computer = one unified story told in plain English.
              </p>
              <p>
                We wanted to bring the world of performance tuning together with
                modern data analytics. Link Engine Management gives us the
                nervous system &mdash; 100+ CAN channels of real-time engine
                data. NVIDIA&apos;s Jetson Orin gives us the brain &mdash; 40
                TOPS of edge AI processing telemetry and vision in under 50ms.
                Boost Barn gives us the muscle &mdash; a properly built STI that
                delivers data{" "}
                <span className="italic text-kisti-accent">fast</span>.
              </p>
              <p>
                The same pattern applies to any business: replace sensors with
                databases, cameras with APIs, the ECU with your data warehouse,
                and the Jetson with your AI layer. Zeus doesn&apos;t just store
                data &mdash; it makes data speak human. Or in this case, speak
                racer.
              </p>
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Section 4 — Built By */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">Built By</h2>
            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                {
                  src: "/assets/boost_barn_logo.png",
                  alt: "Boost Barn",
                  role: "Build",
                },
                {
                  src: "/assets/aldc_logo.svg",
                  alt: "ALDC",
                  role: "Platform + Zeus",
                },
                {
                  src: "/assets/link_logo.svg",
                  alt: "Link Engine Management",
                  role: "ECU",
                },
                {
                  src: "/assets/jetson_orin_logo.svg",
                  alt: "NVIDIA",
                  role: "Edge",
                },
              ].map((partner) => (
                <div
                  key={partner.alt}
                  className="flex flex-col items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-4"
                >
                  <img
                    src={partner.src}
                    alt={partner.alt}
                    className="h-8"
                    draggable={false}
                  />
                  <span className="text-xs text-foreground/50">
                    {partner.role}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-6 text-center text-sm text-foreground/50 italic">
              KiSTI is built by people who believe data should talk, not just
              sit in dashboards.
            </p>
          </section>
        </article>
      </main>
    </>
  );
}
