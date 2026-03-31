# KiSTI — Next Session Prompt (kisti-14)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (headless voice mode — no display)
**Test baseline**: 767 tests passing
**Team session**: `kisti-speaks`
**Deploy path**: `/home/aldc/repos/kisti/` on Jetson (branch: `kisti-headless`)
**Launcher**: `~/k` (headless, auto-detects mic)

## Section 1: What kisti-13 Did

### ECU Keyword Guard — 3-Tier Split (voice_manager.py:1154-1200)
- Split `_ECU_KEYWORDS` into `_ECU_LIVE_PHRASES`, `_ECU_COMPONENT_BARE`, `_LIVE_DATA_INDICATORS`
- Multi-word live phrases (oil temp, brake pressure) always block when CAN disconnected
- Bare component words (brake, tire, boost) only block when combined with a live-data indicator
- "tell me about the brakes" → now reaches persona (was "No ECU connected")
- "what's my brake pressure" → still correctly blocked
- 17 new tests in `tests/test_ecu_guard.py`

### TTS Disk Cache (tts_engine.py)
- SHA-256 hash-based disk cache at `data/tts_cache/`
- Cache key computed after TTS_SUBSTITUTIONS applied
- Binary format: 4B sample_rate + 4B envelope_len + envelope floats + raw PCM
- Model hash validation — auto-invalidates on voice model change
- `clear_cache()` method for manual flush
- **Result**: 3,175ms → 2ms for cached persona responses
- 8 new tests in `tests/test_tts_cache.py`

### STT Recognition Improvements (stt_engine.py)
- Added `language=en` + `initial_prompt` with automotive vocabulary to whisper.cpp server requests
- Fixed hallucination filter: `startswith()` → exact match only
  - "yeah what about the boost" was being silently killed as hallucination (starts with "yeah")
  - Now only bare "yeah", "oh", "well" etc. are filtered
- Raised echo suppression overlap threshold 0.3 → 0.5 (voice_manager.py:787)
  - Follow-up questions about same topic no longer suppressed as echo
- 15 new tests in `tests/test_stt_prompt.py`

### Audio Playback — pacat Direct Pipe (voice_manager.py:948-990)
- Replaced temp WAV file + paplay with `pacat --raw` stdin pipe
- Eliminates temp file write + cleanup overhead before speech starts
- Falls back to paplay + WAV if pacat unavailable

### Wake Word Stripping Fix (voice_manager.py:168-183)
- Reordered WAKE_WORDS longest-first: "hey kisty" before "hey ki"
- Was: "Hey Kisty, tell me about oil" → stripped "hey ki" → left "sty, tell me..."
- Now: strips full "hey kisty" cleanly

### Factory Specs + Persona Expansion (build_record.py, llm_engine.py)
- Added `FactorySpec` dataclass with complete 2014 STI factory specifications
- Added `factory_vs_build()` comparison function
- Added piston/bore/stroke fields to `EngineSpec`
- 17 new persona entries: pistons, spark plugs, oil level, battery, factory comparisons,
  gear ratios, differentials, fuel tank, factory weaknesses, DCCD modes, factory turbo/brakes/suspension
- General "oil" catch-all persona entry added
- 34 new tests in `tests/test_persona_factory.py`

### New Scripts
- `scripts/prewarm_tts_cache.py` — pre-synthesize all persona responses + event quotes to warm cache
- `scripts/record_wake_samples.py` — mic recording utility for real wake word samples
- `scripts/__init__.py` — package init for scripts module
- 6 new tests across `tests/test_prewarm.py` and `tests/test_record_wake.py`

### Jetson State at Session End
- Deployed: both commits (`ea8bc49` main features + `8011bac` hotfixes)
- Branch: `kisti-headless`
- KiSTI running headless with new code
- Synthetic wake word sample generation in progress (200 positive + 500 negative)
- TTS cache prewarm in progress

## Section 2: Prioritized TODO for kisti-14

