# KiSTI - Progress

## Session: 2026-04-04 (kisti-flir-05 Final Wrap — Learnings Synthesis)

### Status: COMPLETE

### Learnings Captured to Zeus Memory
- ✅ 5 learnings posted to Zeus Memory (tenant 11111111, user jk)
- 1x cce_success_log: ice detection validation with real hardware + PureThermal
- 4x cce_decision_log: kill grip voice alerts (latency unactionable), TTS pronunciation, frame rate halving gotcha, future continuous color gradient UX

### Key Insights
1. **Grip voice alerts removed** — At driving speed, 10s rolling window latency means voice arrives 140-280m late. Screen feedback is instant + peripheral. Voice is wrong UX for continuous surface conditions.
2. **TTS: "Kissty" not "Keesty Eye"** — One syllable vs three; cuts through 80+ dB engine audio at highway speeds. Updated TTS_SUBSTITUTIONS in voice/tts_engine.py.
3. **Frame rate gotcha: cap.read() already blocks** — Added time.sleep() expecting throttle, got halving (9Hz → 4.5Hz). V4L2 native rate already blocks; don't double-throttle.
4. **Ice detection validated** — Real test with dry ice on asphalt. Low grip alert fires after 5s sustained cold, restored after 10s. 1°C dew-point margin confirmed for production.
5. **Next UX direction** — Continuous background color gradient (ice_risk_delta: green→amber→red) instead of discrete labels. Peripheral vision model. Designed for kisti-flir-06.

### Handoff to kisti-flir-06
- Jetson field validation (30+ min continuous, FLIR recovery scenarios)
- Trade show dry run with demo mode
- Implement continuous color gradient UX for surface conditions
- Audio stress test (rapid alerts + FLIR recovery simultaneously)

---

## Session: 2026-04-04 (kisti-flir-05-continued-phase2 — Threaded FLIR Reader + Self-Healing USB Recovery)

### Status: COMPLETE

### Completed
- **Threaded FLIR reader implementation** — Moved cap.read() from QTimer (main thread) to QThread worker. Main thread never blocks on V4L2 I/O. Eliminates 5-30 second UI freezes when PureThermal locks up. Event loop runs independently in worker.
- **Self-healing FLIR recovery** — Worker thread detects consecutive read failures, performs USB reset via sysfs (`echo 0/1 > /sys/bus/usb/devices/.../authorized`), re-opens device. All recovery isolated to worker thread; main UI unaffected during recovery.
- **USB reset security hardening** — Replaced `sudo bash -c` shell command with direct sysfs writes using pathlib.Path.write_text(). Eliminates shell injection vulnerability, faster execution.
- **Graceful FLIR offline state** — Shows "FLIR offline — recovering..." UI indicator instead of freezing. User sees async recovery in progress.

### Files Changed
- `video/flir_reader.py` — NEW/REFACTORED, QThread worker for cap.read(), USB reset logic, retry loop (10x @ 5s backoff)
- `main.py` — Integrated FLIRReaderThread, signals for frame_ready + offline state, graceful error handling
- `ui/screens/video_screen.py` — Display "FLIR offline" during recovery

### Key Decisions
- **Worker thread over timeout property** — OpenCV CAP_PROP_READ_TIMEOUT_MSEC silently ignored by V4L2 backend. Threading is the only reliable way to prevent main thread blocking.
- **Sysfs USB reset vs shell command** — Direct file writes over subprocess calls: safer, faster, more reliable.
- **Retry loop 10x @ 5s** — PureThermal lockup sometimes survives software reset; 50s retry window before declaring offline.

### Learnings Captured
- ✅ 5 learnings posted to Zeus Memory (tenant 11111111, user jk)
- 2x cce_success_log: threaded FLIR reader, self-healing recovery
- 3x cce_decision_log: OpenCV timeout gotcha, USB reset security, PureThermal power cycle limitation

### Don't Repeat
- CAP_PROP_READ_TIMEOUT_MSEC is unreliable — don't set it expecting timeout behavior. Use threading.
- Direct sysfs writes are safer than shell commands for USB control.
- PureThermal may need power cycle, not just software reset — thread up to 10 retries before giving up.

### Next Session (kisti-flir-06)
1. Jetson field validation — run threaded reader on real Jetson for 30+ min, monitor recovery logs
2. Trade show dry run — full demo mode with FLIR recovery scenarios
3. Warm object temporal gating — re-enable with 3s minimum between alerts
4. Audio stress test — rapid alerts while FLIR is recovering

---

## Session: 2026-04-04 (kisti-flir-05-continued — Live Jetson Audio + Voice Alert Tuning)

### Status: COMPLETE

### Completed
- **PulseAudio routing diagnosis** — Identified silent audio failure: paplay sends to PA default sink without verification. Fixed by explicit PA sink assignment. Direct ALSA (plughw:0) confirmed working.
- **USB speaker mono limitation** — Jieli UACDemoV1.0 requires plughw:0 for channel auto-conversion (hw:0 fails). ALSA plugin handles stereo→mono downmix transparently.
- **Voice alert single-fire pattern** — Implemented _fired_types set to prevent spam. Alerts fire once per session; screen + ECU dash handle persistent state. Reduces cognitive load.
- **Grip detection decoupled from CAN** — _check_grip moved out of engine-running gate, now runs sensor-independently like ice_risk. Enables Jetson-only operation.
- **Warm object detection display-only** — Disabled voice (fired 9x/sec), kept visual alert. Pending 3s temporal gating to re-enable voice safely.
- **Ice risk message phrasing simplified** — "Reduce speed. Ice risk." (action-first) vs "Road temp 3°C, dew point 2°C". Voice alerts now prioritize driver action.
- **Jetson deployment path corrected** — GDM kisti-session auto-starts from ~/repos/kisti. rsync and launch scripts verified.
- **Multi-instance lock contention resolved** — Kill all python3 main.py before restart to prevent FLIR/DuckDB lock fights.

### Files Changed
- `alerts/alert_engine.py` — _fired_types set, voice_alert gating, simplified ice_risk message
- `main.py` — grip check sensor-independent gate removal
- `model/vehicle_state.py` — ice_risk check decoupled from ECU gate
- Jetson deployment scripts — path validation

### Key Decisions
- **One-fire voice alerts** — Announcement model (not persistent state) reduces driver distraction. Screen handles continuous display.
- **Sensor-independent safety checks** — ice_risk and grip_detection run without CAN. Enables graceful degradation when ECU offline.
- **Simplified voice copy** — Action (reduce speed) before data (temperatures). Humans process imperative + reasoning in sequence, not simultaneously.

