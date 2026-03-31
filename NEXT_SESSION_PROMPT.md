# KiSTI — Next Session Prompt (kisti-16)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 824 tests passing
**Branch**: `kisti-headless` (commit `9b6b85e`)
**Launcher**: `~/k` (ANTHROPIC_API_KEY + KISTI_WAKE_MODEL + KISTI_NO_WAKE=1)

## Section 1: What kisti-15 Did

### Frontier Engine — LIVE & WORKING
- Restart confirmed, "Frontier LLM engine started" in logs
- Standalone test: boxer engine query → Claude Haiku response ~2s
- 3/3 unique jokes from random pool
- **Prewarm**: 34 queries cached (auto, subaru, tuning, handling, racing, stem)
- **Markdown stripping**: `_strip_markdown()` before TTS, system prompt says "plain text only"
- **2-sentence cap**: `_truncate_sentences()` on both live and cached responses
- **Token cap**: 120 (Intelligent), 60 (Sport), 20 (Sport Sharp) — enough to finish sentences

### Persona → Frontier Passthrough — PARTIALLY WORKING, NEEDS MORE TUNING
- General knowledge signals ("how does", "what is", "compare") bypass persona at score < 10
- Short fragments (≤3 words, score ≤6, no self-ref) pass to frontier
- Self-referencing queries ("your engine", "you make") still match persona
- **Still too greedy on some queries** — JK reported it's "not quite there"
- VAD splits long sentences (pauses mid-question), fragments hit persona separately
- **Check logs on startup** — JK wants next session to verify frontier responses are working

### Wake Word — BROKEN, BYPASSED
- OWW can't load pkl model (expects ONNX)
- Whisper mangles "Hey KiSTI" → "He's to", "Kesti", "See" with USB mic
- `KISTI_NO_WAKE=1` in `~/k` bypasses wake word requirement (all speech → query)
- This means KiSTI responds to ALL ambient speech — only for bench testing
- **Root cause**: USB mic quality + 3x gain + whisper base.en model

### Wake Word Training
- scipy upgraded to 1.15.3
- pkl classifier trained at `/data/models/hey_kisti.pkl` (99.2% accuracy)
- NOT compatible with OWW loader — needs integration layer in `mic_capture.py`
- Real voice samples (JK) still needed

### Voice Commands for Frontier Control — ALREADY DONE (kisti-14)
- "enable cloud" / "disable cloud" / "cloud status" all working with tests

## Section 2: Prioritized TODO for kisti-16

### 1. Tune Persona→Frontier Scoring (HIGH — JK says "not quite there")
- Check logs first: `tail -50 /tmp/kisti_startup.log` — are frontier responses reaching TTS?
- Problem: single-keyword matches ("engine", "subaru", "boxer") intercept general knowledge
- Current fix: GK signals need score ≥10, fragments ≤3 words blocked without self-ref
- Consider: weighted scoring (multi-word keywords score higher than single-word), or whitelist approach
- Key file: `voice/llm_engine.py:488-520` (`_match_persona` scoring logic)
- Test persona changes against: "compare porsche and subaru boxers", "what is trail braking", "tell me about your engine", "tell me a joke"

### 2. JK's Architecture Question: Frontier-First Design
- JK asked: "should we start with frontier AI with local Zeus memory context and only fall back to local LLM when connectivity is lost?"
- This inverts the current tier order: frontier → persona → fallback (instead of persona → frontier → fallback)
- Would make persona a fast-path cache for known questions, frontier the default brain
- Significant architectural change — needs plan mode

### 3. VAD Sentence Splitting
- VAD cuts sentences on natural pauses, sending fragments separately
- "Explain the difference between Porsche and [pause] Subaru Boxer Engines" → 2 queries
- Consider: accumulation buffer that waits for sentence-final intonation or longer silence

### 4. Wake Word Integration (pkl → OWW bridge)
- `/data/models/hey_kisti.pkl` exists but `mic_capture.py` expects ONNX
- Need: load pkl alongside OWW preprocessor, run classifier on embeddings
- Or: full ONNX training via Colab
- Record 50 real voice samples: `python3 scripts/record_wake_samples.py --count 50`

## Section 3: Key Files

| File | Key Lines |
|------|-----------|
| `voice/llm_engine.py` | 130 (engine keywords), 389 (subaru/joke keywords), 466-525 (_match_persona + GK filter + fragment filter) |
| `voice/frontier_engine.py` | 63-75 (_strip_markdown + _truncate_sentences), 207-210 (cache truncation), 240 (live truncation), 367-370 (token caps), 380 (plain text system prompt) |
| `voice/voice_manager.py` | 169-188 (WAKE_WORDS), 835-840 (KISTI_NO_WAKE bypass), 847 (wake word gate) |
| `voice/mic_capture.py` | 75-164 (OWW init + passthrough) |
| `scripts/prewarm_frontier_cache.py` | 37-72 (PREWARM_QUERIES) |

## Section 4: Jetson State

- **KiSTI**: Running, headless, KISTI_NO_WAKE=1
- **Frontier**: Started, 34 cached entries, WiFi connected
- **RAM**: ~2.2 GB / 7.4 GB
- **scipy**: 1.15.3
- **Commit**: `9b6b85e`
