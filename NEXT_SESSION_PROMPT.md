# KiSTI — Next Session Prompt (kisti-15)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (voice mode — KiSTI running fullscreen on Jetson)
**Test baseline**: 804 tests passing
**Team session**: `kisti-speaks`
**Deploy path**: `/home/aldc/repos/kisti/` on Jetson (branch: `kisti-headless`)
**Launcher**: `~/k` (auto-detects mic)

## Section 1: What kisti-14 Did

### FrontierLLMEngine — Cloud AI with Edge Cache (voice/frontier_engine.py)
- NEW `FrontierLLMEngine` class: WiFi-aware cloud LLM (Claude Haiku API) with DuckDB response caching
- 4-tier query resolution: persona (0ms) → frontier_cache (2ms) → live frontier (~500ms) → fallback
- WiFi checker daemon thread (30s interval, HybridSTTEngine pattern from stt_engine.py:332)
- DuckDB `frontier_cache` table: query_hash PK, response_text, TTL (30 days), hit counting
- Direct Claude Messages API via urllib.request, 10s timeout, Haiku model
- Privacy-first: only queries that miss persona AND ECU guard reach frontier (general knowledge only)
- Timezone-safe cache TTL (handles DuckDB naive vs UTC-aware datetimes)
- 26 new tests in `tests/test_frontier_engine.py`

### LLMEngine Integration (voice/llm_engine.py:634-653)
- Added `frontier` parameter to LLMEngine.__init__()
- Wired frontier query between disabled Ollama and FALLBACK_RESPONSE
- Exception-safe: frontier errors gracefully fall back
- LLMEngine.query() flow: persona match → frontier (cache then API) → fallback

### VoiceManager Integration (voice/voice_manager.py)
- Creates FrontierLLMEngine from `ANTHROPIC_API_KEY` env var
- Passes it to LLMEngine via `frontier=` parameter
- Wires DuckDB connection via `set_duckdb_store()` for response caching
- Start/stop lifecycle integrated with voice pipeline

### Car Jokes — Random Selection Pool (voice/llm_engine.py)
- 15 car jokes in `CAR_JOKES` list with `random.choice()` on repeat queries
- Sentinel pattern: `__JOKE__` in PERSONA_RESPONSES → intercepted in `_match_persona()`
- Extended keywords: "another joke", "different joke", "tell me another", "more jokes", "got any more"
- Topics: JDM vs muscle, turbo humor, AWD vs RWD, mechanic jokes, Subaru stereotypes
- Mode-filtered: jokes only in Intelligent mode (fun category)
- 11 new tests in `tests/test_jokes.py`

### Jetson State Verified
- TTS cache: 420 .cache files (well above 100+ target)
- KiSTI running fullscreen (PID 2416), RAM 2.0/7.4 GB, disk 429 GB free
- Wake word samples: `/tmp/kisti_wake_samples/` does NOT exist — needs regeneration

## Section 2: Prioritized TODO for kisti-15

### 1. Deploy kisti-14 Changes to Jetson (HIGH)
- [ ] `git push` on workstation, `ssh aldc@192.168.22.131 "cd repos/kisti && git pull"` on Jetson
- [ ] Add `ANTHROPIC_API_KEY` to Jetson environment (in `~/k` launcher or `.env`)
- [ ] Restart KiSTI to pick up frontier engine + jokes
- [ ] Test: ask a general knowledge question → should get Claude Haiku response
- [ ] Test: ask "tell me a joke" multiple times → should get different jokes
- [ ] Check logs for "Frontier LLM engine started" and "Frontier cache hit/miss" messages

### 2. Regenerate Wake Word Samples + Train (HIGH — blocked on sample gen)
- [ ] `/tmp/kisti_wake_samples/` was lost (reboot/cleanup). Regenerate:
  `ssh aldc@192.168.22.131 "cd repos/kisti && python3 scripts/train_wake_word.py"`
- [ ] This generates 200 positive + 500 negative synthetic samples, then trains custom verifier
- [ ] Output model: `/data/models/hey_kisti.pkl`
- [ ] Set `KISTI_WAKE_MODEL=/data/models/hey_kisti.pkl` in `~/k`
- [ ] Record ~50 real "Hey KiSTI" samples with JK's voice:
  `python3 scripts/record_wake_samples.py --count 50`
- [ ] Retrain with combined synthetic + real for better accuracy

