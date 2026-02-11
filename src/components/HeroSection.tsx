export default function HeroSection() {
  return (
    <section className="relative z-10 flex flex-col items-center px-4 pt-24 pb-8 text-center">
      {/* KiSTI wordmark in STI font style */}
      <img
        src="/assets/kisti_logo.png"
        alt="KiSTI"
        className="h-12 sm:h-16 lg:h-20"
        draggable={false}
      />
      <h1 className="mt-4 text-2xl font-bold tracking-tight text-foreground sm:text-3xl lg:text-4xl">
        Make Data Speak Racer
      </h1>
      <p className="mt-4 max-w-2xl text-base text-foreground/60 sm:text-lg">
        Real-time edge telemetry on a 2014 Subaru STI. Pull in after a lap
        and quickly understand what&apos;s working and what&apos;s not from your
        car&apos;s own suite of sensors — now it can tell you in plain English.
      </p>

      {/* Built by badges */}
      <div className="mt-5 flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs text-foreground/40">
          <span>Built by</span>
          <img
            src="/assets/boost_barn_logo.png"
            alt="Boost Barn"
            className="h-6"
            draggable={false}
          />
        </div>
        <span className="text-foreground/20">|</span>
        <div className="flex items-center gap-2 text-xs text-foreground/40">
          <span>Powered by</span>
          <img
            src="/assets/aldc_logo.svg"
            alt="ALDC"
            className="h-6"
            draggable={false}
          />
        </div>
      </div>

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
