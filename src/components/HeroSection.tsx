"use client";

import { useState, useEffect } from "react";

const WORDS = ["Human", "Racer"];
const DISPLAY_MS = 4700;
const ANIM_MS = 600;

export default function HeroSection() {
  const [index, setIndex] = useState(0);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced) {
      setIndex(1); // Show "Racer" statically
      return;
    }

    const interval = setInterval(() => {
      setAnimating(true);
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % WORDS.length);
        setAnimating(false);
      }, ANIM_MS);
    }, DISPLAY_MS + ANIM_MS);

    return () => clearInterval(interval);
  }, []);

  const nextIndex = (index + 1) % WORDS.length;
  const glowStyle = {
    textShadow:
      "0 0 20px rgba(139,92,246,0.5), 0 0 40px rgba(139,92,246,0.25)",
  };

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
        Make Data Speak{" "}
        <span className="animate-hero-word relative inline-block overflow-hidden align-baseline" style={{ height: "1.15em", top: "0.2em" }}>
          {/* Invisible sizer — forces container width to widest word */}
          <span className="invisible block text-kisti-accent" aria-hidden="true">Human</span>
          {/* Current word */}
          <span
            className="absolute inset-0 text-kisti-accent transition-all duration-[600ms] ease-in-out"
            style={{
              ...glowStyle,
              transform: animating ? "translateY(-100%)" : "translateY(0)",
              opacity: animating ? 0 : 1,
            }}
          >
            {WORDS[index]}
          </span>
          {/* Next word */}
          <span
            className="absolute inset-0 text-kisti-accent transition-all duration-[600ms] ease-in-out"
            style={{
              ...glowStyle,
              transform: animating ? "translateY(0)" : "translateY(100%)",
              opacity: animating ? 1 : 0,
            }}
          >
            {WORDS[nextIndex]}
          </span>
        </span>
      </h1>
      <p className="mt-4 max-w-2xl text-base text-foreground/60 sm:text-lg">
        Real-time edge telemetry on a 2014 Subaru STI. Pull in after a lap
        and understand what&apos;s working and what&apos;s not from your
        car&apos;s own suite of sensors,
        <br />
        just by asking it.
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
