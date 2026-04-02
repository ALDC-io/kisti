# KiSTI — Next Session Prompt (kisti-22: Visual Verify + FLIR Hardware + Boost Barn Prep)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 895 tests, all passing
**Branch**: `kisti-headless`
**Latest commit**: `b1efc19` pushed to origin, deployed to Jetson (running as PID 75796)

## Section 1: What Was Done (kisti-21 session)

### Screen Redesign — Zero MXG Overlap
All 3 screens stripped of everything the AiM MXG Strada 7" already shows (gear, speed, RPM, boost, lambda, oil, coolant, throttle, IDC, battery, fuel, IAT, MAP, TPS, ethanol). Now shows ONLY what the MXG cannot.

**Sport Sharp** (`ui/sharp_screen.py`):
- Delta bar (top) + Timing with theoretical best (left)
- FLIR 4-corner brake temps in heat-colored 2x2 grid (right, y=80..170)
- G-force micro circle 55px with 5-frame trail (right, y=170..250)
- AWD status strip: DCCD bar + surface badge + ABS/VDC dots (right, y=250..280)
- Sector strip (y=280..320)
- Brake + STEERING trace replacing throttle — trail-brake analysis (y=320..380)
- 5-zone safety vitals: OIL | COOL | OIL T | BRK T (new) | DCCD — dim-until-warning (y=380..440)

**Sport** (`ui/sport_screen.py`):
- DCCD bar + surface + slip + FLIR 2x2 summary (top)
- DCCD/brake/steering/yaw performance bars + G-force circle with 100-dot trail (middle)
- Wheel speed deltas + brake/steering trace (bottom)

**Intelligent** (`ui/intelligent_screen.py`):
- Expanded weather card (Yoctopuce) + warm-up + DCCD + GPS fix (top)
- FLIR 4-corner brake temps + vehicle health overview (middle)
- Brake temp sparklines + wheel speed delta bars (bottom)

### DiffState FLIR Fields
`model/vehicle_state.py`: `brake_temp_fl/fr/rl/rr`, `flir_available`, `flir_frame_ts`, `update_flir()`, `is_flir_stale(timeout=2.0)`

### FLIR Lepton Reader
`sensors/flir_lepton_reader.py`: PureThermal USB reader. Auto-detects 160x120 thermal camera on /dev/video0-4. ROI-based brake temp extraction. Radiometric centi-Kelvin conversion. Follows Yoctopuce QObject+QTimer+Signal pattern. Currently shows "FLIR NOT CONNECTED" — no hardware wired yet.

