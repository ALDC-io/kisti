# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 550 tests passing
**Team session**: `kisti-speaks` (session_id: `71182e9b-8794-458f-b9d6-01a301c9ff58`)

## What Was Done (2026-03-30)

### Race Analysis Engine — Phases 1-4 COMPLETE

**Phases 1-2** (earlier session): Core timing engine — `timing/geo.py`, `timing/track_db.py`, `timing/lap_timer.py`, DiffState timing fields, DuckDB timing tables.

**Phase 3** (RS-02 + kisti-08 fixes):
- `timing/timing_manager.py` — TimingManager(QObject) wired to DiffStateBridge. Signals: `lap_completed`, `sector_completed`, `track_detected`, `p2p_completed`. blockSignals prevents re-entrant emission.
- `can/kisti_can.py` — Realistic Laguna Seca waypoint GPS trace (replaces oval). 13 waypoints crossing S/F + 3 sector lines.
- `main.py` — TimingManager wired with voice announcements + session debrief on K1 toggle.
- 26 tests in `tests/test_timing_manager.py` (synthetic rectangular track).

**Phase 4** (RS-02):
- `timing/track_learner.py` — TrackLearner class (180 LOC, pure Python). Records GPS, detects loop closure (50m threshold, 500m min distance), auto-generates S/F line + 3 sectors + center/radius. source="learned".
- `timing/timing_manager.py` — Enhanced `_try_detect_track()`: if `find_track()` returns None → creates TrackLearner, feeds GPS, on loop closure saves to DuckDB + configures LapTimer.
- 22 tests in `tests/test_track_learner.py`, 6 tests added to `tests/test_timing_manager.py` (TestTrackLearning).

**Also this session (kisti-07/kisti-08)**:
- CUDA OOM fix: whisper.cpp CUDA + Ollama CPU allocation on Jetson 8GB
- Echo protection: mic pauses during UI audio playback (main.py lines 521-541)
- blockSignals fix for TimingManager re-entrant state_changed

## Prioritized TODO

### BEFORE ANYTHING: Resolve File Conflicts + Push
- `main.py`, `timing/timing_manager.py`, `tests/test_timing_manager.py` — edited by kisti-07, kisti-08, RS-02
- Changes are in different sections — `git pull --rebase` should merge cleanly
- Verify 550 tests pass after merge

### TUI Task Visibility Fix
- RS-02 events posted but don't appear on project board — session project is `kisti-006` (voice pipeline), not race analysis
- Fix: `/team project /home/aldc/projects/active/2026-03-30-kisti-race-analysis/` or re-post events with matching task IDs

### Phase 5: Voice Integration (NEXT)
1. **Timing announcements** — enhance `_on_lap_complete` in main.py. Mode-aware: I=full, S=lap+delta, S#=PBs only.
2. **`_answer_from_timing()` method** in `voice/voice_manager.py` — keyword match on DiffState timing fields. Insert before `_answer_from_sensors()` at line 588. Queries: "what's my delta?", "theoretical best?", "last lap?", "what track?", "sector times?"
3. **Voice commands** — "point to point mode", "set start point", "circuit mode", "use lap N as reference". Add `set_timing_manager()` to voice_manager.
4. **Pit lane debrief** — on session end, speak summary from `timing_mgr.get_session_summary()`.
5. **LLM timing context** — add timing fields to `_build_telemetry_context()`.

### Phase 6: UI + Data Sync
6. `ui/widgets/timing_display.py` — live delta/splits on 800x480
7. Three SI Drive mode layouts: I=full, S=timing, S#=minimal
8. Parquet export of lap_times
9. Zeus Memory timing summary push

## Key Files

| File | Purpose |
|------|---------|
| `timing/timing_manager.py` | Qt bridge — auto-detect, track learning, DuckDB |
| `timing/track_learner.py` | GPS trace → auto-generate track definition |
| `timing/lap_timer.py` | Core timing engine |
| `timing/geo.py` | GPS geometry primitives |
| `timing/track_db.py` | Track database |
| `voice/voice_manager.py:540-600` | handle_voice_query dispatch chain |
| `voice/voice_manager.py:854-883` | _answer_from_sensors (template for timing queries) |
| `main.py:332-360` | TimingManager creation + voice wiring |
| `main.py:390-420` | Session toggle with timing debrief |

## Architecture Notes

### Voice Query Dispatch (for Phase 5)
```
handle_voice_query(transcription):
  1. Commands: "say", "remember", "quiet" → immediate
  2. _answer_from_timing(lower)  ← ADD THIS
  3. _answer_from_sensors(lower) → ambient/weather
  4. LLM → persona response
```

### Project File
- `/home/aldc/projects/active/2026-03-30-kisti-race-analysis/README.md`
