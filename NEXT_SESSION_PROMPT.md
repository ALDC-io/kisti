# KiSTI — Next Session Prompt (kisti-18)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 845 tests passing
**Branch**: `kisti-headless`
**Launcher**: `~/k` (ANTHROPIC_API_KEY + KISTI_WAKE_MODEL + KISTI_NO_WAKE=1)

## Section 1: What kisti-17 Did

### Whisper Model Upgrade — DONE
- Upgraded from base.en (142MB) to **medium.en (1.5GB)** on GPU (CUDA was already compiled)
- small.en tested but **rejected** — "Porsche and Subaru" → "potions to brew". medium.en gets proper nouns right
- Latency: base.en ~130ms, small.en ~400ms, **medium.en ~1000ms** on GPU
- Added proper nouns to initial_prompt (Porsche, Subaru, WRX, STI, Brembo, Recaro)
- HTTP timeout bumped 10→15s

### Frontier-First Architecture — DONE
- **Routing flipped**: `_match_safety_fast_path()` → frontier → `_match_persona()` fallback → hard fallback
- Safety/joke/identity queries: instant (<1ms). Everything else: frontier (Claude Haiku)
- `_match_safety_fast_path()`: 20 pre-computed instant entries, min score >= 3
- `_match_persona()` unchanged, demoted to offline/failure fallback
- Timeout-based ack: `threading.Timer(0.3)` — "Let me think about that" only if frontier >300ms
- `LLMEngine.is_real` reflects frontier availability, not Ollama
- 20 new tests → 845 total

### Response Quality Tuning — IN PROGRESS
- Token cap: 100 (Intelligent), 60 (Sport), 20 (Sport Sharp)
- Sentence truncation: 3 (Intelligent), 2 (Sport), 1 (Sport Sharp)
- System prompt: "Lead with the answer, never filler. When comparing, cover BOTH sides."
- **Still an issue**: 3-sentence truncation + model verbosity = comparisons get cut off before covering both sides. The sentence splitter `(?<=[.!?])\s+` is correct but the model spends too many sentences on topic A before reaching topic B.

### TTS Substitutions — DONE
- Added `" 911"` → `" nine eleven"` (was saying "nine hundred and eleven")

### VAD Threshold — DONE
- SPEECH_END_FRAMES 14→19 (448→608ms)

### Stray Persona Match — RESOLVED
- "Yeah, that's it." can't reproduce; kisti-16's score>=10 threshold already fixed it

## Section 2: Prioritized TODO for kisti-18

### 1. Streaming TTS (BIGGEST WIN for latency)
- Current: synthesize entire response → play. TTS is 75% of pipeline latency
- Proposed: split response into sentences, synthesize+play sentence 1 immediately, synthesize remaining in background while playing
- This would cut perceived latency from ~9s to ~2-3s for longer responses
- Requires changes to `voice/tts_engine.py` and `voice/voice_manager.py`

### 2. Response Truncation Strategy
- 3-sentence cap in `_truncate_sentences()` cuts comparisons mid-thought
- Options: (a) bump to 4 sentences and accept TTS cost, (b) tell model to use semicolons instead of periods for related clauses, (c) remove truncation and rely on 100-token cap + system prompt
- Test what the model actually produces with the "cover BOTH sides" prompt instruction

### 3. Install whisper-server systemd service
- Service file updated in repo but NOT installed on Jetson
- Run: `sudo cp ~/repos/kisti/scripts/jetson/whisper-server.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable whisper-server`
- Currently running via nohup

### 4. Wake Word (deferred from kisti-15)
- OWW can't load pkl model, `KISTI_NO_WAKE=1` bypasses

### 5. Edge Memory ONNX Model
- Embedder disabled — needs `/data/models/all-MiniLM-L6-v2-int8/model_quantized.onnx`

## Section 3: Key Files

| File | Key Lines | What Changed |
|------|-----------|--------------|
| `voice/llm_engine.py` | 435-457 (_INSTANT_RESPONSES), 472-513 (_match_safety_fast_path), 655-715 (query routing) | Frontier-first architecture |
| `voice/frontier_engine.py` | 386-403 (system prompt + token caps), 247-249 (truncation) | Response tuning |
| `voice/voice_manager.py` | 33 (import), 713-729 (timeout ack), 746 (log width 200) | Ack pattern + logging |
| `voice/stt_engine.py` | 27 (medium.en), 213 (initial_prompt), 224 (15s timeout) | Whisper upgrade |
| `voice/tts_engine.py` | 55 (" 911" substitution) | TTS fix |
| `voice/mic_capture.py` | 38 (SPEECH_END_FRAMES=19) | VAD threshold |

## Section 4: Jetson State

- **KiSTI**: Running headless, frontier-first routing, KISTI_NO_WAKE=1
- **Whisper**: medium.en on GPU (CUDA), flash attention, ~1s latency
- **Frontier**: Claude Haiku, WiFi connected, conversation history working
- **RAM**: ~3.3 GB available
- **Disk**: 191 GB free (medium.en downloaded to /data/whisper.cpp/models/)
- **systemd**: whisper-server via nohup (NOT systemd yet)

## Section 5: Latency Profile

| Stage | Time | Notes |
|-------|------|-------|
| VAD silence | 608ms | SPEECH_END_FRAMES=19 |
| STT (medium.en GPU) | ~1000ms | Proper nouns accurate |
| LLM safety fast-path | <1ms | Safety/joke/identity |
| LLM frontier live | 1500-3000ms | Claude Haiku API |
| LLM frontier cache | <2ms | DuckDB local |
| TTS (Piper) | ~100ms/word | **Main bottleneck** — streaming TTS is #1 priority |
| Total (safety) | ~2s | Fast path |
| Total (frontier) | ~7-10s | Dominated by TTS |
