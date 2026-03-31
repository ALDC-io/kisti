**Subject:** Garage-Built AI Co-Driver Running on Jetson

---

Dear NVIDIA Developer Relations Team,

I'm JK, CEO of Analytic Labs (ALDC). I want to show you something your hardware made possible that I don't think you've seen yet.

NVIDIA's automotive AI story is McLaren, Mercedes, BMW — billion-dollar OEMs with billion-dollar budgets. That's impressive. But it's not the whole story.

We built an AI co-driver in a garage. A 12-year-old Subaru, a Jetson Orin NX, and open-source software. No OEM partnership. No venture funding. No team of 50 engineers. The car talks to the driver in plain English while they're driving — full voice AI pipeline, 17 live sensor channels, edge memory that persists across sessions — all running offline on a single Jetson.

That wasn't possible two years ago. Jetson changed that.

The story NVIDIA hasn't told yet is that Jetson didn't just make edge AI cheaper for the companies that could already afford it. It made automotive AI accessible to regular people. The kind of people who don't drive McLarens and don't know anyone who does. The kind of people who wrench on their cars on weekends. That market — grassroots, aftermarket, enthusiast automotive AI — exists now, and NVIDIA is the reason.

KiSTI is the proof.

## What We Built

The Subaru runs on E85 — corn-derived ethanol. That conversion requires a full sensor suite to manage fuel composition, combustion, and engine safety in real time. We work with [Link Engine Management](https://www.linkecu.com/), one of the premier companies building motorsports-grade engine computers, who is sponsoring the complete electronics package: ECU, power distribution, dash, and sensors.

That gives us 17+ sensor channels streaming live over CAN bus. Instead of just logging that data, we built an AI system on Jetson that turns it into a conversational co-driver:

- **Voice pipeline**: whisper.cpp STT + Piper TTS — fully offline, no cloud, no cellular
- **Sensor fusion**: 17 CAN bus channels from the Link ECU + external sensors (IR tire temps, thermal camera, weather station, 6-axis IMU/GPS)
- **Edge memory**: DuckDB + ONNX embeddings — the car remembers previous sessions
- **LLM co-driver**: Mode-aware — casual at cruise, clinical under load, emergency-only at the limit
- **Cloud sync**: Store-and-forward to our Zeus Memory platform when WiFi is available

The system is running, with 805 passing tests and a live interactive demo at [kisti.analyticlabs.io](https://kisti.analyticlabs.io). We've tested at Mission Raceway in BC, Canada, and the platform expands as additional sensors come online.

## Why This Matters to NVIDIA

Every Jetson success story on your blog is a robotics lab, a drone company, or an industrial automation firm. Those are important. But they're expected — of course well-funded companies build AI on your hardware.

What's unexpected is someone building an AI co-driver for a 12-year-old car in their garage. That's the story that makes a developer community sit up. That's the story that makes someone think "I could do that" — and then buy a Jetson to try. That grassroots energy is what turned Arduino and Raspberry Pi into ecosystems, not just products. Jetson is already there technically. Project KiSTI is the proof point for the narrative.

We're offering to help tell the story that Jetson has made automotive AI an everyman pursuit — and to showcase what the full NVIDIA edge stack can do:

### In-Car: Jetson AGX Thor
**1,000+ TOPS | 128GB | 40-130W configurable**

The configurable power envelope matters in a car. Low power for the voice pipeline when the cabin is quiet, full power when the engine is running and noise masks everything — unlocking simultaneous LLM + vision + full telemetry. If a garage-built car can run an AI co-driver on AGX Thor, the message is clear: this hardware is for everyone building at the edge, not just OEMs.

### Pit-Side: DGX Spark
**1 PFLOP | 128GB | 1.2 kg**

A portable AI workstation that sits trackside in the toolbox. Session replay, failure pattern analysis, multi-session trends — running locally, no connectivity needed. The motorsports engineer's AI assistant. If the in-car Jetson shows what edge AI can do in motion, the DGX Spark shows what it can do at rest — and it fits in a backpack.

## What We're Asking

We'd like NVIDIA to partner with us on the hardware for both tiers — Jetson AGX Thor for in-car and DGX Spark for pit-side — in exchange for a real-world showcase of grassroots automotive AI running on the NVIDIA stack:

- **Live demo site**: [kisti.analyticlabs.io](https://kisti.analyticlabs.io) — interactive telemetry, driver view, pit engineer dashboard
- **Real track content**: Heat, vibration, G-forces, engine noise — demos that can't be staged in a lab
- **E85 sustainability angle**: Edge AI in a renewable-fuel car — a narrative no one else has
- **Production software**: 805+ tests, edge memory, cloud sync — not a prototype
- **Sponsor precedent**: Link Engine Management already sponsors the electronics package

ALDC builds enterprise intelligence systems for real organizations — KiSTI is the same architecture applied at the edge under extreme conditions. More at [aldc.io](https://www.aldc.io).

I'd welcome 15 minutes to demo the system and discuss how this fits NVIDIA's developer community story. Happy to share architecture details, GPU profiling data, or track session footage.

Best regards,

**JK**
CEO, Analytic Labs (ALDC)
contact@analyticlabs.io