### Learnings Captured
- ✅ 10 learnings posted to Zeus Memory (tenant 11111111, user jk)
- 7x cce_failed_approach: PulseAudio routing, USB mono, warm object spam, FLIR lockup, grip gating, grip window tuning, multi-instance locks
- 3x cce_decision_log: single-fire voice alerts, sensor-independent checks, simplified voice phrasing

### Don't Repeat
- PulseAudio silent failures — always test with aplay direct check, not just paplay
- USB audio devices may not support mono — use plughw:0 (plugin layer) for format conversion
- Warm object detection at 9 Hz creates voice alert spam — needs temporal gate (fire once per 3s minimum)
- FLIR device locks require full restart, not just USB reset
- Two KiSTI instances will deadlock — always pkill -f 'main.py' before relaunch
- Grip detection behind engine gate is wrong — grip matters at any speed, independent of CAN

### Next Session (kisti-flir-06)
1. Warm object temporal gating — re-enable voice with 3s minimum between alerts
2. FLIR auto-recovery udev rule — attempt USB reset on V4L2 timeout
3. Trade show dry run — 1+ hour continuous demo mode on Excelon, verify no crashes
4. Audio stress test — rapid ice/grip/object alerts simultaneously, verify no speech overlap

---

## Session: 2026-04-04 (kisti-flir-05 — PatternEngine + Ice Risk Voice Alert + Surface Hysteresis)

### Status: COMPLETE

### Completed
- **PatternEngine + ParkedDebrief wired into main.py** — Pattern detection signals (ice_risk_imminent, knock_burst) routed to voice alerts. ParkedDebrief runs in background thread with WiFi connectivity gate. Enables coaching analysis during canyon driving with persistent state.
- **Surface state hysteresis N=3** — DRY/WET/COLD transitions require 3 consecutive readings to prevent spurious flips from noisy FLIR. LOW_GRIP transitions fire immediately for safety. Prevents jittery state changes on radiometric sensor data.
- **Ice risk voice alert sensor-independent** — AlertEngine._check_ice_risk() fires when road_temp within 1°C of dew_point. No ECU required. Example voice: "Road temp is 3°C, dew point is 2°C — ice forming now."
- **Demo mode auto-session start** — QTimer.singleShot(5000) launches KiSTI at trade show startup. Loops SI-Drive modes, cycling voice alerts and pattern outputs. Jetson standalone on Excelon — no laptop required.
- **Jetson live demo validation** — Confirmed on real hardware: FLIR Y16 mean=30137 (~28°C), Yocto ambient + humidity + dew point, DuckDB pattern memory, PatternEngine.match() on real data.
- **Voice alert signal routing separated** — VOICE_ALERT_TYPES routed separately from alert_fired handler. Prevents double-speak when alert fires + routes to voice. AlertEngine.voice_alert only for critical+advisory.
- **13 tests added** (1072→1085).

### Files Changed
- `alerts/alert_engine.py` — _check_ice_risk() method, voice_alert signal routing
- `main.py` — PatternEngine + ParkedDebrief wiring, demo mode auto-start timer
- `model/vehicle_state.py` — Surface state hysteresis (N=3) + immediate LOW_GRIP
- `tests/test_surface_hysteresis.py` — NEW, 138 lines, surface state transition tests
- `tests/test_alert_routing.py` — voice_alert routing verification
- `tests/test_alerts.py` — +8 ice risk + hysteresis tests

### Key Decisions
- **Hysteresis N=3 with immediate LOW_GRIP** — Safety-critical ice detection can't wait for 3 readings. Dry/wet/cold can tolerate hysteresis; ice risk can't.
- **Dew point ice detection** — road_temp ≤ dew_point is definitive "ice forming NOW" signal. More reliable than fixed <0°C thresholds.
- **Demo mode with 5s startup delay** — Enough time for Jetson boot + display negotiation. Auto-loop lets passive viewers see all 3 SI-Drive modes without intervention.

### Learnings Captured
- ✅ 8 learnings posted to Zeus Memory (tenant 11111111, user jk)
- 5x cce_success_log: PatternEngine wiring, surface hysteresis, ice risk alert, demo mode, Jetson validation
- 3x cce_decision_log: voice alert routing, DISPLAY=:0 SSH gotcha, dew_point fixture gotcha

### Don't Repeat
- Surface hysteresis test fixtures must use low dew_point (0.0°C not 10.0°C) — otherwise road_temp=3°C triggers ice detection instead of COLD state transition
- SSH to Jetson doesn't inherit DISPLAY — must set DISPLAY=:0 explicitly in launch script
- Demo mode requires QTimer, not blocking sleep — allows event loop to process signals

### Next Session (kisti-flir-06)
1. Trade show deployment validation — run demo mode on Excelon for 30+ min, verify voice alerts fire correctly
2. ParkedDebrief remote sync — test WiFi upload of coaching data to Nextcloud
3. Session persistence — verify DuckDB pattern memory survives Jetson restart
4. Voice response tuning — adjust dew_point delta (currently 1°C) based on user feedback

---

## Session: 2026-04-03 (kisti-28 — Radiometric FLIR + Real Sensor Mode)

### Status: COMPLETE

### Completed
- **Y16 radiometric mode enabled** — PureThermal switched from BGR AGC to Y16 (uint16 centi-Kelvin). Real road surface temperatures now flowing. Confirmed mean=29837 (25.2°C) from live radiometric data.
- **OpenCV Y16 bug guard** — Added `.view(uint16).reshape(120,160)` workaround for OpenCV flattened uint8 bug.
- **Mock CAN disabled** — `mock.start()` commented out. Only real sensors active: FLIR, Yocto, Korlan (when connected). Screens show "---" for unavailable CAN data.
- **Default screen → Intelligent** — Stack default changed from Sport (index 1) to Intelligent (index 0) for real-sensor mode.
- **SI-Drive locked to Intelligent** — Mock SI-Drive tick locked to mode 0 for FLIR testing.
- **4-column weather card** — WEATHER | ROAD | HUMIDITY | BARO evenly spaced across 800px. Road temp heat-colored from FLIR. BARO right-aligned.
- **Surface state inference from sensors** — `update_road_surface()` derives surface_state when no CAN: <0°C=LOW GRIP, <5°C=COLD, road<dew_point=LOW GRIP (ice forming), road<dew_point+3=WET (condensation), delta>5+humid=WET.
- **Dew point black ice detection** — road_temp ≤ dew_point → active frost/ice formation. Tested with cold glass bottle: sub-zero triggered LOW GRIP alert.
- **CLAHE contrast + temporal smoothing** — Adaptive histogram equalization + 70/30 frame blend for stable thermal patterns. Cached CLAHE object.
- **Frame throttle to ~3 Hz** — Skip 2 of 3 FLIR frames to prevent Jetson CPU lockup (was 55% at 9Hz).
- **LUT-based inferno colormap** — Precomputed 256-entry LUT replaces per-frame np.interp. QImage cached off paint thread.
- **Coaching text moved to bottom bar** — No longer overlays FLIR image. Dedicated bar at y=456-480.
- **ROAD SURFACE label removed** — Clean thermal image, no text overlay.
- **Sport voice ticker relocated** — Moved from G-force circle overlap to empty FLIR panel (top-right).
- **Compact weather card** — 148px→108px, FLIR panel shifted up (y=118, 192px tall).
- **FLIR diagnostic logging** — Frame dtype/shape/mean on first read, road temps every 3s.

