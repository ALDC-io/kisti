# NEXT SESSION PROMPT — KiSTI kisti-flir-07

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1106 passed, 11 skipped

---

## Before starting work
1. `echo "KiSTI FLIR-07" > /tmp/tui-project-label`
2. Write phases to `/tmp/tui-phases.json`

## kisti-flir-06 summary (what was built)

### Road Condition Detection UX — Visual-First Redesign
- **Per-zone surface classification**: Each FLIR zone (L/C/R) classified independently with its own hysteresis (N=3). Overall `surface_state` = worst zone. New `classify_surface()` helper in `model/vehicle_state.py`.
- **New DiffState fields**: `surface_state_left`, `surface_state_center`, `surface_state_right` — all default DRY.
- **Per-zone background tint**: All 3 screens use `paint_zone_tint()` — screen mood shifts per-zone (DRY=invisible, WET=blue, COLD=purple, LOW_GRIP=red). Alpha: Intelligent=28, Sport=18, Sharp=12.
- **Edge glow for LOW_GRIP**: `paint_edge_glow()` — 8px inner-border red pulse (~1Hz) when any zone is LOW_GRIP. Drawn on all 3 screens.
- **Zone bar**: `paint_zone_bar()` — 3-segment horizontal bar colored by per-zone state. Replaced badge pill on Intelligent and Sport screens.
- **Shared utilities**: `ui/road_condition.py` — `paint_zone_tint`, `paint_edge_glow`, `paint_zone_bar`, `zone_states_from_snap`, `any_zone_low_grip`, `worst_state_label`.

### Screen Changes
- **Intelligent**: Badge pill → zone bar (260×40px) + worst-condition label. Per-zone tint at alpha 28.
- **Sport**: Badge pill → compact zone bar (60×18px). Reserved FLIR panel (510..790) now shows large zone bar (260×50px) with "ROAD CONDITION" label.
- **Sport Sharp**: Sector strip (when not timing) uses surface classification colors instead of heat gradient. "ROAD CONDITION" label added.

### Alert Engine Changes
- **`grip_low_grip` removed from VOICE_ALERT_TYPES** — screen visual is primary channel. Voice had 10s latency (280m at highway speed).
- **`ice_risk_imminent` stays in voice** — genuine emergency.
- **`_check_grip` docstring fixed**: 10s/50% (was 60s/60%).
- **Module-level imports**: `Counter`, `SurfaceState` moved out of `_check_grip()` (was importing at 2Hz).
- **`_gps_was_live`**: Dedicated `bool` attribute instead of storing in `_last_alert` dict.

### FLIR Fixes
- **`_consecutive_warm` now resets to 0** after `warm_object_detected` emits — prevents signal firing every frame while warm object visible.

### Theme
- **`ROAD_BG_*` tuples** in `ui/theme.py`: DRY=(10,10,10), WET=(10,15,45), COLD=(25,10,50), LOW_GRIP=(50,5,5).

## Remaining from code review (kisti-flir-07 work)

### Medium priority
1. **Udev rule for FLIR USB** — `ACTION=="add", ATTR{idVendor}=="1e4e", RUN+="/bin/chmod a+w %S%p/authorized"`. Eliminates sudo dependency.
2. **_label_blobs performance** — pure Python flood fill on 19K pixels. Add hot_count ceiling (>30% = skip) or use scipy.ndimage.label.
3. **Auto-detect device safety** — opening all /dev/videoN can steal other sensor handles. Add VID check or --flir-device flag.
4. **Two status lines on Intelligent screen** — user reported duplicate text at bottom. Investigate coaching bar vs voice ticker overlap.

### Nice to have
5. **Rogers Pass route tag** — auto-tag sessions with route name.
6. **Debrief display on Intelligent screen** — currently coaching bar only (24px, single line). Could use larger overlay when parked.
7. **Visual verification on Jetson** — rsync and test zone bar rendering on Strada 7" display. Check sunlight visibility.

## Key files
- `ui/road_condition.py` (shared paint functions — zone tint, edge glow, zone bar)
- `model/vehicle_state.py` (per-zone classification, classify_surface())
- `ui/intelligent_screen.py` (zone bar, per-zone tint)
- `ui/sport_screen.py` (zone indicators, FLIR panel)
- `ui/sharp_screen.py` (classification colors in sector strip)
- `alerts/alert_engine.py` (grip removed from voice, _gps_was_live fixed, imports moved)
- `sensors/flir_lepton_reader.py` (_consecutive_warm reset)
- `tests/test_flir_recovery.py` (8 new recovery + warm reset tests)
- `tests/test_surface_hysteresis.py` (13 new per-zone + classify_surface tests)

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `avg > 0` guard blocks sub-zero detection → use `!= 0.0`
- Two KiSTI processes fight for `/dev/video0` → kill ALL before restart
- `CAP_PROP_READ_TIMEOUT_MSEC` is silently ignored by V4L2 backend
- PureThermal lockup can survive USB reset — worker thread retries with backoff
- GDM auto-restarts kisti-session on process exit — don't `kill -9` the session itself
- Dew point in test fixtures: dew_point=10.0 + road=3.0 → LOW_GRIP (not COLD). Use dew_point=0.0 for COLD tests
- LOW_GRIP bypasses hysteresis (safety-critical) — tests must account for this
- Rsync to `~/repos/kisti` on Jetson, NOT `~/kisti`
- `_check_grip` must be in sensor-independent section (before `is_engine_stale` gate)
- Don't add `time.sleep()` in FLIR worker thread — `cap.read()` blocks at native frame rate
- TTS pronunciation: "Kissty" not "Keesty Eye" (voice/tts_engine.py TTS_SUBSTITUTIONS)
- `classify_surface()` is the single source of truth for surface classification thresholds
- Per-zone hysteresis is independent — each zone has its own counter/pending state
- `_consecutive_warm` must reset after emit or it fires every frame
- `_gps_was_live` is a dedicated bool, NOT stored in `_last_alert` dict
