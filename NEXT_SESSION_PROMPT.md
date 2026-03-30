Continue KiSTI voice conversation hardening (kisti-007). Repo: /home/aldc/repos/kisti/.
Jetson at 192.168.22.131 (SSH user aldc, sudo password: aldc1234).
Project: /home/aldc/projects/active/2026-03-29-kisti-006/
Team session: kisti-speaks (71182e9b)
TUI: python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-speaks

## What was done (kisti-007 session, commit 775587e)

### Echo suppression — DONE (voice_manager.py)
- Removed sensor/telemetry words from WAKE_WORDS (temperature, boost, oil pressure,
  humidity, tire, etc.) — these caused echo loops when KiSTI said responses containing them
- Added echo text suppression: tracks `_last_spoken_text` + `_last_spoken_at`,
  rejects transcriptions with >40% word overlap within 3s of speaking
- Sensor questions still work via 5s conversation window after wake word activation
- **VERIFIED on Jetson**: "I'm listening" played with ZERO re-trigger (was looping before)

### Token caps + context window — DONE (llm_engine.py)
- Intelligent: 64 -> 256 tokens (conversational depth)
- Sport: 32 -> 64 tokens
- Sport Sharp: unchanged at 20
- Added `num_ctx: 8192` explicitly to Ollama options

### STT is_real cosmetic fix — DONE (stt_engine.py:319)
- `is_real` now checks `self._backend is not None` (whisper.cpp server sets _backend not _model)
- "Let me think about that." acknowledgment now appears before LLM queries

### Test baseline: 385/385 (was 380, +5 echo suppression tests)

## What was tried and failed (THIS SESSION)
- Ollama panicked on first query with num_ctx=8192 (HTTP 500, loadModel crash)
  — restarted Ollama service, models available again. May need model warmup on startup
- Mic got stuck paused after ~4 minutes — race condition between dual speech paths
  (AudioPlayer UI path + _do_speak voice loop path both toggle mic pause/resume)

## What was tried and failed (PRIOR SESSIONS — DO NOT REPEAT)
- sounddevice.InputStream — PortAudio ARM resampler breaks Silero VAD (max 0.20)
- scipy.signal.decimate 48kHz->16kHz — also fails Silero (max 0.18)
- os.pipe() without start_new_session — parecord writes 0 bytes
- stdbuf -oL/-o0 — doesn't fix PA internal buffering
- Adding wake phrase words (hey/hi/hello/kisti) to Whisper hallucination filter — blocks valid wake words
- Echo guard 2.0s was too long (killed barge-in), 0.3s too short. 0.8s is the sweet spot
- time.sleep(0.8) in Qt signal handler — FROZE THE UI. Always QTimer.singleShot()
- OWW_THRESHOLD_BARGE_IN at 0.92 alone doesn't prevent echo — echo arrives at 0.99
- sudo -n systemctl start ollama fails in GDM session — need sudoers.d entry
- Setting KISTI_WAKE_MODEL to nonexistent ONNX path — openwakeword crashes. Must check file exists

## Known issues — ACTIVE BUGS

### 1. Mic stuck paused (CRITICAL)
After a few interactions, mic stops capturing speech. Root cause: dual speech paths
race on mic pause/resume. Both `_do_speak` (voice loop) and AudioPlayer (UI path)
toggle mic state. Fix options:
a) Remove the `response_ready.emit()` → AudioPlayer path for query responses
   (only use for system/alert speech that doesn't go through _do_speak)
b) Add a mic resume watchdog — if no speech capture for 10s while in IDLE state, force resume
c) Unify to single speech path

### 2. Ollama cold start panic
First query after GDM restart hits HTTP 500. Ollama panics loading model with num_ctx=8192.
Fix: add a warmup query in kisti-session after Ollama starts (curl to /api/chat with tiny prompt).

## Prioritized TODO for next session

### 1. Fix mic stuck bug (CRITICAL)
- The dual speech path mic race must be resolved before conversation UAT
- See "Known issues" above for fix options
- After fix, verify: 10+ consecutive queries without mic dropping out

### 2. Train custom "Hey KiSTI" wake word (HIGH)
- Run: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && python3 scripts/train_wake_word.py"`
- Needs Piper voices at /data/piper/ (Danny confirmed, check for others)
- openwakeword custom_verifier_model path is fastest (~2-5 min)
- After training, update WAKE_WORDS to remove jarvis variants, keep kisti variants

