# NEXT SESSION PROMPT — KiSTI kisti-30

**Branch**: `kisti-headless`  
**Working dir**: `/home/aldc/repos/kisti`  
**Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)  
**Run KiSTI**: `~/k`  
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`  
**Test baseline**: 1025 passed, 11 skipped (1036 collected)

---

## What Was Done (kisti-29)

### --demo flag
- `python3 main.py --demo` starts mock CAN with SI-Drive cycling I→S→S# every 15s
- Default (no flag) stays sensor-only with Intelligent locked
- Files: `main.py` (argparse), `can/kisti_can.py`

### Warm object detection
- Pure numpy in `sensors/flir_lepton_reader.py`
- EMA baseline (median, alpha=0.1) → threshold (+10°C) → flood-fill blobs (>20px) → 2-frame debounce → LEFT/CENTER/RIGHT → voice alert via speak_alert("warning")
- No scipy dependency. ~80 lines of detection + labeling code

### ABS/VDC indicators + wheel speed spread on Intelligent screen
- Row 2 in status strip (y=406) of `ui/intelligent_screen.py`
- Left: ABS indicator — red dot + bold "ABS" when active, dim when off
- Center: Wheel speed spread — `max(|FL-FR|, |RL-RR|)` color-coded (cyan <2, yellow 2-5, red >5 km/h)
- Right: VDC/TC indicator — yellow dot + "VDC" when active, dim when off
- Uses existing `_wheel_delta_color()` thresholds

### System overview saved
- **Zeus ZMID**: `9fba1ea7-7d80-4a49-a38d-79edfffabfde` (Management tenant)
- **Nextcloud**: `ALDC Management/CCE_projects/Reports/kisti-system-overview-2026-04-03.md`
- **Share link**: https://cloud.aldc.io/s/pwJDXix7gSgzFJ9 (pw: `KiSTI2026!`)
- Covers: full Tier 1 (working sensors/analysis/alerts), voice pipeline status, Tier 2 gap analysis (offline ChatGPT-quality voice)

---

## TODO — Priority Order

### 1. Tier 2 voice architecture — offline ChatGPT-quality voice
JK's vision: full offline conversational voice comparable to ChatGPT Voice. Read the system overview (ZMID `9fba1ea7-7d80-4a49-a38d-79edfffabfde`) for the complete gap analysis. Core principle: **sensors always on, always tracking, always logging** — voice is an output layer on top.

**Step 1: VRAM profiling** — SSH to Jetson, run KiSTI with full sensors, capture `nvidia-smi` to establish actual GPU memory budget for LLM + TTS.

**Step 2: LLM selection** — Benchmark on Orin NX:
- Llama 3.1 8B Q4_K_M (~4.5GB + 1-2GB KV cache)
- Mistral 7B Q4_K_M
- Phi-3 Medium
- Measure: tokens/sec, first-token latency, memory footprint

**Step 3: TTS upgrade** — Evaluate:
- Kokoro (lightweight, good quality)
- XTTS-v2 (voice cloning, heavier)
- Must support streaming (first-chunk latency matters most)

**Step 4: Architecture** —
- Context injection: vehicle state → LLM system prompt each turn
- Conversation memory: sliding window in DuckDB edge memory
- Streaming pipeline: STT → LLM (streaming) → TTS (streaming, speak while generating)
- Target: sub-1.5s end-to-end, ideally sub-1s

### 2. GPS09 Pro Open hardware install
- Software fully integrated (CAN 0x6A4-0x6A7, decode/encode, mock, tests)
- Hardware pending physical install. After install: verify live IMU 6-axis @ 50Hz

### 3. Custom wake word ("Hey KiSTI")
- Current: `hey_jarvis_v0.1` (OWW fallback)
- Need: Colab openWakeWord training with recorded samples

### 4. Tune session prep (Aaron @ Boost Barn)
- KiSTI must be in-car with working mic
- Known bug: self-triggering loop from 3x mic gain — may need voice disabled during tune

### 5. CAN-to-Strada text alerts
- When Korlan cable arrives: send coaching text as CAN to Link ECU → Strada 7" display

### 6. Remove diagnostic logging (after road test validates readings)
- Road temp log every 3s in `model/vehicle_state.py`
- Frame format log in `sensors/flir_lepton_reader.py`

---

## Key Files
| File | Role |
|------|------|
| `ui/intelligent_screen.py` | Status strip: surface/slip/DCCD + ABS/spread/VDC + coaching |
| `sensors/flir_lepton_reader.py` | Y16 radiometric, warm object detection |
| `can/kisti_can.py` | CAN decode, mock CAN, --demo SI-Drive cycling |
| `voice/frontier_engine.py` | Claude Haiku via WiFi, 4-tier fallback |
| `model/vehicle_state.py` | DiffState dataclass, DiffStateBridge, surface state inference |
| `data/build_record.py` | BASELINES (single source of truth for alert thresholds) |
| `main.py` | Entry point, --demo flag, sensor wiring |

## Don't Repeat
- `avg > 0` guard in surface state blocks sub-zero detection → use `!= 0.0` check
- Two KiSTI processes fighting for `/dev/video0` → kill headless before starting fullscreen
- CLAHE at 9 Hz overwhelms Jetson CPU → throttle to 3 Hz first
- OpenCV may return Y16 as flattened uint8 `(120,320,1)` → `.view(uint16).reshape(120,160)`
- Self-triggering loop: 3x mic gain amplifies speaker output → echo guard 0.4s not always enough
- One GPU job at a time on Jetson — check `nvidia-smi` before launching models
- Batch VRAM at 500K sims max, never full N×months arrays

## Architecture Notes
- **Sensors always on** — non-negotiable. CAN 50Hz, FLIR 3Hz, Yocto continuous. Analysis runs regardless of voice state
- **Voice = output layer** — alerts, coaching, conversation ride on top of sensor pipeline
- **Tier 2 goal** — offline voice quality matching ChatGPT Voice. This is the next major milestone
- **VRAM budget** — 16GB shared (Orin NX). ~2-3GB sensors, ~8-9GB available for LLM+TTS. 8B Q4 model should fit (~6GB) but needs profiling
- **Frontier bridge** — Claude Haiku over WiFi fills the gap until local LLM quality catches up
