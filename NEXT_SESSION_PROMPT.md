# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`)
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 496 tests passing

## What Was Done (2026-03-30)

### Race Analysis Engine — Phases 1 & 2 COMPLETE

Built the core timing subsystem to replace AiM Race Studio 3 post-session analysis with real-time, in-car, voice-delivered race analysis.

**Phase 1 — GPS Geometry & Track Database:**
- `timing/geo.py` — 7 GPS primitives (haversine, line_segment_crossing, bearing, perpendicular_line, etc.)
- `timing/track_db.py` — DuckDB-backed TrackDatabase (find_track by GPS, sectors, seed import)
- `data/tracks_seed.json` — 18 seed tracks (Laguna Seca, Area 27, Mission, COTA, Nurburgring, etc.)
- DuckDB schema extended: `tracks`, `track_sectors`, `lap_times` tables + `imu_gyro_z` column + timing telemetry columns
- 67 tests (42 geo + 25 track DB)

**Phase 2 — Lap Timer Core Engine:**
- `timing/lap_timer.py` — LapTimer with update(), get_delta(), get_predicted_lap(), get_theoretical_best()
- ReferenceLap with distance-indexed time_at_distance() (binary search + interpolation)
- Point-to-point mode (set_p2p_mode/set_circuit_mode)
- DiffState extended: 10 timing fields + update_timing() on DiffStateBridge
- 44 tests (lap detection, sectors, delta, predictive, theoretical best, P2P, edge cases)

**Also this session:**
- Validated iPhone hotspot sync (full write/read/delete round-trip to Nextcloud)
- Updated KiSTI memory files (test count 268→380→496, voice pipeline status, GPS09 Pro)
- Saved GPS09 Pro Open IMU as key sensor to memory
- Saved race analysis vision: "Drive into pits, KiSTI explains it all"

## Prioritized TODO

### Phase 3: Qt Integration & Mock Enhancement (NEXT)
1. **Create `timing/timing_manager.py`** — TimingManager(QObject) wired to DiffStateBridge
   - Connect to `bridge.state_changed`, detect GPS updates, call `LapTimer.update()`
   - Emit signals: `lap_completed(dict)`, `sector_completed(dict)`, `track_detected(str)`
   - Push timing data to bridge via `update_timing()`
   - Files: new `timing/timing_manager.py`, modify `main.py` (wire after bridge creation ~line 317)

2. **Enhance MockCanGenerator GPS trace** — Replace Laguna Seca oval with realistic circuit loop
   - Must cross known start/finish line so LapTimer detects laps in sim mode
   - File: `can/kisti_can.py` lines 1177-1216 (`_gps_tick()`)

3. **Tests**: `tests/test_timing_manager.py` — 20+ integration tests

### Phase 4: Track Intelligence
4. **Create `timing/track_learner.py`** — TrackLearner (GPS trace → auto-detect start/finish + sectors)
5. **Track auto-recognition** in TimingManager — find_track on first GPS fix
6. **Point-to-point voice commands** — "set start point", "set end point"

### Phase 5: Voice Integration
7. **Timing voice announcements** in `main.py` — lap complete, sector complete (mode-aware I/S/S#)
8. **Voice queries** in `voice/voice_manager.py` — "what's my delta?", "theoretical best?", "what track?"
9. **Pit lane debrief** — auto-triggered on session end, speaks full summary

### Phase 6: UI + Data Sync
10. **`ui/widgets/timing_display.py`** — live delta, predicted, sector splits (800x480)
11. **Three SI Drive mode screen layouts** — I=full info, S=timing focus, S#=minimal/critical only (saved to memory: `project_kisti_gui_refactor.md`)
12. **Parquet export** — add lap_times to sync
13. **Zeus Memory** — timing summary push on session end

## Key Files

| File | Purpose |
|------|---------|
| `timing/geo.py` | GPS geometry primitives (haversine, crossing) |
| `timing/track_db.py` | Track database (find, save, seed) |
| `timing/lap_timer.py` | Core LapTimer engine (delta, predictive, theo best) |
| `model/vehicle_state.py:207-218` | DiffState timing fields |
| `model/vehicle_state.py:581-612` | DiffStateBridge.update_timing() |
| `data/duckdb_store.py:175-210` | Timing DuckDB tables |
| `data/duckdb_store.py:639-700` | Timing CRUD methods |
| `data/tracks_seed.json` | 18 seed tracks |
| `main.py:317-331` | SyncManager wiring (pattern for TimingManager) |
| `main.py:371-385` | Session toggle (K1) — hook timing signals here |
| `can/kisti_can.py:1177-1216` | MockCanGenerator._gps_tick() — needs realistic trace |

## Architecture Notes

### Data Flow (target state)
```
GPS09 Pro (CAN) → CanListener → DiffStateBridge → TimingManager → LapTimer
                                                        ↓
                                              ┌────────┼────────┐
                                              ↓        ↓        ↓
                                           Voice    DuckDB    UI
                                          (debrief) (persist) (display)
```

### Key Design Decisions
- **Distance-indexed delta** (not time-indexed) — handles variable speed through corners
- **Pure Python timing engine** — zero new dependencies on Jetson
- **Voice-first, screen-second** — pit debrief is primary UX
- **Mode-aware verbosity**: I=full, S=lap+delta, S#=PBs only

### GPS09 Pro Open
- Hardware pending install. Software fully integrated (CAN 0x6A4-0x6A7)
- 25Hz GPS + 100Hz 6-axis IMU. CAN configurable in Race Studio 3
- **IMU is the key sensor** — grip analysis, body dynamics, corner profiling

### Project File
- `/home/aldc/projects/active/2026-03-30-kisti-race-analysis/README.md`
- Full 6-phase plan with task breakdown
