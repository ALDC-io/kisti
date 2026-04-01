# KiSTI - Progress

## Session: 2026-04-01 (kisti-19 — Frontier Live + Wake Word Fixes)

### Completed
- **Frontier cloud AI working** — Synced valid ANTHROPIC_API_KEY from workstation, sourced `~/.env` in kisti-session. Full pipeline: wake → STT → Claude Haiku → streaming TTS (5.4s total).
- **Wake word punctuation fix** — Whisper adds commas/periods that broke exact matching ("Hey, Keisty" ≠ "hey keisty"). Now strips punctuation with `re.sub(r'[^\w\s]', '', text)` before all wake/quiet/resume matching.
- **Phonetic variants expanded** — Added keisty, keesty, keesey, keesi, casey + "hey" combos. Quiet/resume commands also expanded.
- **Fuzzy matching** — Added "keesti" as third target alongside "jarvis"/"kisti" for edit-distance matching.

### Files Changed
- `scripts/kisti-session` — Added `set -a && . ~/.env && set +a` for API key sourcing
- `voice/voice_manager.py` — Punctuation stripping before wake/quiet/resume matching, expanded WAKE_WORDS, QUIET_COMMANDS, RESUME_COMMANDS

### Key Decisions
- Sync `~/.env` from workstation via scp (dcli has no ARM64 build for Jetson)
- Text-based wake word matching is inherently fragile — custom ONNX model is the real fix

### Don't Repeat
- Whisper medium.en adds punctuation — ALWAYS strip before string matching
- dcli has no Linux ARM64 binary — don't try npm install or binary copy from x86_64
- Jetson `~/.env` can go stale — need periodic sync from workstation or Dashlane

---

## Session: 2026-03-31 (kisti-18 — Streaming TTS + Whisper Service)

### Completed
- **Streaming TTS architecture** — Split multi-sentence responses, pipe PCM to single pacat process. First sentence plays immediately (~1s), remaining sentences synthesize while first plays. Perceived latency: 4s → 1s.
- **Whisper-server systemd service** — Installed on Jetson with medium.en + flash attention. Automated startup via `systemctl enable --now`. Verified running post-install.
- **Removed sentence truncation (Intelligent mode)** — Changed max_s: 4 → 99 (effectively unlimited). Token cap (150 tokens) is now the only response length constraint. Kept for Sport (2) and Sport Sharp (1) modes.
- **Test coverage** — 19 new tests in test_tts_streaming.py (split_sentences validation, streaming path selection, latency verification). All 864 tests passing (845 baseline + 19 new).
- **LED frame-skipping** — When streaming TTS starts mid-playback, skip already-elapsed frames to keep waveform display synchronized with audio playback.

### Files Changed
- `voice/tts_engine.py` — Added `split_sentences(text: str) -> list[str]` regex-based sentence splitter
- `voice/voice_manager.py` — Refactored `_do_speak()` into router + `_speak_single()` + `_speak_streamed()`. Streaming opens pacat, pipes first PCM, iterates remaining sentences while first plays. Handles pacat fallback, barge-in, mic pause/resume, LED frame-skipping.
- `voice/frontier_engine.py` — max_s change: Intelligent 4→99, Sport 2, Sport Sharp 1
- `scripts/install_whisper_service.sh` — New idempotent service install script
- `tests/test_tts_streaming.py` — New test file: 12 split_sentences tests + 7 streaming integration tests

### Key Decisions
- Streaming TTS decouples response length from perceived latency. Token cap is now primary constraint (not sentence count).
- Single pacat process for all sentences avoids process spawn overhead and audio dropouts between sentences.
- Sentence truncation safe to remove for Intelligent mode because streaming makes TTS latency ~1s regardless of response length.

### Don't Repeat
- Do NOT truncate sentences for Intelligent mode anymore — streaming makes longer responses free.
- word-wrap commands in terminal = silent syntax breakage. Always write long commands to script file, commit/push, give one-line run command.

### Learnings
- Git rebase conflicts on Jetson auto-commit cron: detached HEAD after `git reset --hard`, stale rebase-merge state. Fix: `git fetch -q && git reset --hard origin/kisti-headless && git checkout kisti-headless`, then `git rebase --abort` if needed.

---

## Session: 2026-03-31 (kisti-17 — Whisper Upgrade + Frontier-First Architecture)

### Completed
- **Whisper medium.en on GPU** — CUDA already compiled (GGML_CUDA=ON). small.en rejected (mangled proper nouns). medium.en accurate.
- **Frontier-first architecture** — safety-fast-path → frontier → persona-fallback → hard-fallback
- **Timeout-based ack** — 300ms timer, no ack on cache hits
- **VAD** — SPEECH_END_FRAMES 14→19 (608ms)
- **TTS fix** — "911" → "nine eleven", "flat-four boxer" in build spec
- **Response tuning** — 150 tokens, 4-sentence cap, "cover BOTH sides" prompt, no preamble filler
- **Log width** — LLM response log widened to 200 chars for debugging
- **Test count** — 845 (+20 new)

### Files Changed
- `voice/llm_engine.py` — frontier-first routing, _match_safety_fast_path(), boxer engine context
- `voice/frontier_engine.py` — token caps, sentence truncation, system prompt tuning
- `voice/voice_manager.py` — timeout ack, log width
- `voice/stt_engine.py` — medium.en, proper noun prompt, 15s timeout
- `voice/tts_engine.py` — "911" substitution
- `voice/mic_capture.py` — VAD threshold
- `scripts/jetson/whisper-server.service` — medium.en + flash attention
- `tests/` — 20 new tests across 4 files

### Key Decisions
- medium.en over small.en: proper noun accuracy > 600ms STT savings
- TTS is 75% of latency — streaming TTS is #1 priority for kisti-18
- 150 max_tokens Intelligent mode: balance between depth and 4-5s TTS

### Don't Repeat
- Do NOT use small.en — mangles Porsche→potions, Subaru→brew in real use
- Do NOT remove sentence truncation without streaming TTS — causes 12s+ total latency
- Always check CMakeCache.txt before rebuilding CUDA deps (whisper.cpp already had CUDA)

