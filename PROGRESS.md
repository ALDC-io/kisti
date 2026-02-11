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

## Phase 7: Zeus Rebrand + Why KiSTI + Chat — COMPLETE (2026-02-10)
- [x] Rebrand "Zeus Memory" → "Zeus" across 4 files
- [x] `/why` page — Knight Industries STI origin, Ki (気) philosophy, ALDC + Boost Barn collab
- [x] Nav: "Why KiSTI" link between Technology and Partners
- [x] Zeus chat widget — FAB, 384×448 panel, 34 Q&A entries, keyword matcher
- [x] KITT voice waveform — 3×14 mirrored horizontal segments, KiSTI logo red (#C80A33)
- [x] KITT scan bar — red (#C80A33) bidirectional sweep (KITT-style)
- [x] Typewriter effect — 25ms/char with blinking cursor
- [x] KiSTI persona — first-person voice, Knight Industries STI identity, born 2014, upgraded 2026
- [x] Boost Barn knowledge — shop details, builds portfolio, contact info, tuning platforms
- [x] Favicon — replaced Vercel with KiSTI logo
- [x] Vercel toolbar hidden
- [x] Hero tagline — "just by asking it." on its own line
- [x] Double-response bug fixed (useRef for callback, not useEffect dep)
- [x] Brand voice audit — no negative competitor references ("work hard, be kind")

## Phase 8: Driver View — ZMID Spec Match (1ec8edc3) — COMPLETE (2026-02-10)
- [x] KistiMode: expanded from 30 → 250 idle lines across 14 categories (personality, STI/Subaru, EJ257 jokes & build philosophy, Boost Barn, ALDC, FLIR thermal, track tips, tire/brake telemetry, engine/powertrain, Zeus Memory, motorsport trivia, weather/environment, philosophy/humor, data geek jokes)
- [x] KistiMode: scrolling message log — newest at top, older messages fade, max 8 visible
- [x] KistiMode: typewriter speed 35ms → 30ms
- [x] KistiMode: cursor accent #E60000 → #C80A33 (brand red)
- [x] KistiMode: removed redundant logo above waveform
- [x] DriverSoftkeyBar: KiSTI logo height 14px → 28px
- [x] DriverStatusBar: removed KiSTI logo and mode text, keep Link ECU logo only
- [x] TrackMode: removed corner temp labels — pure visual heatmap
- [x] TrackMode: cold tire color #0077DD → #50B4FF per ZMID spec
- [x] ZeusScanBar: purple → red (#C80A33), left-to-right-only → bidirectional sweep (KITT-style)
- [x] zeusResponses: added website refs (www.boostbarnmotorsports.com, www.aldc.io) to all 10 relevant Q&A entries
- [x] Build: zero errors, 8 commits pushed

### Files Modified
- `src/components/driver/KistiMode.tsx` — 250 idle lines (14 categories), scrolling log, 30ms typewriter, #C80A33 cursor, removed logo
- `src/lib/zeusResponses.ts` — website references added to Boost Barn and ALDC Q&A entries
- `src/components/driver/DriverSoftkeyBar.tsx` — logo 28px
- `src/components/driver/DriverStatusBar.tsx` — removed KiSTI logo + mode text
- `src/components/driver/DriverDisplay.tsx` — removed mode prop from StatusBar
- `src/components/driver/TrackMode.tsx` — removed corner labels, updated cold color to #50B4FF
- `src/components/chat/ZeusScanBar.tsx` — red gradient, bidirectional animation
- `src/app/globals.css` — kittScan keyframes: bounce back-and-forth, 2.4s cycle

### Learnings
- **useEffect callback identity**: Putting callback props in useEffect deps causes re-fires on parent re-render. Use useRef to store callbacks, depend only on stable values (IDs).
- **Brand voice**: Never reference competing products negatively. Describe what you ARE, not what you're not relative to others.
- **Zeus API URL**: Use `zeus.aldc.io`, not `zeus-api.analyticlabs.io` (no DNS records).
- **Persona layering**: Volunteer the identity ("Knight Industries STI"), but layer details like "subsidiary of Analytic Labs" behind direct questions only.
- **Logo assumptions**: Always check actual image dimensions before applying CSS crops. The plan assumed 1536x1024 with 65% padding, but the real file was 1332x329 (already tight). Wasted a commit.
- **KITT scan bar**: CSS `translateX(-100%)` to `translateX(300%)` is one-way only. For back-and-forth, add a 50% keyframe and double the duration.
- **Spec vs reality**: When implementing from a spec (ZMID 1ec8edc3), always cross-check asset files before assuming the spec's description of those assets is accurate.
- **Chat Q&A website refs**: Always include partner/company website URLs in chat responses for lead generation (Boost Barn → www.boostbarnmotorsports.com, ALDC → www.aldc.io).
