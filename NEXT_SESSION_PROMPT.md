# NEXT SESSION PROMPT — KiSTI kisti-29

**Branch**: `kisti-headless`  
**Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)  
**Run KiSTI**: `~/k`

---

## What Was Done (kisti-28)

### Radiometric FLIR — Real Temperature Data
- **Y16 mode enabled** — Set V4L2 FOURCC to `Y16` on PureThermal 3. Frames are now uint16 centi-Kelvin. Confirmed: `dtype=uint16, shape=(120,160), mean=29837` = 25.2°C real room temp.
- **OpenCV Y16 bug guard** — `.view(uint16).reshape(120,160)` workaround in `_poll()` for flattened uint8 bug.
- `road_temp_left/center/right` now have **real Celsius values** from FLIR ROI averaging.

### Surface State Inference (no CAN needed)
- `update_road_surface()` in `model/vehicle_state.py` derives surface_state from FLIR + Yocto:
  - `avg < 0°C` → LOW_GRIP (ice)
  - `avg ≤ dew_point` → LOW_GRIP (frost/ice actively forming)
  - `avg < 5°C` → COLD
  - `avg < dew_point + 3°C` → WET (condensation risk)
  - `ambient - avg > 5°C + humidity > 70%` → WET
  - else → DRY
- **Tested live**: cold glass bottle → road temp dropped to -3.6°C → LOW GRIP triggered.

### Mock CAN Disabled
- `mock.start()` commented out in `main.py`. Only real sensors: FLIR, Yocto, Korlan.
- Default screen changed to Intelligent (index 0).
- SI-Drive mock locked to Intelligent for testing (needs `--demo` flag to restore rotation).

### UI Changes
- **4-column weather card**: WEATHER | ROAD | HUMIDITY | BARO — evenly spaced, BARO right-aligned.
- **CLAHE + temporal smoothing** on FLIR image. Frame throttle to ~3 Hz.
- **LUT inferno colormap** — precomputed 256-entry, QImage cached off paint thread.
- **Coaching text** moved from FLIR image overlay to bottom bar (y=456-480).
- **Sport voice ticker** relocated from G-force circle to empty FLIR panel.
- **Compact weather card** — 108px tall, FLIR panel starts at y=118.

### Tests
- 1006 passed, 0 failed (before this session's non-test changes).
- New tests added: BGR signal separation, non-radiometric returns 0.0, lap_in_progress key.
- **TODO**: Run full suite to verify nothing broken by mock disable / Y16 changes.

---

## Current State

**All changes committed and pushed** on `kisti-headless`. Deployed to Jetson. Running in sensor-only mode (no mock).

Diagnostic logging active:
- FLIR frame dtype/shape/mean on first read
- Road temps L/C/R + surface state every 3s

---

## TODO — In Priority Order

### 1. Run full test suite
```bash
cd /home/aldc/repos/kisti
python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py 2>&1 | tail -10
```

### 2. Add `--demo` flag to main.py
- When `--demo`: start mock CAN, restore SI-Drive rotation (15s cycle)
- When no flag (default): real sensors only, Intelligent default
- This lets us demo at trade shows while running real sensors on the road

### 3. Warm object detection prototype
**Approach** (no ML, pure numpy):
- Maintain running average of road ROI temp (3-second window)
- Each frame: threshold pixels >10°C above road baseline
- Find connected components >20 pixels
- Require blob present in 2+ consecutive frames (debounce)
- Emit signal: `warm_object_detected(position: str)` — "LEFT" / "CENTER" / "RIGHT"
- Alert: "WARM OBJECT AHEAD" on coaching bar + voice TTS

**Files**: `sensors/flir_lepton_reader.py` (detection), `alerts/alert_engine.py` (alert), coaching bar (display)

### 4. CAN-to-Strada text alerts
- When Korlan cable arrives: send coaching text as CAN message to Link ECU
- Link G5 can forward to Strada 7" configurable text display
- CAN frame format: TBD after reading Link CAN protocol docs

### 5. YOLO animal detection (future)
- Second camera (visible light, 720p USB)
- FLIR triggers "warm blob" → visible camera classifies
- Jetson Orin Nano GPU runs YOLOv8-nano inference
- "DEER AHEAD" / "ANIMAL ON ROAD" specific alerts

### 6. Remove diagnostic logging
- Remove road temp log every 3s from `vehicle_state.py`
- Remove frame format log from `flir_lepton_reader.py`
- (Keep until road test validates readings are correct)

### 7. Order CAN hardware (JK action)
- PN 101-5104 cable ($75)
- DB9 breakout ($14)
- 120Ω terminator ($13)

---

## Key Files
| File | What changed |
|------|-------------|
| `sensors/flir_lepton_reader.py` | Y16 FOURCC, OpenCV uint8 workaround, diagnostic log |
| `model/vehicle_state.py` | Surface state inference, dew point ice detection, road temp log |
| `can/kisti_can.py` | SI-Drive locked to Intelligent, mock FLIR removed |
| `main.py` | Mock CAN disabled |
| `ui/main_window.py` | Default screen Intelligent, flir_reader wired |
| `ui/intelligent_screen.py` | 4-col weather, LUT inferno, CLAHE, throttle, coaching bar |
| `ui/sport_screen.py` | Voice ticker relocated, FLIR panel cleared |
| `ui/sharp_screen.py` | lap_in_progress gate, gradient bar |

---

## Architecture Notes
- **Y16 FOURCC** auto-disables AGC on PureThermal fw≥1.0.0. No CCI commands needed. Resets on power cycle but Y16 request happens every startup in `flir_lepton_reader.start()`.
- **Surface state priority**: LOW_GRIP (ice/frost) > COLD (<5°C) > WET (condensation/rain) > DRY
- **Dew point = ice predictor**: `road_temp ≤ dew_point` means moisture is condensing and freezing on the road surface. This is THE black ice signal.
- **Frame pipeline**: FLIR 9Hz → skip 2/3 → float32 temporal blend → uint8 normalize → CLAHE → LUT inferno → QImage cache → paintEvent blit
- **Warm object detection approach**: road baseline (3s avg) + threshold (>10°C above) + connected components (>20px) + debounce (2 frames) = "WARM OBJECT AHEAD"
- **Mock CAN**: still created but not started. Add `--demo` flag to restore for presentations.
