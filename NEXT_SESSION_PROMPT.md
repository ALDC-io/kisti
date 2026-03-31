# KiSTI — Next Session Prompt (kisti-18)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 845 tests passing
**Branch**: `kisti-headless`
**Launcher**: `~/k` (ANTHROPIC_API_KEY + KISTI_WAKE_MODEL + KISTI_NO_WAKE=1)

## Section 1: What kisti-17 Did

### Whisper Model Upgrade — DONE
- Upgraded from base.en (142MB) to **medium.en (1.5GB)** for better proper noun transcription
- CUDA was already compiled in (`GGML_CUDA=ON`) — no rebuild needed
- whisper-server running on GPU with flash attention (`-fa` flag)
- Updated `whisper-server.service` to use medium.en
- Updated `stt_engine.py`: model name, initial_prompt (added Porsche/Subaru/WRX/STI/Brembo/Recaro), timeout 10→15s
- **Latency benchmarks** (3s audio, GPU):
  - base.en: ~130ms | small.en: ~400ms | **medium.en: ~1000ms**
- RAM usage: whisper-server ~2.3GB, system 3.3GB available

### Frontier-First Architecture — DONE
- **Flipped routing**: safety fast-path → frontier → persona fallback → hard fallback
- Created `_match_safety_fast_path()`: catches safety/joke/identity queries instantly (<1ms)
  - Pre-computed `_INSTANT_RESPONSES` list: 20 entries (safety + joke + identity/greeting)
  - Minimum score >= 3 to prevent 2-char substring false positives ("fr" in "france")
- `_match_persona()` demoted to offline/failure fallback (still unchanged internally)
- `LLMEngine.query()` rewritten with 4-tier routing
- `LLMEngine.is_real` now reflects frontier availability, not Ollama
- **Timeout-based ack**: `threading.Timer(0.3)` — "Let me think about that" only fires if frontier takes >300ms. Cache hits get no ack.
- 20 new tests added → 845 total

### Stray Persona Match — RESOLVED
- "Yeah, that's it." cannot reproduce on current code — zero matches across all persona entries
- The kisti-16 score >= 10 threshold already fixed this class of false positive

### VAD Silence Threshold — DONE
- Bumped `SPEECH_END_FRAMES` from 14 (448ms) to 19 (608ms)
- Covers most mid-sentence pauses. Negligible responsiveness impact given medium.en (~1s) in pipeline.

## Section 2: Prioritized TODO for kisti-18

### 1. Live Testing & Latency Profiling
- Test medium.en transcription quality with real speech (say "Porsche", "KiSTI", "Subaru" etc.)
- Measure end-to-end pipeline latency: speech end → STT → frontier → TTS start
- If medium.en proper noun accuracy isn't noticeably better than small.en, consider switching back (400ms vs 1000ms)
- Check if 608ms VAD threshold feels natural or too slow in conversation

### 2. Whisper Model Decision: medium.en vs small.en
- medium.en: best accuracy, ~1s STT latency (right at the acceptable limit)
- small.en: good accuracy, ~400ms (2.5x faster)
- **large-v3** (3.1GB): most accurate but would consume ~4GB total with KiSTI — risky on 7.4GB Jetson
- Decision depends on real-world testing results

### 3. Update systemd whisper-server.service on Jetson
- The service file was updated in the repo but NOT installed on the Jetson
- Run: `sudo cp ~/repos/kisti/scripts/jetson/whisper-server.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable whisper-server`
- Currently running via nohup, not systemd

### 4. Wake Word (deferred from kisti-15)
- OWW can't load pkl model, `KISTI_NO_WAKE=1` bypasses
- Real voice samples still needed for custom "Hey KiSTI" model

### 5. Edge Memory ONNX Model
- Embedder disabled: `ONNX model not found at /data/models/all-MiniLM-L6-v2-int8/model_quantized.onnx`
- Download/install for memory search to work

## Section 3: Key Files

| File | Key Lines | What Changed |
|------|-----------|--------------|
| `voice/llm_engine.py` | 435-457 (_INSTANT_RESPONSES), 472-513 (_match_safety_fast_path), 655-715 (query routing) | Frontier-first architecture |
| `voice/voice_manager.py` | 33 (import), 713-729 (timeout ack) | Ack pattern redesign |
| `voice/stt_engine.py` | 27 (model name), 213 (initial_prompt), 224 (timeout) | medium.en upgrade |
| `voice/mic_capture.py` | 38 (SPEECH_END_FRAMES=19) | VAD threshold bump |
| `scripts/jetson/whisper-server.service` | 11 (medium.en + -fa) | Service file update |

## Section 4: Jetson State

- **KiSTI**: Running, headless, KISTI_NO_WAKE=1, frontier-first routing
- **Whisper**: medium.en on GPU (CUDA), flash attention on, ~1s latency
- **Frontier**: Started, WiFi connected, conversation history working
- **RAM**: ~3.3 GB available (whisper-server 2.3GB + KiSTI ~750MB)
- **Disk**: 191 GB free
- **systemd**: whisper-server running via nohup (NOT systemd yet)