---

## Session: 2026-03-31 (kisti-16 — Persona Scoring + Frontier History)

### Files Changed
- `voice/llm_engine.py` — unified self-ref guard, system prompt rewrite
- `voice/frontier_engine.py` — conversation history (last 3 turns)
- `voice/voice_manager.py` — wire dialogue.last_turns to LLM query
- `voice/mic_capture.py` — VAD SPEECH_END_FRAMES 8→14 (448ms)
- `tests/test_voice.py` — 18 tests updated for frontier routing
- `tests/test_persona_factory.py` — 6 tests updated

### Key Decisions
- Persona self-ref guard: score>=10 required for non-safety/non-joke/no-self-ref queries
- Frontier conversation history: last 3 turns as multi-turn messages, cache skipped with history
- System prompt: conversational tone, no spec volunteering in general knowledge answers
- VAD: 256ms→448ms silence threshold reduces sentence splitting

### Done This Session
- [x] Persona scoring fix — unified self-ref guard replaces GK+fragment filters
- [x] Frontier conversation history — follow-up questions now work
- [x] System prompt rewrite — conversational, not spec-heavy
- [x] VAD silence threshold bumped 256ms→448ms
- [x] 825 tests passing (824 baseline +1 new self-ref test)
- [x] Verified live on Jetson: "Porsche vs Subaru" → frontier, no spec dump

### Next Session (kisti-17)
- [ ] Upgrade Whisper to medium.en (1.5GB) — small.en downloaded, medium.en needs download
- [ ] Check whisper.cpp CUDA support — rebuild with -DGGML_CUDA=ON for GPU inference
- [ ] Frontier-first architecture (plan mode) — invert persona→frontier to frontier→persona
- [ ] Investigate stray persona match: "Yeah, that's it." scored >=10 unexpectedly
- [ ] VAD further tuning — still splits on longer pauses

### Don't Repeat
- Don't use two separate filters (GK signal + fragment) for persona routing — gap exists for medium-length fragments without GK prefixes
- Don't leave SPEECH_END_FRAMES at 8 (256ms) — too aggressive, splits natural speech pauses
- Whisper base.en insufficient for proper nouns in automotive context

---

## Session: 2026-03-31 (CCE Auto-Learn System Debug)

### Completed
- **Fixed CCE auto-learn capture system** — Three critical bugs preventing session learnings from reaching leaderboard
  1. Marker file uniqueness: day-only format → per-session timestamp (prevents same-day collision)
  2. Source field routing: `cce-session-auto-learn` → `cce_success_log` (leaderboard counter recognition)
  3. Hook execution order: moved auto-learn before session file cleanup (file access + parameter passing)
- **Migrated historical learnings** — Updated 41 misrouted memories from wrong source to `cce_success_log`
- **Verified leaderboard** — Total increased 2063 → 2104, JK Confidential confirmed clean

### Learnings
- **Failed Approaches** (none this session — system redesign went well)
- **Successes**
  - Multi-file hook coordination: stop hook, session-end hook, auto-learn script must share SESSION_ID
  - Marker file pattern matters: unique per-session prevents collision; explicit parameter passing bypasses cache reads
  - Source field critical: must match `/api/learnings/count` filter to appear on leaderboard
  - ZEUS_ALDC_API_KEY routing: confirms all team learnings to Management tenant, never falls back to personal key
- **Decisions**
  - Parameter-driven approach: pass SESSION_ID as $1 to functions instead of relying on cache files
  - Unique marker names: per-minute resolution (not per-day) for same-day multi-session support
  - Hook ordering: auto-learn must run before cleanup phase to ensure file availability

### Architecture Notes
- Auto-learn system is core to CCE leaderboard — single source of truth for session work capture
- Hook bundle (v114) packages these fixes; always publish after editing hooks
- Session lifecycle: SessionStart → hook sync → work → SessionEnd/Stop → auto-learn → cleanup
- Marker pattern: `auto-learn-{SESSION_ID}` acts as idempotency guard; must be unique

---

## Session: 2026-02-10

### Completed
- Project structure created (~20 Python files)
- Data layer: models.py (8 dataclasses), mock_generator.py (10Hz/1Hz)
- UI theme: dark automotive palette (2014 STI inspired), QSS stylesheet
- Status bar: mode, clock, GPS/LOG/NET indicators, Nvidia + Link ECU logos
- Softkey bar: STREET/TRACK/AUDIO/LOG/SETTINGS (all modes switchable)
- STREET mode: mock map, corner grid, oil gauge, sensor status, alerts, pit summary modal
- TRACK mode: thermal quadrant + sparklines, track map, oil gauge + brake strip, sensor status, findings list, session widget
- SETTINGS mode: corporate branding (KiSTI + Nvidia + Link ECU), system info, sensor connection status
- Splash screen: 3-second boot screen with logos and branding
- Main window: QStackedWidget mode switching, F11 fullscreen, CLI args
- Branding utility: SVG/PNG logo loader with caching (ui/branding.py)
- Oil pressure: PSI + temp + sparkline with color-coded thresholds
- Front sensor suite: Teledyne IR, LiDAR, RGB, Weather camera status display
- Corporate logos: Link ECU (SVG), Nvidia (PNG) in status bar, settings, splash
- README with install/run/display instructions

### Architecture
- `data/models.py`: VehicleState, CornerData, GPSData, OilPressureData, FrontSensorSuite, CameraStatus, SessionData, SystemState, KistiFinding
- `data/mock_generator.py`: 10Hz temps/oil/sensors + 1Hz GPS/session/findings
- `ui/branding.py`: Logo loader (Nvidia PNG + Link ECU SVG)
- `ui/splash_screen.py`: 3s boot screen with corporate logos
- `ui/settings_mode.py`: System info + sensor status + branding
- `ui/widgets/oil_gauge.py`: Oil pressure gauge with sparkline
- `ui/widgets/sensor_status.py`: Front camera array status