### RS3 Shift LED Investigation
`rs3/shift_led_investigation.md`: AiM MXG shift LEDs are firmware-controlled (NOT CAN-addressable). Solution: RS3 math channels read SI-Drive CAN frame (0x6B0) for mode-aware shift thresholds (I=off, S=5500, S#=6800 RPM).

### Test Fixes
- Fixed 2 pre-existing stack index failures (default = Sport index 1, not Intelligent index 0)
- Added 10 FLIR tests: field defaults, staleness, snapshot copy, heat colors, all 3 screens accept data
- 885 → 895 tests, all passing

## Section 2: Prioritized TODO

### 1. Visual verification on Jetson
- KiSTI is already running on the Excelon (PID 75796)
- Rotate SI-Drive knob to each mode, check layout spacing, font readability, color contrast on 800x480
- All FLIR cells show "FLIR NOT CONNECTED" or "--- " (expected)
- Verify G-force circle renders, brake/steering trace scrolls, weather card populates
- Note any layout tweaks needed (font too small, elements overlapping, etc.)

### 2. Wire FLIR Lepton hardware
- Confirm camera model (FLIR Lepton 3.x with PureThermal breakout)
- Install opencv-python on Jetson: `pip3 install opencv-python-headless`
- Add udev rule for PureThermal USB: `SUBSYSTEM=="usb", ATTRS{idVendor}=="1e4e", ATTRS{idProduct}=="0100", MODE="0666"`
- Wire in main.py: instantiate `FLIRLeptonReader`, connect `temps_updated` signal to `bridge.update_flir()`
- Calibrate ROI rectangles for camera mounting position (which pixels = which brake disc)
- This is the hardest part — ROI depends on physical camera placement

### 3. RS3 shift light config at Boost Barn
- Bring laptop with Race Studio 3
- Follow `rs3/shift_led_investigation.md` pre-tune checklist
- Key: define SI_Drive_Mode CAN channel (0x6B0 byte 0 uint8), create ShiftPoint/ShiftWarning math channels
- Verify CAN byte order (BE vs LE) with live data before configuring RS3
- Save RS3 config backup before and after

### 4. Mock CAN data for screens
- The mock CAN generator may need updates to populate the new fields screens expect
- Check `data/mock_generator.py` — does it generate DCCD, wheel speeds, IMU, steering, brake pressure?
- If not, update it so screens render properly without real CAN hardware

### 5. FLIR ROI calibration tool
- Future: build a simple calibration UI that shows the thermal image with draggable ROI rectangles
- Or: manual calibration by pointing camera at known hot spots, adjusting ROI in config

## Section 3: Key Files

| File | What It Does |
|------|-------------|
| `ui/sharp_screen.py` | Sport Sharp — timing, FLIR, G-micro, AWD, traces (803 lines) |
| `ui/sport_screen.py` | Sport — DCCD, FLIR, G-force circle, steering/yaw, traces (591 lines) |
| `ui/intelligent_screen.py` | Intelligent — weather, FLIR, health, sparklines, wheel deltas (952 lines) |
| `model/vehicle_state.py` | DiffState + DiffStateBridge — all telemetry fields + FLIR |
| `sensors/flir_lepton_reader.py` | FLIR Lepton PureThermal USB reader (214 lines) |
| `sensors/yoctopuce_reader.py` | Yoctopuce weather sensor (pattern reference) |
| `rs3/shift_led_investigation.md` | RS3 shift light config guide |
| `scripts/deploy-to-jetson.sh` | SSH pull + relaunch |
| `~/k` | One-command deploy wrapper (commit + push + deploy) |
| `tests/test_modes.py` | 39 tests: modes, status bar, FLIR fields |

## Section 4: Architecture

### Screen data flow
```
CAN bus (1 Mbps)  →  kisti_can.py  →  DiffStateBridge.update_*()
Yoctopuce USB     →  yoctopuce_reader.py  →  DiffStateBridge.update_ambient()
FLIR USB          →  flir_lepton_reader.py  →  DiffStateBridge.update_flir()
TimingManager     →  DiffStateBridge.update_timing()

DiffStateBridge.snapshot()  →  MainWindow (20Hz QTimer)
  → active_screen.update_state(snap)
  → sharp_screen.update_timing(timing_dict)
```

### Screen design philosophy
- **MXG Strada** = critical instruments (RPM, speed, gear, boost, shift lights, oil, coolant, lambda)
- **KiSTI Excelon** = context the MXG can't show (FLIR thermal, G-forces, DCCD/AWD, wheel dynamics, timing, weather, steering analysis, AI insights)

### FLIR integration gap
The reader (`flir_lepton_reader.py`) is built but not wired into `main.py`. The connection point is:
```python
flir = FLIRLeptonReader()
flir.temps_updated.connect(lambda t: bridge.update_flir(t.fl, t.fr, t.rl, t.rr))
flir.start()
```

## Section 5: Don't Repeat
- AiM MXG shift LEDs are NOT CAN-addressable — RS3 math channels only
- SI-Drive OEM values (1/2/3) differ from Link remapped values (0/1/2) — RS3 uses remapped
- `_heat_color` pattern: blue (<150) → green (<300) → yellow (<450) → red (>500) for brakes
- Worktree agents may apply changes via hooks — verify file state before writing
- Stack default index = 1 (Sport), not 0 (Intelligent) — tests updated to match
- Never give multi-step SSH commands — use `~/k` for deploy
