# KiSTI Voice Pipeline — Continue from kisti-voice-004

Read `claude-next-step-kisti-voice-004.md` for full handoff context. **15 commits shipped, 13/17 tasks done, 344/344 tests passing**. Full voice pipeline verified on Jetson (whisper.cpp CUDA + Silero VAD + openwakeword + reference resolver + keypad control + Deepgram hybrid STT).

## What was done this session (1 commit)

1. **Deepgram cloud hybrid STT (2.3)** — DONE
   - `HybridSTTEngine` in `voice/stt_engine.py` — uses Deepgram nova-3 when WiFi reachable, whisper.cpp when offline
   - WiFi check runs every 30s in background daemon thread (google.com HEAD request)
   - Auto-selected at VoiceManager init if `DEEPGRAM_API_KEY` env var is set
   - 3 new tests — 344 total passing
   - Confidence: 0.98 Deepgram vs 0.95 whisper.cpp

2. **Custom wake model support (mic_capture.py)** — DONE (landed from previous session)
   - `KISTI_WAKE_MODEL` env var: file path → custom ONNX, model name → built-in OWW, empty → hey_jarvis_v0.1
   - VoiceManager passes env var to MicCapture constructor automatically

## Immediate next tasks (in order)

1. **Train custom "hey kisti" openwakeword model** — HIGH PRIORITY
   - Colab notebook: https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb
   - Deploy ~200KB ONNX to `/data/models/hey_kisti.onnx` on Jetson
   - Set `KISTI_WAKE_MODEL=/data/models/hey_kisti.onnx` in Jetson `.env`
   - Infrastructure already wired — just drop in the file and set env var

2. **Add DEEPGRAM_API_KEY to Jetson .env** — needed to activate HybridSTTEngine on Jetson
   - Key in Dashlane vault under "Deepgram" (or create at deepgram.com)
   - Add to `/home/aldc/.env` on Jetson
   - Deploy and verify: `kisti-session` log should say "Initialized Deepgram hybrid STT engine"

3. **False wake rate + WER baseline (3.7)** — Record audio during a real drive session, measure false triggers per hour and word error rate.

## TUI session
Team session `kisti-voice-004` is still active. Relaunch TUI:
```
python3 /home/aldc/zeus-memory/scripts/cce-team-panel.py --name kisti-voice-004
```
Post all progress to TUI — JK expects every task start/complete and inline comments posted there.

## Key context
- Jetson: 192.168.22.131 (SSH user aldc, sudo: aldc1234)
- whisper.cpp server: systemd service at :8081, base.en ggml model
- torchaudio MUST stay at 2.8.0 (2.11 breaks — needs CUDA 13, Jetson has 12.6)
- ChatGPT deep research stored in Zeus: architecture (cb7f514a), routing model (cf19c8e1), dialogue manager design (c72ccc8d)
- STT benchmarks in Zeus: 0c5079d0 (3s audio = 211ms P50)
- Deploy: `bash scripts/deploy-to-jetson.sh` or see handoff for full command
- kisti-03 and kisti-04 are other contributing CCE instances — coordinate via team session events
