# KiSTI - Progress

## Session: 2026-04-01 (kisti-23 — "Less Is More" Screen Redesign)

### Status: 85% COMPLETE — Pending Icon Overlap Fix + Sport# Canyon Redesign

### Completed
- **Sport screen locked** — User confirmed perfect. No changes. 462 lines, removed 111 lines of dead code (`_paint_wheel_speeds()` + `_paint_brake_steering_trace()`). G-force circle r=140 (575, 270), performance bars 28px tall, 13pt fonts.
- **Sport# redesigned to 4-section timing layout** — Delta bar (y=0..90) + lap time 60pt Courier (y=90..280) + sectors (y=280..380) + safety vitals 4-zone (y=380..480). Removed DCCD zone (was zone 5), removed FLIR temps, removed G-force micro. 457 lines, clean timing-focused.
- **Intelligent redesigned to 3-section simplification** — Weather card huge fonts (temp 56pt, humidity 36pt, y=0..160) + FLIR 2x2 grid 370px cells heat-colored + warm-up badge (y=160..340) + status strip DCCD/surface/SLIP (y=340..480). Removed sparklines, wheel deltas, health panel, dew point, density altitude. 525 lines, readable at arm's length.
- **Main window fixes** — Removed TopStatusBar instantiation, hid legacy widgets (KistiModeWidget, DiffModeWidget, TrackModeWidget). Fixed z-order ghost text/blue square artifacts.
- **Mock data optimized** — Reduced rates (50Hz→20Hz dynamics, 20Hz→10Hz context, 9Hz→5Hz FLIR), reduced steering noise ±15°→±3°, SI-Drive rotation 15s.
- **804+ tests passing** — All tests green throughout session.

### Files Changed
- `ui/sport_screen.py` — Minor: removed dead methods (~111 lines)
- `ui/sharp_screen.py` — Major rewrite: 4-section layout, removed dynamics/FLIR/G-micro/AWD/traces, safety vitals 4 zones only
- `ui/intelligent_screen.py` — Major rewrite: 3 sections (weather/FLIR/status), removed sparklines/wheel deltas/health
- `ui/main_window.py` — Removed TopStatusBar, hid legacy widgets
- `data/mock_generator.py` — Reduced update rates, noise, SI-Drive rotation

### Pending Issues (Priority Order)
1. **Icon overlaps** (CRITICAL) — User reported top-left overlaps on Intelligent (DCCD bar vs surface badge) and Sport (DCCD vs FLIR labels). Need closeup screenshots, bounding box measurement, repositioning.
2. **Sport# canyon redesign** — User: "sport sharp... just a big lap time? remember we'll be driving canyons as well right?" Currently timing-only. Need G-force circle (Option A: replace sectors, Option B: split lap time horizontally, Option C: corner of vitals).
3. **DCCD deprioritization** — User: "i think we may be focusing too much on dccd lock up — it's not that primary is it?" If overlapping, shrink/move it. May not be essential to all screens.

### Key Decisions
- **One question per screen** — Sport="How am I driving?", Sport#="Am I faster?" (with canyon feedback TBD), Intelligent="What are the conditions?"
- **Arm's length readability** — Min 13pt for bars, 40pt+ for primary numbers. Test on Excelon at 1m distance.
- **Timing-first Sport#** — Initially stripped to lap time + delta + sectors (no DCCD, no FLIR, no G-force micro). User feedback suggests canyon driving requires G-force intensity feedback — design pending.

### Learnings Captured
- ✅ cce_success_log: Widget z-order ghost text fix — remove entirely instead of hiding (ZM: 26702eb8)
- ✅ cce_failed_approach: Pycache stale bytecode on deploy — rm __pycache__ after git pull (ZM: 49bce6c2)
- ✅ cce_decision_log: Icon overlap debugging requires hardware screenshots (ZM: 69d0bc07)
- ✅ cce_decision_log: DCCD lock % not a primary indicator — deprioritize (ZM: 22015015)
- ✅ cce_decision_log: Sport# must be canyon-capable, not just track timing (ZM: b8f3ccd4)
- ✅ cce_decision_log: 800x480 arm's length readability — min font sizes established (ZM: d2d96d63)

### Don't Repeat (From This Session)
- Z-order battles: hidden widgets still paint. Remove instead of hide.
- Pycache stale bytecode: clear after git pull, before restart.
- Arm's length fonts: min 13pt for readability on 800x480 at 1m.
- User drives both track + canyon — Sport# must serve both modes.

### Next Session (kisti-24)
1. **Deploy & screenshot** — commit redesign, push, deploy to Jetson, capture closeup screenshots of all 3 screens (focus on icon overlaps)
2. **Fix icon overlaps** — measure bounding boxes, adjust DCCD/surface badge/SLIP delta positioning on Intelligent; DCCD/FLIR labels on Sport
3. **Sport# canyon redesign** — decide G-force placement, implement, test on hardware
4. **Test baseline** — verify 804+ tests still passing, run `pytest -x -q`

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
