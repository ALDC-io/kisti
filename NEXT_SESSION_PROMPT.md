# KiSTI Voice Pipeline — Continue from kisti-voice-004

Read `claude-next-step-kisti-voice-004.md` for full handoff context. 12 commits shipped, 10/17 tasks done, 318/318 tests passing. Full voice pipeline verified on Jetson (whisper.cpp CUDA + Silero VAD + openwakeword).

## Immediate next tasks (in order)

1. **Train custom "hey kisti" openwakeword model** — Currently using hey_jarvis (phonetic approximation). Train on Google Colab: https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb. Deploy ~200KB ONNX to `/data/models/hey_kisti.onnx` on Jetson. Update `mic_capture.py` model path from `hey_jarvis_v0.1` to custom model.

2. **Reference resolver (3.5)** — Contextual rewrite of vague queries before routing. DialogueState and VoiceResponse are already built (this session). Use `_dialogue.context_summary()` to resolve "that", "it", "those temps". Claude prompt template stored in Zeus `c72ccc8d`. Add rewrite step in `voice_manager.handle_voice_query()` before LLM query.

3. **Button pad CAN toggle** — Wire Link G5 `keypad_pressed` signal (already on `DiffStateBridge`) to voice on/off or push-to-talk in `main.py`. Quick win.

4. **Deepgram cloud hybrid (2.3)** — `HybridSTTEngine` in `stt_engine.py`: Deepgram when WiFi, whisper.cpp when offline. Need `DEEPGRAM_API_KEY` in `.env`.

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
