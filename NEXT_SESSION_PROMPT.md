# KiSTI — Next Session Prompt (kisti-20: Visual HMI Redesign)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 864 tests passing
**Branch**: `kisti-headless`

## Section 1: What kisti-18/19 Did

### Streaming TTS — DONE
- Split multi-sentence responses, pipe PCM to single pacat process
- First sentence plays in ~1s, rest synthesizes during playback
- Perceived latency: 4s → 1s. Streaming pattern: "Streaming TTS: 1/5"
- `split_sentences()` in `voice/tts_engine.py`, `_speak_streamed()` in `voice/voice_manager.py`
- 19 new tests in `tests/test_tts_streaming.py`

### Frontier Cloud AI — WORKING
- `ANTHROPIC_API_KEY` sourced from `~/.env` in `scripts/kisti-session`
- Claude Haiku via WiFi, DuckDB cache for offline replay
- Full pipeline: STT 1.8s + LLM 2.4s + TTS 0.9s = ~5s total
- Comprehensive boxer engine knowledge in system prompt (flat-2 through flat-12)

### Wake Word — IMPROVED
- Punctuation stripping before matching (`re.sub(r'[^\w\s]', '', text)`)
- Added phonetic variants: keesti, keesty, keesey, keisty, casey
- Quiet/resume commands expanded with same variants
- Still using `hey_jarvis_v0.1` OWW model — custom ONNX model not yet trained

### Whisper-server — SYSTEMD
- Installed as systemd service, `enable --now`, auto-restart on failure
- medium.en + flash attention on GPU

### Sentence Truncation — REMOVED (Intelligent)
- max_s: Intelligent 99, Sport 2, Sport Sharp 1
- Token cap (150) is now the only constraint for Intelligent mode

## Section 2: Primary TODO for kisti-20

### Visual HMI Redesign — Multi-Display Synchronized Interface

This is a **major new feature**: redesign KiSTI's visual screens on the Kenwood Excelon (800x480 HDMI) to work as a synchronized companion to the Link MXG Strada 7" dash, with SI-Drive as the master mode selector.

**Context**: KiSTI currently has 6 display modes (KiSTI/STREET/TRACK/DIFF/VIDEO/SETTINGS) but they were designed independently. The next phase designs them as part of a coherent multi-display system where:
- **AiM MXG Strada 7"** = critical driver display (RPM, shift lights, alarms, core data)
- **Kenwood Excelon** (KiSTI/Jetson) = secondary context display (trends, maps, AI, diagnostics)
- **SI-Drive** = master mode selector controlling both displays simultaneously

**The three modes and their intent**:
- **INTELLIGENT** = calm / safety / diagnostic / street / bad weather. Useful, informative, not distracting. Rich context on Excelon (weather, trends, diagnostics, AI co-driver). MXG shows clean gauges.
- **SPORT** = fast road / mountain road / spirited driving. Performance-focused. Excelon shows boost/oil/brake trends, corner data. MXG shows essential performance data, progressive shift lights.
- **SPORT#** = track / attack / maximum repeatability. Minimal distraction, maximum signal. Excelon shows lap timing, delta, brake traces. MXG shows aggressive shift lights, alarms only.

### Hardware Integration Context

**Already integrated / available signals**:
- LinkECU G5 Neo 4 (central ECU, CAN master)
- LinkECU Razor PDM (power distribution)
- SI-Drive controller (reads as analog voltage on LinkECU)
- RPM, MAP/boost, TPS, IAT, coolant temp, oil pressure, speed, gear
- Flex fuel / ethanol %
- DCCD center diff (CAN 0x6A0-0x6A3 already decoded in `can/can_config.py`)
- AiM GPS09 Pro Open IMU/GPS (CAN 0x6A4-0x6A7 already decoded)

**Planned / not yet installed**:
- AP Racing front brakes (hardware ready)
- Brake pressure sensor (1x front initially, 2x later)
- AiM MXG Strada 7" dash (purchased, not yet installed)

**CAN bus layout** (defined in `can/can_config.py`):
- `0x6A0` DIFF @ 50Hz: DCCD command/dial %, surface state, flags, slip delta
- `0x6A1` CONTEXT @ 20Hz: Gear, speed, throttle %
- `0x6A2` WHEEL_SPEED @ 50Hz: FL/FR/RL/RR
- `0x6A3` DYNAMICS @ 50Hz: Steering angle, yaw rate, lateral G, brake pressure
- `0x6A4-0x6A7` GPS09 IMU: Position, speed, heading, 6-axis IMU