### Files Changed
- `sensors/flir_lepton_reader.py` — Y16 FOURCC, OpenCV uint8 workaround, frame format diagnostic log
- `model/vehicle_state.py` — Surface state inference from FLIR+Yocto, dew point ice detection, road temp logging
- `can/kisti_can.py` — Mock FLIR removed (prior), SI-Drive locked to Intelligent
- `main.py` — Mock CAN disabled
- `ui/main_window.py` — Default screen → Intelligent, flir_reader to IntelligentScreenWidget
- `ui/intelligent_screen.py` — 4-col weather card, LUT inferno, CLAHE+smoothing, frame throttle, coaching bar, compact layout
- `ui/sport_screen.py` — Voice ticker relocated, FLIR panel → fillRect
- `ui/sharp_screen.py` — lap_in_progress gate, gradient bar
- `tests/test_flir_lepton.py` — BGR test, non-radiometric returns 0.0
- `tests/test_timing_manager.py` — lap_in_progress in expected_keys

### Key Decisions
- **Y16 over BGR** — Requesting Y16 FOURCC auto-disables AGC on PureThermal fw≥1.0.0. No CCI commands needed. Settings reset on power cycle but Y16 request happens every startup.
- **Sensor-only mode** — Mock CAN disabled for real-world testing. Screens gracefully show "---" for missing data.
- **Dew point as ice predictor** — road_temp ≤ dew_point is the definitive "ice forming NOW" signal. More accurate than fixed thresholds alone.
- **~3 Hz FLIR sufficient** — Thermal patterns don't need 9 Hz. 3 Hz saves CPU while giving 2-3 frames per car length at canyon speeds.

### Don't Repeat
- `avg > 0` guard in surface state blocked sub-zero detection — use `!= 0.0` check instead
- Two KiSTI processes fighting for `/dev/video0` → kill headless before starting fullscreen
- CLAHE at 9 Hz overwhelms Jetson CPU → throttle to 3 Hz
- OpenCV may return Y16 as flattened uint8 (120,320,1) → `.view(uint16).reshape(120,160)`

### Learnings Captured
- ✅ 11 learnings posted to Zeus Memory (zeus.aldc.io, tenant 11111111, user jk)
- 7x cce_success_log: Y16 radiometric, dew point ice detection, mock FLIR removal, 3Hz throttle, weather card, coaching bar, sector gating
- 4x cce_decision_log: Y16 FOURCC AGC disable, dew point vs fixed thresholds, 3Hz over CLAHE tuning, Intelligent default

### Future Ideas (scoped)
1. **Warm object detection** — Numpy hot-spot: running road temp baseline, detect pixel clusters >10°C above baseline, >20px connected component, 2+ consecutive frames. "WARM OBJECT AHEAD" + L/C/R position. No ML needed.
2. **YOLO animal detection** — Second visible-light camera (720p+) + YOLO on Jetson GPU for species ID. FLIR triggers, visible classifies.
3. **CAN-to-Strada alerts** — Pipe coaching text to Link ECU Strada 7" info line via CAN output. Needs Korlan cable.
4. **Restore mock for demo** — Re-enable mock CAN with a `--demo` flag for trade show / presentation mode.

### Next Session (kisti-29)
1. **Deploy to Jetson for road test** — Drive with FLIR active, observe real road temps + surface state changes
2. **CAN hardware** — Order PN 101-5104 ($75), DB9 breakout ($14), 120Ω terminator ($13)
3. **Warm object detection prototype** — Implement hot-spot algo in flir_lepton_reader.py
4. **Restore SI-Drive rotation** — Add `--demo` flag to main.py, re-enable mock when flag set
5. **Run full test suite** — Verify all tests pass with current changes

---

## Session: 2026-04-03 (kisti-27 — FLIR UI Overhaul + Mock Cleanup)

### Status: COMPLETE

### Completed
- **400°C bug fixed** — BGR fallback in `flir_lepton_reader.py` was scaling uint8 pixels to fake 100–600°C range. Fix: emit `frame_updated` from BGR path then `return` (skip temps). `_roi_mean_temp` fallback now returns `0.0` instead of raw non-radiometric value.
- **Mock FLIR removed entirely** — Removed `_flir_fl/fr/rl/rr` state vars, `_flir_timer` setup, start/stop calls, and `_flir_tick()` method from `can/kisti_can.py`. Also removed `MOCK_FLIR_HZ` import reference. Road surface data now comes ONLY from the real FLIR sensor.
- **`lap_in_progress` flag added** — `timing_manager.py:get_timing_data()` now includes `"lap_in_progress": timer._lap_start_ts is not None`. Sector strip gates on this flag.
- **Intelligent screen: live IR image** — `IntelligentScreenWidget` now accepts `flir_reader` param. `frame_updated` signal connected → `_on_frame_updated`. `_draw_flir_panel` rewritten: renders 160×120 uint16 frame as inferno-colormap QImage scaled to full 800×180px band. 5-stop numpy vectorized colormap (black→purple→orange→yellow→white), no matplotlib. Semi-transparent overlay labels.
- **Sport screen: no numeric FLIR** — `_paint_flir_summary` simplified to just `fillRect(BG_PANEL)`. Background tint (existing, alpha=15) is the road temp visual signal.
- **Sharp screen: sectors black until lap active** — `_draw_sector_strip` now checks `lap_in_progress`; draws black `BG_DARK` placeholder blocks when no lap is active. No more red fills from previous lap showing during canyon cruise.
- **Sharp screen: FLIR gradient bar** — `_draw_flir_strip` replaces large `{temp:.0f}°C` text with 3-zone heat-colored gradient bar (alpha=80, no text). Clean visual without distracting numbers.
- **BGR test added** — `test_poll_bgr_frame_emits_frame_updated_but_not_temps` verifies signal separation.
- **1006 tests passing, 0 failed** (baseline maintained).

