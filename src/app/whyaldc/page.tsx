import Nav from "@/components/Nav";

const TIMELINE = [
  {
    marker: "Day 1",
    text: "Connect your data. Cross-source intelligence begins immediately.",
  },
  {
    marker: "Day 90",
    text: "Organizational patterns emerge. Cross-functional insights deepen.",
  },
  {
    marker: "Year 1",
    text: "Institutional memory that no manual process can replicate.",
  },
];

const FRONTIER_CAN = [
  "Summarize documents and reports",
  "Answer questions about data",
  "Draft communications",
  "Remember conversations and browse the web",
];

const SINGLE_MODEL_TRAP = [
  "No institutional knowledge",
  "No live operational data",
  "No cross-source synthesis",
  "No institutional memory",
];

const STACK = [
  {
    name: "Eclipse",
    role: "Data Platform",
    description:
      "Ingests operational data via 123 connectors — CRM records, financial systems, project files, meeting recordings, and industry research.",
    color: "#f59e0b",
  },
  {
    name: "Zeus Memory",
    role: "Context Layer",
    description:
      "Persistent institutional knowledge that compounds with every analysis and interaction. Over 204,000 active memories with 5-tier retention.",
    color: "#8b5cf6",
  },
  {
    name: "Zeus Chat",
    role: "Evidence Engine",
    description:
      "Conversational interface with intelligent model routing. Routes each task to the optimal frontier AI based on task requirements.",
    color: "#10b981",
  },
];

const SOURCES = [
  "CRM Records",
  "Meeting Transcripts",
  "Financial Data",
  "Project Files",
  "Email Archives",
  "Industry Research",
  "Team Utilization",
  "Operational Systems",
];

const VIEWS = [
  "Executive Intelligence Brief",
  "Client Relationship Timeline",
  "Competitive Landscape Analysis",
  "Operational Performance Dashboard",
  "Knowledge Discovery Workbench",
  "Strategic Initiative Tracker",
];

const PROCESS = [
  {
    stage: "Ingest",
    description:
      "Connect operational systems and documents. AI sorts and organizes incoming content automatically.",
    detail: "123 connectors, encrypted at rest, auto-cleaned",
  },
  {
    stage: "Analyze",
    description:
      "Intelligent search across all sources. Pattern discovery surfaces insights humans would miss.",
    detail: "Voyage + Gemini embeddings, semantic + full-text search",
  },
  {
    stage: "Govern",
    description:
      "Automatic retirement of outdated information. AI validates accuracy across sources.",
    detail: "5-tier retention, relevance scoring, audit trail",
  },
  {
    stage: "Deliver",
    description:
      "Dashboards, reports, and conversational Q&A — all with evidence citations.",
    detail: "Multi-model routing, feedback loops, confidence scores",
  },
];

