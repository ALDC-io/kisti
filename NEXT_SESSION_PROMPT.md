# NEXT SESSION PROMPT — KiSTI kisti-flir-06

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1085 passed, 11 skipped

---

## Before starting work
1. `echo "KiSTI FLIR-06" > /tmp/tui-project-label`
2. Write phases to `/tmp/tui-phases.json` — TUI reads every 1s. Format: `[{"id":"1","name":"...","status":"pending|in_progress|completed","detail":"..."}]`. Update on every phase start/complete.

## kisti-flir-05 summary (what was built)

### Threaded FLIR reader (major refactor)
- **Complete rewrite** of `sensors/flir_lepton_reader.py` — `_FrameWorker(QThread)` owns `cap.read()` loop. Main thread NEVER blocks on V4L2 I/O. Eliminates 5-30s UI freezes on PureThermal lockup.
- **Self-healing**: worker detects consecutive read failures → releases handle → USB-resets PureThermal via direct sysfs writes → re-opens device. All in worker thread, up to 10 attempts with 5s backoff.
- **USB reset**: direct sysfs `echo 0/1 > authorized` (no shell injection). Falls back to `sudo -n` if no write permission. Sysfs path: `/sys/bus/usb/devices/*/authorized` matching "WebCam" or "PureThermal" product string.

### PatternEngine + ParkedDebrief wired into main.py
- **PatternEngine**: created inside `if db_store:` with session_id getter. Starts/stops on session toggle. 1Hz analysis cycle.
- **Pattern → voice**: `ice_risk_imminent` → "Reduce speed. Ice risk." / `ice_risk_trending` → "Caution, road cooling toward dew point." / `knock_burst` → knock events.
- **ParkedDebrief**: Haiku analysis on session end. Background thread, WiFi-gated. Speaks all 3 insights with 3s pauses. Cycles on Intelligent screen coaching bar (5s per insight, green `[1/3]` prefix).
- **voice_alert signal**: AlertEngine's `voice_alert` wired to `voice_mgr.speak_alert()`. General handler skips VOICE_ALERT_TYPES to prevent double-speak.

### Surface state hysteresis
- `DiffStateBridge.SURFACE_HYSTERESIS_N = 3` (at 3Hz = ~1s settling). DRY↔WET↔COLD require N consecutive readings. LOW_GRIP immediate (safety-critical).

### Smart grip alert system
- **Rolling 10s window** (20 samples at 2Hz) with 50% dominance threshold.
- Only announces when dominant state genuinely shifts. Brief excursions (tunnel, bridge) filtered.
- Manages its own lifecycle — bypasses `_fired_types` for re-entry alerts on multi-zone drives.
- LOW_GRIP → "Low grip." / DRY after danger → "Grip restored."

### Ice risk alert
- `_check_ice_risk()` in AlertEngine — fires when road temp within 1°C of dew point.
- Uses `_ice_risk_active` flag: fires once on entry, resets when delta > 3°C.
- Sensor-independent (no ECU required). `_check_grip` also moved to sensor-independent.

### Alert UX overhaul
- **Once per session**: `_fired_types` set replaces time-based debounce. Each alert type voices once.
- **Action first**: "Reduce speed. Ice risk." not "Ice risk. Road temp..."
- **VOICE_ALERT_TYPES**: oil_pressure_low/critical, coolant_critical, fuel_pressure_critical, ice_risk_imminent, grip_low_grip.
- **Warm object voice disabled**: too many false positives stationary. Display-only.

### Demo mode
- Auto-session start after 5s (`QTimer.singleShot` → `session_toggle.emit()`).

### Jetson deployment
- **GDM session**: `kisti-session` runs from `~/repos/kisti`. Rsync target must be `~/repos/kisti` NOT `~/kisti`.
- **USB speaker**: Jieli UACDemoV1.0 at card 0. Mono not supported — use `plughw:0`. PA default sink set to USB. Volume 60%.
- **Piper TTS**: `/data/piper/piper`, model `/data/piper/en_US-danny-low.onnx`, sample rate 16000 Hz.

