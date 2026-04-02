# KiSTI — Next Session Prompt (kisti-22: FLIR Integration + Visual Verify)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 885 tests (2 pre-existing failures: stack default index)
**Branch**: `kisti-headless`
**Latest commit**: `ef72eb2` pushed to origin

## Section 1: What Was Done (kisti-21 session)

### All 3 screens redesigned — zero MXG overlap
Every screen stripped of gear/speed/RPM/boost/lambda/oil/coolant/throttle/IDC/battery/fuel/IAT/MAP/TPS.
Now shows ONLY what the AiM MXG Strada 7" cannot display.

**Sport Sharp** (`ui/sharp_screen.py`):
- Delta bar + timing (left) + FLIR 4-corner temps + G-force micro (55px) + AWD strip (right)
- Sectors, brake+steering trace, 5-zone safety vitals (OIL/COOL/OILT/BRKT/DCCD)
- Theoretical best time added below BEST

**Sport** (`ui/sport_screen.py`):
- DCCD bar + surface + slip + FLIR 2x2 (top)
- DCCD/brake/steering/yaw bars + G-force circle 100-dot trail (middle)
- Wheel speed deltas + brake/steering trace (bottom)

**Intelligent** (`ui/intelligent_screen.py`):
- Weather card expanded + warm-up + DCCD + GPS (top)
- FLIR 4-corner temps + vehicle health overview (middle)
- Brake temp sparklines + wheel speed deltas (bottom)

### DiffState FLIR fields added
`model/vehicle_state.py`: `brake_temp_fl/fr/rl/rr`, `flir_available`, `flir_frame_ts`, `update_flir()`, `is_flir_stale(timeout=2.0)`

### RS3 shift LED investigation
`rs3/shift_led_investigation.md`: AiM shift LEDs need RS3 math channels reading SI-Drive CAN (0x6B0) for mode-aware thresholds.

## Section 2: Prioritized TODO

### 1. Visual verification on Jetson
- Deploy: `~/k` (one command)
- Rotate SI-Drive to each mode, verify screens render on 800x480 Excelon
- Check layout spacing, font readability, color visibility
- Currently all FLIR cells show "FLIR NOT CONNECTED" (expected — no sensor wired yet)

### 2. FLIR Lepton integration
- **Hardware**: FLIR Lepton (likely PureThermal USB breakout)
- **Pattern**: Follow Yoctopuce reader at `sensors/yoctopuce_reader.py` (QObject + QTimer polling)
- **New file**: `sensors/flir_lepton_reader.py`
- **Dependencies**: Need `opencv-python` or `pyuvc` on Jetson
- **Udev**: Add FLIR USB rule to `scripts/jetson/` (vendor 0x1e4e)
- **Wire**: Instantiate in `main.py`, connect to `bridge.update_flir(fl, fr, rl, rr)`
- **Challenge**: Extracting per-corner brake temps from a thermal image requires ROI mapping (camera position → brake disc regions). May need calibration step.

### 3. Fix pre-existing test failures
- `tests/test_modes.py::TestMainWindowSIDrive::test_si_drive_switches_stack` — expects stack index 0 (Intelligent) but default is 1 (Sport)
- `tests/test_modes.py::TestMainWindowSIDrive::test_invalid_mode_ignored` — same issue
- Fix: update test expectations OR update `main_window.py` default

### 4. FLIR tests
- Add to `tests/test_modes.py`: FLIR field copy in snapshot, staleness, heat color thresholds

### 5. Boost Barn tune session
- RS3 config for SI-Drive mode-aware shift lights (see `rs3/shift_led_investigation.md`)
- Verify CAN byte order (BE vs LE) with live data
- Verify KiSTI screen layout during actual driving

## Section 3: Key Files

| File | What It Does |
|------|-------------|
| `ui/sharp_screen.py` | Sport Sharp — timing, FLIR, G-micro, AWD, traces |
| `ui/sport_screen.py` | Sport — DCCD, FLIR, G-force circle, steering/yaw, traces |
| `ui/intelligent_screen.py` | Intelligent — weather, FLIR, health, sparklines, wheel deltas |
| `model/vehicle_state.py` | DiffState + DiffStateBridge (FLIR fields at lines ~223-228, ~240) |
| `sensors/yoctopuce_reader.py` | Pattern for FLIR reader (QObject + QTimer + signal) |
| `rs3/shift_led_investigation.md` | RS3 shift light config guide |
| `ui/widgets/sti_heatmap_widget.py` | Reference for heat color functions |

## Section 4: Architecture Notes

All 3 screens are pure QPainter (`paintEvent`). Data arrives via:
- `update_state(DiffState)` at 20Hz (CAN + Yoctopuce + FLIR)
- `update_timing(dict)` at 4Hz (TimingManager → only Sport Sharp uses this)

FLIR integration will require:
1. Camera → per-frame thermal image (160x120 uint16)
2. ROI extraction → 4 brake disc regions → temperature values
3. Feed to `bridge.update_flir(fl, fr, rl, rr)`

The ROI mapping (which pixels = which brake disc) depends on camera mounting position. This will need a calibration/config step.
