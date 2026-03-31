# KiSTI — Next Session Prompt (kisti-17)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 825 tests passing
**Branch**: `kisti-headless` (commit `82dde70`)
**Launcher**: `~/k` (ANTHROPIC_API_KEY + KISTI_WAKE_MODEL + KISTI_NO_WAKE=1)

## Section 1: What kisti-16 Did

### Persona Scoring Fix — DONE
- Replaced two fragile filters (GK signals + fragment filter) with unified self-ref guard
- Rule: non-safety, non-joke queries without self-reference ("your", "you", "my", "kisti") need score >= 10
- Single keywords like "engine"(6), "boxer"(6), "subaru"(6) now route to frontier
- Self-referencing queries still match persona instantly
- 18 tests updated to expect frontier routing; 1 new self-ref test added → 825 total

### Frontier Conversation History — DONE
- `FrontierLLMEngine.query()` and `_call_api()` now accept `conversation_history` parameter
- Last 3 `DialogueTurn` objects passed as multi-turn messages to Claude API
- Cache skipped when conversation history present (context-dependent answers)
- Wired through `LLMEngine.query()` → `voice_manager.py` passes `self._dialogue.last_turns`
- Verified working in logs: follow-up questions get contextual answers

### System Prompt Rewrite — DONE
- `KISTI_SYSTEM_PROMPT` rewritten to be conversational, not spec-heavy
- Build facts kept as reference ("share when asked, not by default")
- Added: "Do NOT mention your own build, specs, or parts in general knowledge answers"
- Removed: roast mode spec ammunition, "fire back with specs" instruction
- Verified: "Porsche vs Subaru" answer no longer references "our EJ257"

### VAD Silence Threshold — DONE
- `SPEECH_END_FRAMES` bumped from 8 (256ms) to 14 (448ms)
- Reduces sentence splitting on natural speech pauses
- Still splitting on longer pauses — may need further tuning

## Section 2: Prioritized TODO for kisti-17

### 1. Upgrade Whisper Model (HIGH — JK says transcription is poor)
- Current: `ggml-base.en.bin` (142MB) — misses proper nouns ("Porsche" → "Portia's")
- `ggml-small.en.bin` (466MB) already downloaded at `/data/whisper.cpp/models/`
- **Recommended**: Download `medium.en` (1.5GB) for best accuracy — Jetson has 5GB RAM free
- Download: `cd /data/whisper.cpp/models && bash download-ggml-model.sh medium.en`
- Restart whisper-server: `pkill -f whisper-server && nohup /data/whisper.cpp/build/bin/whisper-server -m /data/whisper.cpp/models/ggml-medium.en.bin --host 127.0.0.1 --port 8081 -t 4 > /tmp/whisper_server.log 2>&1 &`
- Then restart KiSTI: `pkill -f 'python3.*main' && nohup ~/k > /tmp/kisti_startup.log 2>&1 &`
- **Test latency** — medium.en will be slower (~0.5-1s vs 0.2s for base). If too slow, fall back to small.en
- Consider: start with small.en, test, then try medium.en

### 2. Frontier-First Architecture (JK wants this — needs plan mode)
- Current: persona → frontier → fallback
- Proposed: frontier → persona → fallback
- Persona becomes fast-path cache for known answers, frontier is default brain
- Eliminates scoring problem entirely — everything goes to frontier unless known fast answer
- Key concern: latency (frontier ~2-4s vs persona <1ms) and offline behavior
- **Start with plan mode** — significant architectural change

### 3. VAD Further Tuning
- 448ms helps but still splits on longer pauses
- Consider accumulation buffer that waits for sentence-ending patterns
- Or: increase to 600ms but test for responsiveness tradeoff

### 4. Stray Persona Match Investigation
- "Yeah, that's it." → persona_match: "The difference between a project car..." (score >= 10 somehow)
- Low priority — investigate which keyword entry is matching

### 5. Wake Word (deferred from kisti-15)
- OWW can't load pkl model, `KISTI_NO_WAKE=1` bypasses
- Real voice samples still needed for custom "Hey KiSTI" model

## Section 3: Key Files

| File | Key Lines | What Changed |
|------|-----------|--------------|
| `voice/llm_engine.py` | 32-66 (system prompt), 493-510 (unified self-ref guard) | Prompt rewrite + scoring fix |
| `voice/frontier_engine.py` | 191-265 (query with history), 374-420 (_call_api multi-turn) | Conversation history |
| `voice/voice_manager.py` | 718 (passes dialogue.last_turns) | Wired conversation history |
| `voice/mic_capture.py` | 38 (SPEECH_END_FRAMES=14) | VAD threshold bump |

## Section 4: Jetson State

- **KiSTI**: Running, headless, KISTI_NO_WAKE=1, commit `82dde70`
- **Whisper**: base.en model (small.en downloaded but NOT active yet)
- **Frontier**: Started, WiFi connected, conversation history working
- **RAM**: ~2.2 GB / 7.4 GB (plenty for model upgrade)
- **Disk**: 191 GB free
