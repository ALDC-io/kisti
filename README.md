# KiSTI — Edge Telemetry Platform

Interactive demo of ALDC's edge telemetry platform built on a 2014 Subaru STI. Sensor nodes connect via CAN bus to a Link ECU G4X, which feeds an NVIDIA Jetson Orin for edge inference and cloud sync.

**Live**: [kisti.analyticlabs.io](https://kisti.analyticlabs.io)

## Stack

- **Next.js 15** (App Router, TypeScript)
- **Tailwind CSS v4**
- **SVG overlay** with percentage-based coordinates
- **Mock telemetry** engine with Gaussian random walk
- **Vercel** deployment

## Features

- Interactive SVG schematic with 10 sensor/compute nodes
- Real-time telemetry with 6-7Hz update rate
- Brake FR vs FL asymmetry "story" (FR runs 15-40°F hotter)
- Zeus Findings with severity badges and clickable related-node chips
- Cloud sync status indicator (ONLINE/QUEUED/OFFLINE)
- Responsive design (375px-1440px)
- Keyboard accessible with reduced-motion support

## Development

```bash
npm install
npm run dev    # http://localhost:3000
npm run build  # Production build
```

## Deployment

See [DEPLOY.md](./DEPLOY.md) for Vercel + Cloudflare configuration.
