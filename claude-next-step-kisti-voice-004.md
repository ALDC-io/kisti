Continue KiSTI voice pipeline tuning. Repo: /home/aldc/repos/kisti/. Jetson at
192.168.22.131 (SSH user aldc, sudo password: aldc1234).

## What was done this session (11 commits, 481dcbc)

### Phase 1: Blocking Fixes — COMPLETE
- Qt signal/slot fix: "Powering on" speaks AFTER hardware detection (thread-safe)
- AccountsService auto-login baked into deploy-to-jetson.sh
- Tests 318/318, deployed and verified

### Phase 2: STT Upgrade — 2/3 DONE
- **whisper.cpp CUDA server**: Built with GGML_CUDA on Orin Nano, running as
  systemd service at :8081. stt_engine.py auto-detects and uses it. Benchmarks:
  1s=173ms, 2s=200ms, 3s=211ms (1.8x faster than PyTorch 380ms), 5s=246ms.
  Model: ggml-base.en at /data/whisper.cpp/models/ggml-base.en.bin
- **openwakeword CPU pre-filter**: hey_jarvis model runs alongside Silero VAD.
  Only wake-word or conversation-window utterances reach Whisper. Passthrough
  mode auto-enables during conversation window.
- Deepgram cloud hybrid: NOT DONE (needs API key, separate session)

### Phase 3: Routing & UX — 5/7 DONE
- Analysis acknowledgement: "Let me think about that." before LLM inference
- Context injection: Ring buffer of recent vehicle events (ABS, boost, coolant,
  oil, mode changes) injected into LLM telemetry context (last 5 events, 60s)
- Structured output contract: VoiceResponse dataclass (text, source, tier,
  latency_ms, facts, status, can_interrupt) — all response paths produce it
- Dialogue state v1: DialogueState with topic stack (keyword-inferred), last 5
  turns compact, temporal anchors, vehicle event tracking
- STT latency benchmarked: P50/P95 measured (see Zeus 0c5079d0)
- Grip report compacted to "Conditions <status>." format

### Architecture & Research
- ChatGPT deep research ingested: 5-layer KiSTI architecture doc (Zeus cb7f514a),
  Routing Decision Model v1.0 (Zeus cf19c8e1), Dialogue State Manager + Response
  Composer design (Zeus c72ccc8d) with Claude prompt templates and JSON schemas
- Deep Research capability spun off as separate project:
  /home/aldc/projects/active/deep-research-capability/NEXT_SESSION_PROMPT.md

### Fixes
- torchaudio 2.11→2.8 downgrade (was compiled for CUDA 13, Jetson has 12.6)
- Added /usr/local/cuda/lib64 to LD_LIBRARY_PATH in kisti-session
- cmake needs explicit -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc (SSH PATH)

## What needs doing next (prioritized)

### High Priority
1. **Train custom "hey kisti" openwakeword model** — Google Colab notebook
   (~1hr, 200KB ONNX). Replace hey_jarvis with custom model for much better
   accuracy. Notebook: https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb
   Deploy to /data/models/hey_kisti.onnx, update mic_capture.py model path.

2. **Reference resolver (3.5)** — Contextual rewrite before routing. Uses
   DialogueState to resolve "that", "it", "those temps". Claude prompt template
   in Zeus c72ccc8d. Add to voice_manager before LLM query.

3. **Button pad CAN toggle** — Wire Link G5 keypad_pressed signal to
   voice on/off or push-to-talk. DiffStateBridge.keypad_pressed(int) already
   emits. Just needs connection in main.py.

### Medium Priority
4. **Deepgram cloud hybrid (2.3)** — HybridSTTEngine: Deepgram when WiFi
   available, whisper.cpp when offline. Check connectivity every 30s. Need
   DEEPGRAM_API_KEY in .env.

5. **False wake rate + WER baseline (3.7)** — Record audio during a real
   drive session, measure false triggers per hour and word error rate.

### Future (Phase 4)
6. Barge-in pause/continue/resume policy (4.1)
7. Unified Response Composer (4.2) — single voice layer using VoiceResponse
8. Latency instrumentation (4.3) — mouth-to-ear TTFB tracing
9. Regression QA harness (4.4) — replay tests + golden cases

## Team session
- Session: kisti-voice-004 (a049c437-2b8a-4d2f-9fca-c878fe472427)
- TUI: python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-voice-004

## Key files
- voice/stt_engine.py — whisper.cpp HTTP backend + PyTorch fallback
- voice/voice_manager.py — VoiceResponse, DialogueState, context injection,
  acknowledgement, openwakeword passthrough
- voice/mic_capture.py — Silero VAD + openwakeword pre-filter
- voice/llm_engine.py — persona-first + Ollama LLM
- ui/kisti_mode.py — Qt signal/slot fix, compact grip report
- scripts/kisti-session — CUDA LD_LIBRARY_PATH, USB speaker, mic
- scripts/jetson/whisper-server.service — systemd service for whisper.cpp
- scripts/deploy-to-jetson.sh — deploys + restores AccountsService

## Test baseline
- 318/318 tests on Manx
- whisper.cpp server: 211ms P50 for 3s audio (12x real-time on CUDA)
- Full pipeline verified: whisper.cpp + Silero VAD + openwakeword all running

## Deploy command
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null && echo aldc1234 | sudo -S cp scripts/jetson/kisti-session-user /var/lib/AccountsService/users/aldc 2>/dev/null && echo aldc1234 | sudo -S cp scripts/jetson/gdm-custom.conf /etc/gdm3/custom.conf 2>/dev/null && echo aldc1234 | sudo -S systemctl restart gdm 2>/dev/null && echo DEPLOYED"
