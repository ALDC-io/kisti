"""KiSTI - Microphone Capture with Voice Activity Detection

Continuous audio capture from USB microphone via ALSA (arecord subprocess).
Uses webrtcvad for lightweight VAD — no GPU, no PulseAudio dependency.

When speech is detected, the complete utterance is emitted as raw PCM for
WhisperTRT transcription.

Designed for the Jetson Orin Nano minimal X session where PulseAudio is killed
and audio is routed direct to ALSA.
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

SAMPLE_RATE = 16000       # WhisperTRT expects 16kHz
FRAME_DURATION_MS = 30    # webrtcvad frame size (10, 20, or 30 ms)
FRAME_BYTES = SAMPLE_RATE * 2 * FRAME_DURATION_MS // 1000  # 960 bytes per 30ms frame

# VAD tuning for in-car environment (engine noise, road noise)
VAD_MODE = 2              # 0=least aggressive, 3=most aggressive. 2 = moderate
SPEECH_START_FRAMES = 8   # ~240ms of voiced frames to trigger speech start
SPEECH_END_FRAMES = 20    # ~600ms of silence to end utterance (longer for car noise)
MAX_UTTERANCE_S = 10.0    # Hard cap — prevent runaway capture
MIN_UTTERANCE_S = 0.3     # Ignore very short bursts (clicks, bumps)

# Pre-roll: keep N frames before speech detection fires, so we don't clip the start
PRE_ROLL_FRAMES = 5       # ~150ms lookback


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

        # Check for webrtcvad
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(VAD_MODE)
        except ImportError:
            log.warning("webrtcvad not installed — mic capture disabled (pip install webrtcvad)")
            return

        # Check for ALSA capture device
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

    def _probe_mic(self) -> bool:
        """Check if the ALSA capture device exists."""
        try:
            # Quick probe: try to open the device for 0.1s
            proc = subprocess.run(
                ["arecord", "-D", self._device, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
                 "-c", "1", "-d", "0", "-q"],
                capture_output=True,
                timeout=3,
            )
            # arecord -d 0 exits immediately — returncode 0 means device is valid
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

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
        """Stream audio from arecord and run VAD on each frame."""
        proc = subprocess.Popen(
            ["arecord", "-D", self._device, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
             "-c", "1", "-t", "raw", "-q"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            self._vad_process(proc)
        finally:
            proc.terminate()
            proc.wait(timeout=2)

    def _vad_process(self, proc: subprocess.Popen) -> None:
        """Read frames from arecord stdout and detect speech utterances."""
        pre_roll: list[bytes] = []  # Circular buffer for pre-roll
        speech_buffer: list[bytes] = []
        voiced_count = 0
        silent_count = 0
        in_speech = False
        speech_start_time = 0.0

        while self._running and proc.poll() is None:
            frame = proc.stdout.read(FRAME_BYTES)
            if len(frame) < FRAME_BYTES:
                break

            # Skip processing while paused (TTS playing — echo suppression)
            if self._paused:
                voiced_count = 0
                silent_count = 0
                in_speech = False
                speech_buffer.clear()
                pre_roll.clear()
                continue

            is_speech = self._vad.is_speech(frame, SAMPLE_RATE)

            if not in_speech:
                # Waiting for speech to start
                pre_roll.append(frame)
                if len(pre_roll) > PRE_ROLL_FRAMES:
                    pre_roll.pop(0)

                if is_speech:
                    voiced_count += 1
                else:
                    voiced_count = 0

                if voiced_count >= SPEECH_START_FRAMES:
                    # Speech detected — start capturing
                    in_speech = True
                    silent_count = 0
                    speech_start_time = time.monotonic()
                    # Include pre-roll so we don't clip the beginning
                    speech_buffer = list(pre_roll)
                    speech_buffer.append(frame)
                    pre_roll.clear()
                    self.listening_started.emit()
                    log.debug("Speech start detected")
            else:
                # In speech — accumulate frames
                speech_buffer.append(frame)

                if is_speech:
                    silent_count = 0
                else:
                    silent_count += 1

                elapsed = time.monotonic() - speech_start_time

                # End conditions: enough silence or max duration
                if silent_count >= SPEECH_END_FRAMES or elapsed >= MAX_UTTERANCE_S:
                    in_speech = False
                    voiced_count = 0
                    silent_count = 0

                    # Check minimum duration
                    duration = len(speech_buffer) * FRAME_DURATION_MS / 1000.0
                    if duration >= MIN_UTTERANCE_S:
                        pcm = b"".join(speech_buffer)
                        log.info("Speech captured: %.1fs (%d bytes)", duration, len(pcm))
                        self.speech_captured.emit(pcm)
                    else:
                        log.debug("Discarding short utterance: %.1fs", duration)

                    speech_buffer.clear()
                    self.listening_stopped.emit()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running