### Session 2 Updates (2026-02-10, evening)
- GT7-style tire indicators: Redesigned CornerCell from segmented bar graphs to rounded tire-shaped indicators with internal fill bars
- GT7 color palette: Blue (cold) → Green (optimal) → Yellow (warm) → Red (overheating) temperature transitions
- Tire wear system: Added tire_wear_pct to CornerData model, wear simulation in mock generator (degrades faster when hot)
- Brake temp strip: Thin vertical bar beside each tire shape
- Visual polish: Gradient fills, tread line overlays, glossy highlights, wear notch marks at 25/50/75%
- Theme additions: TIRE_BLUE, TIRE_BLUE_DARK, TIRE_GREEN, TIRE_YELLOW, TIRE_RED

## Session: 2026-02-16

### DIFF Mode — Center Differential Telemetry (MapDCCD 2014 STI)

Full DIFF tab build from detailed prompt. 7 files added/modified in one session.

### New Files
- `model/vehicle_state.py`: `DiffState` dataclass (13 fields), `DiffStateBridge` (thread-safe QObject with `threading.Lock` + Qt `Signal`), `SurfaceState` IntEnum (DRY/WET/COLD/LOW_GRIP with label + color properties)
- `can/can_config.py`: CAN bus constants — frame IDs (`0x6A0` DIFF @ 50Hz, `0x6A1` CONTEXT @ 20Hz), all byte offsets/scales/bitmasks, stale timeout (500ms), UI refresh (20Hz), mock rates, socketcan config (`can0`, 500kbps)
- `can/kisti_can.py`: Pure decode functions (`decode_diff_frame`, `decode_context_frame`), encode helpers for testing, `CanListenerThread` (daemon thread, reads socketcan, updates bridge), `MockCanGenerator` (QTimer-based canyon driving sim), `create_can_source()` factory (auto-detects real CAN vs mock fallback)
- `ui/diff_mode.py`: Full QPainter DIFF page — `_HeaderBar` (surface state word + CAN status dot), `_BigNumericPanel` (large LOCK% + smaller DIAL%), `_ContextPanel` (gear/speed/throttle/slip with color-coded slip magnitude), `_StatusPills` (BRAKE/H-BRAKE/ABS/VDC active-highlight pills), `DiffModeWidget` (20Hz refresh timer, MARK button → JSONL to `~/kisti/logs/`, 0.6s flash feedback)
- `ui/widgets/diff_sparkline.py`: `DiffSparkline` — ring-buffer QPainter widget (200 samples @ 20Hz = 10s), filled area under curve with alpha, optional zero-line for signed signals, auto-expanding Y-axis
- `tests/test_can_decode.py`: 18 pytest cases across 5 classes — DIFF decode (normal/N-A/negative slip/all flags/zero+full lock/surface fallback/short frame), CONTEXT decode (normal/neutral/high speed/short frame), round-trip encode→decode, DiffState staleness detection, SurfaceState enum validation

### Modified Files
- `ui/main_window.py`: DIFF as stack index 3, `DiffStateBridge` creation, `create_can_source()` wired into splash/close lifecycle, CAN listener start/stop
- `ui/softkey_bar.py`: Added DIFF between TRACK and VIDEO in `_BUTTONS` list

### Architecture Decisions
- **Separate data pipeline**: DIFF tab reads from CAN bus (or mock) via `DiffStateBridge`, independent of existing `MockDataGenerator` — no coupling between telemetry sources
- **Thread-safe bridge pattern**: CAN listener thread writes via lock-protected `update_diff()`/`update_context()`; UI reads via `snapshot()` copy at 20Hz QTimer — no per-frame UI updates
- **Graceful degradation**: Auto-detects `python-can` + `can0` availability; falls back to `MockCanGenerator` with simulated canyon driving (random walk + sinusoidal DCCD, correlated throttle/speed/gear, occasional slip spikes)
- **Editable CAN constants**: All arbitration IDs, byte offsets, scaling factors, flag bitmasks in single `can/can_config.py` — ready for real Link G4X CAN config

### Prompt
The DIFF tab was built from a detailed Claude Code prompt specifying:
- MapDCCD center diff telemetry for 2014 STI
- CAN message layout (0x6A0 DIFF, 0x6A1 CONTEXT) with byte-level spec
- QPainter sparklines (10s rolling, 200 samples @ 20Hz)
- MARK segment marker → JSONL logging
- python-can socketcan listener with mock fallback
- WVGA 800x480 layout optimized for in-motion readability

## Session: 2026-02-16 (continued)

### DIFF Tab Visual Redesign — Driver-Intuitive Layout

Replaced the text-heavy engineer view (big % numbers, text rows, text pills) with a visual layout readable at speed. Inspired by MoTeC, GT-R ATTESA MFD, and McLaren F1 telemetry UX.

### Changes

**`ui/diff_mode.py` — Full internal rewrite**
- **Removed**: `_HeaderBar`, `_BigNumericPanel`, `_ContextPanel`, `_StatusPills`
- **Added `_SlimStatusBar`** (24px): Surface dot+word, CAN status dot, gear (18pt bold), speed (13pt)
- **Added `_TorqueSilhouette`**: Top-down STI body (QPainterPath from `sti_heatmap_widget.py`), per-wheel torque glow (CYAN based on throttle × lock fraction), per-wheel speed data with individual intensity, L-R differential visualization on rear axle for LSD lock state, slip warning: >2 km/h = YELLOW wheels, >5 = RED + 4Hz pulse
- **Added `_AxleBalanceBar`** (x2, stacked): Horizontal L-R balance bars showing signed wheel speed delta. Rear axle: GREEN (matched/locked) → YELLOW → RED (slipping). Front axle: CYAN informational. Bar deflects left/right to show which wheel is faster. White indicator dot at tip. Center tick = zero reference
- **Added `_SplitBar`**: Vertical bar (30px wide) showing F:R torque distribution via DCCD lock. GREEN (open, 41:59) → CYAN → BLUE (locked, 50:50). Exaggerated scale: 41-50% real range remapped to 15-85% visual range
- **Added `_EventDots`**: 4 colored circles for BRK (RED), HB (YELLOW), ABS (CYAN), VDC (HIGHLIGHT) — replaces text pills
- **Added `_BottomStrip`**: 3 compact sparklines (LOCK/SLIP/THR) + event dots + MARK button

