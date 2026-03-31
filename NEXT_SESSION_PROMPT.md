# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: https://kisti.analyticlabs.io
**Branch**: `kisti-headless` (must merge to `main` for production Vercel deploy)
**Deploy**: Vercel auto-deploys from `main` only. kisti-headless → Preview URL only.

## What Was Done (2026-03-30)

### NVIDIA Product Cards + Leader Lines on Homepage
- Jetson Orin NX Super Dev Kit card on RHS of car schematic with green (#76b900) leader lines
- H100 HGX card below pit engineer view — **NEEDS REPLACING with DGX Spark** (see TODO #1)
- Dynamic SVG with dual-color markers (amber Link, green Nvidia)
- Nvidia panel fades when NodeSidebar opens

### Schematic + Site Updates
- "Jetson Orin" → "Jetson Orin NX" in kistiGraph.ts + partners page
- "Weather Cam" → "Weather Station" (Yoctopuce Yocto-Spruce)
- Tech page: 100 TOPS, Voice AI Pipeline section, Vehicle/E85 section, specific sensor models
- Partners: NVIDIA role "Edge AI Platform" with Orin NX 100 TOPS capabilities

### NVIDIA Sponsorship Docs
- `docs/nvidia-sponsorship-letter.md` — complete draft, real specs, E85 angle, 3.5M+ memories
- `docs/nvidia-sponsorship-strategy.md` — DRIVE AGX research, target hardware comparison, pitch points

## Prioritized TODO

### 1. Replace H100 with DGX Spark on Homepage (HIGH)
The H100 HGX is a data center rack — wrong for pit crew. Replace with **NVIDIA DGX Spark**:
- **Product**: DGX Spark — 1 PFLOP FP4, 128GB, 1.2 kg, ~$3,000, Mac Mini size
- **Role on site**: "Pit-Side AI" under the pit engineer view
- **Image URLs** (PNY CDN, clean isolated product shots on transparent bg):
  - Best 3/4 angle: `https://d2vfia6k6wrouk.cloudfront.net/productimages/ef15a000-baca-4109-a81e-b2f9010d00f9/images/spark-3qtr-right.png`
  - Top view: `https://d2vfia6k6wrouk.cloudfront.net/productimages/ef15a000-baca-4109-a81e-b2f9010d00f9/images/spark-3qtr-top-left.png`
- Download to `public/assets/nvidia_dgx_spark.png`
- Delete `public/assets/nvidia_h100.jpg`
- Edit `src/app/page.tsx` ~lines 463-488:
  - href → `https://www.nvidia.com/en-us/products/workstations/dgx-spark/`
  - img src → `/assets/nvidia_dgx_spark.png`
  - bg → `bg-white` (product is gold on transparent)
  - alt/name → "NVIDIA DGX Spark"
  - role → "Pit-Side AI"
  - spec → "1 PFLOP, 128GB, 1.2 kg"
- After edit: `git checkout main && git merge kisti-headless && git push origin main`

### 2. Update Sponsorship Letter with Three-Tier Stack (HIGH)
Current letter asks generically for "AGX Orin/Thor/DRIVE AGX". Update to the clear three-tier ask:
- **In-car**: Jetson AGX Thor — 1,000+ TOPS, 128GB, 40-130W configurable (40W mode = quiet for voice)
- **Pit-side**: DGX Spark — 1 PFLOP, 128GB, 1.2 kg (portable AI workstation trackside)
- **Cloud**: Zeus Memory — 3.5M+ memories, deep analysis
- Add noise argument: AGX Thor configurable 40W for voice, 130W only when engine running
- Mention DGX Spark replaces the generic "cloud compute" ask

### 3. Save Work to Nextcloud (MEDIUM)
- Target: `/home/aldc/nextcloud-rclone/ALDC Management/CCE_projects/02-ai-chat-visualization/2026-03-20-kisti-edge-ai-codriver/`
- Copy `docs/nvidia-sponsorship-letter.md` and `docs/nvidia-sponsorship-strategy.md` there

### 4. In-Car Product Card — User's Actual vs Displayed Hardware (LOW)
- User's actual hardware: Jetson Orin Nano (40 TOPS, 8GB)
- Site shows: Jetson Orin NX 16GB (100 TOPS) — this is the target/sponsor ask
- Consider: add subtle "current" vs "target" distinction, or keep as-is for the pitch

## Key Files

| File | Purpose |
|------|---------|
| `src/app/page.tsx` | Homepage — product cards, leader lines, H100 card (~line 463) |
| `src/app/tech/page.tsx` | Tech — voice AI pipeline, vehicle/E85, sensor details |
| `src/app/partners/page.tsx` | Partner cards (NVIDIA = "Edge AI Platform") |
| `src/lib/kistiGraph.ts` | Schematic nodes (Jetson at x:50, y:88) |
| `docs/nvidia-sponsorship-letter.md` | Sponsorship pitch letter |
| `docs/nvidia-sponsorship-strategy.md` | Research + strategy + comparison tables |
| `public/assets/nvidia_h100.jpg` | DELETE — replace with DGX Spark |
| `public/assets/nvidia_jetson_orin_nx.jpg` | Cropped Orin NX dev kit product shot |

## Jetson State (from kisti-14/15)
- Orin Nano, 8GB RAM, whisper-server port 8081
- Frontier engine deployed (Claude Haiku via ANTHROPIC_API_KEY)
- 805 tests passing, TTS cache 420 files
- Branch: kisti-headless
