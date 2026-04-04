# NEXT SESSION PROMPT — KiSTI kisti-flir-05

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1072 passed, 11 skipped

---

## Before starting work
1. `echo "KiSTI FLIR-05" > /tmp/tui-project-label`
2. Write phases to `/tmp/tui-phases.json` — TUI reads every 1s. Format: `[{"id":"1","name":"...","status":"pending|in_progress|completed","detail":"..."}]`. Update on every phase start/complete.

## kisti-30 summary (what was built)
- **DuckDB**: 4 new tables (flir_readings, surface_transitions, knock_events, patterns) + session_name/route_tag. File: `data/duckdb_store.py`
- **Native-rate logging**: CAN buffered at 50Hz (was 1Hz), FLIR 3Hz wired, surface_state_changed signal on DiffStateBridge. File: `main.py`, `model/vehicle_state.py`
- **Pattern engine**: `analysis/pattern_engine.py` — 1Hz CPU-only cycle, thermal/drivetrain/dynamics patterns, 30s debounce
- **Alert routing**: `voice_alert`/`display_alert` signals on AlertEngine. VOICE_ALERT_TYPES = oil_pressure_low/critical, coolant_critical, fuel_pressure_critical. File: `alerts/alert_engine.py`
- **Haiku debrief**: `analysis/parked_debrief.py` — builds session summary from DuckDB, calls Haiku, stores 3-point insight
- **TUI**: `/home/aldc/tools/agent-tui.py` has phase board reading `/tmp/tui-phases.json`

## Phases for this session

**Phase 1 — Wire PatternEngine + ParkedDebrief into main.py**
PatternEngine: create instance, start on K1 session start, stop on session end. ParkedDebrief: auto-trigger on session end when WiFi available (reuse sync/sync_manager.py connectivity check). Connect pattern_detected → voice for ice_risk_imminent/knock_burst. Wire voice_alert signal from AlertEngine → voice_manager.speak().

**Phase 2 — FLIR pipeline hardening**
Validate Y16 radiometric path in sensors/flir_lepton_reader.py. Add hysteresis to surface state transitions in model/vehicle_state.py (require N consecutive readings before DRY↔WET↔COLD). Tune ice risk for 0-3°C dew point delta (Rogers Pass). Confirm warm object 2-frame debounce.

**Phase 3 — Ice risk voice alert**
Add ice_risk_imminent to VOICE_ALERT_TYPES. Add _check_ice_risk() to AlertEngine reading FLIR road temp vs dew point, fires when delta < 1°C. #1 safety feature for Rogers Pass.

**Phase 4 — Demo mode validation**
Verify --demo works with PatternEngine, FLIR logging, session naming. Target: 30min unattended.

**Phase 5 — Tests + handoff**
Test count >= 1072. Update NEXT_SESSION_PROMPT.md.

## Key files
`data/duckdb_store.py` (17 tables) | `main.py:541-700` (data collection wiring) | `model/vehicle_state.py` (DiffStateBridge + surface_state_changed) | `alerts/alert_engine.py` (voice/display routing) | `analysis/pattern_engine.py` (1Hz patterns) | `analysis/parked_debrief.py` (Haiku debrief) | `data/build_record.py` (BASELINES)

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `purge_synced` uses midnight cutoff — tests need backdating
- `knock_count`/`iam` not yet on DiffState — use `getattr(snap, 'knock_count', None)`
- `avg > 0` guard blocks sub-zero detection → use `!= 0.0`
- Two KiSTI processes fight for `/dev/video0` → kill headless before fullscreen
