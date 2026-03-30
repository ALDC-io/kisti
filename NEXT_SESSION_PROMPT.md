# KiSTI — Next Session Prompt (kisti-11)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 625 tests passing
**Team session**: `kisti-speaks` (session_id: `71182e9b-8794-458f-b9d6-01a301c9ff58`)

## Join the CCE Team Session

```
cce-team join project kisti-speaks as kisti-11
```

TUI panel running on pts/7.

## Section 1: What RS-03 Did (Phases 5-8, Race Analysis)

### Phase 5: Voice Timing Integration (49 tests)
- `_answer_from_timing()` at `voice/voice_manager.py:998` — keyword dispatch: delta, theoretical best, lap time, predicted, sectors, track name, lap count, best lap, pace
- `_handle_timing_command()` at `voice/voice_manager.py:933` — voice commands: P2P mode, set start/end, circuit mode, reference lap N
- Mode-aware lap announcements in `main.py:343-375` — I=full, S=lap+delta, S#=PBs only
- Mode-aware pit debrief at `main.py:436-463` — session end summary by SI Drive mode
- LLM timing context at `voice/voice_manager.py:1098-1109`

### Phase 6: UI + Data Sync (15 tests)
- `ui/widgets/timing_display.py` — TimingDisplayWidget (QPainter, 3 SI Drive layouts)
- Wired into `ui/track_mode.py`, bridge at 4Hz in `main.py:499-513`
- Zeus Memory push in `main.py:407-448` (background thread on session end)
- `offset_line()` in `timing/geo.py:149-161` for P2P voice commands

### Phase 7: Jetson Validation — ALL PASS
- 611/614 on ARM64 (3 pre-existing STT failures: GPU device discovery + SciPy)
- Timing display renders all 3 modes on ARM64 offscreen
- 8/8 voice timing queries pass E2E on Jetson

### Phase 8: Polish & Edge Cases (11 tests)
- GPS jump filter (>500m) in `timing/timing_manager.py`
- Mode-aware sector announcements
- New voice queries: "what lap?", "best lap?", "how's my pace?"

## Section 2: What kisti-10 Did (Phase 9, Voice Pipeline Fixes)

### CRITICAL FIX: Passthrough Bug (`voice_manager.py:738-741`)
- Conversation window timeout was killing text-wake-word mode after first utterance
- `_last_interaction = 0.0` → `in_conversation = False` → `set_passthrough(False)` on first speech
- **Fix**: Removed conversation window passthrough expiry. Text-wake-word mode stays permanent.

### OWW Fallback Wake Detection (`voice_manager.py:775-777`)
- OWW detects "Hey Jarvis" but Whisper drops it from transcription (e.g., "Can you hear me?" instead of "Hey Jarvis, can you hear me?")
- **Fix**: `self._mic._last_wake_detected` used as fallback when text has no wake word

### Ambient Sensor → Voice Pipeline Gap (`main.py:247-258`)
- `voice_mgr.set_telemetry()` was only called from CAN frame callback (line 490). No CAN = no ambient data in voice manager
- Temperature/weather queries fell to 30s Ollama fallback
- **Fix**: `ambient_source.reading_updated` now feeds voice_mgr every ~5s

### Additional Fixes
- **Mic pre-roll** 5→10 frames (160ms→320ms) — captures wake word onset (`mic_capture.py:43`)
- **Persona tuning** — speed/emergency/launch responses rewritten for 2-sentence TTS cap (`llm_engine.py:143-150`)
- **AWD TTS** — "AWD" → "all wheel drive" in `tts_engine.py:45`
- **Millibars** — barometric pressure spoken as "millibars" not "hectopascals"
- **Driving conditions** — "good day for driving?" answers from live ambient (`voice_manager.py:1138-1145`)
- **Unanswered query logging** — fallback queries stored to edge memory with tags [unanswered, voice, improvement] (`voice_manager.py:700-710`)
- **"dc" added to WAKE_WORDS** — Whisper transcribes "KiSTI" as "DC"

## Section 3: Merge Review Status

**All file conflicts are RESOLVED.** The CCE team hook warnings are stale — all changes are committed linearly on main with no actual git conflicts.

```
$ git status
On branch main, up to date with origin/main, working tree clean
```

Recent commit trail (newest first):
```
6aa51a6 Session handoff: Phases 5-8 complete, 625 tests
8e144f8 fix: speak barometric pressure in millibars
c6b572e feat: log unanswered queries + driving conditions
4a66287 fix: ambient sensor data now reaches voice manager without CAN
3732024 fix: persona responses fit 2-sentence TTS cap + AWD
1a5dd8c fix: AWD TTS substitution
a847390 Race analysis Phase 8: GPS dropout, sector announcements
84e4e60 merge: rs-02/rs-03 changes
b02255b Race analysis Phases 5+6: voice timing + UI + Zeus push
```

