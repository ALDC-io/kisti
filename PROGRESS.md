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
- [x] KITT scan bar — purple gradient sweep during "thinking" phase
- [x] Typewriter effect — 25ms/char with blinking cursor
- [x] KiSTI persona — first-person voice, Knight Industries STI identity, born 2014, upgraded 2026
- [x] Boost Barn knowledge — shop details, builds portfolio, contact info, tuning platforms
- [x] Favicon — replaced Vercel with KiSTI logo
- [x] Vercel toolbar hidden
- [x] Hero tagline — "just by asking it." on its own line
- [x] Double-response bug fixed (useRef for callback, not useEffect dep)
- [x] Brand voice audit — no negative competitor references ("work hard, be kind")

## Phase 8: Driver View — ZMID Spec Match (1ec8edc3) — COMPLETE (2026-02-10)
- [x] KistiMode: expanded from 30 → 100 idle lines across 10 categories (personality, STI/Subaru, Boost Barn, ALDC, FLIR thermal, track tips, tire/brake telemetry, engine/powertrain, Zeus Memory, motorsport trivia)
- [x] KistiMode: scrolling message log — newest at top, older messages fade, max 8 visible
- [x] KistiMode: typewriter speed 35ms → 30ms
- [x] KistiMode: cursor accent #E60000 → #C80A33 (brand red)
- [x] KistiMode: logo cropped via CSS (object-fit/position, overflow container) to remove 65% PNG padding
- [x] DriverSoftkeyBar: KiSTI logo height 14px → 28px with CSS crop
- [x] TrackMode: removed corner temp labels — pure visual heatmap
- [x] TrackMode: cold tire color #0077DD → #50B4FF per ZMID spec
- [x] Build: zero errors

### Files Modified
- `src/components/driver/KistiMode.tsx` — 100 idle lines, scrolling log, 30ms typewriter, #C80A33 cursor, logo crop
- `src/components/driver/DriverSoftkeyBar.tsx` — logo 28px + crop styling
- `src/components/driver/TrackMode.tsx` — removed corner labels, updated cold color to #50B4FF

### Learnings
- **useEffect callback identity**: Putting callback props in useEffect deps causes re-fires on parent re-render. Use useRef to store callbacks, depend only on stable values (IDs).
- **Brand voice**: Never reference competing products negatively. Describe what you ARE, not what you're not relative to others.
- **Zeus API URL**: Use `zeus.aldc.io`, not `zeus-api.analyticlabs.io` (no DNS records).
- **Persona layering**: Volunteer the identity ("Knight Industries STI"), but layer details like "subsidiary of Analytic Labs" behind direct questions only.
