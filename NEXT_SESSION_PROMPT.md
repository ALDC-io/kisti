# KiSTI — Next Session Prompt (kisti-13)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (headless voice mode — no display)
**Test baseline**: 687 tests passing
**Team session**: `kisti-speaks` (session_id: `28ee8c4a-5260-4a09-8224-b57c7dd882fb`)
**Deploy path**: `/home/aldc/repos/kisti/` on Jetson
**Launcher**: `~/k` (headless, auto-detects mic)

## Section 1: What kisti-12 Did

### Headless Voice Mode (THE BIG WIN)
- Added `--headless` flag — QCoreApplication, no MainWindow, no X11, no display
- **Eliminated all UI freezes** that plagued the entire session
- RAM: 4.2 GB → 1.9 GB used (Ollama killed + no Qt GUI)
- Boot greeting speaks via voice_mgr.speak() directly
- `~/k` script updated for headless, auto-detects USB mic
- GNOME autostart still exists at `~/.config/autostart/kisti.desktop` (fullscreen mode)
- Full UI preserved on `main` branch — `--headless` is opt-in

### Freeze Investigation Trail (for context)
1. Waveform viz wasn't animating during voice responses (response_ready disabled for mic race)
2. Added cross-thread Qt signal (waveform_envelope) → froze compositorless X11
3. Replaced with shared-var polling (40Hz) → still froze
4. Disabled polling → still froze
5. Killed Ollama (2.5 GB GPU memory freed) → still froze
6. **Went headless → freezes stopped.** Root cause: Qt/X11 compositorless rendering on Jetson

### Waveform Viz Code (preserved but disabled)
- `voice_manager._waveform_data` shared variable (set by voice thread, polled by UI)
- `kisti_mode._voice_poll_tick` (40Hz polling) — disabled in current code
- `kisti_mode.on_voice_envelope` removed, `on_voice_state_changed` removed
- The LED waveform via CAN (`led_frame_ready` → Strada shift lights) still works in `_do_speak()`
- **Future**: waveform goes on Link ECU Strada display, not Kenwood

### Mock Data Disabled
- `can_config.py`: `MOCK_ENABLED = False`
- `config.py`: `RADAR_MOCK_ENABLED = False`
- No fake sensor data until real hardware connected

### No-ECU Guard
- ECU keyword queries ("boost", "rpm", "tire", "brake", "speed", etc.) return "No ECU connected. Link G five not installed yet."
- Component temp queries (cpu, gpu, turbo, intercooler) no longer return ambient weather
- Expanded `_COMPONENT_QUALIFIERS` and `_ECU_KEYWORDS` in `voice_manager.py:1143-1170`

### Ollama Disabled
- `llm_engine.py:547-555`: Ollama call commented out — goes straight to fallback
- Ollama systemd service file moved to `.disabled`: `/etc/systemd/system/ollama.service.disabled`
- Frees 2.5 GB RAM on Jetson

### Branches
- `main` — current working state (headless + all fixes)
- `kisti-12-waveform-fix` — waveform signal/polling experiments
- `kisti-headless` — headless development branch (merged to main)

## Section 2: Prioritized TODO for kisti-13

### 1. Train Custom "Hey KiSTI" Wake Word (HIGH — the reason for this session)
- [ ] Use OpenWakeWord training pipeline (Colab notebook)
- [ ] Generate synthetic training data with Piper TTS (multiple voices/speeds)
- [ ] Record ~50 real "Hey KiSTI" samples for validation
- [ ] Train .onnx model on Colab GPU
- [ ] Deploy to Jetson: replace `hey_jarvis_v0.1` in mic_capture.py
- [ ] Env var `KISTI_WAKE_MODEL` already supports custom model path
- [ ] Validate false positive rate with car noise / background conversation
- OWW docs: https://github.com/dscripka/openWakeWord
- OWW training: https://github.com/dscripka/openWakeWord#training-new-models

### 2. Fix ECU Keyword Guard — Too Aggressive (HIGH)
- "tell me about the brakes" → "No ECU connected" (wrong — should be persona)
- "what's my brake pressure" → "No ECU connected" (correct — live data query)
- **Fix**: split `_ECU_KEYWORDS` into two lists: live-data keywords (pressure, temp, reading) vs component names (brake, tire, suspension)
- Only block live-data queries without CAN. Let "tell me about X" fall through to persona.
- Same issue with: tire, suspension, boost (bare word), speed, brake, braking
- File: `voice_manager.py:1152-1175`

### 3. TTS Speed — Response Latency (HIGH)
- Pipeline: STT ~250ms (fast), LLM ~10ms (instant persona), **TTS 1.5-3.5s (bottleneck)**
- Piper model: `en_US-danny-low.onnx` (already low quality = fast)
- **Fix**: TTS cache for frequent persona responses — pre-synthesize and cache WAV files
- First hit synthesizes + caches, repeat plays cached WAV instantly
- ~86 persona responses = ~86 cached WAVs, trivial disk space

### 4. Add Missing Persona Responses (MEDIUM)
- "pistons" — unanswered, needs persona response (Manley forged, bore/stroke)
- Check edge DuckDB: `SELECT * FROM memories WHERE tags LIKE '%unanswered%'` for more gaps
- Coolant temp persona: `["coolant temp", "coolant temperature", "water temp"]`

### 5. Soak Test Headless Mode (MEDIUM)
- [ ] Leave KiSTI headless running for extended period
- [ ] Verify no memory leaks, no freezes, no mic drift

### 6. Phase 10: Hardware Integration (BLOCKED on hardware)
- [ ] GPS09 Pro CAN wiring (JK)
- [ ] Real GPS data validation
- [ ] IMU-assisted track learning

## Section 3: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `main.py` | Bootstrap + headless mode | 65 (--headless flag), 110-118 (display skip), 127-136 (QCoreApp), 569-575 (window conditional), 580 (_speak helper), 710-715 (headless boot greeting) |
| `voice/voice_manager.py` | Voice pipeline | 256 (waveform_data signal removed), 276 (_waveform_data shared var), 879-880 (set waveform_data), 907 (clear waveform_data), 1143-1170 (ECU keyword guard) |
| `voice/llm_engine.py` | LLM engine | 547-555 (Ollama DISABLED) |
| `voice/mic_capture.py` | Mic + wake word | KISTI_WAKE_MODEL env var for custom model |
| `can/can_config.py` | CAN config | 428 (MOCK_ENABLED = False) |
| `config.py` | General config | 33 (RADAR_MOCK_ENABLED = False) |
| `ui/kisti_mode.py` | KITT waveform (unused in headless) | 595-601 (poll timer disabled) |

## Section 4: Test Baseline

```
687 passed in 36.28s (workstation, 2026-03-30 19:20 PDT)
Jetson: headless mode, no display tests needed
```

## Section 5: Jetson System State

- **Ollama**: DISABLED (service file renamed, not running)
- **whisper-server**: Running at port 8081 (base.en model, 4 threads, ~523 MB)
- **RAM**: 1.9 GB used / 5.3 GB available (headless + no Ollama)
- **KiSTI launcher**: `~/k` (headless, auto-detects USB mic)
- **GNOME autostart**: still at `~/.config/autostart/kisti.desktop` (fullscreen mode, not used)
- **WiFi**: Connected (JK iPhone hotspot or Heckler)
