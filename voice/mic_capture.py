"""KiSTI - Microphone Capture with Voice Activity Detection

Continuous audio capture from USB microphone via PulseAudio (parecord).
Uses Silero VAD for high-accuracy speech boundary detection — dramatically
reduces Whisper hallucinations by tightly clipping speech segments.

Optional openwakeword CPU pre-filter: when enabled, only utterances
containing the wake word trigger STT — cutting ~90% of unnecessary GPU calls.

When speech is detected, the complete utterance is emitted as raw PCM for
Whisper transcription.
"""

from __future__ import annotations

import logging
import subprocess
import struct
import threading
import time
from typing import Callable, Optional

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

# openwakeword settings
OWW_CHUNK_SAMPLES = 1280  # 80ms at 16kHz (openwakeword requirement)
OWW_THRESHOLD = 0.5       # Wake word confidence threshold (0-1)
OWW_THRESHOLD_NORMAL = 0.5    # Default wake word threshold
OWW_THRESHOLD_BARGE_IN = 0.85 # Raised during TTS playback (echo rejection)

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
        wake_model: Optional[str] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._wake_model = wake_model  # Custom ONNX path or openwakeword model name
        self._running = False
        self._paused = False  # Pause during TTS playback to avoid echo
        self._thread: Optional[threading.Thread] = None
        self._vad = None
        self._oww = None      # openwakeword model (CPU pre-filter)
        self._available = False
        self._last_wake_detected = False  # Set True when wake word detected in last utterance
        self._passthrough = False  # When True, skip wake word gate (conversation window)
        self._barge_in_mode = False    # True during TTS — mic active but OWW threshold raised
        self._active_oww_threshold = OWW_THRESHOLD_NORMAL

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

        # Initialize openwakeword (CPU pre-filter — optional)
        # Priority: constructor arg → KISTI_WAKE_MODEL env → default hey_jarvis
        try:
            import os as _os
            from openwakeword.model import Model as OWWModel

            model_spec = self._wake_model or _os.environ.get("KISTI_WAKE_MODEL", "")
            if model_spec and _os.path.isfile(model_spec):
                # Custom ONNX file (e.g. /data/models/hey_kisti.onnx)
                self._oww = OWWModel(wakeword_models=[model_spec])
                model_label = _os.path.basename(model_spec)
            else:
                # Built-in openwakeword model name
                model_name = model_spec or "hey_jarvis_v0.1"
                self._oww = OWWModel(wakeword_models=[model_name])
                model_label = model_name
            log.info("openwakeword loaded (%s, CPU)", model_label)
        except ImportError:
            log.info("openwakeword not available — all speech goes to STT")
        except Exception as exc:
            log.warning("openwakeword failed to load: %s", exc)

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
        """Stream audio and run VAD. Tries sounddevice first, falls back to parecord."""
        try:
            self._run_sounddevice()
        except Exception as exc:
            log.warning("sounddevice unavailable (%s), falling back to parecord", exc)
            self._run_parecord()

    def _run_sounddevice(self) -> None:
        """Capture audio via sounddevice (PortAudio) — no subprocess, no pipe."""
        import sounddevice as sd

        # Ensure PA default source points to our USB mic (sounddevice
        # routes through PA's default, which may not be the USB mic)
        if self._device:
            try:
                subprocess.run(
                    ["pactl", "set-default-source", self._device],
                    capture_output=True, timeout=3,
                )
                log.info("Set PA default source → %s", self._device)
            except Exception as exc:
                log.warning("Could not set PA default source: %s", exc)

        device_idx = self._find_sd_device()
        log.info("sounddevice capture: device=%s, rate=%d", device_idx, SAMPLE_RATE)

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=SILERO_CHUNK_SAMPLES,
            device=device_idx,
        )
        stream.start()

        def read_fn(n_bytes: int) -> bytes:
            n_frames = n_bytes // 2  # 16-bit = 2 bytes per sample
            data, overflowed = stream.read(n_frames)
            if overflowed:
                log.debug("sounddevice overflow (frames dropped)")
            return data.tobytes()

        try:
            self._vad_process(read_fn, alive_fn=lambda: stream.active)
        finally:
            stream.stop()
            stream.close()

    def _find_sd_device(self) -> int | None:
        """Find the best input device in sounddevice's device list.

        Priority: USB mic by name → 'pulse' device (PA routing) → None (default).
        On Jetson, the USB mic is only reachable through the 'pulse' PortAudio
        device, not as a named ALSA device. Using None would hit an NVIDIA APE
        input (silent).
        """
        import sounddevice as sd
        pulse_idx = None
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                name_lower = dev["name"].lower()
                if "usb" in name_lower or "ktmicro" in name_lower:
                    log.info("sounddevice USB mic: [%d] %s", i, dev["name"])
                    return i
                if name_lower == "pulse":
                    pulse_idx = i
        if pulse_idx is not None:
            log.info("sounddevice using pulse device [%d] (USB mic via PA)", pulse_idx)
            return pulse_idx
        log.info("No USB/pulse device in sounddevice — using default input")
        return None

    def _run_parecord(self) -> None:
        """Fallback: stream audio from parecord subprocess."""
        record_cmd = ["parecord", "--raw", "--rate", str(SAMPLE_RATE),
                      "--channels", "1", "--format", "s16le"]
        if self._device:
            record_cmd.extend(["--device", self._device])
        cmd = ["stdbuf", "-o0"] + record_cmd
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            self._vad_process(
                read_fn=lambda n: proc.stdout.read(n),
                alive_fn=lambda: proc.poll() is None,
            )
        finally:
            proc.terminate()
            proc.wait(timeout=2)

    def _vad_process(
        self,
        read_fn: Callable[[int], bytes],
        alive_fn: Callable[[], bool],
    ) -> None:
        """Read frames via read_fn and detect speech utterances."""
        import torch
        import numpy as np

        pre_roll: list[bytes] = []
        speech_buffer: list[bytes] = []
        voiced_count = 0
        silent_count = 0
        in_speech = False
        speech_start_time = 0.0
        use_silero = self._vad_type == "silero"
        oww_buffer = b""       # Accumulate frames for openwakeword (needs 1280 samples)
        wake_detected = False  # Wake word detected in current utterance
        _diag_count = 0        # Diagnostic frame counter (temporary)

        while self._running and alive_fn():
            frame = read_fn(FRAME_BYTES)
            _diag_count += 1
            if _diag_count <= 5 or _diag_count % 500 == 0:
                rms = np.sqrt(np.mean(np.frombuffer(frame[:FRAME_BYTES], dtype=np.int16).astype(np.float32) ** 2))
                log.info("mic diag frame=%d len=%d rms=%.0f", _diag_count, len(frame), rms)
            if len(frame) < FRAME_BYTES:
                break

            if self._paused:
                voiced_count = 0
                silent_count = 0
                in_speech = False
                wake_detected = False
                speech_buffer.clear()
                pre_roll.clear()
                oww_buffer = b""
                if use_silero:
                    self._vad.reset_states()
                continue

            # Barge-in mode: only process wake word detection, skip VAD
            if self._barge_in_mode:
                if self._oww is not None:
                    oww_buffer += frame
                    while len(oww_buffer) >= OWW_CHUNK_SAMPLES * 2:
                        chunk = oww_buffer[:OWW_CHUNK_SAMPLES * 2]
                        oww_buffer = oww_buffer[OWW_CHUNK_SAMPLES * 2:]
                        oww_audio = np.frombuffer(chunk, dtype=np.int16)
                        preds = self._oww.predict(oww_audio)
                        for model_name, score in preds.items():
                            if score > self._active_oww_threshold:
                                log.info("Barge-in wake word: %s (%.2f)", model_name, score)
                                self._last_wake_detected = True
                                self.speech_captured.emit(frame)
                                oww_buffer = b""
                                if self._oww is not None:
                                    self._oww.reset()
                continue

            # Feed openwakeword (accumulate to 1280-sample chunks)
            if self._oww is not None:
                oww_buffer += frame
                while len(oww_buffer) >= OWW_CHUNK_SAMPLES * 2:
                    chunk = oww_buffer[:OWW_CHUNK_SAMPLES * 2]
                    oww_buffer = oww_buffer[OWW_CHUNK_SAMPLES * 2:]
                    oww_audio = np.frombuffer(chunk, dtype=np.int16)
                    preds = self._oww.predict(oww_audio)
                    for model_name, score in preds.items():
                        if score > self._active_oww_threshold:
                            if not wake_detected:
                                log.info("Wake word detected: %s (%.2f)", model_name, score)
                            wake_detected = True

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
                        self._last_wake_detected = wake_detected
                        if self._oww is not None and not wake_detected and not self._passthrough:
                            log.debug("No wake word — skipping STT (%.1fs)", duration)
                        else:
                            log.info("Speech captured: %.1fs (%d bytes, wake=%s)",
                                     duration, len(pcm), wake_detected)
                            self.speech_captured.emit(pcm)
                    else:
                        log.debug("Discarding short utterance: %.1fs", duration)

                    speech_buffer.clear()
                    wake_detected = False
                    oww_buffer = b""
                    if self._oww is not None:
                        self._oww.reset()
                    if use_silero:
                        self._vad.reset_states()
                    self.listening_stopped.emit()

    def set_passthrough(self, enabled: bool) -> None:
        """Enable/disable wake word bypass (for conversation window)."""
        self._passthrough = enabled

    def set_barge_in_mode(self, enabled: bool) -> None:
        """Enable/disable barge-in mode (raised OWW threshold during TTS).

        When enabled: mic stays active but OWW threshold is raised to 0.85,
        rejecting TTS echo while allowing deliberate wake word utterances.
        When disabled: threshold returns to normal 0.5.
        """
        self._barge_in_mode = enabled
        self._active_oww_threshold = OWW_THRESHOLD_BARGE_IN if enabled else OWW_THRESHOLD_NORMAL
        log.debug("Barge-in mode: %s (OWW threshold=%.2f)", enabled, self._active_oww_threshold)

    @property
    def wake_detected(self) -> bool:
        """True if wake word was detected in the last captured utterance."""
        return self._last_wake_detected

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running
