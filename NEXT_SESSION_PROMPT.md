Continue KiSTI voice pipeline UAT. Repo: /home/aldc/repos/kisti/. Jetson at
192.168.22.131 (SSH user aldc, sudo password: aldc1234).

## What was done (kisti-05 + kisti-06, commits aaf8272 → af09adf)

### parecord pipe blocker — FIXED + CLEANED UP
The mic capture pipeline is fully working. Three-part fix:

1. **os.pipe2() instead of subprocess.PIPE** — raw fd I/O bypasses Python's
   BufferedReader. Alone this wasn't enough.
2. **start_new_session=True** — isolates parecord from KiSTI's Qt process group.
   Without this, PA's epoll in the child process is blocked by inherited state.
   This was the real fix.
3. **3x software gain** — USB mic (KTMicro) has NO ALSA capture control. PA is
   sole amplifier. At PA 300%, speech RMS ~1000 (Silero needs ~2000+). 3x
   software multiply in read_fn brings it to detection range.

### Cleanup completed (kisti-06, commit af09adf)
- Removed unused `struct` import
- Removed diagnostic logs: "VAD loop starting", "First frame received", `_frame_n` counter
- Removed dead `_find_sd_device()` method (never called in production)
- Removed `TestSounddeviceBackend` class (5 dead tests for removed code)

### What was tried and failed
- **sounddevice.InputStream** — captures audio fine, but PortAudio's ARM
  resampler (48kHz→16kHz) produces audio Silero VAD can't detect (max conf
  0.20 even at high RMS). PA's native resampler works (conf 0.55+). NOT viable.
- **scipy.signal.decimate** at 48kHz→16kHz — also fails Silero (max 0.18)
- **os.pipe() alone** (without start_new_session) — parecord still writes 0 bytes
- **stdbuf -o0** — doesn't affect PA-internal buffering

### Verified on Jetson
- Wake word detection: hey_jarvis_v0.1 at 0.67-1.00 confidence
- STT: "How is the oil pressure?" transcribed correctly (0.24s, conf 0.9)
- Full pipeline: mic → VAD → OWW → STT → persona → TTS → speaker

### Test baseline
- 361/361 on dev machine (366 original, 5 dead sounddevice tests removed)
- Expect 358/361 on Jetson (same 3 pre-existing env-specific failures)

## Prioritized TODO for next session

### 1. Train custom "Hey KiSTI" wake word model (HIGH)
- openwakeword supports custom ONNX training
- Currently using `hey_jarvis_v0.1` — user wants "Hey KiSTI"
- Set `KISTI_WAKE_MODEL=/data/models/hey_kisti.onnx` in kisti-session
- Memory notes misheard variants: need to include in training data
- Training guide: https://github.com/dscripka/openwakeword (custom model docs)

### 2. Start Ollama for real LLM responses (MEDIUM)
- Currently persona-first mode (Ollama stopped for GPU headroom)
- KiSTI says "I'm listening" instead of answering questions
- `sudo systemctl start ollama` on Jetson, or modify kisti-session line 63
- Test: ask "How is the oil pressure?" — should get actual LLM response

### 3. Echo/barge-in tuning (MEDIUM)
- 3x software gain makes OWW trigger on KiSTI's own speaker output
- User reported "i'm listening i'm listening" loop — self-triggering
- May need to increase OWW_THRESHOLD_BARGE_IN above 0.85 (voice/mic_capture.py:50)
- Or increase echo guard duration beyond 0.3s
- Or mute mic during TTS entirely (current: mic paused during TTS)

### 4. Rename misleading method names (LOW)
- `_run_sounddevice()` → `_run_parecord_pipe()` (it uses parecord, not sounddevice)
- `_run_arecord()` → `_dispatch_capture()` (dispatcher, not arecord)
- Update docstrings to match

## Key files
- voice/mic_capture.py:226-286 — `_run_sounddevice()` (os.pipe + parecord, despite name)
- voice/mic_capture.py:312+ — `_vad_process()` with generic read_fn/alive_fn
- voice/voice_manager.py — PipelineTrace, _compose_and_speak, barge-in
- scripts/kisti-session:83-87 — PA mic gain (300%)
- tests/test_voice.py — 361 tests, all passing

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo aldc1234 | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"
