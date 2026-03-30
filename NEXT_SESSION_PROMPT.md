Continue KiSTI voice pipeline UAT. Repo: /home/aldc/repos/kisti/. Jetson at
192.168.22.131 (SSH user aldc, sudo password: aldc1234).

## What was done this session (kisti-04, commits c9b5ebc → 10deecf)

### Phase 4 — ALL CODE COMPLETE, 361/361 tests
- **4.1 Barge-in**: mic stays active during TTS with raised OWW threshold (0.85).
  Wake word interrupts playback. Critical alerts use full pause. Echo guard 2.0→0.3s.
- **4.2 Response Composer**: `_compose_and_speak()` unifies all handle_voice_query paths.
  VoiceResponse created for every response. record_turn for all user queries.
- **4.3 Latency instrumentation**: PipelineTrace dataclass tracks STT→LLM→TTS→speaker.
  Logged per interaction. DuckDB voice_latency table stores all traces.
- **4.4 QA harness**: conftest.py with shared fixtures. 17 new tests.

### Previous session work (kisti-03)
- Reference resolver upgraded (idiomatic phrase detection, staleness check)
- Wake word model path configurable (KISTI_WAKE_MODEL env var)
- Button pad K1/K4 conflict fixed (K4 voice toggle via mode_manager, K2 PTT)
- Deepgram hybrid STT engine

### Mic gain tuning
- kisti-session script: ALSA=100%, PA=200% (was ALSA=60%, PA=150%)
- 500% drowned Silero VAD in noise. 200% gives clean separation:
  ambient RMS=110 (conf 0.002), speech RMS=2100-4500 (conf 0.87-1.0)

## CRITICAL BLOCKER: parecord pipe buffering (NOT YET FIXED)

**Problem**: parecord subprocess in mic_capture.py writes ZERO bytes to its stdout
pipe. `cat /proc/<pid>/fdinfo/1` shows `pos: 0` after minutes of running. The mic
capture thread blocks forever on `proc.stdout.read(1024)`.

**Root cause**: parecord uses PulseAudio's internal buffering, NOT libc stdio.
`stdbuf -o0` and `stdbuf -oL` don't help because they only affect libc buffers.
parecord's PA client writes to stdout via PA's async mainloop, which buffers
independently.

**Confirmed**: Manual `parecord ... > file` works (62KB/2s). Manual Python
`subprocess.Popen + stdout=PIPE` in a standalone script works. But inside KiSTI's
Qt event loop + threading, the pipe stays empty.

**Hypothesis**: Qt's event loop or Python's GIL interferes with the pipe read.
The mic capture thread calls `proc.stdout.read(1024)` which blocks, but the
parecord child process may need the PA mainloop to run, which requires the GIL
or event loop attention.

**Possible fixes (try in order)**:
1. **Use `parec` instead of `parecord`** — same binary, different name, may have
   different buffering behavior
2. **Use `--latency-msec=50`** flag on parecord — forces smaller buffer sizes
3. **Replace parecord with PyAudio/sounddevice** — read directly from PA in Python,
   no subprocess needed. `sounddevice.InputStream` with callback avoids pipe entirely
4. **Use `os.pipe()` + `os.read()`** instead of `subprocess.PIPE` — lower-level,
   avoids Python's buffered IO wrapper
5. **Set `bufsize=0`** on `subprocess.Popen` (already default, but worth verifying)
6. **Try `PIPE` + `fcntl.F_SETFL, O_NONBLOCK`** then poll/select loop instead of
   blocking read

**Key diagnostic commands**:
```bash
# Check pipe position (should increase if data flowing):
pid=$(pgrep -of parecord); cat /proc/$pid/fdinfo/1

# Test parecord standalone:
timeout 2 parecord --raw --rate 16000 --channels 1 --format s16le \
  --device alsa_input.usb-KTMicro_USB_MIC_INPUT_Adapter_2020-02-20-0000-0000-0000-00.mono-fallback \
  | wc -c  # Should be ~62000

# Test Silero VAD (confirms speech detection works at 200%):
# See test scripts in session logs

# Check PA source state:
pactl list sources short | grep -i usb
```

## Team session
- Session: kisti-voice-004 (a049c437-2b8a-4d2f-9fca-c878fe472427)
- kisti-04 is conductor
- TUI: python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-voice-004
- Project board: 5 phases, 24 tasks, 19 done. Phase 5 = UAT (5 items pending)

## Key files
- voice/mic_capture.py:216-232 — `_run_arecord()` spawns parecord, THIS IS THE BUG
- voice/mic_capture.py:234+ — `_vad_process()` reads frames, runs Silero VAD
- voice/voice_manager.py — PipelineTrace, _compose_and_speak, barge-in in _do_speak
- data/duckdb_store.py — voice_latency table
- scripts/kisti-session — mic gain (ALSA=100%, PA=200%)
- tests/conftest.py — shared fixtures
- tests/test_voice.py — 361 tests

## Test baseline
- 361/361 on dev machine (Manx)
- 358/361 on Jetson (3 pre-existing env-specific failures)

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo aldc1234 | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"