**`ui/widgets/diff_sparkline.py` — Minor**
- Added `compact: bool = False` param: label_w=36 (was 48), minHeight=22 (was 28), 8pt font (was 9)

**`can/can_config.py` — New CAN frames**
- `0x6A2` WHEEL_SPEED (50Hz): FL/FR/RL/RR uint16 BE × 100 = km/h
- `0x6A3` DYNAMICS (50Hz): steering_angle×10 (int16), yaw_rate×100 (int16), lateral_g×1000 (int16), brake_pressure×10 (uint16)
- Added MOCK_WHEEL_HZ=50, MOCK_DYNAMICS_HZ=50

**`model/vehicle_state.py` — Extended DiffState**
- Added: wheel_speed_fl/fr/rl/rr, steering_angle, yaw_rate, lateral_g, brake_pressure
- Added: wheel_frame_ts, dynamics_frame_ts staleness tracking
- Added: `is_wheel_stale()`, `is_dynamics_stale()` methods
- Added: `update_wheel_speeds()`, `update_dynamics()` bridge methods

**`can/kisti_can.py` — New decoders + mock data**
- `decode_wheel_speed_frame(data)`: 4× uint16 BE → km/h
- `decode_dynamics_frame(data)`: steering, yaw, lat-G, brake pressure
- CAN listener handles 0x6A2 and 0x6A3
- Mock generator: `_ws_tick()` simulates per-wheel speeds with steering-based L-R differential + DCCD lock effect on rear LSD. `_dyn_tick()` simulates sinusoidal canyon steering, yaw, lateral G, brake pressure

### Design Decisions
1. **Car silhouette with per-wheel glow** replaces big numeric — driver sees WHERE power goes spatially
2. **Horizontal L-R balance bars** (not arc gauges) — show both magnitude AND direction of wheel speed differential, like a lateral G meter
3. **Rear bar**: GREEN center (locked) → RED extremes (slipping) — driver wants LSD locked
4. **Front bar**: CYAN informational — open diff shows understeer/cornering behavior
5. **Vertical split bar** for center diff (F:R) — no duplication with L-R bars
6. **Color = information**: CYAN=torque flow, GREEN=matched/locked, YELLOW=mild slip, RED=hard slip
7. **STI torque split**: 41F:59R (open) → 50:50 (locked) — visualized in split bar with exaggerated scale

### Research: 2014 STI CAN Bus Sensors
- **CAN ID 0xD4 (212)**: Individual wheel speeds FL/FR/RL/RR from ABS sensors (Hall effect + reluctor ring), formula X × 0.05625 = km/h
- **Link G4X WRX11X** can receive: brake pressure, all 4 wheel speeds, handbrake, traction mode, diff mode, steering wheel position
- **VDC module**: Steering angle, yaw rate, lateral G — all available on OEM CAN bus
- Link ECU re-encodes onto KiSTI publish bus (0x6A2, 0x6A3)

## Session: 2026-02-17

### Mission Raceway Session Data — Full Link ECU Telemetry

Added complete Mission Raceway track day session with 6 laps (1 warm-up, 3 hot, 2 cool-down) and full Link G4X ECU telemetry across 19 sensor channels.

### New Files
- `src/lib/missionRacewayCircuit.ts`: 24-point CCW circuit path (9 turns, 2.25 km), turn labels T1-T9, `getCircuitPosition()` interpolation
- `src/lib/missionRacewaySession.ts`: Complete 6-lap session dataset with per-lap ECU data (brake temps, tire temps, EGT, boost, oil, AFR, sector times, G-forces)

### Modified Files
- `src/lib/driverTelemetry.ts`: Swapped to Mission Raceway circuit, GPS to 49.1325°N/-122.3025°W, elevation 30m, lap duration 82s
- `src/lib/mockTelemetry.ts`: Session-phase-aware baselines (warm-up 0-105s, hot 105-350s, cool-down 350s+)
- `src/lib/zeusResponses.ts`: 7 Mission Raceway Q&As + standalone keywords for lap/session queries + starter chip
- `src/lib/kistiGraph.ts`: Brake FR description references Mission Raceway data
- `src/components/driver/TrackMode.tsx`: Updated circuit import

### Learnings
- **Keyword matcher scoring**: Standalone queries ("how many laps") must win against competing entries ("how many" → sensor count = 8 pts). Always add short standalone keywords, not just compound phrases requiring topic prefix
- **Module swap grep**: When replacing a shared module import, always grep `src/` for ALL importers — `driverTelemetry.ts` was updated but `TrackMode.tsx` was missed until build failed

### Next Steps
- Finalize Link G4X CAN publish bus IDs (currently placeholder 0x6A0-0x6A3)
- Real CAN testing on bench with Link ECU + MapDCCD
- Vehicle dynamics visualization (steering angle, yaw rate, lat-G overlay)
- Teledyne IR camera feed integration
- LiDAR point cloud visualization
- Voice integration (KiSTI spoken insights)
- LOG mode page (session recording/playback)
- Touch optimization for Excelon capacitive screen
- Performance profiling on Jetson GPU

## Session: 2026-03-28 (Part 2) — Full Voice Pipeline + HDMI Audio Fix

### Completed
- **HDMI audio architecture**: Discovered Jetson HDA resets pin-ctl to 0x00 when PA exits. Switched entire audio stack from direct ALSA (aplay) to PulseAudio (paplay/parecord). Set HDMI as default PA sink explicitly (analog-stereo has no output on Jetson)
- **Mic pipeline**: Switched arecord→parecord, auto-resolve ALSA device names to PA source names. Gain: ALSA 60% + PA source 150%
- **STT working**: Whisper tiny.en CUDA with initial_prompt bias, expanded hallucination filter (okay, see you tomorrow, prompt echoes)
- **Conversation window**: 8s follow-up window resets after TTS playback (not wake word)
- **Wake word variants**: Added misheard variants (keys to, keeps to, christy, etc.)
- **1.5s echo guard**: Post-playback mic delay to prevent KiSTI hearing its own voice
- **100+ quotes**: Dukes of Hazzard, Seinfeld, Friends, Peaky Blinders, Sopranos, Breaking Bad, Teen Titans, car movies (F&F, Smokey, Gone in 60s, Vanishing Point, Rush, Days of Thunder, Ford v Ferrari, Baby Driver, Bullitt)
- **Star Trek technobabble**: 22 quotes mapped to real car systems (warp core=engine, nacelles=wheels, dilithium=fuel)
- **Brain rot Trek**: Gen-alpha slang + Star Trek tech (bussin, no cap, rizz applied to turbo/DCCD)
- **Subaru roast mode**: 12 instant persona responses for every Subaru stereotype. Asks "Logan or Adam?" before roasting
- **"Say X" parrot command**: Bypasses LLM for TTS latency testing
- **AccountsService fix**: GDM auto-login to KiSTI session (not GNOME) now persistent
- **Handoff pattern**: claude-next-step-{project}-{NN}.md in repo root for session continuity
- **18 commits**, 281+ tests passing

