# KiSTI — Next Session Prompt (kisti-12)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 687 tests passing
**Team session**: `kisti-speaks` (session_id: `28ee8c4a-5260-4a09-8224-b57c7dd882fb`)
**Deploy path**: `/home/aldc/repos/kisti/` on Jetson (NOT `/home/aldc/kisti/`)

## Join the CCE Team Session

```
cce-team join project kisti-speaks as kisti-12
```

You are the **conductor** for this session.

## Section 1: What kisti-11 Did

### Persona Narrative Expansion (29 new responses)
- TIER 1 tech: DCCD education (2), turbo operation (4), oil/coolant service (3), fuel economy (3)
- TIER 1 safety: knock detection, fuel quality warning, oil temperature
- TIER 2: braking technique, cornering, g-force, weight transfer, overheat emergency, blowout emergency
- TIER 3 (fun): clutch, flywheel, AiM Strada, brake fluid, Grimmspeed, suspension, swaybars, PDM
- Oil pressure keywords tightened (`["oil pressure", "oil psi"]` not bare `"oil"`)
- Total persona responses: ~86 (up from 57)

### ECU Sensor Voice Handlers (20+ queries)
- `_answer_from_sensors()` expanded: oil temp/pressure, coolant, IAT, boost, battery, fuel pressure, injector duty, lambda/AFR, ethanol, RPM, speed, wheel speeds, brake pressure, steering angle, lateral G, yaw rate, DCCD percent, gear
- ECU block gated on `s.can_connected` — returns live CAN data when Link G5 is online
- Ambient block gated independently on `s.ambient_available`
- Component temp guard at TOP of method prevents "oil temperature" from hitting ambient handler

### Temperature Routing Fix
- Guard at `voice_manager.py:1132-1139`: checks for component qualifiers ("engine", "oil", "coolant", "tire", etc.) BEFORE ambient block
- Without CAN: falls to persona. With CAN: falls to ECU handler
- Tested: "oil temperature" → persona match, "temperature" → ambient

### Echo Loop Mitigation
- Echo guard: 0.4s → 0.8s (`voice_manager.py:897`)
- Word overlap threshold: 40% → 30% (`voice_manager.py:783`)
- Self-trigger suppression: known KiSTI phrases ("I'm listening", "loud and clear", etc.) within 5s of last speech auto-suppressed (`voice_manager.py:787-793`)
- Software gain stays at 3x (2x caused Whisper to drop quieter words like "oil")

### Other
- Sensor onboarding doc: `docs/sensor_onboarding.md`
- TUI progress bar per-session colors in `zeus-memory/scripts/cce-team-panel.py`

## Section 2: Prioritized TODO for kisti-12

### 1. Soak Test Echo Loop (HIGH — validate on Jetson)
- [ ] Leave KiSTI running with mic active for 10+ minutes of conversation
- [ ] Confirm no self-triggering "I'm listening" loops with 0.8s guard + 3x gain
- [ ] If loops recur: extend guard to 1.0s or add RMS-based suppression post-guard
- [ ] Check unanswered query log in edge memory for new patterns

### 2. Check Edge Memory for Real-World Gaps (HIGH)
- [ ] Query edge DuckDB: `SELECT * FROM memories WHERE tags LIKE '%unanswered%' ORDER BY created_at DESC`
- [ ] Identify top unanswered queries that should be persona responses
- [ ] Add missing responses to `PERSONA_RESPONSES` in `voice/llm_engine.py`

### 3. Whisper Transcription Quality (MEDIUM)
- Whisper mangles wake word: "Jarvis House of Oil Temperature", "Jarvis has the tire temperature"
- OWW fallback catches it but noise could affect keyword matching
- Consider: strip known wake-word-adjacent garbage before keyword matching

### 4. Coolant Temperature Persona (MEDIUM)
- [ ] Currently no dedicated coolant temp persona response
- [ ] Add: `["coolant temp", "coolant temperature", "water temp"]` → "Normal range 85 to 95 degrees. Above 100 is warm, above 105 back off immediately."

### 5. Phase 10: Hardware Integration (BLOCKED)
- [ ] GPS09 Pro CAN wiring (hardware — JK)
- [ ] Real GPS data validation vs AiM Race Studio 3
- [ ] IMU-assisted track learning

### 6. Future Enhancements
- [ ] Custom "Hey KiSTI" wake word (Colab training)
- [ ] Track map dynamic outline from GPS trace
- [ ] Session-end eager Nextcloud sync on K1 toggle
- [ ] Run tests on Jetson ARM64 (expect 684+ with 3 pre-existing STT failures)

## Section 3: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `voice/llm_engine.py` | Persona responses | 96-98 (oil pressure), 114-117 (knock/fuel safety), 150-195 (TIER 1 DCCD/turbo/oil/fuel), 196-222 (TIER 2 driving/emergency), 223-260 (TIER 3 components) |
| `voice/voice_manager.py` | Voice pipeline | 783 (30% overlap), 787-793 (self-trigger guard), 897 (0.8s echo guard), 1132-1139 (component temp guard), 1142-1230 (ECU handlers), 1253-1280 (ambient) |
| `voice/mic_capture.py` | Mic capture | 284-287 (3x software gain) |
| `docs/sensor_onboarding.md` | Sensor checklist | Full file |
| `tests/test_voice.py` | Voice tests | ~1075-1300 (TIER 1-3 + temp routing + ECU sensor tests) |

## Section 4: Test Baseline

```
687 passed in 38.7s (workstation, 2026-03-30 13:45 PDT)
Jetson: not yet tested with kisti-11 changes (expect 684+ with 3 pre-existing STT failures)
```

## Section 5: Sensor Coverage Summary

- **93 total data elements** across all sensors
- **~50 voice-queryable** (ambient 6, ECU 25+, timing 15, persona ~86)
- **Key gaps**: GPS altitude/heading, IMU accel/gyro (pending GPS09 Pro install)
- **Onboarding pattern**: `docs/sensor_onboarding.md`