### 1. Research: Network-Connected Frontier AI Model Integration (HIGH — NEW)
- [ ] Research architecture for a complementary network-connected mode that uses frontier AI models (Claude, GPT-4o, Gemini) when WiFi/cellular available
- [ ] Design hybrid inference: local persona (instant, offline) + frontier API (deep reasoning, online)
- [ ] **Online benefits**: Complex multi-turn conversation, nuanced automotive diagnostics, real-time weather/traffic integration, deeper build knowledge via RAG against Zeus Memory cloud
- [ ] **Offline corpus enrichment**: When online, download and cache frontier model responses to expand the local persona/knowledge base. Next time offline, those responses are available locally
- [ ] Consider: Claude API via Zeus Memory proxy (auth already exists), Deepgram STT is already hybrid (stt_engine.py:327 HybridSTTEngine), conversation context window management, cost/latency tradeoffs
- [ ] Design pattern: persona match (0ms) → cached frontier response (2ms) → live frontier API (~500ms) → fallback
- [ ] Privacy: which queries go to cloud? User consent model? Edge-first, cloud-optional
- [ ] Existing infrastructure: `HybridSTTEngine` already checks WiFi every 30s, `DEEPGRAM_API_KEY` env var pattern, Zeus Memory API at `api.analyticlabs.io`
- [ ] Prototype: add a `FrontierLLMEngine` class alongside the existing `LLMEngine` in `voice/llm_engine.py`

### 2. Train Custom "Hey KiSTI" Wake Word (HIGH — in progress)
- [ ] Check if synthetic sample generation completed (`/tmp/kisti_wake_samples/`)
- [ ] Record ~50 real "Hey KiSTI" samples: `python3 scripts/record_wake_samples.py --count 50`
- [ ] Train custom verifier locally: `python3 scripts/train_wake_word.py`
- [ ] Or: upload to Colab for full ONNX training
- [ ] Deploy: `export KISTI_WAKE_MODEL=/data/models/hey_kisti.pkl` in `~/k`
- [ ] Validate false positive rate with car noise / background conversation
- [ ] Env var `KISTI_WAKE_MODEL` already supported in mic_capture.py:119-128
- OWW has 6 pretrained tflite models on Jetson, 10 Piper voices available for synthesis

### 3. TTS Pre-warm Verification (MEDIUM)
- [ ] Verify prewarm script completed on Jetson
- [ ] Check `data/tts_cache/` directory — should have ~100+ .cache files
- [ ] Test: all persona responses should be instant on first query after restart

### 4. Expand Car Jokes / Humor Responses (MEDIUM)
- [ ] Currently only 1 joke entry: "A Mustang, a Camaro, and an STI walk into a corner..."
- [ ] Add 10-15 more car jokes with keyword variety: "another joke", "different joke", "tell me another", "more jokes", "got any more"
- [ ] Consider: random selection from a list (like event_quotes pattern) instead of single response
- [ ] Topics: JDM vs muscle, turbo life, AWD vs RWD, mechanic humor, car meet culture, Subaru-specific
- [ ] Could integrate with event_quotes.py pattern for variety on repeat queries

### 5. Soak Test All Changes (MEDIUM)
- [ ] Leave KiSTI headless running for extended period
- [ ] Verify: ECU guard allows bare component queries through to persona
- [ ] Verify: TTS cache works across restarts
- [ ] Verify: STT accuracy improved (filler words not filtered, echo suppression relaxed)
- [ ] Verify: pacat audio pipe works reliably (no silent failures)
- [ ] Check edge DuckDB for new unanswered queries: `SELECT * FROM memories WHERE tags LIKE '%unanswered%'`

### 5. Phase 10: Hardware Integration (BLOCKED on hardware)
- [ ] GPS09 Pro CAN wiring (JK)
- [ ] Real GPS data validation
- [ ] IMU-assisted track learning