export default function WhyALDCPage() {
  return (
    <>
      <Nav />
      <main className="relative min-h-screen overflow-hidden pt-14">
        {/* Subtle watermark */}
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 flex items-center justify-center select-none"
        >
          <span className="text-[16rem] font-bold leading-none text-white/[0.015]">
            EI
          </span>
        </div>

        <article className="relative mx-auto max-w-4xl px-4 py-16">
          {/* Hero */}
          <header>
            <h1 className="text-4xl font-bold sm:text-5xl">
              Why{" "}
              <span className="text-kisti-accent">ALDC</span>
            </h1>
            <p className="mt-2 text-xl text-foreground/60">
              Enterprise Intelligence &mdash; The Compounding Advantage
            </p>
            <p className="mt-6 text-foreground/70">
              KiSTI turns 19 sensors into a conversation. The same platform does
              it for your entire organization &mdash; CRM, financials, meetings,
              projects, and research &mdash; all speaking human.
            </p>
          </header>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Timeline */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              The System Gets Smarter Every Day
            </h2>
            <div className="mt-8 space-y-6">
              {TIMELINE.map((item) => (
                <div key={item.marker} className="flex items-start gap-4">
                  <span className="mt-0.5 shrink-0 rounded-full bg-kisti-accent/15 px-3 py-1 text-sm font-bold text-kisti-accent">
                    {item.marker}
                  </span>
                  <p className="text-foreground/70">{item.text}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Intelligence Multiplier */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              The Intelligence Multiplier
            </h2>
            <p className="mt-4 text-foreground/70">
              ALDC doesn&apos;t replace your AI tools &mdash; it makes them
              dramatically more effective. Gemini, ChatGPT, Copilot, Claude
              &mdash; they&apos;re all powerful on their own. But without
              institutional context, they&apos;re guessing.
            </p>

            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              {/* What frontier AI does well */}
              <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-6">
                <h3 className="text-sm font-semibold text-green-400">
                  What frontier AI does well
                </h3>
                <ul className="mt-4 space-y-2">
                  {FRONTIER_CAN.map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-foreground/70"
                    >
                      <span className="mt-1 text-green-400">+</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* The single-model trap */}
              <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
                <h3 className="text-sm font-semibold text-red-400">
                  The single-model trap
                </h3>
                <ul className="mt-4 space-y-2">
                  {SINGLE_MODEL_TRAP.map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-foreground/70"
                    >
                      <span className="mt-1 text-red-400">&times;</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <p className="mt-6 rounded-lg border border-kisti-accent/20 bg-kisti-accent/5 p-4 text-sm text-foreground/60">
              The AI models are the same ones everyone has access to. The
              difference is that every task your organization runs through this
              system makes the next one faster, more accurate, and more
              valuable.
            </p>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* The Stack — KiSTI analogy */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              AI-Native Intelligence Architecture
            </h2>
            <p className="mt-4 text-foreground/70">
              In KiSTI, sensors feed an ECU, the ECU feeds a Jetson, and the
              Jetson feeds Zeus. In your organization, the pattern is identical
              &mdash; just swap the hardware for your business systems.
            </p>

            {/* KiSTI → Enterprise mapping */}
            <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <p className="font-semibold text-kisti-accent">KiSTI</p>
                  <p className="mt-1 text-foreground/50">
                    Sensors → CAN → Link ECU → Jetson → Zeus
                  </p>
                </div>
                <div>
                  <p className="font-semibold text-kisti-accent">
                    Your Organization
                  </p>
                  <p className="mt-1 text-foreground/50">
                    Data Sources → APIs → Eclipse → Zeus Memory → Zeus Chat
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 grid gap-6 sm:grid-cols-3">
              {STACK.map((system) => (
                <div
                  key={system.name}
                  className="rounded-xl border border-white/10 bg-white/5 p-6"
                >
                  <div
                    className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold"
                    style={{
                      backgroundColor: `${system.color}20`,
                      color: system.color,
                    }}
                  >
                    {system.role}
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    {system.name}
                  </h3>
                  <p className="mt-2 text-sm text-foreground/60">
                    {system.description}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Unified View */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              One Unified View. Unlimited Perspectives.
            </h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-sm font-semibold text-foreground/50">
                  Data Sources Ingested
                </h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SOURCES.map((s) => (
                    <span
                      key={s}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-foreground/70"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground/50">
                  Purpose-Built Views
                </h3>
                <ul className="mt-3 space-y-2">
                  {VIEWS.map((v) => (
                    <li
                      key={v}
                      className="flex items-center gap-2 text-sm text-foreground/70"
                    >
                      <span className="text-kisti-accent">&#9656;</span>
                      {v}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* How It Works */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              How the Intelligence Layer Works
            </h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {PROCESS.map((step, idx) => (
                <div
                  key={step.stage}
                  className="rounded-xl border border-white/10 bg-white/5 p-6"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-kisti-accent/15 text-sm font-bold text-kisti-accent">
                      {idx + 1}
                    </span>
                    <h3 className="text-lg font-bold text-foreground">
                      {step.stage}
                    </h3>
                  </div>
                  <p className="mt-3 text-sm text-foreground/70">
                    {step.description}
                  </p>
                  <p className="mt-2 text-xs text-foreground/40">
                    {step.detail}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Evidence */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Audit-Ready Evidence, On Demand
            </h2>
            <p className="mt-4 text-foreground/70">
              Every answer comes with confidence scores, source citations, and
              an audit trail. No black boxes, no hallucinations without
              attribution.
            </p>
            <div className="mt-6 rounded-xl border border-kisti-accent/20 bg-[#0d0d20] p-6 font-mono text-sm">
              <p className="text-foreground/40">
                &gt; What are clients saying about our response times?
              </p>
              <div className="mt-4 space-y-2 text-foreground/70">
                <p>
                  <span className="text-green-400">91% confidence</span>{" "}
                  <span className="text-foreground/30">|</span>{" "}
                  <span className="text-kisti-accent">47 meetings analyzed</span>
                </p>
                <p>
                  Three recurring themes across Q4 client interactions:
                </p>
                <ul className="ml-4 space-y-1 text-foreground/60">
                  <li>1. Response time satisfaction: 78% positive mentions</li>
                  <li>2. Proactive communication: 64% requesting more</li>
                  <li>3. Technical depth: 89% positive, up from 71% in Q3</li>
                </ul>
                <p className="mt-3 text-xs text-foreground/30">
                  Sources: CRM Activity Log Q4 &bull; Meeting Transcripts
                  &mdash; Strategic Planning &bull; Industry Report 2025
                </p>
              </div>
            </div>
          </section>

          {/* Divider */}
          <div className="my-12 h-px w-full overflow-hidden rounded-full bg-white/10">
            <div className="animate-kitt-divider h-full w-1/4 rounded-full bg-gradient-to-r from-transparent via-kisti-accent to-transparent" />
          </div>

          {/* Closing CTA */}
          <section className="text-center">
            <h2 className="text-3xl font-bold text-foreground">
              Unmatched Capability
            </h2>
            <p className="mt-4 text-foreground/70">
              Enterprise Intelligence isn&apos;t a product you install.
              It&apos;s a capability that compounds from the moment you start.
            </p>
            <p className="mt-2 text-sm font-semibold text-kisti-accent">
              The organizations that begin first compound the furthest.
            </p>

            <div className="mt-10 rounded-xl border border-kisti-accent/30 bg-kisti-accent/5 p-8">
              <h3 className="text-xl font-bold text-foreground">
                Start the Conversation
              </h3>
              <p className="mt-3 text-foreground/60">
                Ready to see what Enterprise Intelligence looks like for your
                organization?
              </p>
              <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
                <a
                  href="mailto:contact@analyticlabs.io"
                  className="inline-block rounded-lg bg-kisti-accent px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-kisti-glow"
                >
                  Get in Touch
                </a>
                <a
                  href="https://www.aldc.io"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block rounded-lg border border-kisti-accent/30 px-6 py-3 text-sm font-semibold text-kisti-accent transition-colors hover:bg-kisti-accent/10"
                >
                  Visit ALDC
                </a>
              </div>
            </div>
          </section>
        </article>
      </main>
    </>
  );
}
