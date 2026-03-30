Continue KiSTI voice pipeline hardening (kisti-006). Repo: /home/aldc/repos/kisti/.
Jetson at 192.168.22.131 (SSH user aldc, sudo password: aldc1234).
Project: /home/aldc/projects/active/2026-03-29-kisti-006/
TUI: python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-speaks

## What was done (kisti-006 session, commits 113445b → dc49234)

### Phase 1: Custom wake word scaffolding — DONE
- Created `scripts/train_wake_word.py` — synthetic sample generation via Piper TTS
  (7 phrase variants × 6 voices × 5 speeds = ~210 positive samples)
  + openwakeword `train_custom_verifier()` path (fast, .pkl)
  + full ONNX training YAML config path (for Colab)
- `KISTI_WAKE_MODEL` env added to kisti-session (conditional: falls back to
  hey_jarvis_v0.1 when /data/models/hey_kisti.onnx doesn't exist yet)
- 19 new tests (TestWakeWordTraining + TestWakeModelSessionConfig)
- **MODEL NOT YET TRAINED** — script exists, needs to run on Jetson

### Phase 2: Ollama enabled — DONE
- kisti-session: `systemctl stop ollama` → `systemctl start ollama` + 3s warmup
- Added `/etc/sudoers.d/ollama-kisti` for passwordless systemctl on Jetson
- LLM engine confirmed: `llama3.2:3b via Ollama` in startup log

### Phase 3: Echo/barge-in — DONE (3 layers)
1. OWW_THRESHOLD_BARGE_IN 0.85 → 0.92 (mic_capture.py:49)
2. Echo guard 0.3s → 0.8s (voice_manager.py)
3. RMS > 5000 echo gate in barge-in path (mic_capture.py)
4. **CRITICAL FIX** (main.py:476-491): AudioPlayer.playback_started → mic.pause(),
   playback_finished → QTimer(800ms) → mic.resume(). Root cause was
   kisti_mode._start_speaking() played audio WITHOUT any mic interaction —
   echo at 0.99 confidence triggered "I'm listening" loop.

### Phase 4: Cleanup — DONE
- `_run_sounddevice()` → `_run_parecord_pipe()` (definition, call site, docstring, log)

### Hotfix: WAKE_WORDS text list — DONE
- Added "jarvis" + "hey jarvis" to WAKE_WORDS (voice_manager.py:171)
- Root cause: OWW detects hey_jarvis audio pattern, Whisper transcribes as
  "Jarvis, ..." text, but "jarvis" wasn't in WAKE_WORDS → query silently dropped
- **General rule**: for ANY OWW model, check what Whisper transcribes the trigger
  phrase as and add that text to WAKE_WORDS

### Test baseline: 380/380 (was 361, +19 new)

## What was tried and failed (THIS SESSION)
- `time.sleep(0.8)` in Qt signal handler → FROZE THE UI. Always QTimer.singleShot()
- OWW_THRESHOLD_BARGE_IN at 0.92 alone doesn't prevent echo — echo arrives at 0.99
- `sudo -n systemctl start ollama` fails in GDM session — need sudoers.d entry
- Setting KISTI_WAKE_MODEL to nonexistent ONNX path → openwakeword crashes. Must check file exists

## What was tried and failed (PRIOR SESSIONS — DO NOT REPEAT)
- sounddevice.InputStream — PortAudio ARM resampler breaks Silero VAD (max 0.20)
- scipy.signal.decimate 48kHz→16kHz — also fails Silero (max 0.18)
- os.pipe() without start_new_session — parecord writes 0 bytes
- stdbuf -oL/-o0 — doesn't fix PA internal buffering
- Adding wake phrase words (hey/hi/hello/kisti) to Whisper hallucination filter — blocks valid wake words
- Echo guard 2.0s was too long (killed barge-in), 0.3s too short. 0.8s is the sweet spot

## Verified on Jetson (latest deploy dc49234)
- Echo protection: 4 startup lines without self-trigger ✓
- Ollama: llama3.2:3b connected ✓
- Wake word: hey_jarvis_v0.1 loaded (CPU), "jarvis" in WAKE_WORDS ✓
- whisper.cpp: server connected at port 8081, 0.29-0.32s latency ✓
- USB speaker: Jieli @ 78% ✓
- USB mic: KTMicro PA=300% ✓
- Nextcloud sync: weather data syncing ✓

## Known issues
- **STT=mock in startup log** — cosmetic only. whisper.cpp server mode doesn't set
  `self._model`, so `is_real` returns False. Fix: stt_engine.py:319 should check
  `self._backend is not None` not just `self._model`
- **Custom "Hey KiSTI" wake word not trained** — script exists at
  scripts/train_wake_word.py but needs Piper voices on Jetson to generate samples.
  Currently using hey_jarvis_v0.1 (say "Hey Jarvis" to trigger)

## Prioritized TODO for next session

### 1. Conversation quality UAT (HIGH)
- JK testing live on Jetson — collect feedback on LLM responses
- Test: "Hey Jarvis, how is the oil pressure?" → should get real LLM response
- Test conversation flow: wake word → question → answer → follow-up (8s window)
- If LLM too slow (~2-4s), tune persona responses to cover common queries
- If LLM hallucinating, adjust system prompt in llm_engine.py

### 2. Train custom "Hey KiSTI" wake word (HIGH)
- Run: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && python3 scripts/train_wake_word.py"`
- Needs Piper voices at /data/piper/ (Danny confirmed, check for others)
- openwakeword custom_verifier_model path is fastest (~2-5 min)
- Test: "Hey KiSTI" triggers, "Hey Jarvis" does not
- After training, update WAKE_WORDS to remove jarvis variants, keep kisti variants

### 3. Fix STT=mock cosmetic log (LOW)
- stt_engine.py:319 — `is_real` should check `self._backend is not None`

### 4. Conversation window multi-turn (MEDIUM)
- After wake word + answer, follow-up questions shouldn't need re-saying wake word
- Conversation window is 8s (voice_manager.py). Verify it works end-to-end
- May need to extend window or make it adaptive

### 5. Response quality tuning (MEDIUM)
- Expand persona keyword responses for common car questions
- Tune LLM system prompt for vehicle context awareness
- Test mode filtering: Intelligent=full, Sport=short, Sport Sharp=critical only

## Architecture notes (for the incoming session)

### Dual speech path — CRITICAL to understand
Two independent paths play audio through the speaker:
1. **voice_manager._do_speak()** — has barge-in mode, sets OWW threshold, manages
   echo guard. Used for LLM/persona responses to voice queries.
2. **kisti_mode._start_speaking()** → AudioPlayer — used for startup speech, alerts,
   ambient announcements, UI-triggered speech. Had ZERO echo protection until
   main.py wiring fix (commit 48e064c).

Echo protection now works via main.py wiring: AudioPlayer.playback_started → mic.pause(),
playback_finished → QTimer(800ms) → mic.resume(). This covers path #2.

### Wake word detection — two layers
1. **Audio layer**: openwakeword (OWW) detects audio pattern (hey_jarvis model)
2. **Text layer**: Whisper transcribes speech, voice_manager checks WAKE_WORDS list
Both must agree. When switching wake word models, must update WAKE_WORDS text list
to match what Whisper transcribes the trigger phrase as.

### LLM 3-tier fallback
1. Persona keyword match (sub-ms, 200+ curated responses)
2. Ollama llama3.2:3b (2-4s on Orin Nano)
3. Fallback: "Not sure about that. Ask me about boost, oil, or brakes."

## Key files
- main.py:476-491 — echo protection wiring (AudioPlayer → mic pause/resume)
- voice/mic_capture.py:49 — OWW_THRESHOLD_BARGE_IN = 0.92
- voice/mic_capture.py:225 — _run_parecord_pipe() (renamed)
- voice/mic_capture.py:355 — RMS > 5000 echo gate
- voice/voice_manager.py:168-182 — WAKE_WORDS list (includes jarvis)
- voice/voice_manager.py:689-721 — _on_speech_captured (wake word + query routing)
- voice/llm_engine.py:90-275 — PERSONA_RESPONSES
- voice/llm_engine.py:412-463 — 3-tier query (persona → Ollama → fallback)
- scripts/kisti-session — Ollama start + KISTI_WAKE_MODEL fallback
- scripts/train_wake_word.py — wake word sample gen + training (not yet run)
- tests/test_voice.py — 380 tests passing

## CCE session info
- Team session: kisti-speaks (71182e9b)
- TUI: `python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-speaks`
- Zeus ZMIDs: echo root cause (d8926bcf), wake word text mismatch (8b84ddd8),
  OWW ARM64 (12ad1a39), whisper.cpp CUDA (40a16647)

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo aldc1234 | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"
