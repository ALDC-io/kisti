export default function HeroSection() {
  return (
    <section className="relative z-10 flex flex-col items-center px-4 pt-24 pb-8 text-center">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
        <span className="text-kisti-accent">KiSTI</span>
        <span className="text-foreground"> — Make Data Speak Racer</span>
      </h1>
      <p className="mt-4 max-w-2xl text-base text-foreground/60 sm:text-lg">
        Real-time edge telemetry on a 2014 Subaru STI. Link ECU G4X + NVIDIA
        Jetson Orin — sensor fusion, AI diagnostics, cloud sync.
      </p>
      <div className="mt-6 flex gap-3">
        <a
          href="#schematic"
          className="rounded-lg bg-kisti-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-kisti-glow"
        >
          Explore Live Data
        </a>
        <a
          href="/tech"
          className="rounded-lg border border-white/20 px-5 py-2.5 text-sm font-medium text-foreground/80 transition-colors hover:border-white/40 hover:text-foreground"
        >
          How It Works
        </a>
      </div>
    </section>
  );
}
