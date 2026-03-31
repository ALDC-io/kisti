# NVIDIA Sponsorship Strategy — KiSTI

## Current Hardware
- **Jetson Orin NX Super Developer Kit 16GB** — 100 TOPS, 16GB LPDDR5, 10-25W
- Only major compute component without a sponsorship partner

## Current Limitations
- LLM inference disabled to preserve GPU headroom for whisper.cpp STT
- Camera streams throttled — can't run all 4 simultaneously with voice pipeline
- Embedding generation competes with real-time speech recognition
- Track sessions with full sensor + vision + voice push thermal envelope
- No concurrent GPU-intensive tasks — one at a time

## Target Hardware Comparison

### In-Car Edge Compute

| Spec | Orin NX 16GB (current) | AGX Orin 64GB | AGX Thor | DRIVE AGX Orin | DRIVE AGX Thor |
|---|---|---|---|---|---|
| **TOPS** | 100 | 275 | 1,000+ | 254 | 1,000 |
| **Memory** | 16GB LPDDR5 | 64GB LPDDR5 | 128GB LPDDR5X | 32GB LPDDR5 | 128GB LPDDR5X |
| **Bandwidth** | 102 GB/s | 204 GB/s | 273 GB/s | ~204 GB/s | 273 GB/s |
| **Power** | 10-25W | 15-60W | 40-130W | ~100-200W | 75-130W |
| **CAN** | 1x | 1x | 4x | 2+ CAN FD | 4x CAN |
| **Cameras** | 4 (8 virtual) | 6 (12 virtual) | 16x CSI-2 | 16x GMSL2 | 16x CSI-2 |
| **USB** | 3x USB 3.2 | 4x USB 3.2 | 3x USB 3.2 | USB 3.2 | 3x USB 3.2 |
| **Safety Cert** | None | None | None | ISO 26262 ASIL-D | ISO 26262 + ISO 21434 |
| **Price** | ~$600 | $1,999 | $3,499 | $7,500 | TBD |
| **Access** | Open | Open | Open | OEM-gated program | OEM-gated program |
| **Form Factor** | 69.6x45mm module | 100x87mm module | ~100x87mm module | 147.7x147.7mm, 5.6kg | Similar |

### DRIVE AGX Access Requirements
- NVIDIA DRIVE AGX SDK Developer Program membership
- Corporate/university email required (no personal Gmail)
- "Appropriate agreements on file with NVIDIA"
- Designed for OEMs, Tier 1 suppliers, research institutions
- ALDC corporate credentials could qualify

## Recommendation

### In-Car: DRIVE AGX Orin (sponsorship ask) / Jetson AGX Thor (self-funded fallback)
- DRIVE AGX positions KiSTI in NVIDIA's automotive division (not just maker/hobbyist)
- ISO 26262 certification shows we're serious about automotive AI
- 16x GMSL2 camera inputs future-proofs the vision pipeline
- Multiple CAN FD interfaces for Link ECU + AiM Strada + expansion
- AGX Thor ($3,499) is the fallback if DRIVE program access isn't granted

### Pit-Side: DGX Spark
- **1 PFLOP FP4, 128GB unified memory, 1.2 kg** — portable AI workstation
- Sits trackside with pit crew for deep analysis (session replay, failure synthesis)
- Replaces cloud dependency — runs locally at the track without connectivity
- ~$3,000 — Mac Mini form factor, travels in the toolbox

## Sponsorship Pitch Summary

**What makes KiSTI compelling to NVIDIA:**
1. Real vehicle, real sensors, real track time — not a simulation
2. Full voice AI pipeline running entirely on Jetson CUDA
3. E85 corn-derived ethanol — sustainability narrative
4. Live public demo at kisti.analyticlabs.io
5. Enterprise Intelligence platform (ALDC) behind it — same architecture at the edge
6. Link ECU already sponsoring — precedent for hardware partnerships
7. 625+ test suite — production-grade, not a prototype
8. Content-ready: track days, engine noise, G-forces = compelling demos

**What NVIDIA gets:**
- Real-world Jetson showcase under extreme conditions
- Automotive edge AI reference implementation
- E85 + AI narrative (unique positioning)
- Live interactive demo site
- Enterprise customer pathway (ALDC → KiSTI → Enterprise Intelligence)

## Prior Sponsorship Reference (Link ECU)
- Contact: Justin Medina (Justin.Medina@linkecu.com)
- Approach worked: John Moran emails with KiSTI narrative + microsite
- Zeus Memory ZMIDs: `7cadeb39`, `a1435e23`, `dca9ebee` (emails), `9f6387ea` (trigger)
- Result: Full electronics stack sponsored (G5 Neo 4, Razor PDM, Strada 7", Keypad, sensors)

## Files
- **Sponsorship letter**: `docs/nvidia-sponsorship-letter.md`
- **This strategy doc**: `docs/nvidia-sponsorship-strategy.md`
