# NEXT SESSION PROMPT — KiSTI FLIR Road Surface Integration

**Branch**: `kisti-headless`  
**Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)  
**Run KiSTI**: `~/k`

---

## What Was Done (this + prior session)

1. **`sensors/flir_lepton_reader.py`** — `BrakeTemps` → `RoadSurfaceTemps(left, center, right)`, 3 horizontal ROI strips, `frame_updated` signal emitting raw uint16 numpy frames

2. **`model/vehicle_state.py`** — Added `road_temp_left/center/right/road_surface_ts` to `DiffState`, `update_road_surface()` bridge method, `is_road_surface_stale(timeout=2.0)` helper. Old `brake_temp_fl/fr/rl/rr` + `update_flir()` kept intact for future ECU/CAN.

3. **`main.py`** — Signal rewired `update_flir()` → `update_road_surface()`, `flir_reader` passed to `MainWindow`

4. **`ui/widgets/camera_feeds.py`** — `IRCameraFeed` removed, `LiveThermalFeed` added (uint16 → inferno colormap → QImage, staleness indicator)

5. **`ui/video_mode.py`** — `flir_reader` param, `LiveThermalFeed` connected to `frame_updated` signal

6. **`ui/main_window.py`** — `VideoModeWidget` added to stack as index 3, key `4` shortcut

7. **`ui/intelligent_screen.py`** — `_draw_flir_panel` rewritten: 3 L/CTR/R heat-colored zone cards. Background tint uses road surface average (alpha=15).

8. **`ui/sport_screen.py`** — `_paint_flir_summary` rewritten: 3-column compact L/CTR/R display in top-right panel. Background tint added.

9. **`ui/sharp_screen.py`** — `_draw_flir_strip` rewritten: 3-zone horizontal display. `_draw_safety_vitals` uses `road_temp_center`. Background tint added.

10. **`tests/test_flir_lepton.py`** — New test file (~20 tests)

11. **`timing/timing_manager.py`** — Pre-existing bug fixed: `int()` → `max(1, round(...))` in `get_timing_data()` so sub-ms lap times in tests show as ≥1ms not 0.

---

## Current State

**All changes are UNCOMMITTED** on `kisti-headless`. No commits made yet.

- Last full run (before timing fix): 1005 passed, 1 failed (`test_timing_after_lap`)
- Timing fix verified: `test_timing_after_lap` now PASSES
- Expected after full run: **1006 passed, 0 failed**

---

## TODO — In Priority Order

### 1. Verify test suite is clean
```bash
cd /home/aldc/repos/kisti
python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py 2>&1 | tail -10
```
Expected: 1006 passed, 0 failed.

### 2. Commit all changes
Files to stage (all modified + 1 untracked):
```
main.py
model/vehicle_state.py
sensors/flir_lepton_reader.py
timing/timing_manager.py
ui/intelligent_screen.py
ui/main_window.py
ui/sharp_screen.py
ui/sport_screen.py
ui/video_mode.py
ui/widgets/camera_feeds.py
tests/test_flir_lepton.py   ← untracked, git add explicitly
NEXT_SESSION_PROMPT.md
```
Suggested message: `feat: FLIR road surface integration (3-zone L/CTR/R) + timing ms fix`

### 3. Deploy to Jetson
```bash
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"
```
Press `4` → confirm live 160×120 thermal image in top-right quadrant.

### 4. Update PROGRESS.md
- Advance FLIR road surface integration to DONE
- Note timing pre-existing fix resolved

---

## Key Files
| File | What changed |
|------|-------------|
| `sensors/flir_lepton_reader.py` | New data model + frame_updated signal |
| `model/vehicle_state.py` | road_temp_* fields + update_road_surface() |
| `main.py` | Signal rewire + flir_reader to MainWindow |
| `ui/widgets/camera_feeds.py` | LiveThermalFeed replaces IRCameraFeed |
| `ui/video_mode.py` | flir_reader param, LiveThermalFeed wired |
| `ui/main_window.py` | VideoModeWidget in stack, key 4 |
| `ui/intelligent_screen.py` | 3-zone road surface display |
| `ui/sport_screen.py` | 3-zone road surface display |
| `ui/sharp_screen.py` | 3-zone road surface display |
| `timing/timing_manager.py` | round() fix for best_lap_ms |
| `tests/test_flir_lepton.py` | ~20 new tests (untracked) |

---

## Architecture Notes
- `_brake_heat_color(temp_c)`: blue(≤5°C) → green(15°C) → yellow(40°C) → red(≥55°C) — in all 3 screens
- Background tint alpha=15 (very subtle) uses `(left+center+right)/3` average
- Old `brake_temp_fl/fr/rl/rr` fields in DiffState untouched — reserved for ECU/CAN
- `is_road_surface_stale(timeout=2.0)` lives on `DiffState` itself
- `frame_updated` signal emits raw uint16 numpy array before ROI processing
