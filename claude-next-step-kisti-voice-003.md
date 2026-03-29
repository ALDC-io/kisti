Continue KiSTI voice pipeline tuning. Repo: /home/aldc/repos/kisti/. Jetson at
192.168.22.131 (SSH user aldc, sudo password: aldc1234).

## What was done this session (16 commits, 92e912a)

### Phase 1-3: COMPLETE
- Persona-first query flow: keyword match runs BEFORE Ollama (instant <1ms)
- 50 curated persona responses (was 25): safety/tech/fun categories
- Mode-aware filtering: Intelligent=all, Sport=safety+tech truncated, Sport Sharp=safety 5 words
- Echo guard 2.0s + mic pauses during TTS playback (no self-hearing loop)
- Silero VAD replaces webrtcvad (much better speech boundary detection)
- Whisper base.en replaces tiny.en (40% accuracy improvement)
- Danny voice (en_US-danny-low, 16kHz) as default TTS
- Live Yocto sensor routing: temp/humidity/pressure/weather → real data BEFORE persona
- Short responses: all persona capped at 2 sentences, fallback shortened
- WHP→wheel horsepower, PSI→pounds in audio_player.py abbreviations
- USB speaker auto-detected as default sink (survives reboots) — both kisti-session script AND main.py
- Ollama stopped at boot to free GPU for Whisper
- Implicit wake phrases: "can you hear me", "temperature", "boost", etc. (Whisper drops "KiSTI")
- Conversation window tightened 8s→5s
- VAD mode 3 + STT lock (one Whisper call at a time)
- deploy-to-jetson.sh one-command deploy

### STT Architecture Research: COMPLETE
Full research in agent output. Key findings:
- base.en is the sweet spot (fits in 6GB, 40% better than tiny.en)
- faster-whisper/CTranslate2: no prebuilt ARM64 CUDA wheel, needs source build — skip
- whisper.cpp CUDA: confirmed working on Jetson, ~130ms for 3s audio (vs 380ms PyTorch)
- NVIDIA Riva: overkill, Docker overhead too high for 8GB
- Distil-Whisper: distills from large, still ~800M params — too big
- Deepgram cloud hybrid: <300ms on WiFi, best accuracy, clean Python SDK
- Silero VAD: major hallucination reduction — DONE this session

## What needs fixing NOW (blocking)

1. **"Powering on" timing**: Currently speaks before hardware detection.
   User wants it AFTER detection so it confirms readiness. But _queue_lines
   touches Qt UI and can't be called from the hardware detection thread
   (background thread). Need to use Qt signal/slot to emit from detect
   thread → speak on main thread. The _detect_hardware method runs in a
   QThread — use a signal like `hw_detect_done = Signal(str)` to send the
   message back to the main thread for speaking.

2. **AccountsService auto-login**: Gets lost on some GDM restarts. Current
   fix writes /var/lib/AccountsService/users/aldc + /etc/gdm3/custom.conf
   via sudo. Should be baked into kisti-session install script.

3. **Whisper still hallucinating**: base.en is better than tiny.en but still
   mangles "KiSTI" often. The implicit wake phrases (temperature, boost, etc.)
   are a workaround. Real fix is Phase 2 (whisper.cpp or Deepgram).

## Phase 2 STT (next session priorities)

1. **whisper.cpp CUDA server** — build with `-DGGML_CUDA=ON -DCUDA_ARCHITECTURES=87`.
   Run as persistent HTTP server. Modify stt_engine.py to POST audio.
   Target: base.en in 130ms for 3s audio (vs current ~380ms PyTorch).

2. **Deepgram cloud hybrid** — when on WiFi (iPhone hotspot), <300ms STT
   with ~1-3% WER. Fall back to local when offline. Deepgram Python SDK.
   Architecture: `HybridSTTEngine` checks connectivity every 30s.

3. **openwakeword CPU pre-filter** — Whisper only fires after wake word
   confidence, cutting 90% of unnecessary GPU calls.

## Key files
- voice/llm_engine.py — persona responses, mode filtering, query flow
- voice/voice_manager.py — orchestrator, wake words, sensor routing, STT lock
- voice/stt_engine.py — Whisper wrapper (currently base.en PyTorch)
- voice/mic_capture.py — Silero VAD, speech capture
- voice/audio_player.py — TTS abbreviation expansions (WHP, PSI, etc.)
- voice/tts_engine.py — Piper TTS config (Danny voice, 16kHz)
- ui/kisti_mode.py — startup sequence, hardware detection, grip report
- scripts/kisti-session — boot script (USB speaker, Ollama stop, mic gain)
- scripts/deploy-to-jetson.sh — one-command deploy

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo 'aldc1234' | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo 'aldc1234' | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"

## Audio config (resets on GDM restart if not in kisti-session script)
- USB speaker: alsa_output.usb-Jieli_Technology_UACDemoV1.0_4150344C36313516-00.analog-stereo @ 78%
- Mic: alsa_input.usb-KTMicro_USB_MIC_INPUT_Adapter_2020-02-20-0000-0000-0000-00.mono-fallback @ 150%
- ALSA mic capture volume: 60% (set via amixer in kisti-session)

## Test baseline
- 318/318 tests on Manx, 92/93 on Jetson (1 pre-existing: test_mock_transcription expects no Whisper)
- Danny voice confirmed working
- Persona-first: 0.0s for keyword matches
- STT: ~0.3-0.5s with base.en (better accuracy than tiny.en, still hallucinations on noisy audio)
- End-to-end: ~3s (within acceptance, target <2s with Phase 2)
