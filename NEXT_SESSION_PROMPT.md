# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 522 tests passing

## Join the CCE Team Session

```
cce-team join project kisti-speaks as kisti-09
```

Key context from kisti-08 (previous contributor):
- Committed + pushed Phase 3 (TimingManager Qt integration) + 3 bug fixes
- **OPEN BUG**: Mic still not responding to voice on Jetson after restart. blockSignals fix deployed but voice UAT failed — KiSTI doesn't respond to speech. The re-entrant signal fix was necessary but NOT sufficient. Deeper mic investigation needed.
- Code is deployed on Jetson (git pull done, service restarted)
- 522 tests passing on workstation

## What Was Done (kisti-08, 2026-03-30)

### Phase 3 — TimingManager Qt Integration: COMPLETE
- `timing/timing_manager.py` — TimingManager(QObject) wired to DiffStateBridge
  - Connects to `bridge.state_changed`, detects GPS updates, calls `LapTimer.update()`
  - Emits signals: `lap_completed`, `sector_completed`, `track_detected`, `p2p_completed`
  - Pushes timing data to bridge via `update_timing()` with `blockSignals` guard
- `main.py` — TimingManager wired after bridge creation (~line 333)
  - Voice announcements for lap complete + track detected
  - Session lifecycle: `set_session_id()` on K1 start, pit lane debrief on stop
- `can/kisti_can.py` — MockCanGenerator GPS trace replaced with Laguna Seca waypoint interpolation (crosses S/F + all 3 sector lines per lap)
- `tests/test_timing_manager.py` — 26 tests (synthetic rectangular track)

### Bug Fixes (committed in same push)
1. **blockSignals in `_update_bridge_timing()`** (`timing/timing_manager.py:216-248`) — `update_timing()` was re-emitting `state_changed`, doubling signal traffic per GPS tick. Fixed with `blockSignals(True/False)` wrapper. This fixed the double-lap test failure.
2. **`lap_number` → `lap_count`** (`data/duckdb_store.py:344`) — telemetry INSERT was using wrong field name, recording NULL for lap count.
3. **Double-lap detection** — root cause was bug #1 (re-entrant signal). blockSignals fix resolved it.

### Phases 1 & 2 (done by prior sessions)
- `timing/geo.py` — 7 GPS primitives, `timing/track_db.py` — track database, `timing/lap_timer.py` — core LapTimer
- DiffState: 10 timing fields + `update_timing()` on DiffStateBridge
- 18 seed tracks, DuckDB timing tables

## Prioritized TODO — START HERE

### 1. FIX: Mic not capturing speech on Jetson (CRITICAL)
The blockSignals fix reduced signal traffic but KiSTI still doesn't respond to voice. Investigate on the Jetson:
- SSH in and check logs: `ssh aldc@192.168.22.131 "journalctl -u kisti --no-pager -n 100"` or check `~/.kisti/logs/`
- Look for: "Mic capture started", "Speech start detected", "Speech captured", "STT:", "Echo suppressed"
- Key suspects:
  - AudioPlayer echo protection at `main.py:525-534` — `playback_started` → `mic.pause()`, `playback_finished` → 800ms delay → `mic.resume()`. If startup speech queue never fully drains, mic may stay paused
  - Echo suppression at `voice/voice_manager.py:698` — 40% word overlap within 3s, may be too aggressive at 9x mic gain
  - PulseAudio source conflict — parecord may not get the USB mic if PA reassigned it
  - Wake word gate at `voice/mic_capture.py:430` — OWW must detect wake word OR passthrough must be True
- Debug approach: add `log.info("_paused=%s, _barge_in=%s", self._paused, self._barge_in_mode)` at top of `_vad_process` loop to see if mic is stuck

### 2. Conversation quality UAT (after mic fix)
- Live voice test on Jetson with real mic
- Test "Hey KiSTI" / "Hey Jarvis" wake word
- Verify multi-turn conversation window (passthrough mode)

### 3. Train "Hey KiSTI" wake word
- Script exists: `scripts/train_wake_word.py`
- Must run on Jetson (needs Piper TTS for synthetic samples)

### 4. Response quality tuning
- Token caps: I=256, S=64, SS=20
- Echo suppression: 40% word overlap within 3s
- Echo guard: 0.8s post-playback delay

## Key Files

| File | Purpose |
|------|---------|
| `timing/timing_manager.py` | Qt bridge: GPS → LapTimer → signals + DuckDB |
| `timing/geo.py` | GPS geometry primitives |
| `timing/track_db.py` | Track database (find, save, seed) |
| `timing/lap_timer.py` | Core LapTimer engine |
| `voice/mic_capture.py` | Mic capture + VAD + wake word gate |
| `voice/voice_manager.py` | Voice pipeline orchestrator |
| `voice/audio_player.py` | AudioPlayer (UI path, Piper TTS → paplay) |
| `main.py:333-358` | TimingManager creation + voice wiring |
| `main.py:525-534` | Echo protection: AudioPlayer → mic pause/resume |
| `model/vehicle_state.py:207-218` | DiffState timing fields |
| `model/vehicle_state.py:581-612` | DiffStateBridge.update_timing() |
| `can/kisti_can.py:807-860` | Laguna Seca waypoint data + interpolation |

## Architecture Notes

### Data Flow
```
GPS09 Pro (CAN) → CanListener → DiffStateBridge → TimingManager → LapTimer
                                        ↓                  ↓
                                   state_changed      ┌────┼────┐
                                   (blockSignals)     ↓    ↓    ↓
                                                   Voice DuckDB  UI
```

### Voice Pipeline (mic → speech)
```
parecord (USB mic) → os.pipe2() → 3x gain → Silero VAD → OWW wake gate
    → speech_captured signal → VoiceManager._on_speech_captured
    → whisper.cpp STT → echo suppression → wake word check
    → handle_voice_query → LLM/persona → _speak_queue → _do_speak
    → Piper TTS → paplay (HDMI) → echo guard 0.8s → mic resumes
```

### Key Design Decisions
- `blockSignals` on `_update_bridge_timing` — prevents re-entrant `state_changed`
- Distance-indexed delta (not time-indexed) — handles variable speed through corners
- Voice-first, screen-second — pit debrief is primary UX
- Mode-aware verbosity: I=full, S=lap+delta, S#=PBs only

### CCE Team Session
- Session: `kisti-speaks` (ID: `71182e9b-8794-458f-b9d6-01a301c9ff58`)
- TUI panel running on pts/7: `python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-speaks`
- Post events via: `curl -X POST -H "X-API-Key: $ZEUS_ALDC_API_KEY" -H "Content-Type: application/json" -d '{"type":"task_claimed","actor":"kisti-09","content":"..."}' "$ZEUS_API_BASE_URL/api/team-session/71182e9b-8794-458f-b9d6-01a301c9ff58/event"`
- Use `learning` or `task_claimed`/`task_completed` event types (broadcast requires original conductor)