## Section 3: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `main.py` | Bootstrap + headless mode | 65 (--headless flag), 127-136 (QCoreApp), 710-715 (headless boot greeting) |
| `voice/voice_manager.py` | Voice pipeline | 168-183 (WAKE_WORDS longest-first), 787 (echo overlap 0.5), 860 (_do_speak), 948-990 (_start_audio pacat + fallback), 1154-1200 (3-tier ECU guard) |
| `voice/llm_engine.py` | Persona + LLM | 91-430 (PERSONA_RESPONSES, now ~103 entries), 450-494 (_match_persona) |
| `voice/tts_engine.py` | TTS + disk cache | 124-135 (__init__ cache params), 154-174 (speak with cache), 176-239 (cache methods) |
| `voice/stt_engine.py` | STT engine | 27 (base.en model), 91 (hallucination exact match), 199-214 (whisper.cpp + language/prompt) |
| `voice/mic_capture.py` | Mic + wake word | 119-128 (KISTI_WAKE_MODEL), 159-165 (passthrough mode) |
| `data/build_record.py` | Build + factory specs | 24-128 (EngineSpec with pistons), 137-168 (BaselineTargets), 214-310 (FactorySpec), 313 (FACTORY), 316-330 (factory_vs_build) |
| `scripts/train_wake_word.py` | Wake word training | Full pipeline, 200+ pos / 500+ neg samples |
| `scripts/prewarm_tts_cache.py` | TTS cache pre-warm | Pre-synthesizes all persona + event quotes |
| `scripts/record_wake_samples.py` | Real sample recorder | parecord 16kHz mono, count-based |

## Section 4: Test Baseline

```
767 passed in 38.45s (workstation, 2026-03-30 20:20 PDT)
Jetson: headless mode, all changes deployed
```

## Section 5: Jetson System State

- **Ollama**: DISABLED (service file renamed, not running)
- **whisper-server**: Running at port 8081 (base.en model, 4 threads, ~523 MB)
- **RAM**: ~2.5 GB used / 4.7 GB available (headless + no Ollama)
- **Disk**: /data NVMe 429 GB free, root 191 GB free
- **GPU**: Orin Nano, CUDA 12.6, no GPU processes currently
- **KiSTI launcher**: `~/k` (headless, auto-detects USB mic)
- **WiFi**: Connected (JK iPhone hotspot or Heckler)
- **Piper voices**: 10 available at `/data/piper/` (danny-low, lessac-medium, amy-medium, joe-medium, alba-medium, cori-medium, semaine-medium, kusal-medium, libritts_r-medium, ryan-medium)
- **Branch**: `kisti-headless` (deployed commits ea8bc49 + 8011bac)
- **Background tasks**: Synthetic wake word generation + TTS prewarm (may have completed)

## Section 6: Architecture Notes for Frontier AI Integration

The current voice pipeline is:
```
Mic → VAD → STT (whisper.cpp) → Wake Word Check → Query Routing:
  1. Commands (say/remember/timing)
  2. Sensors (_answer_from_sensors, ECU guard)
  3. LLM/Persona:
     a. _match_persona() — keyword scoring, <1ms
     b. Ollama (DISABLED, commented out)
     c. FALLBACK_RESPONSE
```

The frontier integration slot is at step 3b — where Ollama used to be. Instead of local LLM:
- Check WiFi availability (HybridSTTEngine pattern already exists)
- If online: call frontier API (Claude/GPT-4o) with build context + telemetry + query
- Cache the response text + TTS audio for offline replay
- If offline: check cached frontier responses before falling back

Key files to study:
- `voice/stt_engine.py:327` — HybridSTTEngine with WiFi check pattern (reuse for LLM)
- `voice/llm_engine.py:547-555` — Ollama call site (replacement point)
- `data/edge_memory.py` — DuckDB local storage (could store cached frontier responses)
- Zeus Memory API — cloud RAG for build knowledge, meeting clips, service history
