# NEXT SESSION PROMPT — KiSTI kisti-flir-06

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1085 passed, 11 skipped

---

## Before starting work
1. `echo "KiSTI FLIR-06" > /tmp/tui-project-label`
2. Write phases to `/tmp/tui-phases.json` — TUI reads every 1s. Format: `[{"id":"1","name":"...","status":"pending|in_progress|completed","detail":"..."}]`. Update on every phase start/complete.

## kisti-flir-05 summary (what was built)

### Phase 1 — PatternEngine + ParkedDebrief wired into main.py
- **PatternEngine**: created inside `if db_store:` block with session_id getter lambda. Starts on session start, stops on session end. 1Hz analysis gated by active session.
- **PatternEngine → voice**: `ice_risk_imminent` and `knock_burst` patterns route to `voice_mgr.speak_alert()` with mode-appropriate messages.
- **ParkedDebrief**: created with ANTHROPIC_API_KEY from env. On session end, runs in background thread. Checks WiFi via `SyncManager._check_connectivity()`. If online, generates Haiku debrief and speaks first insight. Silent failure if no WiFi.
- **voice_alert signal**: AlertEngine's `voice_alert` signal now wired to `voice_mgr.speak_alert()`. General `alert_fired` handler skips VOICE_ALERT_TYPES to prevent double-speak.
- Files: `main.py` (lines 553-564 creation, 643-644 start, 689-711 stop+debrief, 735-753 pattern→voice wiring)

### Phase 2 — FLIR pipeline hardening
- **Surface state hysteresis**: `DiffStateBridge.SURFACE_HYSTERESIS_N = 3` (at 3Hz = ~1s settling). DRY↔WET↔COLD transitions require N consecutive readings. LOW_GRIP transitions immediately (safety-critical, no delay).
- Files: `model/vehicle_state.py` (lines 360-372 init, 637-660 hysteresis logic)
- Y16 radiometric path validated — already solid (centi-Kelvin → Celsius, OpenCV uint8 bug guard, non-radiometric rejection)
- Warm object 2-frame debounce confirmed working

### Phase 3 — Ice risk voice alert
- **`ice_risk_imminent`** added to `AlertEngine.VOICE_ALERT_TYPES`
- **`_check_ice_risk()`** added to AlertEngine — fires CRITICAL when road temp within 1°C of dew point. Runs without ECU (sensor-independent). Guards: no ambient → skip, no FLIR (all zeros) → skip.
- Files: `alerts/alert_engine.py` (lines 112 VOICE_ALERT_TYPES, 177 evaluate call, 335-353 _check_ice_risk)

### Phase 4 — Demo mode validation
- Code review confirmed demo-compatible: PatternEngine works with mock CAN (no FLIR patterns without hardware, drivetrain/dynamics work). ParkedDebrief fails silently without WiFi.

### Phase 5 — Tests
- **+13 new tests** (1072 → 1085): 6 ice risk alert tests (test_alerts.py), 1 VOICE_ALERT_TYPES update (test_alert_routing.py), 8 hysteresis tests (test_surface_hysteresis.py — new file)
- All tests verify behavior, not just existence

## Suggested next phases

**Phase 1 — Jetson deploy + field test**
Deploy to Jetson (`192.168.22.131`), run headless with FLIR attached. Test surface state hysteresis in real driving (warm parking garage → cold outdoor = DRY→COLD transition with 1s delay). Verify ice risk alert doesn't fire on warm days.

**Phase 2 — Pattern engine tuning**
- Adjust thermal pattern thresholds after field data from Rogers Pass
- Add `afr_lean_under_boost` to voice routing if Link G5 CAN is active
- Tune hysteresis N — may need N=5 (1.7s) if FLIR noise causes spurious transitions

**Phase 3 — Debrief UX**
- Speak more than first sentence of debrief (queue all 3 insights with pauses)
- Store debrief text in DuckDB `session_summaries` table (already implemented in `save_summary`)
- Display debrief on Intelligent screen when parked

**Phase 4 — Ice risk trending voice**
- Wire `ice_risk_trending` pattern (delta 1-3°C, decreasing trend) to voice with advisory message
- Add Rogers Pass route tag for session naming

## Key files
`main.py:553-564` (PatternEngine/ParkedDebrief creation) | `main.py:643-644` (start on session) | `main.py:689-711` (stop+debrief on session end) | `main.py:735-753` (pattern→voice) | `model/vehicle_state.py:360-372` (hysteresis init) | `model/vehicle_state.py:637-660` (hysteresis logic) | `alerts/alert_engine.py:335-353` (_check_ice_risk) | `analysis/pattern_engine.py` (1Hz patterns) | `analysis/parked_debrief.py` (Haiku debrief)

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `purge_synced` uses midnight cutoff — tests need backdating
- `knock_count`/`iam` not yet on DiffState — use `getattr(snap, 'knock_count', None)`
- `avg > 0` guard blocks sub-zero detection → use `!= 0.0`
- Two KiSTI processes fight for `/dev/video0` → kill headless before fullscreen
- Dew point in test fixtures: if dew_point=10.0 and road=3.0 → LOW_GRIP (not COLD). Use dew_point=0.0 for COLD tests
- LOW_GRIP bypasses hysteresis (safety-critical) — tests must account for this
