# NVIDIA Sponsorship Letter — KiSTI Edge AI Co-Driver

**Subject:** KiSTI — Real-Time Edge AI Co-Driver on Jetson Orin NX | Sponsorship Inquiry

---

Dear NVIDIA Developer Relations Team,

I'm JK, CEO of Analytic Labs (ALDC). I'm reaching out about KiSTI — a motorsports-grade edge AI co-driver we've built entirely on the Jetson platform, deployed inside a real performance vehicle and tested at speed.

This isn't a concept. It's running.

## The Vehicle

2014 Subaru WRX STI Hatch. IAG 750 Closed Deck short block (rated 750 BHP). BCP X400 turbo. ID1300 injectors. COBB front-mount intercooler. Competition Clutch Stage 2 with ACT lightweight flywheel. Fortune Auto coilovers. CSF race-spec radiator. The vehicle runs exclusively on **E85 — corn-derived ethanol** — making it one of the few edge AI automotive platforms powered by renewable fuel. Full standalone flex fuel tune by Boost Barn Motorsports. $50K+ build, track-tested at Mission Raceway (BC, Canada).

## The AI System

KiSTI (Knight Industries STI) is an edge AI co-driver that monitors **19 sensors and 4 cameras** in real time, speaks to the driver in natural language, and operates **fully offline** — no cloud dependency, no cellular required.

The entire inference stack runs on a single **Jetson Orin NX Super Developer Kit (16GB)**:

- **Speech-to-text**: whisper.cpp with CUDA acceleration (~130ms for 3-second utterances)
- **Text-to-speech**: Piper TTS with sub-200ms end-to-end conversational latency
- **Telemetry**: 17 active sensor channels at 4-10Hz via CAN bus — brake temps (4x thermocouple), tire temps (4x IR), K-type EGT, boost (4-bar MAP), oil temp/pressure, wideband O2, intake air temp, flex fuel content
- **Vision**: 4 cameras (thermal IR, LiDAR depth, high-speed RGB, weather/ambient) via USB 3.0 and CSI
- **Edge memory**: DuckDB + ONNX embeddings for on-device knowledge persistence across sessions
- **Voice modes**: Three operational tiers — Informal (personality-driven, sarcastic), Standard (clinical telemetry), Safety-Critical (emergency alerts only)
- **Wake word**: Custom voice activation with barge-in echo cancellation
- **Cloud sync**: Store-and-forward to Zeus Memory (3.5M+ memories processed) via WiFi when connectivity is available

The system detects anomalies, predicts failure patterns, and tells the driver what's happening — in plain English, while they're driving. It remembers previous sessions, learns the driver's patterns, and adapts its alerts based on operational context.

## The Platform Behind It

KiSTI is built by ALDC — we develop Enterprise Intelligence systems that ingest operational data from 123+ connectors and turn it into conversational, evidence-backed insights. KiSTI demonstrates the same architecture pattern applied to automotive:

| KiSTI | Enterprise |
|-------|-----------|
| Sensors | Data Sources |
| CAN Bus | APIs |
| Link ECU | Eclipse (Data Platform) |
| Jetson Orin NX | Zeus Memory (Context Layer) |
| Voice Co-Driver | Zeus Chat (Evidence Engine) |

This isn't a side project — it's a real-world proof of our core technology running at the edge under extreme conditions (heat, vibration, G-forces, engine noise).

## Sponsored Hardware Stack

Link Engine Management is our ECU and electronics sponsor, providing the complete electronics package: G5 Neo 4 ECU, Razor PDM, AiM Strada 7" Street dash, 8-button CAN Keypad, plus MAP, IAT, flex fuel, and oil pressure sensors. AiM GPS09 Pro provides 6-axis IMU (accelerometer + gyroscope at 100Hz) plus GPS for lap timing and track position.

**The Jetson Orin NX is the only major compute component without a sponsorship partner.**

## What We're Hitting

At 100 TOPS and 16GB shared memory, we're managing — but making real trade-offs:

- **LLM inference disabled** to preserve GPU headroom for whisper.cpp STT
- **Camera streams throttled** — can't run all 4 simultaneously with the voice pipeline active
- **Embedding generation competes** with real-time speech recognition
- **Track sessions with full sensor + vision + voice** push the thermal envelope
- **No concurrent model execution** — one GPU-intensive task at a time

We've proven the concept works at 100 TOPS. More compute would let us prove what it's capable of.

## What We're Looking For

Access to higher-tier Jetson hardware to continue scaling this work:

- **Jetson AGX Orin 64GB** (275 TOPS) — immediate upgrade path, 4x memory headroom
- **Jetson AGX Thor** (1,000+ TOPS, 128GB) — unlocks simultaneous LLM + STT + vision
- **DRIVE AGX Orin/Thor** — production automotive platform, ISO 26262 certified

In exchange, we offer:

1. **Live public demo**: [kisti.analyticlabs.io](https://kisti.analyticlabs.io) — interactive telemetry, driver view, pit engineer dashboard
2. **Zeus Chat interface**: [kisti.analyticlabs.io/zeus](https://kisti.analyticlabs.io/zeus) — talk to the car directly
3. **Real-world benchmarks** from track sessions at Mission Raceway
4. **Content-ready platform**: KiSTI generates compelling demos of edge AI under extreme conditions
5. **Enterprise context**: ALDC's intelligence platform serves real organizations — KiSTI is the same architecture at the edge
6. **625+ test suite**: Production-grade software with comprehensive test coverage
7. **E85 sustainability narrative**: Edge AI powered by renewable corn-derived fuel

## The E85 Angle

The vehicle runs exclusively on E85 — corn-derived ethanol. The intersection of sustainable performance and AI at the edge is a narrative that doesn't exist anywhere else. A Jetson-powered co-driver in an ethanol-fueled performance car is a story that writes itself.

## Links

- **Live Demo**: https://kisti.analyticlabs.io
- **Zeus Chat**: https://kisti.analyticlabs.io/zeus
- **Technology**: https://kisti.analyticlabs.io/tech
- **Partners**: https://kisti.analyticlabs.io/partners
- **Why ALDC**: https://kisti.analyticlabs.io/whyaldc
- **ALDC**: https://www.aldc.io

Happy to share architecture diagrams, GPU profiling data, track session recordings, and detailed benchmarks.

Best regards,

**JK**
CEO, Analytic Labs (ALDC)
contact@analyticlabs.io
