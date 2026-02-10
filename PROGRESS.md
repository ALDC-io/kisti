# KiSTI — Progress

## Phase 1: Project Scaffolding + Data Layer — COMPLETE
- [x] GitHub repo `ALDC-io/kisti` created
- [x] Next.js 15 + TypeScript + Tailwind v4 scaffolded
- [x] Data model: `types.ts`, `kistiGraph.ts` (10 nodes, 9 edges), `mockTelemetry.ts`
- [x] Placeholder SVGs for STI schematic, Link logo, Jetson logo
- [x] Custom color palette in `globals.css` via `@theme inline`

## Phase 2: Landing Page — Schematic Overlay — COMPLETE
- [x] `KistiAthenaOverlay.tsx` — interactive SVG with node circles, edge lines, animated pulse
- [x] `HeroSection.tsx` — title, subtitle, 2 CTAs
- [x] Node selection with highlight/dim behavior
- [x] Live telemetry values rendered on each node

## Phase 3: Right Sidebar — Telemetry + Zeus Findings — COMPLETE
- [x] `NodeSidebar.tsx` — slide-in panel with gradient header
- [x] `TelemetryCard.tsx` — value display, status dot, SVG sparkline
- [x] `ZeusFindingsCard.tsx` — severity badges, clickable related-node chips
- [x] `CloudSyncIndicator.tsx` — ONLINE/QUEUED/OFFLINE with pending count

## Phase 4: Secondary Pages + Navigation — COMPLETE
- [x] `Nav.tsx` — fixed dark navbar, active link indicator, mobile hamburger
- [x] `/tech` — system architecture, data pipeline stages, specs grid
- [x] `/partners` — partner cards, contact CTA
- [x] `/media` — placeholder media grid with Coming Soon

## Phase 5: Polish + Performance — COMPLETE
- [x] Accessibility: aria-labels, keyboard nav, role attributes
- [x] Reduced-motion support via `prefers-reduced-motion` media query
- [x] robots.txt
- [x] OG metadata

## Phase 6: Deployment + DNS — COMPLETE
- [x] Push to GitHub
- [x] Connect Vercel (ALDC team, auto-deploy on push)
- [x] Cloudflare A record → 76.76.21.21
- [x] SSL provisioned via Let's Encrypt
- [x] Smoke test: all 4 routes return 200 on kisti.analyticlabs.io
