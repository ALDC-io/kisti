# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 625 tests passing
**Team session**: `kisti-speaks` (session_id: `71182e9b-8794-458f-b9d6-01a301c9ff58`)
**Zeus ZMID**: `14969d98-554f-4df0-a33b-cc57eb7d8384` (session summary)

## What Was Done (2026-03-30)

### Race Analysis Engine — Phases 1-8 COMPLETE (RS-03 delivered P5-P8)

**Phases 1-4** (earlier sessions — JK, RS-02): Core timing engine, TimingManager Qt bridge, TrackLearner, track auto-recognition, P2P mode. 550 tests.

**Phase 5** (RS-03, 49 tests): Voice timing integration
- `_answer_from_timing()` at `voice/voice_manager.py:998` — keyword dispatch: delta, theoretical best, lap time, predicted, sectors, track name, lap count, best lap, pace
- `_handle_timing_command()` at `voice/voice_manager.py:933` — voice commands: P2P mode, set start/end point, circuit mode, reference lap N
- Mode-aware announcements at `main.py:343-375` — I=full detail, S=lap+delta, S#=PBs only
- Mode-aware pit debrief at `main.py:436-463` — session end summary varies by SI Drive mode
- LLM timing context at `voice/voice_manager.py:1098-1109` — timing fields in `_build_telemetry_context()`
- `set_timing_manager()` wired at `main.py:342`

**Phase 6** (RS-03, 15 tests): UI + Data Sync
- `ui/widgets/timing_display.py` — TimingDisplayWidget (QPainter, 230 LOC). 3 SI Drive layouts: I=full (4 rows), S=compact, S#=delta bar only. Delta flash on sign change. Sector dots.
- Wired into `ui/track_mode.py` between track map and session widget
- Bridge-to-UI at 4Hz in `main.py:499-513`, mode changes propagate
- Zeus Memory push in `main.py:407-448` — `_push_timing_to_zeus()` background thread on session end
- `offset_line()` in `timing/geo.py:149-161` for P2P voice commands
- Parquet export already working via `DuckDBStore.export_session_parquet()`

**Phase 7** (RS-03): Jetson Validation — ALL PASS
- 611/614 tests on ARM64 (3 pre-existing STT failures: GPU device discovery + SciPy version)
- Timing display renders 100% in all 3 SI Drive modes on ARM64 offscreen
- 8/8 voice timing queries pass E2E on Jetson
- Pit debrief summary verified (laps/best/last/theo/track)
- Zeus push: graceful skip when ZEUS_API_KEY not set on Jetson
- **Sim test**: track auto-detected ("WeatherTech Raceway Laguna Seca" from 18 seeded tracks), all voice queries resolve via timing source. No completed laps in 50s (mock trace too slow for full 3.6km lap).

**Phase 8** (RS-03, 11 tests): Polish & Edge Cases
- GPS jump filter (>500m) in `timing/timing_manager.py` prevents false S/F crossings after satellite reacquire
- Mode-aware sector announcements in `main.py`: I=time+split, S=time, S#=silent
- New voice queries: "what lap am I on?", "best lap?", "how's my pace?"

### Kisti-10 Concurrent Work (same session)
- Fixed ambient sensor → voice pipeline gap (temp/weather queries were falling to LLM because voice_mgr never got ambient data without CAN). Now feeds every 5s.
- Unanswered queries logged to edge memory for future improvement
- Conversation window passthrough fix — timeout was killing text-wake-word mode
- OWW fallback catches Whisper dropping "Hey Jarvis" prefix
- Mic pre-roll increased to 320ms
- Driving conditions sensor handler added

## Prioritized TODO

### Merge Review (FIRST PRIORITY)
- Multiple agents edited the same files. File conflicts flagged by team hook:
  - `main.py` — RS-02, RS-03, kisti-07, kisti-10 all edited
  - `voice/voice_manager.py` — RS-02, RS-03, kisti-10 edited
  - `timing/timing_manager.py` — RS-02, RS-03 edited
  - `timing/geo.py` — kisti-07, RS-03 edited
  - `voice/llm_engine.py` — kisti-07, RS-03 edited
- The Jetson auto-commit cron (`scripts/jetson_auto_commit.sh` every 5 min) picked up some changes before agents committed. Check `git log --oneline -20` for merge commits.
- Run `python3 -m pytest --tb=short -q` to verify 625+ tests still pass after any merges.

### Phase 9: Voice Pipeline Fixes (kisti-10 mostly done)
- [ ] Verify ambient-to-voice gap fix works on Jetson with real Yoctopuce sensor
- [ ] Test unanswered query logging to edge memory
- [ ] Validate OWW passthrough fix doesn't cause false wakes

### Phase 10: Hardware Integration (BLOCKED — GPS09 Pro pending install)
- [ ] GPS09 Pro CAN wiring to Jetson (hardware — JK)
- [ ] Real GPS data validation vs AiM Race Studio 3
- [ ] IMU-assisted track learning

### Future Enhancements
- [ ] Custom "Hey KiSTI" wake word (Colab training)
- [ ] Track map dynamic outline from GPS trace on TRACK mode
- [ ] Status bar track name + timing mode
- [ ] Session-end eager export (force Nextcloud sync on K1 toggle)

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `voice/voice_manager.py:933-1090` | Timing commands + queries + dispatch | ~160 |
| `voice/voice_manager.py:1098-1109` | LLM timing context | 12 |
| `ui/widgets/timing_display.py` | Timing display widget (3 modes) | 230 |
| `ui/track_mode.py` | TRACK mode layout with timing | 85 |
| `main.py:340-400` | Mode-aware announcements + sector | 60 |
| `main.py:407-448` | Zeus push function | 42 |
| `main.py:499-513` | Bridge → UI timing wiring | 15 |
| `timing/timing_manager.py:140-160` | GPS jump filter | 15 |
| `timing/geo.py:149-161` | offset_line for P2P | 13 |
| `tests/test_voice_timing.py` | 60 voice timing tests | ~440 |
| `tests/test_timing_display.py` | 15 display + push tests | ~120 |

## Architecture Notes

### Voice Query Dispatch Chain (complete)
```
handle_voice_query(transcription):
  1. Commands: "say", "remember", "quiet" -> immediate
  2. Timing commands: "P2P", "circuit mode", "reference lap N" -> _handle_timing_command
  3. _answer_from_timing(lower) -> delta, sectors, track, lap count, best, pace
  4. _answer_from_sensors(lower) -> ambient/weather
  5. LLM -> persona response (with timing context in system prompt)
```

### SI Drive Timing Layouts
```
Intelligent (full):     Sport (compact):     Sport Sharp (minimal):
LAP 5 | Laguna [CIR]   1:31.2    -0.3       [green|red] -0.3
1:31.2  -0.3 (g/r)     [S1] [S2] [S3]       (delta bar only)
PRED 1:31.8 THEO 1:29.7
[S1] [S2] [S3]
```

### DuckDB Gotcha (from sim test)
`DuckDBStore.open()` MUST be called before use. Test scripts creating DuckDBStore in temp dirs get `_conn=None` if they skip `open()`. Also `seed_tracks()` needed from `data/tracks_seed.json` for track auto-detection.

## Project Board
Full project with 10 phases, 51 tasks at:
`/home/aldc/projects/active/2026-03-30-kisti-race-analysis/README.md`
P1-8: COMPLETE (42/42). P9: kisti-10 in progress. P10: blocked on hardware.