### Files Changed
- `can/kisti_can.py` — Removed mock FLIR entirely (state vars + timer + _flir_tick)
- `sensors/flir_lepton_reader.py` — BGR fallback fix (emit frame, return early, 0.0 fallback in _roi_mean_temp)
- `timing/timing_manager.py` — Added `lap_in_progress` to get_timing_data()
- `ui/main_window.py` — Pass `flir_reader=flir_reader` to IntelligentScreenWidget
- `ui/intelligent_screen.py` — flir_reader param, _on_frame_updated slot, live IR image in _draw_flir_panel, inferno colormap
- `ui/sport_screen.py` — _paint_flir_summary → fillRect only (background tint is signal)
- `ui/sharp_screen.py` — lap_in_progress gate in _draw_sector_strip; gradient bar in _draw_flir_strip
- `tests/test_flir_lepton.py` — test_non_radiometric_passthrough → test_non_radiometric_returns_zero; added BGR test
- `tests/test_timing_manager.py` — test_all_keys_present: added lap_in_progress to expected_keys

### Key Decisions
- **No temps from BGR frames** — Non-radiometric AGC mode (PureThermal default) gives relative contrast, not Celsius. Emit frame for display, emit nothing for temps. Road temp stays stale (correct) rather than garbage.
- **Inferno colormap in-code** — 5 numpy stops avoids matplotlib dependency on Jetson. 3ms/frame worst case for 160×120.
- **Sector black vs invisible** — Black `BG_DARK` blocks communicate "sector tracking available but not active" better than hiding the strip entirely.
- **Background tint = FLIR signal in Sport/Sharp** — Full-screen alpha=15 tint provides at-a-glance road temp context without numbers cluttering the display.

### Don't Repeat
- BGR AGC frame dtype is NOT uint16 — it's uint8 with 3 channels. Can't use `frame.dtype == np.uint16` to detect it; must check `len(frame.shape) == 3`.
- `return mean_raw` in `_roi_mean_temp` for non-radiometric values (0–16383) was the source of 400°C readings. Always gate on `> 20000`.
- Mock FLIR was calling `update_flir()` (OLD brake API), NOT `update_road_surface()` — it was polluting the wrong bridge fields entirely.

### Learnings to Capture
- cce_success_log: FLIR 400°C fix + mock removal + live IR on Intelligent screen
- cce_decision_log: Non-radiometric BGR → emit frame, return early (no temps), 0.0 fallback

### Next Session (kisti-28)
1. **Deploy to Jetson** — `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"`
2. **Verify on Jetson** — Press `1`: should see live inferno IR image in middle band (y=160-340). Press `2`/`3`: background tint only, no FLIR numbers. Start timing: S1/S2/S3 should be black; press lap → activates.
3. **Confirm 400°C gone** — kisti-session.log should NOT show road temp warnings; values should be 0 (stale) or real radiometric Celsius.
4. **CAN hardware order** — JK action: PN 101-5104 ($75), DB9 breakout ($14), 120Ω terminator ($13)
5. **Boost Barn tune** — Aaron @ Boost Barn, WO #15562. KiSTI must be in-car with mic working.

---

## Session: 2026-04-03 (kisti-26 — FLIR Road Surface Integration Complete)

### Status: COMPLETE

### Completed
- **FLIR road surface refactor** — `BrakeTemps` → `RoadSurfaceTemps(left, center, right)` with 3 horizontal ROI strips. `frame_updated` signal emits raw uint16 numpy frames.
- **DiffState road_temp fields** — Added `road_temp_left/center/right/road_surface_ts`, `update_road_surface()` bridge method, `is_road_surface_stale(timeout=2.0)` helper. Old `brake_temp_fl/fr/rl/rr` + `update_flir()` kept for future ECU/CAN.
- **VideoModeWidget** — `LiveThermalFeed` (uint16→inferno colormap→QImage, staleness indicator) added to main window stack as index 3, key `4` shortcut.
- **3-zone displays on all 3 screens** — Intelligent, Sport, and Sharp all show L/CTR/R heat-colored road temps with full-page background tint (alpha=15).
- **Timing ms fix** — `int()` → `max(1, round())` in `timing_manager.py:get_timing_data()` — sub-ms lap times in tests now show as ≥1ms (resolves pre-existing `test_timing_after_lap` failure).
- **20 new tests** — `tests/test_flir_lepton.py` covering RoadSurfaceTemps, ROI strips, frame_updated signal, DiffState bridge, staleness.
- **1006 tests passing, 0 failed** (was 985 + timing failure). Committed and deployed to Jetson.

### Files Changed
- `sensors/flir_lepton_reader.py` — New data model + frame_updated signal
- `model/vehicle_state.py` — road_temp_* fields + update_road_surface() + is_road_surface_stale()
- `main.py` — Signal rewire + flir_reader to MainWindow
- `ui/widgets/camera_feeds.py` — LiveThermalFeed replaces IRCameraFeed
- `ui/video_mode.py` — flir_reader param, LiveThermalFeed wired to frame_updated
- `ui/main_window.py` — VideoModeWidget in stack, key 4
- `ui/intelligent_screen.py` — 3-zone L/CTR/R heat-colored cards + background tint
- `ui/sport_screen.py` — 3-column compact L/CTR/R display + background tint
- `ui/sharp_screen.py` — 3-zone horizontal display, safety vitals use road_temp_center
- `timing/timing_manager.py` — round() fix for best_lap_ms
- `tests/test_flir_lepton.py` — NEW: 20 tests

### Key Decisions
- **Road surface not brakes** — FLIR is forward-facing camera reading road surface (L/CTR/R strips), not 4 individual brake temps. Old brake fields kept for future ECU/CAN.
- **`_brake_heat_color` scale** — blue(≤5°C) → green(15°C) → yellow(40°C) → red(≥55°C). Road surface thermal range vs old brake range (150-500°C).
- **frame_updated signal on raw frames** — Emit before ROI processing so video mode gets full 160×120 for display while thermal reader gets cropped strips for temps.

### Learnings Captured
- ⚠️ Zeus API unreachable — captured in PROGRESS.md only
- cce_success_log: FLIR road surface integration (11 files, 20 tests, 1006 passing, timing fix)
- cce_decision_log: is_road_surface_stale() on DiffState + round() for ms timing conversions
- cce_failed_approach: int() truncation → 0 for sub-ms monotonic timestamps; fix = round()

### Don't Repeat
- `int(seconds * 1000)` silently truncates sub-ms timing values → 0. Use `max(1, round(best_s * 1000)) if best_s > 0 else 0`.
- Old `brake_temp_fl/fr/rl/rr` fields in DiffState are intentionally untouched — reserved for ECU/CAN brake data. Don't remove them.
- `is_road_surface_stale()` lives on DiffState itself, not on the bridge.
- Background tint alpha=15 (6% opacity) — anything higher visually competes with data.

