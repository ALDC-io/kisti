# KiSTI - Progress

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
