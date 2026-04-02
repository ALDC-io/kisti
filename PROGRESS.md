# KiSTI - Progress

## Session: 2026-04-01 (kisti-21/22 — Screen Redesign + FLIR + Tests + Deploy)

### Status: COMPLETE

### Completed
- **Sport Sharp redesigned** — Removed 120px gear/speed/RPM. Replaced with FLIR 4-corner brake temps (heat-colored 2x2), G-force micro circle (55px, 5-frame trail), AWD status strip (DCCD + surface + ABS/VDC). Throttle trace → steering trace (trail-brake analysis). 5-zone safety vitals (added BRK T). Theoretical best time added to timing.
- **Sport redesigned** — Removed gear/speed/RPM/boost arc/oil/coolant/lambda/IDC. New: DCCD bar + FLIR summary (top), steering + yaw bars + G-force circle (middle), wheel deltas + brake/steering trace (bottom). G-force 100-dot trail preserved exactly.
- **Intelligent redesigned** — Removed gear/speed/boost/RPM/THR/MAP/TPS/oil/coolant/IAT/battery/lambda/IDC. New: expanded weather card + warm-up + DCCD + GPS (top), FLIR 4-corner + vehicle health (middle), brake temp sparklines + wheel deltas (bottom).
- **DiffState FLIR fields** — Added brake_temp_fl/fr/rl/rr, flir_available, flir_frame_ts, update_flir() bridge method, is_flir_stale(timeout=2.0).
- **FLIR Lepton reader** — sensors/flir_lepton_reader.py, PureThermal USB, auto-detect 160x120, ROI-based brake temp extraction, radiometric centi-Kelvin conversion. Not yet wired to main.py.
- **RS3 shift LED investigation** — rs3/shift_led_investigation.md. AiM shift LEDs not CAN-addressable. RS3 math channels reading SI-Drive 0x6B0 for mode-aware thresholds.
- **Test fixes** — Fixed 2 pre-existing failures (stack default = Sport index 1). Added 10 FLIR tests.
- **895 tests passing** — all green.
- **Deployed to Jetson** — KiSTI running on Excelon (PID 75796).

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
- **MXG = critical, KiSTI = context** — All 3 screens show ONLY data MXG cannot: FLIR thermal, G-forces, DCCD/AWD, wheel deltas, timing, weather, steering/yaw, brake pressure, surface state
- **Safety vitals exception** — Oil PSI, coolant, oil temp stay dim-until-warning on Sport Sharp. FLIR hottest corner added as 5th zone
- **Steering replaces throttle in traces** — brake+steering = trail-brake analysis. MXG shows throttle.

### Learnings Captured
- ✅ cce_success_log: Full screen redesign + FLIR + tests + deploy (ZM: dbe6223f)
- ✅ cce_decision_log: AiM MXG shift LED RS3 math channel approach (ZM: 4a86e2eb)
- ✅ cce_decision_log: MXG=critical/KiSTI=context display philosophy (ZM: fe08250f)
- ✅ cce_failed_approach: Worktree agents apply changes via hooks (ZM: c66b52f1)

### Don't Repeat
- AiM MXG shift LEDs are NOT CAN-addressable — RS3 math channels only
- SI-Drive OEM CAN values (1/2/3) differ from Link remapped (0/1/2) — RS3 uses remapped
- Worktree agents may write to main repo via hooks — always Read before Write
- _heat_color pattern for brakes: blue (<150) → green (<300) → yellow (<450) → red (>500)
- Stack default = Sport (index 1), not Intelligent (index 0)

### Next Session (kisti-22)
1. Visual verify all 3 screens on 800x480 Excelon (KiSTI already running)
2. Wire FLIR reader into main.py (connect temps_updated → bridge.update_flir)
3. Update mock_generator.py to populate FLIR/DCCD/IMU/steering/brake fields for demo mode
4. RS3 shift light config at Boost Barn with Aaron

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
