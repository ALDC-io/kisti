# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 614 tests passing
**Team session**: `kisti-speaks` (session_id: `71182e9b-8794-458f-b9d6-01a301c9ff58`)

## What Was Done (2026-03-30)

### Race Analysis Engine — Phases 1-6 COMPLETE

**Phases 1-4** (earlier sessions): Core timing engine, TimingManager Qt bridge, TrackLearner, 550 tests.

**Phase 5** (RS-03): Voice timing integration — 49 new tests
1. `_answer_from_timing()` in `voice/voice_manager.py:998` — keyword dispatch for delta, theoretical best, lap time, predicted, sectors, track name, lap count. Inserted before `_answer_from_sensors` in dispatch chain.
2. `_handle_timing_command()` in `voice/voice_manager.py:933` — voice commands: P2P mode, set start/end point, circuit mode, reference lap N.
3. Mode-aware announcements in `main.py:343-375` — I=full detail, S=lap+delta, S#=PBs only. Track detected suppressed in S#.
4. Mode-aware pit debrief in `main.py:436-463` — session end summary varies by SI Drive mode.
5. LLM timing context in `voice/voice_manager.py:1098-1109` — track, lap, delta, predicted, theoretical, sector added to `_build_telemetry_context()`.
6. `set_timing_manager()` wired in `main.py:342`.

**Phase 6** (RS-03): UI + Data Sync — 15 new tests
1. `ui/widgets/timing_display.py` — TimingDisplayWidget (QPainter, 230 LOC). Three SI Drive layouts: I=full (4 rows), S=compact, S#=delta bar only. Delta flash on sign change. Sector progress dots.
2. Wired into `ui/track_mode.py` — TrackModeWidget now has timing display between track map and session widget. `update_timing(snap)` and `set_timing_mode(mode)`.
3. Bridge-to-UI wiring in `main.py:499-513` — updates at ~4 Hz, mode changes propagate.
4. Zeus Memory push in `main.py:407-448` — `_push_timing_to_zeus()` fires background thread on session end, POSTs timing summary to Zeus API.
5. Parquet export already working via `DuckDBStore.export_session_parquet()` (includes lap_times table).
6. `timing/geo.py` — added `offset_line()` for voice P2P start/end point creation.

## Prioritized TODO

### Phase 7: On-Jetson Validation
- [ ] Deploy to Jetson and test timing display on 800x480 AiM Strada
- [ ] Test voice commands with live mic: "what's my delta?", "point to point mode", "circuit mode"
- [ ] Verify timing display layout in all three SI Drive modes via K3
- [ ] Test pit lane debrief at session end (K1 toggle)
- [ ] Verify Zeus Memory push with real session data

### Phase 8: Polish & Edge Cases
- [ ] Handle track re-detection after GPS dropout
- [ ] Add voice "what lap am I on?" (currently mapped as "how many laps")
- [ ] Sector time announcements (per-sector mode-aware?)
- [ ] Custom wake word "Hey KiSTI" for timing commands (Colab training)

## Key Files

| File | Purpose |
|------|---------|
| `voice/voice_manager.py:933-1065` | Timing commands + queries |
| `voice/voice_manager.py:1098-1109` | LLM timing context |
| `ui/widgets/timing_display.py` | Timing display widget (3 modes) |
| `ui/track_mode.py` | TRACK mode layout with timing |
| `main.py:340-375` | Mode-aware announcements |
| `main.py:407-448` | Zeus push function |
| `main.py:499-513` | Bridge-to-UI timing wiring |
| `timing/geo.py:149-161` | offset_line for P2P |
| `tests/test_voice_timing.py` | 49 voice timing tests |
| `tests/test_timing_display.py` | 15 display + push tests |

## Architecture Notes

### Voice Query Dispatch (complete)
```
handle_voice_query(transcription):
  1. Commands: "say", "remember", "quiet" -> immediate
  2. Timing commands: "P2P", "circuit mode", "reference lap N" -> _handle_timing_command
  3. _answer_from_timing(lower) -> delta, sectors, track, lap count
  4. _answer_from_sensors(lower) -> ambient/weather
  5. LLM -> persona response (with timing context in system prompt)
```

### SI Drive Timing Layouts
```
Intelligent: LAP 5 | Laguna Seca [CIR]
             1:31.2  -0.3 (green/red)
             PRED 1:31.8  THEO 1:29.7
             [S1] [S2] [S3] (sector dots)

Sport:       1:31.2    -0.3
             [S1] [S2] [S3]

Sport Sharp: [green bar|red bar] -0.3
             (delta bar only)
```
