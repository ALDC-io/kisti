Continue KiSTI voice pipeline tuning. Repo: /home/aldc/repos/kisti/. Jetson at
192.168.22.131 (SSH user aldc).

Context: Voice pipeline is working end-to-end (mic → STT → LLM → TTS → HDMI).
Aaron's tune session at Boost Barn is the deadline — KiSTI must be reliable
and entertaining in the car.

What works (2026-03-28 session, 18 commits):
- HDMI audio via PulseAudio (paplay). PA must stay running — Jetson HDA resets
  pin-ctl without it. See feedback_jetson_hdmi_audio.md
- Mic via parecord (PA holds ALSA devices). ALSA 60% + PA source 150%
- Whisper tiny.en CUDA with initial_prompt "Hey KiSTI, the AI co-driver"
- 8-second conversation window after wake word (resets after TTS playback)
- 1.5s echo guard post-playback
- 100+ movie/TV/brain-rot quotes wired into event system
- Subaru jokes + roast battle mode (Logan/Adam)
- "Say X" parrot command for latency testing
- Cold boot: 3/3 GDM restart cycles passed
- AccountsService configured for KiSTI session auto-login

What is NOT working or needs improvement:
1. CRITICAL: installed /usr/local/bin/kisti-session is STALE — has ALSA 30%
   instead of 60%, old PA volume. Mic gain resets every reboot. Need one
   interactive sudo: sudo cp ~/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session
2. STT quality: many empty results, hallucinations on background noise,
   Whisper occasionally crashes with "Key and Value must have same sequence
   length" (GPU memory pressure from Ollama + Whisper sharing 8GB)
3. Echo: KiSTI still hears its own TTS sometimes despite 1.5s guard
4. LLM latency: 2-4s on llama3.2:3b (hardware-bound on Orin Nano 8GB)
5. Barge-in: not working (mic paused during TTS for echo suppression)
6. Mode tiers not implemented: Intelligent=fun/jokes, Sport=clinical/data,
   Sport Sharp=emergency only. See feedback_kisti_voice_mode_tiers.md
7. Persona responses need expansion — most questions fall through to slow
   LLM. Every common question should have a curated instant answer

Immediate priorities:
1. Fix the sudo cp (one interactive password, permanent fix)
2. Expand persona responses — add 20-30 more curated answers for common
   questions. This is the biggest quality/speed win (instant, no GPU)
3. Implement mode tiers for voice filtering
4. Increase echo guard or implement proper echo cancellation
5. Consider cloud LLM fallback when on WiFi for better conversation quality
