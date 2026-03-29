"""KiSTI - Microphone Capture with Voice Activity Detection

Continuous audio capture from USB microphone via PulseAudio (parecord).
Uses Silero VAD for high-accuracy speech boundary detection — dramatically
reduces Whisper hallucinations by tightly clipping speech segments.

When speech is detected, the complete utterance is emitted as raw PCM for
Whisper transcription.
"""

from __future__ import annotations

import logging
import subprocess
import struct
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("kisti.voice.mic")

SAMPLE_RATE = 16000       # Whisper expects 16kHz
# Silero VAD processes 512-sample chunks at 16kHz (32ms)
SILERO_CHUNK_SAMPLES = 512
SILERO_CHUNK_BYTES = SILERO_CHUNK_SAMPLES * 2  # 16-bit = 2 bytes/sample
FRAME_DURATION_MS = 32    # Silero chunk duration
FRAME_BYTES = SILERO_CHUNK_BYTES  # 1024 bytes per chunk

# VAD tuning for in-car environment
SPEECH_THRESHOLD = 0.5    # Silero confidence threshold (0-1). Higher = stricter
SPEECH_START_FRAMES = 6   # ~192ms of speech to trigger capture start
SPEECH_END_FRAMES = 12    # ~384ms of silence to end utterance
MAX_UTTERANCE_S = 10.0    # Hard cap — prevent runaway capture
MIN_UTTERANCE_S = 0.3     # Ignore very short bursts (clicks, bumps)

# Pre-roll: keep N frames before speech detection fires
PRE_ROLL_FRAMES = 5       # ~160ms lookback

# Legacy constants for test compatibility
VAD_MODE = 3