## Section 4: Prioritized TODO for kisti-11

### 1. Persona Narrative Expansion (HIGH PRIORITY)
Full gap audit at `docs/persona_gap_audit.md` — 42 keyword entries needed (~25-30 responses).
- **57 persona responses** exist (7 safety, 17 tech, 33 fun)
- **TIER 1 (12 responses)**: DCCD education (2), turbo operation (4), oil/coolant service (3), fuel economy (3), knock/detonation (2)
- **TIER 2 (6 responses)**: braking/cornering technique (4), overheat/blowout emergency (2)
- **TIER 3 (8 responses)**: component specs (clutch, flywheel, AiM, brakes, exhaust, suspension, swaybars, PDM)
- **Pattern**: Apply Zeus Chat prepopulated-narrative approach — expand persona responses so fewer queries fall to slow Ollama fallback
- Keep all responses to 2 sentences max (TTS latency constraint at `llm_engine.py:323-326`)
- The unanswered query log in edge memory will show real gaps over time

### 2. Validate Phase 9 Fixes on Jetson (MEDIUM)
- [ ] Confirm ambient-to-voice fix works on Jetson with real Yoctopuce sensor (tested briefly — "22.8 degrees" confirmed)
- [ ] Confirm OWW passthrough fix doesn't cause false wakes in extended use
- [ ] Test driving conditions handler: "Hey Jarvis, good day for driving?"
- [ ] Run full test suite on Jetson: expect 611+ (3 pre-existing STT failures)

### 3. Self-Triggering Loop (KNOWN BUG)
- Mic gain (PA 300% + 3x software) amplifies speaker output → Whisper transcribes KiSTI's own speech → "I'm listening" loop
- Echo guard (0.4s) helps but isn't bulletproof with 3x gain
- Potential fix: longer echo guard, or reduce software gain now that PA 300% alone gives adequate RMS (raw RMS=529, with 3x=1586, 0% clipping)

### 4. Phase 10: Hardware Integration (BLOCKED)
- [ ] GPS09 Pro CAN wiring to Jetson (hardware — JK)
- [ ] Real GPS data validation vs AiM Race Studio 3
- [ ] IMU-assisted track learning

### 5. Future Enhancements
- [ ] Custom "Hey KiSTI" wake word (Colab training)
- [ ] Track map dynamic outline from GPS trace
- [ ] Status bar track name + timing mode
- [ ] Session-end eager Nextcloud sync on K1 toggle

## Section 5: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `voice/voice_manager.py` | Voice pipeline orchestrator | 738-742 (passthrough fix), 775-777 (OWW fallback), 933-1090 (timing commands/queries), 1098-1109 (telemetry context), 1122-1149 (sensor handler), 700-710 (fallback logging) |
| `voice/mic_capture.py` | Mic capture + VAD | 43 (PRE_ROLL_FRAMES=10), 87 (passthrough flag), 163 (passthrough=True at start), 285 (3x software gain) |
| `voice/llm_engine.py` | Persona responses + Ollama LLM | 168-276 (PERSONA_RESPONSES), 278 (FALLBACK_RESPONSE), 323-343 (2-sentence truncation) |
| `voice/stt_engine.py` | Whisper STT | 27 (base.en model), 28 (whisper.cpp at :8081) |
| `voice/tts_engine.py` | Piper TTS + substitutions | 31-53 (TTS_SUBSTITUTIONS including AWD) |
| `voice/audio_player.py` | UI AudioPlayer path | 247-272 (_expand_abbreviations) |
| `main.py` | Main app wiring | 247-258 (ambient→voice feed), 343-375 (mode-aware announcements), 490 (CAN telemetry feed), 528-540 (echo protection) |
| `ui/widgets/timing_display.py` | Live timing widget | Full file — 3 SI Drive layouts |
| `data/build_record.py` | Vehicle specs | BASELINES (alert thresholds), EngineSpec, build_summary() |
| `data/event_quotes.py` | 47 event categories | Wired in main.py + alerts |

## Section 6: Test Baseline

```
625 passed in 38.67s (workstation, 2026-03-30 12:47 PDT)
611 passed on Jetson ARM64 (3 pre-existing STT failures: GPU device discovery + SciPy version)
```

Test breakdown by area (approximate):
- Original baseline: ~380 (model, CAN, sensors, UI, voice, alerts, memory)
- Phase 1-4 timing: ~130 (geo, track_db, lap_timer, timing_manager, track_learner)
- Phase 5-6 voice timing: ~64 (voice_timing, timing_display)
- Phase 7-8 polish: ~11 (additional queries, GPS dropout)
- Phase 9 (kisti-10): 0 new tests added (all fixes were runtime behavior)

## Project Board

Full project with 10 phases, 52 tasks at:
`/home/aldc/projects/active/2026-03-30-kisti-race-analysis/README.md`
P1-9: COMPLETE (52/52). P10: blocked on hardware.
