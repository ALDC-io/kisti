"""KiSTI - Voice Orchestrator

Manages the full voice pipeline: mic → STT → LLM → TTS → speaker + LEDs.
Runs as a QThread, integrates with the PySide6 event loop.

Handles:
  - Continuous audio capture with VAD
  - Wake word detection ("Hey KiSTI")
  - Voice state machine (Idle → Listening → Thinking → Speaking)
  - Mode-aware filtering (Intelligent/Sport/Sport Sharp)
  - LED waveform driving during speech
"""

from __future__ import annotations

import logging
import queue
import struct
import subprocess
import threading
import time
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from model.vehicle_state import DiffState, SIDriveMode
from voice.llm_engine import LLMEngine
from voice.mic_capture import MicCapture
from voice.stt_engine import STTEngine
from voice.tts_engine import TTSEngine
from voice.led_waveform import LEDFrame, LEDWaveformGenerator

log = logging.getLogger("kisti.voice")

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024  # samples per audio read
WAKE_WORDS = [
    "hey kisti", "hey ki", "kisti",
    # Common Whisper misheards of "KiSTI"
    "keys to", "keeps to", "key stee", "keisti", "kisti",
    "christy", "cristy", "kisty", "heykisti",
]
QUIET_COMMANDS = ["quiet please kisti", "quiet please", "quiet kisti", "be quiet"]
RESUME_COMMANDS = ["hey kisti"]


class VoiceState(IntEnum):
    """Voice pipeline state machine."""
    IDLE = 0        # Waiting for wake word or command
    LISTENING = 1   # Actively capturing user speech
    THINKING = 2    # Processing with LLM
    SPEAKING = 3    # Playing TTS audio + LED waveform
    QUIET = 4       # Voice silenced (K4 or voice command)
    OFF = 5         # Voice fully disabled


class VoiceToggleState(IntEnum):
    """K4 voice toggle cycle: Normal → Quiet → Off → Normal."""
    NORMAL = 0
    QUIET = 1
    OFF = 2