class MicCapture(QObject):
    """Continuous microphone capture with VAD-based utterance detection.

    Emits speech_captured(bytes) with complete utterance PCM (16kHz mono 16-bit).
    Falls back gracefully if no mic is available or webrtcvad not installed.

    Signals:
        speech_captured(bytes): Complete utterance as raw PCM
        listening_started(): VAD detected speech start
        listening_stopped(): VAD detected speech end
    """

    speech_captured = Signal(bytes)
    listening_started = Signal()
    listening_stopped = Signal()

    def __init__(
        self,
        device: str = "default",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._running = False
        self._paused = False  # Pause during TTS playback to avoid echo
        self._thread: Optional[threading.Thread] = None
        self._vad = None
        self._available = False

    def start(self) -> None:
        """Start capture thread. Safe to call even without a mic."""
        if self._running:
            return

        # Initialize Silero VAD (CPU ONNX — no GPU needed)
        try:
            from silero_vad import load_silero_vad
            self._vad = load_silero_vad()
            self._vad_type = "silero"
            log.info("Silero VAD loaded (CPU ONNX)")
        except ImportError:
            try:
                import webrtcvad
                self._vad = webrtcvad.Vad(VAD_MODE)
                self._vad_type = "webrtcvad"
                log.warning("Silero VAD not available — falling back to webrtcvad")
            except ImportError:
                log.warning("No VAD available — mic capture disabled")
                return

        # Resolve ALSA device names to PulseAudio source names
        # (PA holds all ALSA devices, so arecord can't access them directly)
        if self._device.startswith(("plughw:", "hw:", "default")):
            pa_source = self._find_pa_usb_source()
            if pa_source:
                log.info("Resolved ALSA '%s' → PA source '%s'", self._device, pa_source)
                self._device = pa_source
            else:
                log.info("No USB PA source found, using default")
                self._device = ""  # empty = default PA source

        # Check for capture device
        if not self._probe_mic():
            log.warning("No capture device found — mic capture disabled")
            return

        self._available = True
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="kisti-mic-capture",
        )
        self._thread.start()
        log.info("Mic capture started (device=%s, VAD mode=%d)", self._device, VAD_MODE)

    def stop(self) -> None:
        """Stop capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        self._available = False
        log.info("Mic capture stopped")

    def pause(self) -> None:
        """Pause capture during TTS playback (echo suppression)."""
        self._paused = True

    def resume(self) -> None:
        """Resume capture after TTS playback ends."""
        self._paused = False

    @staticmethod
    def _find_pa_usb_source() -> str:
        """Find PulseAudio source name for USB mic."""
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                lower = line.lower()
                if ("usb" in lower or "mic" in lower) and "monitor" not in lower:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
        except Exception:
            pass
        return ""

    def _probe_mic(self) -> bool:
        """Check if the capture device exists via PulseAudio."""
        try:
            cmd = ["parecord", "--raw", "--rate", str(SAMPLE_RATE),
                   "--channels", "1", "--format", "s16le",
                   "--process-time-msec=500"]
            if self._device:
                cmd.extend(["--device", self._device])
            proc = subprocess.run(cmd, capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return True

    def _capture_loop(self) -> None:
        """Main capture loop — runs in worker thread."""
        while self._running:
            try:
                self._run_arecord()
            except Exception as exc:
                log.error("Mic capture error: %s", exc)
                if self._running:
                    time.sleep(2.0)  # Back off before retry

    def _run_arecord(self) -> None:
        """Stream audio from parecord (PulseAudio) and run VAD on each frame."""
        cmd = ["parecord", "--raw", "--rate", str(SAMPLE_RATE),
               "--channels", "1", "--format", "s16le"]
        if self._device:
            cmd.extend(["--device", self._device])
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            self._vad_process(proc)
        finally:
            proc.terminate()
            proc.wait(timeout=2)

    def _vad_process(self, proc: subprocess.Popen) -> None:
        """Read frames from parecord stdout and detect speech utterances."""
        import torch
        import numpy as np

        pre_roll: list[bytes] = []
        speech_buffer: list[bytes] = []
        voiced_count = 0
        silent_count = 0
        in_speech = False
        speech_start_time = 0.0
        use_silero = self._vad_type == "silero"

        while self._running and proc.poll() is None:
            frame = proc.stdout.read(FRAME_BYTES)
            if len(frame) < FRAME_BYTES:
                break

            if self._paused:
                voiced_count = 0
                silent_count = 0
                in_speech = False
                speech_buffer.clear()
                pre_roll.clear()
                if use_silero:
                    self._vad.reset_states()
                continue

            # Detect speech
            if use_silero:
                audio_float = torch.from_numpy(
                    np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
                )
                confidence = self._vad(audio_float, SAMPLE_RATE).item()
                is_speech = confidence > SPEECH_THRESHOLD
            else:
                is_speech = self._vad.is_speech(frame, SAMPLE_RATE)

            if not in_speech:
                pre_roll.append(frame)
                if len(pre_roll) > PRE_ROLL_FRAMES:
                    pre_roll.pop(0)

                if is_speech:
                    voiced_count += 1
                else:
                    voiced_count = 0

                if voiced_count >= SPEECH_START_FRAMES:
                    in_speech = True
                    silent_count = 0
                    speech_start_time = time.monotonic()
                    speech_buffer = list(pre_roll)
                    speech_buffer.append(frame)
                    pre_roll.clear()
                    self.listening_started.emit()
                    log.debug("Speech start detected")
            else:
                speech_buffer.append(frame)

                if is_speech:
                    silent_count = 0
                else:
                    silent_count += 1

                elapsed = time.monotonic() - speech_start_time

                if silent_count >= SPEECH_END_FRAMES or elapsed >= MAX_UTTERANCE_S:
                    in_speech = False
                    voiced_count = 0
                    silent_count = 0

                    duration = len(speech_buffer) * FRAME_DURATION_MS / 1000.0
                    if duration >= MIN_UTTERANCE_S:
                        pcm = b"".join(speech_buffer)
                        log.info("Speech captured: %.1fs (%d bytes)", duration, len(pcm))
                        self.speech_captured.emit(pcm)
                    else:
                        log.debug("Discarding short utterance: %.1fs", duration)

                    speech_buffer.clear()
                    if use_silero:
                        self._vad.reset_states()
                    self.listening_stopped.emit()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running
