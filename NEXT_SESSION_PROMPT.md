# NEXT SESSION PROMPT — KiSTI kisti-29

**Branch**: `kisti-headless`  
**Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)  
**Run KiSTI**: `~/k`  
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`  
**Test baseline**: 1006 passed, 0 failed

---

## What Was Done (kisti-27 + kisti-28)

### Radiometric FLIR — Real Temperature Data
- **Y16 mode enabled** — V4L2 FOURCC `Y16` on PureThermal 3. Frames = uint16 centi-Kelvin. Confirmed: `dtype=uint16, shape=(120,160), mean=29837` = 25.2°C.
- **OpenCV Y16 bug guard** — `.view(uint16).reshape(120,160)` workaround in `_poll()` for flattened uint8.
- **400°C bug fixed** — BGR fallback was scaling uint8→fake 100-600°C. Fix: emit `frame_updated` then `return` (skip temps). `_roi_mean_temp` returns `0.0` for non-radiometric.
- `road_temp_left/center/right` now have **real Celsius** from FLIR ROI averaging.

### Surface State Inference (no CAN needed)
- `update_road_surface()` in `model/vehicle_state.py` derives surface_state from FLIR + Yocto:
  - `avg < 0°C` → LOW_GRIP (ice)
  - `avg ≤ dew_point` → LOW_GRIP (frost/ice actively forming — THE black ice signal)
  - `avg < 5°C` → COLD
  - `avg < dew_point + 3°C` → WET (condensation risk)
  - `ambient - avg > 5°C + humidity > 70%` → WET
  - else → DRY
- **Tested live**: cold glass bottle → -3.6°C → LOW GRIP triggered.

### Mock CAN Disabled + Mock FLIR Removed
- `mock.start()` commented out in `main.py`. Only real sensors: FLIR, Yocto, Korlan.
- **Mock FLIR deleted entirely** from `kisti_can.py` — `_flir_fl/fr/rl/rr`, `_flir_timer`, `_flir_tick()` all gone.
- Default screen → Intelligent (index 0). SI-Drive mock locked to mode 0.

### UI Changes
- **4-column weather card**: WEATHER | ROAD | HUMIDITY | BARO — evenly spaced, BARO right-aligned.
- **Live FLIR thermal image** on Intelligent screen — CLAHE + temporal smoothing + LUT inferno colormap.
- **Frame throttle** to ~3 Hz (skip 2/3). Prevents Jetson CPU lockup (was 55% at 9Hz).
- **LUT inferno colormap** — precomputed 256-entry (5 stops: black→purple→orange→yellow→white), QImage cached off paint thread.
- **Coaching text** moved from FLIR image overlay to bottom bar (y=456-480).
- **Sport screen** — voice ticker relocated to FLIR panel. FLIR summary → fillRect only (background tint is signal).
- **Sharp screen** — `lap_in_progress` gate: sectors black until active lap. FLIR strip → 3-zone gradient bar (no text).
- **Compact weather card** — 108px tall, FLIR panel starts at y=118.

### Tests
- **1006 passed, 0 failed** — baseline maintained.
- Added: BGR signal separation, non-radiometric returns 0.0, lap_in_progress key.

---

## Current State

**All changes committed and pushed** on `kisti-headless`. Deployed to Jetson. Running in sensor-only mode.

Diagnostic logging active (remove after road test validation):
- FLIR frame dtype/shape/mean on first read
- Road temps L/C/R + surface state every 3s

---

## TODO — In Priority Order

### 1. Run full test suite (verify baseline)
```bash
cd /home/aldc/repos/kisti
python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py 2>&1 | tail -10
```
Expected: 1006 passed, 0 failed.

### 2. Add `--demo` flag to main.py
- When `--demo`: start mock CAN, restore SI-Drive rotation (15s cycle I→S→S#)
- When no flag (default): real sensors only, Intelligent default
- This lets us demo at trade shows while running real sensors on the road
- **Files**: `main.py` (argparse), `can/kisti_can.py` (unlock SI-Drive tick)

### 3. Warm object detection prototype
**Approach** (no ML, pure numpy):
- Maintain running average of road ROI temp (3-second window)
- Each frame: threshold pixels >10°C above road baseline
- Find connected components >20 pixels (scipy.ndimage.label or manual)
- Require blob present in 2+ consecutive frames (debounce)
- Emit signal: `warm_object_detected(position: str)` — "LEFT" / "CENTER" / "RIGHT"
- Alert: "WARM OBJECT AHEAD" on coaching bar + **voice TTS via KiSTI voice pipeline** (whisper STT not needed — this is outbound only: Piper TTS → HDMI audio)

**Files**: `sensors/flir_lepton_reader.py` (detection logic), `alerts/alert_engine.py` (alert routing), coaching bar (display)

### 4. Post learnings to Zeus Memory
Zeus API was unreachable during kisti-28 wrap. 11 learnings need posting:
- 7x `cce_success_log` (Y16, ice detect, mock removal, 3Hz, weather card, coaching bar, sectors)
- 4x `cce_decision_log` (Y16 AGC, dew point algo, 3Hz choice, Intelligent default)
See PROGRESS.md "Learnings Captured" section for details.

### 5. CAN-to-Strada text alerts
- When Korlan cable arrives: send coaching text as CAN message to Link ECU
- Link G5 can forward to Strada 7" configurable text display
- CAN frame format: TBD after reading Link CAN protocol docs

### 6. Remove diagnostic logging (after road test)
- Road temp log every 3s in `model/vehicle_state.py`
- Frame format log in `sensors/flir_lepton_reader.py`
- Keep until real road test validates readings are correct

### 7. Order CAN hardware (JK action)
- PN 101-5104 cable ($75)
- DB9 breakout ($14)
- 120Ω terminator ($13)

### 8. YOLO animal detection (future)
- Second camera (visible light, 720p USB)
- FLIR triggers "warm blob" → visible camera classifies
- Jetson Orin Nano GPU runs YOLOv8-nano inference
- "DEER AHEAD" / "ANIMAL ON ROAD" specific alerts

---

## Key Files
| File | What changed |
|------|-------------|
| `sensors/flir_lepton_reader.py` | Y16 FOURCC, OpenCV uint8 workaround, BGR fix, diagnostic log |
| `model/vehicle_state.py` | Surface state inference, dew point ice detection, road temp log |
| `can/kisti_can.py` | SI-Drive locked to Intelligent, mock FLIR removed entirely |
| `main.py` | Mock CAN disabled |
| `ui/main_window.py` | Default screen Intelligent, flir_reader wired |
| `ui/intelligent_screen.py` | 4-col weather, LUT inferno, CLAHE, throttle, coaching bar |
| `ui/sport_screen.py` | Voice ticker relocated, FLIR panel → fillRect |
| `ui/sharp_screen.py` | lap_in_progress gate, gradient bar (no text) |
| `tests/test_flir_lepton.py` | BGR signal separation test, non-radiometric returns 0.0 |
| `tests/test_timing_manager.py` | lap_in_progress in expected_keys |
| `tests/test_modes.py` | Default screen assertions → index 0 |

---

## Don't Repeat
- `avg > 0` guard in surface state blocks sub-zero detection → use `!= 0.0` check
- Two KiSTI processes fighting for `/dev/video0` → kill headless before starting fullscreen
- CLAHE at 9 Hz overwhelms Jetson CPU → throttle to 3 Hz first
- OpenCV may return Y16 as flattened uint8 `(120,320,1)` → `.view(uint16).reshape(120,160)`
- BGR AGC frame dtype is NOT uint16 — check `len(frame.shape) == 3` not `frame.dtype`
- `return mean_raw` in `_roi_mean_temp` for non-radiometric leaks garbage temps → always `return 0.0`
- Mock FLIR was calling `update_flir()` (OLD brake API) not `update_road_surface()` → it was polluting the wrong bridge fields

## Architecture Notes
- **Y16 FOURCC** auto-disables AGC on PureThermal fw≥1.0.0. No CCI commands needed. Resets on power cycle but Y16 request happens every startup in `flir_lepton_reader.start()`.
- **Surface state priority**: LOW_GRIP (ice/frost) > COLD (<5°C) > WET (condensation/rain) > DRY
- **Dew point = ice predictor**: `road_temp ≤ dew_point` means moisture is condensing and freezing on the road surface. This is THE black ice signal.
- **Frame pipeline**: FLIR 9Hz → skip 2/3 → float32 temporal blend → uint8 normalize → CLAHE → LUT inferno → QImage cache → paintEvent blit
- **Warm object detection approach**: road baseline (3s avg) + threshold (>10°C above) + connected components (>20px) + debounce (2 frames) = "WARM OBJECT AHEAD"
- **Mock CAN**: still created but not started. Add `--demo` flag to restore for presentations.
- **Background tint (alpha=15)** on Sport/Sharp communicates road temp at-a-glance without numbers.
