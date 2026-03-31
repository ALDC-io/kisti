# KiSTI — Next Session Prompt (kisti-16)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (voice mode — KiSTI running fullscreen on Jetson)
**Test baseline**: 824 tests passing
**Team session**: `kisti-speaks`
**Deploy path**: `/home/aldc/repos/kisti/` on Jetson (branch: `kisti-headless`)
**Launcher**: `~/k` (auto-detects mic, sets ANTHROPIC_API_KEY + KISTI_WAKE_MODEL)

## Section 1: What kisti-15 Did

### Task 1: Restart KiSTI with Frontier Engine — DONE
- Killed old PID 2416, started via `~/k`, verified "Frontier LLM engine started" in logs
- Standalone frontier test confirmed: boxer engine headers question → Claude Haiku response in ~2s
- Joke test confirmed: 3/3 unique jokes from `random.choice()` pool
- Live voice tested by JK: persona matches working ("Can you hear me?", "Tell me about the brakes")

### Task 2: Wake Word Training — PARTIAL
- **scipy upgraded** to 1.15.3 (fixes `scipy.io.wavfile` attribute error)
- **OWW custom verifier can't train new wake word**: base `hey_jarvis` model scores "Hey KiSTI" at 0.00008 (needs 0.5). Architectural mismatch — custom verifier only personalizes existing wake words, can't create new ones
- **Alternative approach**: trained raw embedding classifier at `/data/models/hey_kisti.pkl` (99.2% accuracy, 50 KB, logistic regression on openwakeword preprocessor features)
- **pkl model not compatible** with OWW loader in `mic_capture.py` (expects ONNX). Needs integration layer
- `KISTI_WAKE_MODEL=/data/models/hey_kisti.pkl` added to `~/k` (staged, not active)
- `train_wake_word.py` already had correct `hey_jarvis` model name
- **Still needed**: real voice samples (JK), pkl→OWW integration in `mic_capture.py`, or full ONNX training via Colab

### Task 3: Voice Commands for Frontier Control — ALREADY DONE (kisti-14)
- `_handle_frontier_command` at `voice_manager.py:1018-1050` — fully implemented
- Commands: "enable cloud", "disable cloud", "cloud status" + 3 variants each
- DuckDB settings persistence, boot-time consent check, 12 tests
- No work needed this session

### Task 4: Frontier Cache Prewarm + Soak Test — DONE
- **New**: `scripts/prewarm_frontier_cache.py` — 34 queries across 6 categories (auto, subaru, tuning, handling, racing, stem)
- **New**: `tests/test_prewarm_frontier.py` — 7 tests
- **Prewarm executed**: 34/34 queries cached, ~157s total, avg 4s/query
- **Soak status**: KiSTI running healthy, 943 MB RSS (12%), 4.9 GB available, no errors
- Cached queries will serve at ~2ms instead of ~4s

## Section 2: Prioritized TODO for kisti-16

### 1. Wake Word Integration (HIGH — model trained, needs code)
- [ ] Add pkl verifier layer to `mic_capture.py` alongside OWW
- [ ] Load pkl model, extract embeddings from OWW preprocessor, run classifier
- [ ] If positive + threshold, treat as wake detection
- [ ] Record 50 real "Hey KiSTI" samples from JK: `python3 scripts/record_wake_samples.py --count 50`
- [ ] Retrain with real + synthetic samples for better accuracy
- [ ] Alternative: full ONNX training via Colab notebook (https://github.com/dscripka/openwakeword)

### 2. Soak Test Monitoring (MEDIUM — running, needs observation)
- [ ] Monitor frontier cache hit ratio over time (grep logs for "cache hit/miss")
- [ ] Check memory usage stability over 24h
- [ ] Verify WiFi transition handling (connect/disconnect iPhone hotspot)
- [ ] Ask JK to test general knowledge questions via voice to see frontier responses
- [ ] Check for DuckDB memory leaks or connection issues

### 3. Zeus Memory Proxy for Frontier (MEDIUM)
- [ ] Route frontier queries through Zeus API for centralized auth/logging/cost tracking
- [ ] New Zeus endpoint: `POST /api/v1/chat/completions`
- [ ] Single API key management, query attribution per device

### 4. Phase 10: Hardware Integration (BLOCKED on hardware)
- [ ] GPS09 Pro CAN wiring (JK)
- [ ] Real GPS data validation
- [ ] IMU-assisted track learning

## Section 3: Key Files with Line Numbers

| File | Purpose | Key Lines |
|------|---------|-----------|
| `voice/frontier_engine.py` | Frontier LLM engine | 63-95 (class), 99-128 (start), 170-234 (query), 243-288 (cache), 324-338 (cache_stats) |
| `voice/voice_manager.py` | Voice pipeline + commands | 617-675 (command routing), 1018-1050 (_handle_frontier_command), 335-347 (boot consent) |
| `voice/mic_capture.py` | Mic + OWW wake detection | 75-133 (init + OWW load), 358-460 (OWW predict loop) |
| `voice/llm_engine.py` | Persona + frontier wire | 440-455 (car jokes), 460-510 (_match_persona), 634-653 (frontier call) |
| `data/edge_memory.py` | Edge memory + settings | 45 (settings DDL), 375-400 (get/set setting) |
| `scripts/prewarm_frontier_cache.py` | **NEW** Cache prewarm | 37-72 (PREWARM_QUERIES), 75-120 (prewarm function) |
| `scripts/train_wake_word.py` | Wake word training | 329-394 (custom verifier — won't work for new wake word) |
| `tests/test_prewarm_frontier.py` | **NEW** 7 prewarm tests | Full file |

## Section 4: Test Baseline

```
824 passed in 97.57s (workstation, 2026-03-31)
Breakdown: 817 (kisti-14) + 7 (frontier prewarm)
Jetson: running kisti-14 code (commit 0ca70d0) + prewarm script via scp
```

## Section 5: Jetson System State

- **KiSTI running**: PID 56676, headless mode, voice ON
- **Frontier engine**: Started, Claude Haiku, WiFi check 30s
- **Frontier cache**: 34 prewarmed entries in DuckDB
- **Ollama**: DISABLED
- **whisper-server**: Running at port 8081
- **RAM**: 2.2 GB used / 4.9 GB available
- **Disk**: /data NVMe 429 GB free
- **WiFi**: Connected
- **Piper voices**: 10 at `/data/piper/`
- **TTS cache**: 420 .cache files
- **Wake model**: `/data/models/hey_kisti.pkl` (50 KB, not integrated)
- **Wake samples**: 200 positive + 301 negative in `/tmp/kisti_wake_samples/`
- **scipy**: 1.15.3 (upgraded from 1.8.0)
- **Branch**: `kisti-headless` (Jetson has commit `0ca70d0` + prewarm script via scp)
- **ANTHROPIC_API_KEY**: Set in `~/k`
- **KISTI_WAKE_MODEL**: Set in `~/k` (pkl, not active — OWW can't load it)

## Section 6: Uncommitted Changes (workstation)

```
2 files not yet committed:
  scripts/prewarm_frontier_cache.py (new)
  tests/test_prewarm_frontier.py (new)
Branch ahead of origin/kisti-headless by 2 commits
```