## Pending from code review (kisti-flir-06 work)

### High priority
1. **Test recovery path** — no tests exercise `_recover()` or `_FrameWorker`. Add integration tests with mock cap that simulates lockup → recovery.
2. **Docstring accuracy** — `_check_grip` docstring says 60s/60% but code is 10s/50%. Fix docstrings.
3. **Module-level imports** — `_check_grip` imports Counter and SurfaceState at 2Hz. Move to top of file.
4. **GPS state in _last_alert** — `_gps_was_live` boolean stored in `dict[str, float]`. Add dedicated `_gps_was_live` attribute.
5. **`_consecutive_warm` never resets** after detection fires — signal emits every frame while warm object visible.

### Medium priority
6. **Udev rule for FLIR USB** — `ACTION=="add", ATTR{idVendor}=="1e4e", RUN+="/bin/chmod a+w %S%p/authorized"`. Eliminates sudo dependency.
7. **_label_blobs performance** — pure Python flood fill on 19K pixels. Add hot_count ceiling (>30% = skip) or use scipy.ndimage.label.
8. **Auto-detect device safety** — opening all /dev/videoN can steal other sensor handles. Add VID check or --flir-device flag.
9. **Two status lines on Intelligent screen** — user reported duplicate text at bottom. Investigate coaching bar vs voice ticker overlap.

### Nice to have
10. **Rogers Pass route tag** — auto-tag sessions with route name.
11. **Debrief display on Intelligent screen** — currently coaching bar only (24px, single line). Could use larger overlay when parked.

## Key files
`sensors/flir_lepton_reader.py` (threaded reader + self-healing) | `alerts/alert_engine.py` (smart grip + ice risk + once-per-session) | `main.py` (PatternEngine/ParkedDebrief wiring, debrief UX, pattern→voice) | `model/vehicle_state.py` (surface hysteresis) | `tests/test_surface_hysteresis.py` (8 tests) | `tests/test_alerts.py` (ice risk tests)

## Late session additions (post-handoff)
- **Worker sleep removed**: `cap.read()` is the natural rate limiter at 9Hz. Extra sleep halved frame rate.
- **TTS pronunciation**: "Kissty" not "Keesty Eye" — updated in `voice/tts_engine.py` TTS_SUBSTITUTIONS.
- **Ice test validated on hardware**: "Low grip." fires when ice held in front of FLIR for ~5s. "Grip restored." fires ~10s after removal. Screen updates immediately.
- **Driving context**: At 100km/h, 10s rolling window = 280m. Entering danger = ~140m warning (5s). Clearing danger = ~280m (10s). Acceptable — screen shows state instantly, voice confirms.

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `avg > 0` guard blocks sub-zero detection → use `!= 0.0`
- Two KiSTI processes fight for `/dev/video0` → kill ALL before restart
- `CAP_PROP_READ_TIMEOUT_MSEC` is silently ignored by V4L2 backend — don't rely on it
- PureThermal lockup can survive USB reset — worker thread retries with backoff
- GDM auto-restarts kisti-session on process exit — don't `kill -9` the session itself
- Dew point in test fixtures: dew_point=10.0 + road=3.0 → LOW_GRIP (not COLD). Use dew_point=0.0 for COLD tests
- LOW_GRIP bypasses hysteresis (safety-critical) — tests must account for this
- Rsync to `~/repos/kisti` on Jetson, NOT `~/kisti`
- `_check_grip` must be in sensor-independent section (before `is_engine_stale` gate)
- Don't add `time.sleep()` in FLIR worker thread — `cap.read()` blocks at native frame rate
- TTS pronunciation: "Kissty" not "Keesty Eye" (voice/tts_engine.py TTS_SUBSTITUTIONS)