### Design Principles (CRITICAL)

1. **SI-Drive is master** — factory controller selects mode, everything follows
2. **MXG = critical driving display** — immediate data, alarms, shift lights
3. **Excelon = secondary/context display** — trends, AI, maps, config, history
4. **Minimal cognitive load** — information hierarchy > showing every signal
5. **SPORT and SPORT# must feel genuinely different** — not just colors
6. **INTELLIGENT must be useful** — calm diagnostic mode, not throwaway
7. **Fail safe always** — graceful degradation if any device offline
8. **Brake pressure is for driver development** — coaching value, not just display

### Implementation Approach

Use **plan mode** for this — it's a multi-file architectural redesign. The plan should cover:

1. **System architecture** — signal flow between Link, MXG, Jetson/Excelon
2. **Mode model** — full definition of I/S/S# as system-wide states
3. **CAN routing** — what goes where, synchronization, heartbeat
4. **Excelon page redesign** — new layouts for each mode (QPainter, 800x480)
5. **Alarm/warning philosophy** — tiered (Info/Caution/Critical), mode-aware
6. **SI-Drive synchronization** — reading the signal, debounce, mode enum, startup
7. **State machine** — mode transitions, alarm overrides, offline handling
8. **Phased implementation** — MVP first, then brake pressure, then advanced

### What NOT to do
- Do NOT redesign MXG pages — those are configured in AiM RaceStudio3 software
- Do NOT break existing voice pipeline — it stays as-is
- Do NOT remove existing test coverage — 864 tests must stay green
- Do NOT add Ollama/local LLM complexity — frontier is the AI path

## Section 3: Key Files

| File | What It Does |
|------|-------------|
| `ui/main_window.py` | QStackedWidget mode switching, display lifecycle |
| `ui/kisti_mode.py` | Home screen with voice waveform, status, AI responses |
| `ui/street_mode.py` | Map + corner temps + alerts |
| `ui/track_mode.py` | Thermal quadrant, track map, session timing |
| `ui/diff_mode.py` | DCCD torque silhouette, axle balance, sparklines |
| `ui/softkey_bar.py` | Mode selection buttons |
| `ui/settings_mode.py` | System info, sensor status |
| `ui/theme.py` | Color palette, fonts, automotive dark theme |
| `can/can_config.py` | CAN frame IDs, byte layouts, all constants |
| `can/kisti_can.py` | CAN decode/encode, listener thread, mock generator |
| `model/vehicle_state.py` | DiffState, DiffStateBridge, SurfaceState |
| `data/models.py` | VehicleState, CornerData, GPSData, SessionData |
| `voice/voice_manager.py` | Voice pipeline (don't touch for HMI work) |
| `modes/mode_manager.py` | SI-Drive mode state machine |

## Section 4: Jetson State

- **KiSTI**: Running fullscreen, Intelligent mode, Voice ON, Frontier ON, Zeus ON
- **Whisper**: medium.en on GPU (systemd), ~1s STT latency
- **Frontier**: Claude Haiku, WiFi "Heckler" connected
- **RAM**: 3.6G / 7.4G (49%) — healthy
- **GPU**: 3% idle, 59C
- **Disk**: 191G free (root), 427G free (/data)
- **Audio**: USB speaker @ 78%, USB mic @ 300% PA gain
- **Tests**: 864 passing

## Section 5: Architecture Notes

The Kenwood Excelon is driven by the Jetson via HDMI at 800x480. All UI is QPainter-based PySide6 — no web rendering, no external APIs. The display must be readable at a glance while driving.

The MXG Strada is a standalone dash that reads CAN directly from LinkECU. KiSTI doesn't control MXG pages — but KiSTI should be AWARE of what mode the MXG is showing (via the same SI-Drive CAN signal) so both displays are contextually aligned.

SI-Drive mode is read by LinkECU as an analog voltage. LinkECU broadcasts it on CAN. KiSTI's `can/kisti_can.py` already decodes CAN frames. The mode manager (`modes/mode_manager.py`) already has mode state — it needs to be wired to the CAN SI-Drive signal and made to drive display selection.

The existing softkey bar (STREET/TRACK/DIFF etc.) becomes secondary navigation within a mode. SI-Drive selects the primary mode, softkeys allow sub-page navigation within that mode's context.