### 3. Zeus Memory Proxy for Frontier (MEDIUM — enhancement)
- [ ] Current: direct Claude API calls from Jetson via ANTHROPIC_API_KEY
- [ ] Enhancement: route through Zeus Memory API at zeus.aldc.io for centralized auth, logging, and cost tracking
- [ ] Would require new Zeus endpoint: `POST /api/v1/chat/completions` (proxy to Claude API)
- [ ] Benefits: single API key management, query logging in Zeus, cost attribution per device

### 4. Frontier Cache Enrichment (MEDIUM)
- [ ] When online, proactively fill cache with common automotive knowledge queries
- [ ] Script similar to `scripts/prewarm_tts_cache.py` but for frontier responses
- [ ] Precompute answers for known persona gaps (complex explanations, multi-step reasoning)
- [ ] Consider: frontier responses could also be stored in edge_memory as `memory_type="frontier_knowledge"` for semantic search

### 5. Soak Test Frontier Engine (MEDIUM)
- [ ] Leave KiSTI running with frontier engine enabled for extended period
- [ ] Monitor: cache hit ratio, API latency, WiFi transitions
- [ ] Verify: frontier answers cached correctly, available offline after first query
- [ ] Check: no memory leaks from WiFi checker thread

### 6. Phase 10: Hardware Integration (BLOCKED on hardware)
- [ ] GPS09 Pro CAN wiring (JK)
- [ ] Real GPS data validation
- [ ] IMU-assisted track learning

## Section 3: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `voice/frontier_engine.py` | **NEW** Frontier LLM engine | 66-100 (class + lifecycle), 150-220 (query), 230-285 (cache), 290-340 (API call) |
| `voice/llm_engine.py` | Persona + LLM + frontier wire | 91-437 (PERSONA_RESPONSES), 440-455 (CAR_JOKES + sentinel), 460-510 (_match_persona with joke intercept), 546-557 (LLMEngine.__init__ with frontier), 634-653 (frontier call site) |
| `voice/voice_manager.py` | Voice pipeline | 32 (FrontierLLMEngine import), 274-276 (frontier init from ANTHROPIC_API_KEY), 337 (frontier.start()), 374 (frontier.stop()), 433-434 (wire DuckDB to frontier) |
| `tests/test_frontier_engine.py` | **NEW** 26 frontier tests | Full file |
| `tests/test_jokes.py` | **NEW** 11 joke tests | Full file |
| `main.py` | Bootstrap | 65 (--headless), 304-325 (Zeus sync), 710-715 (boot greeting) |
| `voice/stt_engine.py` | STT + hybrid WiFi pattern | 332-486 (HybridSTTEngine — frontier engine modeled on this) |
| `data/edge_memory.py` | Edge memory + DuckDB | 64-376 (EdgeMemory class) |
| `scripts/train_wake_word.py` | Wake word training | 329-394 (custom verifier path) |

## Section 4: Test Baseline

```
804 passed in 44.33s (workstation, 2026-03-31)
Breakdown: 767 (kisti-13 baseline) + 11 (jokes) + 26 (frontier engine)
Jetson: changes NOT yet deployed
```

## Section 5: Jetson System State

- **Ollama**: DISABLED (service renamed, not running)
- **whisper-server**: Running at port 8081 (base.en model)
- **RAM**: 2.0 GB used / 5.3 GB available (8 GB Orin Nano)
- **Disk**: /data NVMe 429 GB free
- **KiSTI running**: PID 2416, fullscreen mode (not headless)
- **WiFi**: Connected
- **Piper voices**: 10 available at `/data/piper/`
- **TTS cache**: 420 .cache files (prewarm complete)
- **Wake samples**: `/tmp/kisti_wake_samples/` DOES NOT EXIST — needs regeneration
- **Branch**: `kisti-headless` (kisti-14 changes NOT yet pushed/deployed)
- **ANTHROPIC_API_KEY**: NOT yet set on Jetson

## Section 6: Architecture — Frontier LLM Integration

```
User speaks → Mic → VAD → STT (whisper.cpp) → Wake Word Check → Query Routing:
  1. Commands (say/remember/timing)
  2. Sensors (_answer_from_sensors, ECU guard)
  3. LLM/Persona:
     a. _match_persona() — keyword scoring, <1ms, includes joke sentinel
     b. FrontierLLMEngine (NEW):
        i.  Cache lookup (DuckDB frontier_cache) — ~2ms
        ii. Live Claude Haiku API (WiFi required) — ~500ms
     c. FALLBACK_RESPONSE
```

Privacy boundary: steps 1-2 + 3a filter out all sensor/personal queries.
Only general knowledge that misses persona matching reaches the frontier engine.
Frontier engine is WiFi-aware (30s check interval) and caches responses for offline replay.