class VoiceManager(QObject):
    """Orchestrates the KiSTI voice pipeline.

    Signals:
        state_changed(int): VoiceState changed
        speaking_text(str): Text being spoken
        led_frame(LEDFrame): LED frame to send via CAN
    """

    state_changed = Signal(int)
    speaking_text = Signal(str)
    led_frame_ready = Signal(object)  # LEDFrame
    response_ready = Signal(str)      # LLM response text for UI AudioPlayer

    def __init__(self, mic_device: str = "default", enable_mic: bool = True,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._stt = STTEngine()
        self._tts = TTSEngine()
        self._llm = LLMEngine()
        self._led = LEDWaveformGenerator()
        self._mic = MicCapture(device=mic_device) if enable_mic else None

        self._state = VoiceState.IDLE
        self._toggle_state = VoiceToggleState.NORMAL
        self._si_drive_mode = SIDriveMode.INTELLIGENT

        self._speak_queue: queue.Queue[str] = queue.Queue(maxsize=10)
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._aplay_proc: Optional[subprocess.Popen] = None
        self._interrupted = False
        self._last_interaction: float = 0.0  # Timestamp of last wake word hit
        self._listen_window_s: float = 8.0   # Stay in conversation mode this long

        # Telemetry snapshot for LLM context
        self._telemetry_snapshot: Optional[DiffState] = None

        # Edge memory for "remember" commands and LLM context
        self._edge_memory = None

        # Wire mic → STT → LLM pipeline
        if self._mic:
            self._mic.speech_captured.connect(self._on_speech_captured)

    def start(self) -> None:
        """Initialize all voice subsystems and start the worker thread."""
        self._stt.start()
        self._tts.start()
        self._llm.start()
        self._running = True

        self._worker_thread = threading.Thread(
            target=self._voice_loop,
            daemon=True,
            name="kisti-voice-manager",
        )
        self._worker_thread.start()

        # Start mic capture (safe to call even without a mic — falls back gracefully)
        if self._mic:
            self._mic.start()

        mic_status = "off"
        if self._mic and self._mic.is_available:
            mic_status = "real"
        elif self._mic:
            mic_status = "no device"

        log.info("Voice manager started (STT=%s, TTS=%s, LLM=%s, Mic=%s)",
                 "real" if self._stt.is_real else "mock",
                 "real" if self._tts.is_real else "mock",
                 "real" if self._llm.is_real else "persona",
                 mic_status)

    def stop(self) -> None:
        """Stop all voice subsystems."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        if self._mic:
            self._mic.stop()
        self._stt.stop()
        self._tts.stop()
        self._llm.stop()
        log.info("Voice manager stopped")

    def set_si_drive_mode(self, mode: SIDriveMode) -> None:
        """Update SI Drive mode — controls voice behavior."""
        self._si_drive_mode = mode
        log.info("Voice mode: %s", mode.label)

    def set_telemetry(self, state: DiffState) -> None:
        """Update telemetry snapshot for LLM context."""
        self._telemetry_snapshot = state

    def set_edge_memory(self, edge_memory: object) -> None:
        """Inject edge memory for 'remember' commands and LLM context."""
        self._edge_memory = edge_memory

    def toggle_voice(self) -> VoiceToggleState:
        """Cycle voice state: Normal → Quiet → Off → Normal (K4 button)."""
        self._toggle_state = VoiceToggleState((self._toggle_state + 1) % 3)
        if self._toggle_state == VoiceToggleState.NORMAL:
            self._set_state(VoiceState.IDLE)
        elif self._toggle_state == VoiceToggleState.QUIET:
            self._set_state(VoiceState.QUIET)
        else:
            self._set_state(VoiceState.OFF)
        log.info("Voice toggle: %s", self._toggle_state.name)
        return self._toggle_state

    def speak(self, text: str) -> None:
        """Queue text to be spoken (from alerts, proactive commentary, etc.)."""
        if self._state in (VoiceState.QUIET, VoiceState.OFF):
            return
        if self._si_drive_mode == SIDriveMode.SPORT_SHARP:
            return  # No queued speech in S#
        try:
            self._speak_queue.put_nowait(text)
        except queue.Full:
            log.debug("Speak queue full, dropping: %s", text[:30])

    def speak_alert(self, text: str, severity: str) -> None:
        """Queue an alert to be spoken — respects mode filtering.

        Critical alerts always speak. Others filtered by SI Drive mode.
        """
        if self._state == VoiceState.OFF:
            return

        # Critical alerts always speak in all modes
        if severity == "critical":
            try:
                self._speak_queue.put_nowait(text)
            except queue.Full:
                pass
            return

        # Non-critical filtering by mode
        if self._si_drive_mode == SIDriveMode.SPORT_SHARP:
            return  # Only critical in S#
        if self._si_drive_mode == SIDriveMode.SPORT and severity == "info":
            return  # No info in Sport

        try:
            self._speak_queue.put_nowait(text)
        except queue.Full:
            pass

    def handle_voice_query(self, transcription: str) -> None:
        """Process a transcribed voice query through the LLM."""
        if not transcription.strip():
            return

        lower = transcription.lower().strip()

        # "Say X" command → repeat back immediately (TTS latency test)
        if lower.startswith("say "):
            phrase = transcription[len("say "):].strip()
            if phrase:
                log.info("Say command: '%s'", phrase)
                self.response_ready.emit(phrase)
                return

        # Check for "remember" commands → store in edge memory
        if lower.startswith("remember ") and self._edge_memory:
            content = transcription[len("remember "):].strip()
            if content:
                self._edge_memory.remember(
                    content=content,
                    memory_type="manual",
                    source="voice",
                )
                self.response_ready.emit("Got it. I'll remember that.")
                return

        # Check for quiet/resume commands
        if any(cmd in lower for cmd in QUIET_COMMANDS):
            self._toggle_state = VoiceToggleState.QUIET
            self._set_state(VoiceState.QUIET)
            self.speak("Going quiet.")
            return
        if any(cmd in lower for cmd in RESUME_COMMANDS) and self._state == VoiceState.QUIET:
            self._toggle_state = VoiceToggleState.NORMAL
            self._set_state(VoiceState.IDLE)
            self.speak("I'm back. What do you need?")
            return

        self._set_state(VoiceState.THINKING)

        # Build telemetry context
        context = self._build_telemetry_context()

        # Build memory context (skip in Sport Sharp — token budget too tight)
        memory_context = ""
        if self._edge_memory and self._si_drive_mode != SIDriveMode.SPORT_SHARP:
            memory_context = self._edge_memory.build_memory_context(transcription)

        # Query LLM
        response = self._llm.query(
            user_message=transcription,
            telemetry_context=context,
            memory_context=memory_context,
            si_drive_mode=self._si_drive_mode.label,
        )

        log.info("LLM response (tier=%s, %.1fs): %s", response.tier, response.latency_s, response.text[:80])
        self.response_ready.emit(response.text)

    def _voice_loop(self) -> None:
        """Main voice processing loop (runs in worker thread)."""
        while self._running:
            try:
                # Process speak queue
                try:
                    text = self._speak_queue.get(timeout=0.1)
                    self._do_speak(text)
                except queue.Empty:
                    # No speech queued — generate idle LED pattern
                    if self._state == VoiceState.IDLE and self._si_drive_mode == SIDriveMode.INTELLIGENT:
                        frame = self._led.kitt_sweep_frame()
                        self.led_frame_ready.emit(frame)
                    time.sleep(1.0 / 30.0)  # ~30 FPS LED rate

            except Exception as exc:
                log.error("Voice loop error: %s", exc, exc_info=True)
                time.sleep(1.0)

    def _on_speech_captured(self, pcm: bytes) -> None:
        """Mic captured a complete utterance — transcribe and process.

        Runs STT then checks for wake word. If the utterance contains a
        wake word (or KiSTI is already in LISTENING state), routes to LLM.

        During SPEAKING state: only listen for wake word (barge-in).
        Stops current TTS playback when wake word detected.
        """
        if self._state == VoiceState.OFF:
            return

        speaking = self._state == VoiceState.SPEAKING

        # Transcribe on a worker thread to avoid blocking Qt
        def _process():
            try:
                result = self._stt.transcribe(pcm)
            except Exception as exc:
                log.error("STT transcription crashed: %s", exc, exc_info=True)
                return
            if not result.text.strip() or result.text == "[mock transcription]":
                log.info("STT: empty/mock result (%.1fs audio, %.2fs latency)", result.duration_s, result.latency_s)
                return

            text = result.text.strip()
            lower = text.lower()
            log.info("STT: '%s' (%.2fs latency, conf=%.1f)", text[:60], result.latency_s, result.confidence)

            has_wake_word = any(w in lower for w in WAKE_WORDS)
            in_conversation = (time.monotonic() - self._last_interaction) < self._listen_window_s

            # During TTS playback, only respond to wake word (barge-in)
            if speaking:
                if has_wake_word:
                    log.info("Barge-in detected — interrupting TTS")
                    self._interrupt_playback()
                else:
                    return  # Ignore TTS echo

            if has_wake_word or in_conversation or self._state == VoiceState.LISTENING:
                self._last_interaction = time.monotonic()
                # Strip wake word prefix from the query
                query = text
                if has_wake_word:
                    for w in WAKE_WORDS:
                        idx = lower.find(w)
                        if idx >= 0:
                            query = text[idx + len(w):].strip(" ,.")
                            break
                if query:
                    self.handle_voice_query(query)
                else:
                    # Just the wake word with no query — acknowledge and listen
                    self._set_state(VoiceState.LISTENING)
                    self.speak("I'm listening.")

        threading.Thread(target=_process, daemon=True, name="kisti-stt-worker").start()

    def _interrupt_playback(self) -> None:
        """Stop current TTS playback (barge-in)."""
        proc = self._aplay_proc
        if proc and proc.poll() is None:
            proc.terminate()
            log.info("TTS playback interrupted")
        self._interrupted = True

    def _do_speak(self, text: str) -> None:
        """Synthesize and play speech with LED waveform."""
        self._set_state(VoiceState.SPEAKING)
        self._interrupted = False
        self.speaking_text.emit(text)

        # Synthesize
        result = self._tts.speak(text)

        # Drive LEDs from amplitude envelope
        if self._si_drive_mode == SIDriveMode.INTELLIGENT:
            frames = self._led.waveform_from_envelope(result.amplitude_envelope)
            for frame in frames:
                if not self._running or self._interrupted:
                    break
                self.led_frame_ready.emit(frame)
                time.sleep(1.0 / 30.0)

        # Play audio — keep mic active for barge-in
        if not self._interrupted:
            self._play_audio(result.audio_pcm, result.sample_rate)

        # Delay mic resume — prevent echo pickup from HDMI reverb
        time.sleep(0.8)
        # Reset conversation window AFTER speaking — user hears response, then has 8s to follow up
        self._last_interaction = time.monotonic()
        self._set_state(VoiceState.IDLE)

    def _play_audio(self, audio_pcm: bytes, sample_rate: int) -> None:
        """Play PCM audio via PulseAudio to HDMI.

        PulseAudio must stay running to keep the HDA pin-ctl active on Jetson.
        Stores paplay process in self._aplay_proc so barge-in can terminate it.
        """
        import subprocess as _sp
        import tempfile
        import wave
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_pcm)
            self._aplay_proc = _sp.Popen(
                ["paplay", wav_path],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            )
            self._aplay_proc.wait(timeout=60)
        except Exception as exc:
            log.warning("Audio playback failed: %s", exc)
        finally:
            self._aplay_proc = None
            import os
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _build_telemetry_context(self) -> str:
        """Build telemetry context string for LLM system prompt."""
        s = self._telemetry_snapshot
        if s is None:
            return "No telemetry available."

        lines = []
        if s.rpm > 0:
            lines.append(f"RPM: {s.rpm:.0f}")
        if s.speed_kph > 0:
            lines.append(f"Speed: {s.speed_kph:.0f} km/h, Gear: {s.gear}")
        if s.map_kpa > 0:
            boost_psi = (s.map_kpa - 101.325) * 0.145038
            lines.append(f"Boost: {boost_psi:.1f} PSI")
        if s.coolant_temp > 0:
            lines.append(f"Coolant: {s.coolant_temp:.0f}°C")
        if s.oil_temp_c > 0:
            lines.append(f"Oil Temp: {s.oil_temp_c:.0f}°C")
        if s.oil_psi > 0:
            lines.append(f"Oil Pressure: {s.oil_psi:.0f} PSI")
        if s.lambda_1 > 0:
            lines.append(f"Lambda: {s.lambda_1:.3f}")
        if s.iat_c != 0:
            lines.append(f"IAT: {s.iat_c:.0f}°C")
        if s.ethanol_pct > 0:
            lines.append(f"Ethanol: {s.ethanol_pct:.0f}%")
        lines.append(f"DCCD: {s.dccd_command_pct:.0f}%")
        lines.append(f"Surface: {s.surface_state.label}")
        lines.append(f"SI Drive: {s.si_drive_mode.label}")

        return "\n".join(lines) if lines else "No telemetry available."

    def _set_state(self, new_state: VoiceState) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(int(new_state))

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def toggle_state(self) -> VoiceToggleState:
        return self._toggle_state
