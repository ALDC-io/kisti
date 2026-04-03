# NEXT SESSION PROMPT — KiSTI kisti-28

**Branch**: `kisti-headless`  
**Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)  
**Run KiSTI**: `~/k`

---

## What Was Done (kisti-27)

1. **400°C FLIR bug fixed** — BGR fallback in `sensors/flir_lepton_reader.py` was scaling 0-255 uint8 pixels to fake 100-600°C. Fix: BGR path now emits `frame_updated` then returns immediately (no temps). `_roi_mean_temp` fallback returns `0.0` instead of raw value.

2. **Mock FLIR removed entirely** — Deleted `_flir_fl/fr/rl/rr` state vars, `_flir_timer`, `_flir_tick()` from `can/kisti_can.py`. Road surface data now comes ONLY from real FLIR.

3. **`lap_in_progress` flag** — Added to `timing/timing_manager.py:get_timing_data()`. Gates sector strip rendering.

4. **Intelligent screen: live IR image** — `IntelligentScreenWidget` wired to `flir_reader.frame_updated`. Renders 160×120 uint16 frame as inferno-colormap QImage scaled to full 800×180px band. 5-stop numpy colormap (no matplotlib). Semi-transparent label overlay.

5. **Sport screen: FLIR panel removed** — Just `fillRect(BG_PANEL)`. Background tint (alpha=15) is the road temp signal.

6. **Sharp screen: sectors black until lap active** — `lap_in_progress` gate draws `BG_DARK` placeholder blocks when no lap running. No stale red fills during canyon cruise.

7. **Sharp screen: FLIR gradient bar** — 3-zone heat-colored bar (alpha=80), no text. Replaces `{temp:.0f}°C` labels.

8. **Tests updated** — `test_non_radiometric_returns_zero` (was passthrough), BGR signal test added. `test_all_keys_present` includes `lap_in_progress`. **1006 passed, 0 failed.**

---

## Current State

**All changes UNCOMMITTED.** Tests passing. Ready to commit and deploy.

---

## TODO — In Priority Order

### 1. Commit all changes
```bash
cd /home/aldc/repos/kisti
git add can/kisti_can.py sensors/flir_lepton_reader.py timing/timing_manager.py \
        ui/main_window.py ui/intelligent_screen.py ui/sport_screen.py ui/sharp_screen.py \
        tests/test_flir_lepton.py tests/test_timing_manager.py PROGRESS.md NEXT_SESSION_PROMPT.md
git commit -m "feat: FLIR UI overhaul — live IR on Intelligent, mock removal, 400°C fix, sector black-until-active"
```

### 2. Deploy to Jetson
```bash
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"
```

### 3. Verify on Jetson
- **Key 1 (Intelligent)**: Middle band (y=160-340) should show live inferno-colormap thermal image of road. If FLIR not connected → "FLIR NOT CONNECTED" dim text.
- **Key 2 (Sport)**: Top-right panel should be solid dark background, no L/CTR/R numbers. Subtle background tint if FLIR active.
- **Key 3 (Sharp)**: S1/S2/S3 blocks should be dark/invisible until timing started. FLIR strip (if shown) = gradient bar, no numbers.
- **kisti-session.log**: Should NOT show 400°C warnings. Road temp = 0 (stale if non-radiometric) or real Celsius (if radiometric mode enabled).

### 4. Hardware actions (JK)
- Order CAN cable PN 101-5104 ($75) + DB9 breakout ($14) + 120Ω terminator ($13)
- Boost Barn tune WO #15562 with Aaron — KiSTI must be in-car with mic

---

## Key Files
| File | What changed |
|------|-------------|
| `sensors/flir_lepton_reader.py` | BGR fallback fix: emit frame, skip temps, 0.0 fallback |
| `can/kisti_can.py` | Removed mock FLIR entirely |
| `timing/timing_manager.py` | Added `lap_in_progress` to get_timing_data() |
| `ui/main_window.py` | Pass flir_reader to IntelligentScreenWidget |
| `ui/intelligent_screen.py` | Live IR image, inferno colormap, flir_reader wiring |
| `ui/sport_screen.py` | _paint_flir_summary → fillRect only |
| `ui/sharp_screen.py` | lap_in_progress gate, gradient bar for FLIR strip |
| `tests/test_flir_lepton.py` | BGR test + renamed non-radiometric test |
| `tests/test_timing_manager.py` | Added lap_in_progress to expected_keys |

---

## Architecture Notes
- **PureThermal default mode** = AGC/non-radiometric → BGR uint8 → 3-channel frame. Cannot extract Celsius. Emit frame for display, skip temps.
- **PureThermal radiometric mode** = uint16 centi-Kelvin (>20000 for room temp). Real Celsius available.
- **Inferno colormap**: 5 stops, numpy vectorized, in `IntelligentScreenWidget._apply_inferno()`. 0→black, 64→#3B0764, 128→#F97316, 192→#FDE047, 255→white.
- **Background tint alpha=15** in Sport + Sharp — this is intentionally subtle (6% opacity). The user confirmed this as the desired road temp visual.
- **`lap_in_progress`** = `timer._lap_start_ts is not None`. None = no active lap. Set on crossing start/finish.
- Old `brake_temp_fl/fr/rl/rr` + `update_flir()` still in DiffState — reserved for future ECU/CAN brake data.