### 3. Conversation quality UAT (HIGH)
- Blocked by mic stuck bug (TODO 1)
- Test: "Hey Jarvis, how is the oil pressure?" -> should get LLM response (not fallback)
- Test conversation flow: wake word -> question -> answer -> follow-up (5s window)
- If LLM too slow (~2-4s), tune persona responses to cover common queries

### 4. Conversation window multi-turn (MEDIUM)
- After wake word + answer, follow-up questions shouldn't need re-saying wake word
- Conversation window is 5s (voice_manager.py:244). Verify it works end-to-end
- May need to extend window or make it adaptive

### 5. Response quality tuning (MEDIUM)
- Expand persona keyword responses for common car questions
- Tune LLM system prompt for vehicle context awareness
- Test mode filtering: Intelligent=full, Sport=short, Sport Sharp=critical only

### 6. Add Ollama warmup to kisti-session (LOW)
- After `systemctl start ollama` + 3s sleep, add a tiny warmup query
- `curl -s -X POST localhost:11434/api/chat -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hi"}],"options":{"num_ctx":8192,"num_predict":1}}'`
- This pre-loads the model into GPU memory before KiSTI's first real query

## Architecture notes (for the incoming session)

### Dual speech path — CRITICAL to understand (and fix)
Two independent paths play audio through the speaker:
1. **voice_manager._do_speak()** — has barge-in mode, manages echo guard,
   tracks _last_spoken_text for echo suppression. Called from voice loop thread.
2. **kisti_mode._start_speaking()** -> AudioPlayer — used for startup speech,
   alerts, UI-triggered speech. Echo protection via main.py:485-494 (mic pause/resume).

**BUG**: `_compose_and_speak` emits `response_ready` (AudioPlayer path) AND
puts text in `_speak_queue` (_do_speak path). Same text gets spoken by BOTH paths.
Both paths toggle mic pause/resume. Race condition causes mic to get stuck paused.

### Wake word detection — two layers
1. **Audio layer**: openwakeword (OWW) detects audio pattern (hey_jarvis model)
2. **Text layer**: Whisper transcribes speech, voice_manager checks WAKE_WORDS list
Both must agree. When switching wake word models, must update WAKE_WORDS text list.

### Echo suppression (NEW in 775587e)
After _do_speak, stores `_last_spoken_text` (lowercase) and `_last_spoken_at`.
In _on_speech_captured, if transcription has >40% word overlap with last spoken text
within 3s, logs "Echo suppressed" and discards. Works alongside the 0.8s hardware guard.

### LLM 3-tier fallback
1. Persona keyword match (sub-ms, 200+ curated responses)
2. Ollama llama3.2:3b (2-4s on Orin Nano, 256 token cap in Intelligent mode)
3. Fallback: "Not sure about that. Ask me about boost, oil, or brakes."

## Key files
- main.py:476-494 — echo protection wiring (AudioPlayer -> mic pause/resume) + response_ready -> queue_speech
- voice/mic_capture.py:49 — OWW_THRESHOLD_BARGE_IN = 0.92
- voice/mic_capture.py:225 — _run_parecord_pipe() (renamed)
- voice/mic_capture.py:355 — RMS > 5000 echo gate
- voice/voice_manager.py:168-176 — WAKE_WORDS list (sensor words REMOVED)
- voice/voice_manager.py:254-256 — _last_spoken_text + _last_spoken_at (echo suppression state)
- voice/voice_manager.py:689-700 — echo suppression check in _on_speech_captured
- voice/voice_manager.py:706-734 — wake word + query routing
- voice/llm_engine.py:75-79 — MODE_TOKEN_CAPS (I:256, S:64, SS:20)
- voice/llm_engine.py:499 — num_ctx: 8192 in Ollama options
- voice/stt_engine.py:319-322 — is_real checks _backend
- scripts/kisti-session — Ollama start + KISTI_WAKE_MODEL fallback
- scripts/train_wake_word.py — wake word sample gen + training (not yet run)
- tests/test_voice.py — 385 tests passing

## CCE session info
- Team session: kisti-speaks (71182e9b)
- TUI: `python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-speaks`
- Zeus ZMIDs: echo root cause (d8926bcf), wake word text mismatch (8b84ddd8),
  OWW ARM64 (12ad1a39), whisper.cpp CUDA (40a16647)

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo aldc1234 | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"
