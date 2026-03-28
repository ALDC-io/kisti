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
import threading
import time
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from model.vehicle_state import DiffState, SIDriveMode
from voice.llm_engine import LLMEngine
from voice.stt_engine import STTEngine
from voice.tts_engine import TTSEngine
from voice.led_waveform import LEDFrame, LEDWaveformGenerator

log = logging.getLogger("kisti.voice")

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024  # samples per audio read
WAKE_WORDS = ["hey kisti", "hey ki", "kisti"]
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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._stt = STTEngine()
        self._tts = TTSEngine()
        self._llm = LLMEngine()
        self._led = LEDWaveformGenerator()

        self._state = VoiceState.IDLE
        self._toggle_state = VoiceToggleState.NORMAL
        self._si_drive_mode = SIDriveMode.INTELLIGENT

        self._speak_queue: queue.Queue[str] = queue.Queue(maxsize=10)
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        # Telemetry snapshot for LLM context
        self._telemetry_snapshot: Optional[DiffState] = None

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
        log.info("Voice manager started (STT=%s, TTS=%s, LLM=%s)",
                 "real" if self._stt.is_real else "mock",
                 "real" if self._tts.is_real else "mock",
                 "real" if self._llm.is_real else "persona")

    def stop(self) -> None:
        """Stop all voice subsystems."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
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

        # Check for quiet/resume commands
        lower = transcription.lower().strip()
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

        # Query LLM
        response = self._llm.query(
            user_message=transcription,
            telemetry_context=context,
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

    def _do_speak(self, text: str) -> None:
        """Synthesize and play speech with LED waveform."""
        self._set_state(VoiceState.SPEAKING)
        self.speaking_text.emit(text)

        # Synthesize
        result = self._tts.speak(text)

        # Drive LEDs from amplitude envelope
        if self._si_drive_mode == SIDriveMode.INTELLIGENT:
            frames = self._led.waveform_from_envelope(result.amplitude_envelope)
            for frame in frames:
                if not self._running:
                    break
                self.led_frame_ready.emit(frame)
                time.sleep(1.0 / 30.0)

        # Play audio (via sounddevice or pyaudio)
        self._play_audio(result.audio_pcm, result.sample_rate)

        self._set_state(VoiceState.IDLE)

    def _play_audio(self, audio_pcm: bytes, sample_rate: int) -> None:
        """Play PCM audio via USB audio output."""
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
            import numpy as np  # type: ignore[import-untyped]
            audio_np = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(audio_np, samplerate=sample_rate, blocking=True)
        except ImportError:
            # sounddevice not available — estimate duration and sleep
            duration = len(audio_pcm) / (sample_rate * 2)
            log.debug("No audio output — simulating %.1fs playback", duration)
            time.sleep(duration)
        except Exception as exc:
            log.warning("Audio playback failed: %s", exc)

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
            lines.append(f"MAP: {s.map_kpa:.0f} kPa ({s.map_kpa * 0.145038 - 14.7:.1f} PSI boost)")
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