### Learnings
- **Jetson HDA pin-ctl**: Does NOT persist after PulseAudio exits (unlike x86 HDA codecs). PA must stay running for HDMI audio. This is hardware-specific and non-obvious
- **PULSE_SERVER blocks PA restart**: When env var is set, `pulseaudio --start` refuses. Must unset before starting PA from Python
- **PA source vs ALSA device**: parecord needs PA source names (alsa_input.usb-KTMicro...), not ALSA names (plughw:1,0). Auto-detection via `pactl list sources short` works
- **Default PA sink wrong on Jetson**: Auto-selected sink is analog-stereo (no output). Must explicitly `pactl set-default-sink alsa_output.platform-3510000.hda...`
- **response_ready.emit() is UI-only**: Does not trigger TTS. Must use `self.speak()` queue for actual audio
- **Whisper initial_prompt echoes**: On silence, Whisper regurgitates the prompt. Add it to hallucination filter
- **Conversation window timing**: Must reset after TTS playback ends, not at wake word detection. Otherwise follow-ups expire before user hears the response
- **Session handoff**: claude-next-step-{project}-{NN}.md in repo root. 2-digit numbers, overwrite if older than 1 day. Zero friction — just the filename

### Next Steps (see claude-next-step-kisti-voice-02.md)
1. Fix sudo cp for kisti-session (one interactive password → permanent mic gain)
2. Expand persona responses (biggest quality win, instant, no GPU)
3. Implement mode tiers (Intelligent=fun, Sport=clinical, S#=emergency)
4. Echo cancellation improvement
5. Cloud LLM fallback when on WiFi

## Session: 2026-03-28 — Event Quotes, Duplicate Process Fix, WhisperTRT

### Completed
- **Event quotes wired**: `ALERT_TYPE_TO_EVENT` mapping + `get_alert_quote()` in `data/event_quotes.py`. Wired `_on_alert()` + `_on_mode_change()` in `main.py` replacing lambdas. 30% chance on alerts, 50% on mode changes. 18 new tests → **281 total passing**
- **Duplicate process fix**: `kisti.service` (systemd) conflicting with GDM `kisti-session`. Added SIGTERM/SIGINT handlers to `main.py`. Moved flock to `XDG_RUNTIME_DIR` in `scripts/kisti-session`. Updated `install-system.sh` to disable `kisti.service`. *Needs manual sudo on Jetson*: `sudo systemctl disable kisti.service && sudo cp ~/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session`
- **WhisperTRT deps installed on Jetson**: Full chain installed — PyTorch 2.8.0 (CUDA=True), numpy 1.26.4, openai-whisper, torch2trt 0.5.0, onnxruntime, whisper_trt. `from whisper_trt import load_trt_model` verified working
- **jetson_setup.sh updated**: Full idempotent install chain including PyTorch, whisper_trt, system config, and service management

### Learnings
- **PyTorch on JetPack 6**: Must use `torch==2.8.0` from `pypi.jetson-ai-lab.io/jp6/cu126` — 2.10.0 needs `libcudss.so.0` which JetPack 6 does not ship
- **numpy must be <2 with PyTorch 2.8.0**: Downgrade with `pip3 install "numpy<2"` after torch install. scipy warns but works
- **whisper_trt not on PyPI**: Must `git clone NVIDIA-AI-IOT/whisper_trt + pip install -e .`. torch2trt also source-only
- **flock /tmp on Jetson**: `/tmp` cleared on reboot creates race window. Use `$XDG_RUNTIME_DIR` instead
- **CCE updater self-healing limit**: If updater crashes before self-update, it cannot fix itself. Manual copy from repo is the recovery path

### Next Steps
- Build WhisperTRT TRT engine on Jetson: `python3 -c "from whisper_trt import load_trt_model; m = load_trt_model('base.en')"`  (~5-10 min first run)
- Test end-to-end voice: mic → WhisperTRT STT → "Hey KiSTI" wake word → LLM → Piper TTS
- SI Drive screen rethink (deferred): 3 layouts driven by CAN SI Drive signal vs current 4-mode K6 cycling

## Session: 2026-03-27 — Jetson Deployment + Ambient Weather + Stress Test

### Completed
- **Ambient weather system**: `YoctopuceReader` condition_changed signal (pressure ±5hPa, temp ±3°C, humidity ±15%)
- **AmbientSimulator**: 6-phase 90s scripted weather scenario, identical signal interface to hardware sensor
- **DuckDB ambient_conditions table**: records independently of ECU sessions
- **Weather event quotes**: 6 new keys (pressure_falling/rising, temp_dropping/rising, humidity_rising/dropping)
- **Minimal X session**: Replaced GNOME → freed ~500MB GPU for Ollama CUDA; `scripts/kisti-session` + `install-session.sh`
- **Audio routing**: Killed PulseAudio + masked socket; `ALSA_DEVICE = "plughw:0,3"` in AudioPlayer
- **LLM selection**: llama3.2:3b (14 tok/s GPU) chosen over nemotron-mini (6.9 tok/s partial GPU)
- **System prompt**: Drive/Static mode (15-word max when RPM>0, full personality when static)
- **voice_mgr.response_ready signal**: Routes LLM responses through AudioPlayer/aplay (not sounddevice)
- **Stress test**: 21/21 queries, zero crashes, 58°C peak, 50% memory, 1.0s–12.1s response times
- **207 tests** passing

### Learnings (2026-03-28)
- **WhisperTRT + Ollama CUDA conflict**: TRT separate CUDA context corrupts when Ollama infers → illegal memory access. Fix: plain openai-whisper CUDA (tiny.en, 12x real-time). TRT engine at /data/whisper/base.en but unused
- **USB mic gain 100% clips**: KTMicro default 100%/0dB clips everything, Whisper returns empty. Fix: `amixer -c $MIC_CARD cset numid=3 30` in kisti-session
- **HDMI HDA pin-ctl 0x00**: Killing PulseAudio before HDMI init leaves output pin disabled. Fix: start PA, sleep 2, kill PA — sets the pin, then direct aplay works
- **Whisper hallucinations on silence**: tiny.en hallucinates "Okay. Okay." and YouTube phrases on noise. Added repetition + phrase filter in stt_engine.py
- **onnx_graphsurgeon + onnx 1.21 incompatible**: Pin to `onnx<1.17` + `onnx_graphsurgeon==0.5.2`

### Learnings
- **.asoundrc unreliable on Jetson**: String card names rejected, plug configs silently fail. Use explicit `-D plughw:0,3` in aplay instead — abandon .asoundrc entirely
- **PulseAudio must be masked, not just killed**: Socket activation respawns it. `systemctl --user mask pulseaudio.socket pulseaudio.service` required in session startup
- **CUDA pre-load order is critical**: Ollama MUST load model before Qt starts — unified memory means Qt GPU claims block Ollama. Reverse order = OOM
- **sounddevice silently fails without PulseAudio**: All KiSTI speech must route through AudioPlayer → aplay, never voice_mgr.speak()
- **Multiple sim auto-quit conflict**: When --sim-ambient + --sim-voice run together, only the longest-running sim controls app.quit(). Conditional check prevents early exit
- **GDM AccountsService wiped on restart**: Must recreate `/var/lib/AccountsService/users/aldc` each time

### Open Bug
- **Waveform not rendering in minimal X session**: All signals fire, envelope correct (PCM peak=32767, env_max=1.000), but widget doesn't visually animate. Debug commit f35a052 adds frame 15/30/60 logging. WA_OpaquePaintEvent added to _KittWaveform and _ScanBar — needs validation on Jetson

### Next Steps
- Validate waveform fix (WA_OpaquePaintEvent) in minimal X session on Jetson
- Remove debug frame logging from kisti_mode.py once viz confirmed working
- Permanent AccountsService fix via tmpfiles.d
- GPS09 Pro IMU/GPS integration (plan saved — placeholder CAN IDs 0x6A4-0x6A7)

---

## Session: kisti-04 (2026-03-29)

### Completed
- **Phase 4 fully implemented** (361/361 tests)
  - 4.1 Barge-in: OWW threshold 0.5→0.85 during TTS, mic stays active, wake word interrupts paplay, echo guard 2.0s→0.3s, critical alerts still use full pause
  - 4.2 Response Composer: `_compose_and_speak()` unifies all 6 response paths, VoiceResponse created for say/remember/quiet/resume/sensor/LLM, record_turn for all user queries
  - 4.3 PipelineTrace: tracks STT→LLM→TTS→speaker timestamps, logs "Pipeline: STT=Xms LLM=Xms TTS=Xms total=Xms", DuckDB voice_latency table
  - 4.4 QA harness: tests/conftest.py shared fixtures, TestPipelineTrace/ResponseComposer/BargeIn/VoiceLatencyDuckDB/GoldenPersona
- **Mic gain tuning**: PA=200% + ALSA=100% is sweet spot for KTMicro USB mic with Silero VAD
- **sounddevice primary capture**: replaced parecord subprocess (pipe pos=0 bug) with sounddevice.InputStream — no subprocess, no pipe, no buffering issue

### Failed Approaches
- `stdbuf -oL` and `stdbuf -o0` do NOT fix parecord pipe buffering — PA uses internal async mainloop (not libc stdio), stdbuf can't intercept it
- PA=500% boost drowns Silero VAD: ambient RMS=2000 at 500%, VAD can't distinguish speech from noise. 200% gives ambient=110 vs speech=2100-4500

### New Patterns
- **CCE team TUI project board**: POST `/api/team-session/{id}/project` with `phases` array to update the board at top of TUI (separate from event stream)
- **Conductor transfer**: no API endpoint — use direct psql `UPDATE zeus_core.cce_team_sessions SET conductor = 'name'`
- **PipelineTrace rounding**: use `round()` not `int()` for ms conversion — float arithmetic causes off-by-one (int(0.1*1000)=99, round=100)
- **parecord pipe diagnosis**: `cat /proc/<pid>/fdinfo/1` — if `pos: 0` after minutes, pipe is stuck (data never flowing)

## Session: kisti-speaks (2026-03-30) — Voice Pipeline + CUDA Strategy

### Completed (4 commits: 775587e → 2bfd3af)
- **Echo suppression**: WAKE_WORDS cleaned of sensor words (caused echo loops). Text overlap rejection: >40% word match within 3s of last speech discarded.
- **Dual speech path fix**: `_compose_and_speak` was emitting `response_ready` (AudioPlayer) AND queuing `_speak_queue` (_do_speak). Both toggled mic pause/resume — race left mic permanently stuck. Removed `response_ready` emit; `_do_speak` is now sole audio path.
- **Token caps**: Intelligent 64→256, Sport 32→64. STT `is_real` fixed to check `_backend` not `_model`.
- **Ollama warmup**: kisti-session waits for API readiness then sends a warm-up query before GDM starts.
- **CUDA strategy**: whisper.cpp CUDA + Ollama CPU. Orin Nano pool fits one model at a time; STT wins (every interaction), LLM loses (rare fallback, persona covers 90%).
- +5 echo suppression tests (385 total at voice session end)

### Failed Approaches
- `num_ctx=8192` in Ollama options → `cudaMalloc failed: out of memory`. Orin Nano unified CUDA pool is exhausted by whisper.cpp + Qt. NEVER set num_ctx on this hardware.
- Sensor/telemetry words in WAKE_WORDS (`temperature`, `boost`, `oil pressure`, `humidity`) → echo re-trigger loops. KiSTI says the word, echo matches WAKE_WORDS, same query fires again.
- Dual speech path (response_ready + _speak_queue) → mic stuck permanently paused after 3-4 interactions.
- sudo password piping with heredoc via SSH unreliable — write to /tmp file first, then sudo cp.

### New Patterns
- **CUDA load order matters**: on Jetson, whichever process loads first gets CUDA. Service ordering via systemd `After=` + `Before=` controls allocation.
- **Ollama systemd CPU mode**: `echo -e "[Service]\nEnvironment=\"CUDA_VISIBLE_DEVICES=\"" > /etc/systemd/system/ollama.service.d/override.conf`
- **Echo suppression via text overlap**: compare Set(transcribed_words) ∩ Set(last_spoken_words) / len(transcribed_words). Threshold 0.4, window 3s.
- **whisper.cpp -ng flag**: `--no-gpu` forces CPU mode. Confirmed working on Orin Nano.

## Session: kisti-08 (2026-03-30) — Phase 3 TimingManager + Mic Bug Investigation

### Completed (1 commit: 87fd800)
- **Phase 3 TimingManager**: `timing/timing_manager.py` wired to DiffStateBridge. Connects GPS → LapTimer, emits `lap_completed`/`sector_completed`/`track_detected`. Voice announcements in main.py, session lifecycle with pit lane debrief.
- **MockCanGenerator**: GPS trace replaced from oval approximation to Laguna Seca waypoint interpolation — crosses S/F + all 3 sector lines per lap.
- **26 tests** (`tests/test_timing_manager.py`, synthetic rectangular track). 522 total.
- **Bug fix — re-entrant state_changed**: `_update_bridge_timing()` was calling `bridge.update_timing()` which re-emitted `state_changed` synchronously on every GPS tick, doubling signal traffic. Fixed with `bridge.blockSignals(True/False)` wrapper. Also fixed double-lap detection (LapTimer was processing each GPS point twice).
- **Bug fix — lap_count field**: `duckdb_store.py:344` used `getattr(state, 'lap_number')` but DiffState field is `lap_count`. Was recording NULL for lap number in telemetry.
- **Jetson deploy**: `git -C /home/aldc/repos/kisti pull` — code live on Jetson.

### Failed Approaches
- **blockSignals alone insufficient**: Fixed signal traffic but KiSTI still not responding to voice on Jetson after deploy. Root cause TBD — check _paused/_barge_in state in logs, AudioPlayer echo protection race at `main.py:525-534`.
- **SSH git pull with ~/kisti path**: Fails in non-interactive SSH. Use `git -C /absolute/path pull` or `git --git-dir=/path/.git pull`.
- **sudo via SSH without tty**: `sudo systemctl restart kisti` over SSH fails — requires tty or sudoers entry. kisti runs via GDM session on tty2, not as a restartable systemd service from SSH.

### New Patterns
- **Qt re-entrant signal guard**: When a signal handler emits another signal on the same QObject, use `obj.blockSignals(True/False)` wrapper to prevent feedback loops. Especially important for bridge objects connected to multiple listeners.
- **DiffState field audit**: After extending DiffState, grep all `getattr(state, ...)` calls in duckdb_store.py to verify field names match exactly.
- **CCE team broadcast restriction**: Only the original session conductor can post `broadcast` events. Joined agents should use `learning`, `task_claimed`, `task_completed` types.

## Session: kisti-web (2026-03-30) — Sponsorship Site Overhaul

### Completed
- **"Why ALDC" page** (1000+ lines): Enterprise Intelligence narrative mapped to KiSTI use case. Data→Knowledge→Conversational arc. Timeline (Day 1/90/Year 1), Intelligence Multiplier, Architecture Stack (Eclipse/Zeus Memory/Zeus Chat). Positioned ALDC as edge AI platform.
- **Zeus Chat page** (/zeus): Full-page immersive interface with left sidebar (capabilities, powered-by tags, clear button), chat area (messages, voice input, starter chips), responsive grid layout
- **Product card leader lines**: Dynamic SVG bezier curves with dual-color markers (amber Link, green NVIDIA). ResizeObserver recalculation on resize/sidebar toggle. Hidden on mobile (hidden lg:block)
- **Proportional sizing**: Real MM dimensions drive aspect ratios and percentage widths (Strada 237mm = 100%, Keypad 123.5mm ≈ 52%, G5 Neo 107mm ≈ 45%). Added calculateProductRatio() helper
- **Link hardware cards**: Strada 7" Street dash, CAN Keypad 8, G5 Neo 4 ECU with leader lines mapping to schematic positions
- **NVIDIA product cards**: Jetson Orin NX Super Dev Kit 16GB (100 TOPS, 16GB LPDDR5) in-car. Identified DGX Spark (1 PFLOP, 128GB, 1.2kg, ~$3,000) for pit-side (pending image replacement)
- **Sponsorship documents**:
  - `docs/nvidia-sponsorship-letter.md` (103 lines): Vehicle specs (IAG 750, BCP X400, E85), AI pipeline (19 sensors, 4 cameras, fully offline), limitations, three-tier hardware ask, 3.5M+ memories figure
  - `docs/nvidia-sponsorship-strategy.md` (80 lines): Target hardware comparison table (Orin NX vs AGX Orin vs AGX Thor vs DRIVE AGX), DRIVE AGX access requirements, sponsorship pitch summary, Link ECU prior reference
- **Technical page updates**:
  - Voice AI Pipeline: STT (whisper.cpp ~130ms), TTS (Piper <200ms), Edge Memory (DuckDB + ONNX), Anomaly Detection
  - Vehicle section: E85 fuel narrative, 360-390 WHP, component tags
  - Sensor details: Cobb 4 Bar MAP, GM IAT, flex fuel, 150 PSI oil pressure (specific models added)
  - Cloud Memories: "3.5M+" (corrected from "204K active")
- **kistiGraph.ts updates**: "Jetson Orin" → "Jetson Orin NX", full 16GB spec in description. "Weather Cam" → "Weather Station" (Yoctopuce Yocto-Spruce)
- **Partners page**: NVIDIA role "Edge Compute" → "Edge AI Platform"
- **PostHog verification**: Confirmed tracking snippet present on live site
- **Production deploy**: kisti-headless → main, Vercel triggered, 100 TOPS + Voice AI Pipeline + E85 visible on kisti.analyticlabs.io

### Learnings
- **Failed approach — H100 HGX for pit-side**: Data center rack product (100W+, $7,500+) unsuitable for track crew work. Corrected with DGX Spark research (Mac Mini form factor, portable, purpose-built workstation)
- **Deploy target**: kisti-headless = Vercel Preview only. Production requires merge to main for auto-deploy
- **Memory positioning**: Use "3.5M+ memories processed" (official ALDC figure) not "204K active" (running count)
- **SVG proportional sizing**: Calculate pixel-to-viewBox ratios accounting for aspect ratio preservation (xMidYMid meet). ResizeObserver needed for responsive recalculation on viewport + sidebar state changes
- **Leader line Bezier math**: Control points leave card horizontally (cx1 = x1 + dx×0.45), arrive at target horizontally (cx2 = x2 − dx×0.25) for smooth aesthetic curves

### Pending
- Replace H100 image with DGX Spark (PNY CDN image URL: `https://d2vfia6k6wrouk.cloudfront.net/productimages/ef15a000-baca-4109-a81e-b2f9010d00f9/images/spark-3qtr-right.png`)
- Update src/app/page.tsx pit engineer card: name "DGX Spark", role "Pit-Side AI", spec "1 PFLOP, 128GB, 1.2 kg", URL to nvidia.com/products/workstations/dgx-spark/, bg-white
- Update nvidia-sponsorship-letter.md with final three-tier ask details (currently template version)
- Save sponsorship docs to Nextcloud: `/home/aldc/nextcloud-rclone/ALDC Management/CCE_projects/02-ai-chat-visualization/2026-03-20-kisti-edge-ai-codriver/`

## Session: 2026-03-31 — Sponsorship Narrative Rewrite + Hardware Alignment

### Completed
- **Sponsorship letter complete rewrite**: Pivoted from enterprise capability showcase to grassroots accessibility narrative. Subject: "Garage-Built AI Co-Driver Running on Jetson". Core argument: "NVIDIA made automotive AI accessible to regular people...The kind of people who don't drive McLarens and don't know anyone who does...That market — grassroots, aftermarket, enthusiast automotive AI — exists now, and NVIDIA is the reason."
- **Three-tier hardware ask crystallized**: In-car (AGX Thor: 1,000+ TOPS, 128GB, 40-130W configurable), Pit-side (DGX Spark: 1 PFLOP, 128GB, 1.2kg), Cloud (Zeus Memory: 3.5M+ memories). Explicit hardware specs + NVIDIA product URLs in sponsorship letter.
- **Website hardware audit + fixes**: Found and fixed 8 locations across 5 files (src/app/page.tsx ×2, src/app/tech/page.tsx ×4, src/app/partners/page.tsx, src/lib/kistiGraph.ts) changing from Orin NX (100 TOPS, 16GB) to AGX Thor (1,000+ TOPS, 128GB) to align with sponsorship ask.
- **Image optimization**: Downloaded NVIDIA Jetson AGX Thor product shot from official CDN (developer.download.nvidia.com), optimized from 7.4MB to 55KB using ffmpeg scale filter while preserving white background quality.
- **Nextcloud archival**: Saved sponsorship documents (letter + strategy) to Nextcloud with markdown formatting for proper rendering.
- **Production deploy**: Merged kisti-headless to main, pushed to GitHub, Vercel auto-deployed. Site now shows AGX Thor (1,000+ TOPS, 128GB LPDDR5X) + DGX Spark (1 PFLOP, 128GB, 1.2kg) across all pages.

### Learnings
- **Sponsorship angle correction**: The pitch is NOT about showcasing what Jetson hardware can do (enterprise story). It's about showing that Jetson *enabled* garage builders to do what was previously only accessible to OEMs (grassroots story). This distinction reversed the entire narrative arc.
- **Website-sponsorship alignment critical**: Site was showing aspirational Orin NX while sponsorship letter asked for AGX Thor. Mixed messaging breaks credibility. Site must always reflect actual hardware ask, not future aspirations.
- **Official CDN sources over marketing**: NVIDIA developer.download.nvidia.com proved more reliable than PNY marketing CDN for product images. Also more authoritative for long-term links.
- **Markdown for Nextcloud archival**: Plain text doesn't render properly in Nextcloud. Keep markdown formatting (**bold**, ## headings) in archived documentation copies.
- **Git stash pattern for merge conflicts**: When local changes block checkout, use `git stash --include-untracked` → `checkout` → `merge` → `push` → `stash pop` workflow. Clean, atomic, low friction.

### Failed Approaches
- **Enterprise-capability pitch**: Initial sponsorship framing focused on demonstrating edge AI capabilities ("Look what you can do on Jetson"). Didn't resonate. Corrected to accessibility pitch ("Look who can now do this, not just McLaren").
- **Plain text for Nextcloud**: Attempted to convert markdown sponsorship letter to plain text for email readability. Broke Nextcloud rendering. Reverted to markdown for archival + separate email review.
- **WebFetch on NVIDIA marketing pages**: Tried to fetch NVIDIA product images from public marketing site — returned 404. Switched to developer.download.nvidia.com CDN which has official product shots.

### Key Decision
- **AGX Thor on site is non-aspirational**: We have an Orin Nano currently installed, but sponsorship ask is for AGX Thor. Site correctly reflects the ask (Thor), not the current hardware (Nano). This keeps messaging aligned with partnership proposal.

### Next Steps
- Confirm sponsorship letter resonates in actual NVIDIA business development call
- Monitor kisti.analyticlabs.io production metrics (PostHog) for visitor intent signals
- E85 sustainability angle in messaging (renewable fuel + edge AI = differentiated story)
