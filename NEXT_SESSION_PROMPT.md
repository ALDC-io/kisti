# KiSTI — Next Session Prompt

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`, pw `aldc1234`). SSH: `ssh aldc@192.168.22.131`
**Live URL**: N/A (embedded Qt on Jetson)
**Test baseline**: 550 tests passing

## Join the CCE Team Session

```
cce-team join project kisti-speaks as kisti-10
```

Session ID: `71182e9b-8794-458f-b9d6-01a301c9ff58`
TUI panel running on pts/7.

## What Was Done (kisti-09, 2026-03-30)

### FIXED: Mic permanently paused after startup TTS
- **Root cause**: `main.py:528` used `QTimer.singleShot(800, mic.resume)` inside a lambda connected to AudioPlayer's `playback_finished` signal. That signal fires from a daemon thread with no Qt event loop — the timer silently never fired, leaving mic paused forever.
- **Fix**: Replaced with `threading.Timer(0.4, mic.resume).start()` — works from any thread.
- Added INFO-level logging to `pause()`/`resume()` for diagnostics.

### FIXED: Voice pipeline latency (~4.8s → ~2.2s)
1. **Concurrent LED + audio** (`voice/voice_manager.py:_do_speak`): LED animation previously ran BEFORE audio playback, adding ~2.5s delay. Now `_start_audio()` returns (proc, wav_path) non-blocking, LEDs animate during playback.
2. **Echo guard 800ms → 400ms** (both `main.py` AudioPlayer path and `voice_manager.py:794` VoiceManager path).
3. **SPEECH_END_FRAMES 12 → 8** (`mic_capture.py`): 256ms silence ends utterance (was 384ms).

### FIXED: Startup speech consolidated
- `ui/kisti_mode.py:_detect_hardware`: Was 4+ sequential lines with 2-3s gaps (~20s total, mic paused throughout). Now ONE consolidated line: "Online. No ECU. Standing by. Conditions good." (~5s, single pause/resume).

### FIXED: OWW wake word detection improvements
1. **Sliding window preservation**: OWW no longer reset on every utterance end — only after successful detection. Prevents split "Hey Jarvis" at natural pauses.
2. **Gain reversal for OWW**: `÷3` before `oww.predict()` to undo software gain (OWW trained on normal audio).
3. **Passthrough mode default**: OWW bypassed — all VAD-detected speech goes to Whisper STT.

### ADDED: Fuzzy wake word matching
- `voice/voice_manager.py`: Added `_fuzzy_wake_word()` with Levenshtein distance ≤ 2 for "hey X" where X ≈ "jarvis"/"kisti".
- Added common Whisper misheards to WAKE_WORDS: "nervous", "service", "jervis", "harvest", "travis", etc.

## Prioritized TODO — START HERE

### 1. CRITICAL: Whisper producing garbage transcriptions
**The #1 blocker.** Whisper base.en transcribes "Hey KiSTI, can you hear me?" as "but when something like this or..." — completely garbled. The voice pipeline is fully working (mic captures speech, STT runs, wake word check runs) but Whisper can't decode the audio.

**Observed Whisper outputs for "Hey Jarvis" attempts:**
- "but when something like this or..." (12:02)
- "Hey, can you stick and hear me?" (11:49)
- "nervous how are the conditions." (11:50)
- "DC Jarvis, you guys there." (10:55 — this one DID work, "jarvis" in text)
- "or something is not cheap." (10:55)

**One success**: At 10:20:56 on the FIRST boot (before latency changes), Whisper correctly transcribed "Hey Jarvis, can you hear me?" with 0.74s latency. All subsequent GDM-restart boots produce garbage.

**Debug approach — investigate audio quality:**
1. **Record raw audio**: SSH in and run `parecord --raw --rate 16000 --channels 1 --format s16le --device alsa_input.usb-KTMicro_USB_MIC_INPUT_Adapter_2020-02-20-0000-0000-0000-00.mono-fallback > /tmp/test.raw` for 5s, then play it back on the workstation to hear what Whisper is getting.
2. **Check gain levels**: The 3x software gain in `mic_capture.py:_run_parecord_pipe` (line 282) + PA 300% = ~9x total. RMS values of 14000-18000 during speech suggest severe clipping. **Try reducing software gain from 3 to 1** (just PA 300%) and test Whisper accuracy.
3. **PA source config**: Verify `pactl get-source-volume` returns 300%. First boot (which worked) ran full kisti-session PA setup; subsequent GDM restarts may not fully reset PA. Try `sudo reboot` instead of GDM restart.
4. **Whisper model**: Currently `base.en` (`voice/stt_engine.py:27`). Try `small.en` for better accuracy (slower but may handle noisy audio better), or test if the whisper.cpp HTTP server at `/tmp/whisper-server.log` is running.

### 2. Jetson restart approach
- `sudo -n /sbin/reboot` (passwordless) for full reboot
- `sudo -n /usr/bin/systemctl restart gdm3` for GDM restart (faster but may not reset PA correctly — this is a suspect in the audio quality issue)
- AccountsService config: `kisti-accountsservice.service` (enabled) restores session on boot, but doesn't run on GDM restart. Use `sudo reboot` to be safe.

### 3. File conflicts from team session
CCE team hooks report conflicts between kisti-07, rs-02, rs-03 in:
- `main.py`, `voice/voice_manager.py`, `voice/mic_capture.py`, `timing/timing_manager.py`, `tests/test_timing_manager.py`, `tests/test_voice.py`
These are all push-to-main edits (no branches). Check `git log --oneline -20` and verify no actual content conflicts.

## Key Files

| File | Purpose |
|------|---------|
| `voice/mic_capture.py` | Mic capture + VAD + OWW gate. Passthrough=True default. SPEECH_END_FRAMES=8. |
| `voice/voice_manager.py` | Voice pipeline orchestrator. _do_speak uses _start_audio (non-blocking). Fuzzy wake word matching. |
| `voice/audio_player.py` | UI AudioPlayer (Piper TTS → paplay). Startup speech path. |
| `voice/stt_engine.py:27` | Whisper model config: `WHISPER_MODEL_NAME = "base.en"` |
| `main.py:528-540` | Echo protection: threading.Timer(0.4, mic.resume) |
| `ui/kisti_mode.py:826` | Startup speech — consolidated to single line |

## Architecture Notes

### Voice Pipeline (current state)
```
parecord (USB mic) → os.pipe2() → 3x gain → Silero VAD → passthrough (OWW bypassed)
    → speech_captured signal → VoiceManager._on_speech_captured
    → whisper.cpp STT → echo suppression → text wake word check + fuzzy match
    → handle_voice_query → persona/LLM → _speak_queue → _do_speak
    → TTS synthesis → _start_audio (non-blocking) → LEDs concurrent → wait
    → echo guard 0.4s → mic resumes
```

### Key Insight: First Boot vs GDM Restart
The ONLY successful Whisper transcription happened on the first boot (full reboot). All subsequent GDM restarts (`sudo systemctl restart gdm3`) produced garbage transcriptions. This strongly suggests PulseAudio state is not fully reset on GDM restart. The kisti-session script kills/restarts PA, but something is different. **Try a full reboot first before any other debugging.**

### CCE Team Session
- Session: `kisti-speaks` (ID: `71182e9b-8794-458f-b9d6-01a301c9ff58`)
- TUI panel running on pts/7
- Post events via: `curl -X POST -H "X-API-Key: $ZEUS_ALDC_API_KEY" -H "Content-Type: application/json" -d '{"type":"task_claimed","actor":"kisti-10","content":"..."}' "$ZEUS_API_BASE_URL/api/team-session/71182e9b-8794-458f-b9d6-01a301c9ff58/event"`