### Next Session (kisti-27)
1. **Jetson live thermal verification** — Press `4` to confirm 160×120 inferno-mapped thermal in VideoMode. FLIR sensor must be connected via USB.
2. **CAN hardware order** — JK action: PN 101-5104 ($75), DB9 breakout ($14), 120Ω terminator ($13)
3. **Post-Boost Barn validation** — Do NOT tune SC-6 session trends until after real ECU data flowing (Boost Barn tune WO #15562, Aaron)

---

## Session: 2026-04-03 (kisti-24 — G5 Parser Dispatch Integration)

### Status: COMPLETE

### Completed
- **G5GenericDashParser integrated into live CAN dispatch** — `CanListenerThread._dispatch_frame()` now routes 0x3E8 frames through the parser instead of the old wrong decode_generic_dash_1/2/3 (big-endian, sequential IDs). Parser gates bridge calls on sub-frame availability. MOCK_ENABLED = True so live path is dormant until CAN sniff confirms ID.
- **Old decode functions kept** — decode_generic_dash_1/2/3 remain in kisti_can.py (test count must only go up). GD1/GD2/GD3 constants in can_config.py kept for import compat.
- **6 new dispatch integration tests** — TestG5DispatchIntegration: partial frame gating, full 4-frame cycle, gd1-not-called-before-frame0, wrong ID rejection, malformed frame rejection.
- **991 tests passing** (was 985, +6 dispatch integration tests). 1 pre-existing failure: test_timing_after_lap.

### Files Changed
- `can/kisti_can.py` — Added G5GenericDashParser import, `_g5_parser` instance in CanListenerThread.__init__, replaced dispatch lines 684-692 with parser-based dispatch
- `can/can_config.py` — Updated deprecation comment to reflect new reality
- `tests/test_can_decode.py` — Added TestG5DispatchIntegration (6 tests)

### Key Decisions
- **Keep old decode functions** — Tests cover them; can't remove. Live path uses parser, test path uses old functions. Both coexist cleanly.
- **Gate gd1/gd2/gd3 calls on sub-frame availability** — `if p.rpm is not None` prevents calling bridge before frame 0 arrives. Avoids bridge seeing all-zero data during first partial cycle.
- **Don't flip MOCK_ENABLED or CAN_INTERFACE** — Still deferred until CAN sniff confirms ID=0x3E8 and LE int16 byte order.

### Don't Repeat
- Don't batch all 3 bridge updates unconditionally per frame — gate each group on its primary field being non-None first
- Old sequential IDs (0x3E9, 0x3EA) are NOT in KISTI_CAN_IDS — removing those dispatch branches was correct
- CanListenerThread can be instantiated with a Mock bridge for unit tests (no Qt required for __init__)

### Learnings Captured
- ✅ cce_success_log: kisti-24 session summary (G5 dispatch integration, parser architecture, 6 tests)

### Next Session (kisti-25)
1. **Order CAN hardware** — JK action: PN 101-5104 ($75), DB9 breakout ($14), 120Ω terminator ($13)
2. **CAN sniff** — Verify CAN ID (expect 0x3E8), byte[0] cycles 0-13, LE int16 signals
3. **Flip to live** — `CAN_INTERFACE = "can1"`, `MOCK_ENABLED = False`, test with G5 running
4. **Post-Boost Barn: SC-6 session trends** — Do NOT start until after real ECU data flowing

---

## Session: 2026-04-03 (kisti-23 — usb_8dev Driver + G5 Generic Dash Parser)

### Status: COMPLETE

### Completed
- **usb_8dev kernel module built and installed** — OOT module for Tegra 5.15.148 kernel. Auto-loads on boot via `/etc/modules-load.d/usb_8dev.conf`. Udev rule auto-brings up `can1` at 1Mbit/s. Loopback test passed: raw CAN traffic verified clean. Korlan USB2CAN (0483:1234) now creates `/dev/can1` interface.
- **G5 Generic Dash protocol corrected** — Major finding: prior `can_config.py` had GENERIC_DASH_BASE_ID=0x360 (sequential frames 0x360-0x362, big-endian). Actual protocol: single CAN ID 0x3E8, multiplexed on byte[0], little-endian int16. Researched from open-source libraries + AIM PDF.
- **G5GenericDashParser written and tested** — New `can/g5_generic_dash.py`: stateful decoder, byte[0] mux dispatch, 6 sub-frames, 15+ properties (rpm/map/tps/temps/lambda/oil/fuel/battery/gear/4× wheel speeds), stale detection, reset. 44 unit tests, all passing.
- **Sector strip fix deployed** — `ui/sharp_screen.py:449`: Added `and sector_times[i] > 0` guard. Unrun sectors (time=0) now stay dark, not pre-populated as red blocks. Commit d139dd7.
- **985 tests passing** — Baseline 942 + 44 new G5GenericDashParser tests. 1 pre-existing failure: `test_timing_after_lap` in `test_timing_manager.py` (not regression).
- **Hardware blocker identified** — CAN cable (PN 101-5104) not yet ordered. Cannot do raw sniff until cable + DB9 breakout + 120Ω terminator arrive.

### Files Changed
- `can/can_config.py` — GENERIC_DASH_BASE_ID 0x360→0x3E8, COUNT 3→14, _G5_INPUT_IDS single ID, GD_FRAME_* constants, GD1/GD2/GD3 deprecated (kept for import compat)
- `can/g5_generic_dash.py` — **NEW**: G5GenericDashParser, mux decode, stale detection
- `tests/test_g5_generic_dash.py` — **NEW**: 44 tests (rejection, None-before-recv, all signals, stale, custom ID, reset)
- `ui/sharp_screen.py` — Sector strip fix at line 449
- `NEXT_SESSION_PROMPT.md` — Full handoff with priorities, hardware buy list, sniff plan

### Key Decisions
- **Single CAN ID > sequential frames** — Link G5 multiplexes 14 sub-frames on one ID, not 3 separate IDs. Simpler, more efficient, matches industry standard.
- **Little-endian signals** — Confirmed LE int16 via AIM + open-source decoders. Prior assumption of big-endian was wrong.
- **Defer integration until post-sniff** — Keep deprecated GD1/GD2/GD3 in can_config.py to avoid breaking kisti_can.py imports. Replace decode_ functions only after hardware verification.

### Learnings Captured
- ✅ cce_success_log: kisti-23 session summary (usb_8dev + G5 parser)
- ✅ cce_decision_log: G5 Generic Dash protocol architecture (single ID, LE int16, mux)

### Don't Repeat
- Verify CAN protocol specs against real hardware BEFORE writing decoders — open-source libraries may have different assumptions
- Always confirm byte order (BE vs LE) via actual hardware sniff — don't trust naming conventions
- Deprecated constants (GD1/GD2/GD3) must stay if downstream imports them by name — add deprecation comment, don't delete

### Next Session (kisti-24)
1. **Order CAN hardware** — JK action: PN 101-5104 ($75), DB9 breakout ($14), 120Ω terminator ($13). DTM4 pinout documented in NEXT_SESSION_PROMPT.md
2. **CAN sniff post-hardware** — Verify actual PCLink CAN ID (expect 0x3E8, may differ), byte[0] cycles 0-13, byte[1]=0x00, LE int16 signals
3. **Integrate G5GenericDashParser into kisti_can.py** — Replace decode_generic_dash_1/2/3 calls, change CAN_INTERFACE to "can1", flip MOCK_ENABLED to False
4. **Post-Boost Barn: SC-6 session trends** — Do NOT start until after real ECU data flowing (Boost Barn tune WO #15562, Aaron)

---

## Session: 2026-04-02 (kisti-27 — Coaching Deploy + SC Assessment)

### Status: COMPLETE

### Completed
- **Deployed coaching phases 2-5 to Jetson** — commit a3eb24c, 14 files, 1009 insertions. Voice ticker, TechniqueAnalyzer, ConditionRules, sector insight all live.
- **SC-1 through SC-6 assessment** — 33/60 = 55%. Coaches in the moment but has no memory. SC-6 (session trends) is the differentiator — not built.
- **GNOME broke on Jetson** — `systemctl restart gdm` clobbered headless setup. Next session must fix before KiSTI displays on Excelon.
- **Fresh session handoff written** — NEXT_SESSION_PROMPT.md updated and pushed (749cd5d).

### Files Changed
- `NEXT_SESSION_PROMPT.md` — Full handoff with GNOME fix instructions, SC scores, SC-2 fix plan

### Key Decisions
- **SC-6 deferred** — Don't build session trends until after Boost Barn real-data validation. Mock data thresholds (brake_pressure std dev) need real-world calibration first.
- **SC-2 fix next** — Shrink TechniqueAnalyzer window 30s→10s, min_samples 10→5. 5-min change, high coaching value.

### Learnings Captured
- ⚠️ Zeus API unreachable during exit — learnings in NEXT_SESSION_PROMPT.md only

### Don't Repeat
- **NEVER use `systemctl restart gdm` for Jetson deploy restart** — re-enables GNOME, breaks headless Excelon display. Use `~/k` wrapper instead.

### Next Session (kisti-28)
1. **Fix GNOME** — disable GDM, restore bash_profile startx line, reboot, verify Excelon display
2. **Fix SC-2** — `coaching/technique_analyzer.py` line 37: `_WINDOW = 30→10`, line 38: `_MIN_SAMPLES = 10→5`
3. **Check DuckDB sessions on Jetson** — query to see if real telemetry has been recorded

---

## Session: 2026-04-02 (kisti-25b — Grip Pills Removed + Full-Page FLIR Tint)

### Status: COMPLETE

### Completed
- **Grip context pills removed** — Removed OPTIMAL/COLD/ICE RISK/HOT pills from all 3 screens. Road temp text color (heat-colored) already communicates condition — label was redundant.
- **Full-page FLIR ambient tint** — All 3 screens now tint entire background based on road surface temp (alpha 15). Blue wash = cold, green = cool, amber = warm. Ambient context, not competing with data.
- **Intelligent road temp left-aligned** — Moved from x=60 to x=20, matching weather text alignment above.
- **Sport G-circle raised** — Center Y from 270→250 so magnitude reading doesn't float at bottom, disconnected from circle.
- **Sport + Sport# FLIR cleaned** — Removed grip hint labels and heat-tinted backgrounds from FLIR summary areas.
- **895 tests passing, deployed to Jetson.**

### Files Changed
- `ui/intelligent_screen.py` — Road temp left-aligned, grip pill removed, full-page tint
- `ui/sport_screen.py` — G-center raised, grip hint + heat bg removed, full-page tint
- `ui/sharp_screen.py` — Grip pill + heat bg removed from FLIR strip, full-page tint

### Key Decisions
- **Color = indicator** — Heat-colored text IS the condition indicator. Separate label pills are redundant on a driving display. Color is faster to parse than text at arm's length.
- **Full-page tint > partial strips** — If FLIR affects background, tint entire page (alpha 15 = 6% opacity) for ambient context. Partial colored strips look like UI elements competing with data.

### Learnings Captured
- ✅ cce_success_log: Grip pills removed, full-page FLIR tint (ZM: 42a684d6)
- ✅ cce_decision_log: Color IS the indicator, no separate labels (ZM: 4eb9f1f6)
- ✅ cce_decision_log: Full-page ambient tint > partial strips (ZM: 98f7c9f3)

### Don't Repeat
- Partial background color = UI element. Full background color = ambient context. Go all-in or don't do it.
- If color already encodes meaning, don't add a text label repeating it.

### Next Session (kisti-26)
1. Test on actual 800x480 Excelon (current verification on 1920x1080 DP-1)
2. Consider: proper `road_surface_temp` field in DiffState (replace brake_temp_fl proxy)
3. Wire TimingManager to populate Sport# with real sector/lap timing
4. On-track validation with real driving data (Aaron @ Boost Barn)

---

## Session: 2026-04-02 (kisti-25 — Screen Redesign Polish + FLIR Clarification)

### Status: COMPLETE
- FLIR clarification (forward-facing road surface camera, not 4 brakes), Sport# dual-mode, Intelligent reordered, widget z-order fix, mock data realistic. 895 tests, 6 learnings captured.

---

## Session: 2026-04-02 (kisti-24 — Screen Redesign Complete + Visual Verification)

### Status: COMPLETE

### Completed
- **Sport# canyon-capable redesign** — Split timing panel horizontally: left (0..480px) lap time 48pt Courier + predicted + best + theoretical, right (480..800px) G-force circle r=80 with 40-dot trail. Canyon intensity feedback alongside timing data. Dual-mode: track times + canyon commitment.
- **Intelligent status strip reorganized** — Surface badge (left, PRIMARY, 20pt, 44px tall pill) → SLIP delta (center) → DCCD bar (right, compact 160px). User feedback: "focusing too much on dccd lock up — not that primary". DCCD deprioritized.
- **G-force circle positioning fix** — Raised _G_CENTER_Y from 185→170 to prevent magnitude label bleeding into sector strip (y=280 boundary).
- **Visual verification on Jetson** — All 3 screens deployed and screenshotted via SSH + xdotool. Zero overlaps confirmed on Intelligent, Sport, and Sport# layouts. Prior session's icon overlap issues fully resolved by TopStatusBar removal + legacy widget hiding.
- **895 tests passing** — Full baseline maintained through all changes.
- **Deployed to Jetson** — Running on Excelon (PID 330047 → restarted to 330047+).

### Files Changed
- `ui/sharp_screen.py` — G-force circle + timing split layout, trail deque, _g_to_pixel(), canyon docstrings
- `ui/intelligent_screen.py` — Status strip reordered: Surface→SLIP→DCCD (compact)

### Key Decisions
- **Sport# = timing + G-force** — Not purely timing. Answers "Am I faster?" for BOTH track (lap times) and canyons (cornering intensity via G-force circle).
- **DCCD deprioritized** — Moved to compact bar on right side of Intelligent status strip (was primary left). User confirmed "not that primary".
- **Surface badge primary on Intelligent** — "What are the conditions?" answered best by surface state (DRY/WET/ICE/LOW GRIP), not DCCD lock percentage.

### Don't Repeat
- X auth changes after relaunch: `serverauth.*` file regenerated on startx restart, SSH loses access. Need to run xhost +local: from within the session context, or use the new auth file.
- xdotool hangs on compositorless X11 if XAUTHORITY is stale (exit code 124 from timeout).

### Next Session (kisti-25)
1. Merge kisti-headless branch to main if ready
2. Test on 800x480 Excelon (current verification was on 1920x1080 DP-1)
3. Consider adding axis labels (BRAKE/ACCEL/L/R) to Sport# G-force circle
4. Wire TimingManager to populate Sport# with real sector/lap data

---

## Session: 2026-04-01 (kisti-22 — FLIR Integration + Screen Layout Audit + Mock Data Optimization)

### Status: COMPLETE

### Completed
- **FLIR Lepton wired to main.py** — FLIRLeptonReader USB sensor now connected to DiffStateBridge via temps_updated signal. Auto-graceful fallback if camera absent. Lines 188-202 main.py, cleanup at line 770-771.
- **Mock data generators refactored** — MockCanGenerator now populates FLIR (180-155°C baseline), ambient weather (temp/humidity/pressure/density-alt/dew-point), wheel speeds, IMU, steering angle, brake pressure. Braking-correlated FLIR with 60/40 front bias + radiative cooling. Lines 915-1384 kisti_can.py.
- **All 3 screens visually audited & fixed** — Comprehensive layout audit identified 8 real overlaps (15+ flagged, many false positives). Sport Sharp: moved "BRAKE TEMPS" header above FLIR grid (was overlapping G-force circle). Sport: removed duplicate DCCD, added LAT G bar (±1.5g), added "BRAKE / STEER" header, fixed steering trace from solid fill to 2px cyan line. Intelligent: moved SLIP delta label up for y=440 boundary compliance.
- **Mock data jitter reduced** — Halved all tick rates (50Hz→20Hz for dynamics, 20Hz→10Hz for context, 9Hz→5Hz for FLIR) to smooth random walk oscillations during demo viewing.
- **SI-Drive rotation optimized** — Reduced mode cycle from 30s→15s for faster demo mode visibility (3 screens in 45s viewport).
- **Cyan block bug fixed** — QPainter brush state leaked from G-force circle (setBrush CYAN) into brake trace drawRect(). 3 failed attempts before finding root cause. Fix: `p.setBrush(Qt.BrushStyle.NoBrush)` before drawRect. Also discovered Jetson __pycache__ race condition in deploy script.
- **Steering trace removed from brake panel** — Dense time-series line overlays rendered poorly regardless of subsampling. Steering already shown in STEER performance bar. Brake panel now brake-only (cleaner).
- **895 tests passing** — all green. Deployed to Jetson, live on Excelon (PID 125537, DISPLAY=:0).

### Files Changed
- `main.py` — FLIRLeptonReader wiring (lines 188-202, cleanup 770-771)
- `can/can_config.py` — MOCK_FLIR_HZ=9, reduced all mock rates
- `can/kisti_can.py` — _flir_tick/_ambient_tick methods, FLIR/weather state vars, timer registration (lines 915-1384)
- `ui/sharp_screen.py` — FLIR grid header repositioning, G-force circle displacement, vitals label height, AWD spacing
- `ui/sport_screen.py` — removed duplicate DCCD, added LAT G bar, added "BRAKE / STEER" label, steering trace line rendering
- `ui/intelligent_screen.py` — SLIP delta y-position adjustment

### Files Changed
- `model/vehicle_state.py` — FLIR fields on DiffState + DiffStateBridge.update_flir()
- `ui/sharp_screen.py` — Full redesign
- `ui/sport_screen.py` — Full redesign
- `ui/intelligent_screen.py` — Full redesign
- `sensors/flir_lepton_reader.py` — NEW FLIR Lepton reader
- `tests/test_modes.py` — Fix 2 failures, add 10 FLIR tests
- `rs3/shift_led_investigation.md`, `rs3/README.md` — RS3 docs
- `NEXT_SESSION_PROMPT.md` — kisti-22 handoff

### Key Decisions
- **Braking-correlated FLIR temps** — Front axle biased 60/40 (more weight transfer) with radiative cooling curves. Realistic thermal dynamics for demo viewing without active driving data.
- **Steering trace as line, not fill** — Switched from overlapping alpha-filled rectangles (rendered as solid blue block) to QPainter line trace between consecutive samples. Shows waveform shape, visually distinct from brake bars.
- **SI-Drive demo rotation 15s** — Reduced from 30s to 15s for passive viewing comfort (all 3 modes visible within 45s window).
- **Mock rate halving** — Higher Hz amplifies random walk oscillations. Halving rates smooths relative movement while preserving dynamics range.

### Learnings Captured
- ✅ cce_success_log: FLIR integration + screen layout audit + mock optimization (ZM: 807937f9)
- ✅ cce_decision_log: SI-Drive demo rotation speed 15s (ZM: 426d0a45)
- ✅ cce_decision_log: Screen layout audit - false positives vs real overlaps (ZM: 4b021367)
- ✅ cce_failed_approach: X11 auth blocker recovery (stale processes + serverauth cleanup) (ZM: 1cfb0435)
- ✅ cce_failed_approach: QPainter brush state leak — cyan block from G-force dot brush (ZM: afe74623)
- ✅ cce_decision_log: Remove steering trace from brake chart — brake-only cleaner (ZM: 92c7781e)

### Don't Repeat
- AiM MXG shift LEDs are NOT CAN-addressable — RS3 math channels only
- SI-Drive OEM CAN values (1/2/3) differ from Link remapped (0/1/2) — RS3 uses remapped
- Worktree agents may write to main repo via hooks — always Read before Write
- _heat_color pattern for brakes: blue (<150) → green (<300) → yellow (<450) → red (>500)
- Stack default = Sport (index 1), not Intelligent (index 0)
- Screen layout pixel-math overlaps often don't manifest visually (separate panels, padding) — test on hardware first
- X11 auth recovery: full cleanup (pkill -9, rm /tmp/serverauth.*, rm /tmp/kisti-session.lock) before startx
- Steering visualization: line trace (QPainter.drawLine) > filled rectangles for dense time-series data
- QPainter drawRect() inherits current brush — ALWAYS setBrush(NoBrush) before border-only drawRect
- Jetson deploy: clear __pycache__ before restart — race condition compiles .pyc from old source
- Debug visual artifacts: check painter state leaks from PREVIOUS paint method FIRST, not just current method

### Next Session (kisti-23)
1. On-track validation with Aaron @ Boost Barn tune session (real driving data, real FLIR)
2. Frontier cloud LLM enable/disable toggle (currently disabled for GPU headroom)
3. Event quotes archival check (47 categories, all wired in main.py)
4. WiFi credential persistence across reboots (Heckler + JK iPhone priority ordering)

---

## Session: 2026-04-01 (kisti-19 — Display Auth Fix + Alert Mode-Awareness)

### Status: COMPLETE

### Completed
- **Jetson X11 auth blocker FIXED** — Removed GDM entirely. getty auto-login + startx pipeline. No more auth errors, no GNOME interference. KiSTI fullscreen on Excelon confirmed.
- **Alert engine mode-aware suppression** — Added `_si_drive_mode` attribute, `set_si_drive_mode()` method, mode-based suppression in `_fire()`: Intelligent fires all, Sport suppresses INFO, Sport# suppresses INFO+ADVISORY, CRITICAL always fires.
- **Critical flash overlay** — NEW ui/widgets/critical_flash_overlay.py (75 lines). QPainter transparent overlay, red/amber border flash on WARNING/CRITICAL in Sport# mode. Integrated to main.py flash_alert().
- **Qt fullscreen fixed** — setFixedSize blocks WM negotiation; changed to setMinimumSize + FramelessWindowHint + WindowStaysOnTopHint. showFullScreen() now honored.
- **One-command deploy** — ~/k wrapper: commit + push + deploy-to-jetson.sh. Per user feedback "use the same script all the time".
- **885 tests passing** — 879 baseline + 6 new mode suppression tests.
- **All commits pushed** — origin/kisti-headless, ready for merge.

### Files Changed
- `scripts/kisti-session` — auto-detect DISPLAY from /tmp/.X11-unix/, XAUTHORITY fallback, xhost +local:
- `scripts/jetson/gdm-custom.conf` — WaylandEnable=false (partial mitigation)
- `scripts/jetson/setup-autologin.sh` — NEW, one-time config: getty + .bash_profile startx integration
- `scripts/jetson/relaunch.sh` — detects GDM vs startx modes, handles both, proper display detection
- `scripts/deploy-to-jetson.sh` — simplified to SSH pull+relaunch
- `~/k` — NEW one-command deploy wrapper
- `alerts/alert_engine.py` — _si_drive_mode, set_si_drive_mode(), suppression logic
- `ui/widgets/critical_flash_overlay.py` — NEW transparent overlay, QPainter red/amber flash
- `ui/main_window.py` — setMinimumSize, frameless hints, flash_alert(), overlay wiring
- `tests/test_alerts.py` — 6 new mode suppression tests

### Key Decisions
- **Remove GDM entirely** — getty + startx simpler than X auth boundary crossing, saves 500MB memory, deterministic boot
- **Qt fullscreen needs both constraints AND hints** — setFixedSize blocks negotiation; must use setMinimumSize + FramelessWindowHint + WindowStaysOnTopHint
- **Alert suppression matrix per SI-Drive mode** — Intelligent=all, Sport=suppress INFO, Sport#=suppress INFO+ADVISORY, CRITICAL always fires

### Learnings Captured
- ✅ cce_success_log: Complete kisti-19 summary (ZM: 431249b7...)
- ✅ cce_failed_approach: XAUTHORITY crossing UID boundary (ZM: 4640533b...)
- ✅ cce_failed_approach: WaylandEnable=false insufficient (ZM: 7b24d23d...)
- ✅ cce_failed_approach: xhost +local: doesn't prevent WM clipping (ZM: fd91-4fcf...)
- ✅ cce_decision_log: Remove GDM entirely (ZM: b94c93c8...)
- ✅ cce_decision_log: Qt fullscreen constraints (ZM: 24839bc3...)

### Don't Repeat
- Haiku hallucinates on automotive domain specifics — always add system prompt context
- Whisper adds punctuation — ALWAYS strip before string matching
- dcli no Linux ARM64 binary
- Zeus Memory POST returns ZMID but GET 404 — don't rely on Zeus for plan storage
- Always use ZEUS_ALDC_API_KEY (management tenant) for shared Zeus memories
- **GDM X auth boundaries are strict** — SSH uid 1000 can't access uid 128 greeter cookies. Simpler to remove GDM than cross boundary.
- **Qt fullscreen under WM** — setFixedSize creates hard constraint that blocks fullscreen negotiation. Need setMinimumSize + frameless/stay-on-top hints.
- **X display detection** — ps output matches timestamps, not display numbers. Use /tmp/.X11-unix/ socket filenames instead.
- **Never give multi-step SSH commands** — wrap in shell script or provide single ~/k wrapper.

### Next Session (kisti-21)
1. **Design review** — User feedback: screens feel "duplicative of the linkecu mxg". Clarify KiSTI's unique value (AI coaching? predictive shifting? grip analysis? sector comparison?). Define content per SI-Drive mode.
2. Verify visual layout on Excelon (3 screens 800x480)
3. Integration tests with real CAN data
4. Deploy to Aaron @ Boost Barn for tune session

---

## Session: 2026-04-01 (kisti-19 — Frontier + Wake Word)
- Frontier cloud AI working, wake word punctuation fix, 864 tests passing
- Don't repeat: Whisper adds punctuation; dcli no ARM64

## Session: 2026-03-31 (kisti-18 — Streaming TTS)
- Streaming TTS 4s→1s, Whisper systemd, 864 tests
- Don't repeat: Don't truncate Intelligent mode sentences
