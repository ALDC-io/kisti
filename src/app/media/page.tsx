import Nav from "@/components/Nav";

const MEDIA_ITEMS = [
  {
    title: "Track Day: Brake Telemetry Analysis",
    type: "Video",
    status: "Coming Soon",
  },
  {
    title: "Jetson Orin Edge Setup Walkthrough",
    type: "Video",
    status: "Coming Soon",
  },
  {
    title: "CAN Bus Data Deep Dive",
    type: "Article",
    status: "Coming Soon",
  },
  {
    title: "Zeus Findings in Action",
    type: "Demo",
    status: "Coming Soon",
  },
  {
    title: "Link G4X Configuration Guide",
    type: "Tutorial",
    status: "Coming Soon",
  },
  {
    title: "KiSTI Build Series — Episode 1",
    type: "Video",
    status: "Coming Soon",
  },
];

export default function MediaPage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen pt-14">
        <section className="mx-auto max-w-4xl px-4 py-16">
          <h1 className="text-3xl font-bold sm:text-4xl">
            <span className="text-kisti-accent">Media</span> &amp; Content
          </h1>
          <p className="mt-4 text-foreground/60">
            Videos, articles, and tutorials about KiSTI&apos;s edge telemetry
            platform. Content is in production.
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MEDIA_ITEMS.map((item) => (
              <div
                key={item.title}
                className="group relative rounded-xl border border-white/10 bg-white/5 p-5 transition-colors hover:border-kisti-accent/30"
              >
                {/* Placeholder thumbnail */}
                <div className="mb-4 flex h-32 items-center justify-center rounded-lg bg-white/5">
                  <span className="text-3xl text-foreground/20">
                    {item.type === "Video"
                      ? "▶"
                      : item.type === "Article"
                        ? "📄"
                        : item.type === "Demo"
                          ? "⚡"
                          : "📖"}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-kisti-accent/10 px-2 py-0.5 text-xs font-medium text-kisti-accent">
                    {item.type}
                  </span>
                  <span className="text-xs text-foreground/40">
                    {item.status}
                  </span>
                </div>

                <h3 className="mt-2 text-sm font-semibold text-foreground/80 group-hover:text-foreground">
                  {item.title}
                </h3>
              </div>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
