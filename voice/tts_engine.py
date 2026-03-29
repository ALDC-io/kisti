"""KiSTI - Text-to-Speech Engine (Piper TTS)

Wraps Piper TTS for offline speech synthesis on the Jetson Orin Nano.
Piper is a fast, lightweight neural TTS (~50 MB per voice model).

Produces PCM audio + amplitude envelope for LED waveform visualization
on the MXG Strada dash.
"""

from __future__ import annotations

import logging
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisti.voice.tts")

# Default paths on Jetson
PIPER_BINARY = Path("/data/piper/piper")
PIPER_VOICE = Path("/data/piper/en_US-danny-low.onnx")
PIPER_CONFIG = Path("/data/piper/en_US-danny-low.onnx.json")
SAMPLE_RATE = 16000  # Danny model sample rate
LED_COUNT = 10

# TTS pronunciation substitutions — applied before synthesis.
# Key = regex-safe literal, Value = phonetic spelling for Piper.
TTS_SUBSTITUTIONS: dict[str, str] = {
    "KiSTI": "Keesty Eye",
    "kisti": "Keesty Eye",
    "KISTI": "Keesty Eye",
    " PSI": " pounds",
    " psi": " pounds",
    " WHP": " wheel horsepower",
    " whp": " wheel horsepower",
    " BHP": " brake horsepower",
    " bhp": " brake horsepower",
    "DCCD": "D C C D",
    " STI": " S T I",
    "ECU": "E C U",
    "IAG": "I A G",
    "FMIC": "front mount intercooler",
    "TGV": "T G V",
    "ID1300": "I D thirteen hundred",
    "DW300C": "D W three hundred C",
    "EJ257": "E J two fifty seven",
    "CSF": "C S F",
    "ARP": "A R P",
    "GSC": "G S C",
}


@dataclass
class TTSResult:
    """Result from TTS engine."""
    audio_pcm: bytes         # Raw PCM (16-bit signed, 22050 Hz, mono)
    sample_rate: int         # Sample rate (Hz)
    duration_s: float        # Audio duration
    latency_s: float         # Synthesis time
    amplitude_envelope: list[float]  # Normalized amplitude per LED frame (0.0-1.0)


def compute_amplitude_envelope(
    audio_pcm: bytes, sample_rate: int, fps: int = 30, num_leds: int = LED_COUNT,
) -> list[float]:
    """Compute amplitude envelope from PCM audio for LED visualization.

    Returns a list of normalized amplitude values (0.0-1.0), one per
    frame at the given fps. Each value represents the RMS amplitude
    of the corresponding audio chunk.
    """
    if not audio_pcm:
        return []

    samples_per_frame = sample_rate // fps
    num_samples = len(audio_pcm) // 2  # 16-bit
    num_frames = max(1, num_samples // samples_per_frame)

    envelope = []
    max_amp = 1.0

    for i in range(num_frames):
        start = i * samples_per_frame * 2
        end = start + samples_per_frame * 2
        chunk = audio_pcm[start:end]
        if len(chunk) < 4:
            envelope.append(0.0)
            continue

        # Compute RMS
        n_samples = len(chunk) // 2
        total = 0.0
        for j in range(n_samples):
            sample = struct.unpack_from("<h", chunk, j * 2)[0]
            total += sample * sample
        rms = (total / n_samples) ** 0.5
        envelope.append(rms)
        if rms > max_amp:
            max_amp = rms

    # Normalize to 0.0-1.0
    if max_amp > 0:
        envelope = [v / max_amp for v in envelope]

    return envelope


class TTSEngine:
    """Piper TTS engine for offline speech synthesis.

    Usage:
        engine = TTSEngine()
        engine.start()
        result = engine.speak("Hello, I'm KiSTI.")
        # Play result.audio_pcm via sounddevice/pyaudio
        # Use result.amplitude_envelope for LED waveform
        engine.stop()
    """

    def __init__(
        self,
        piper_binary: Path = PIPER_BINARY,
        voice_model: Path = PIPER_VOICE,
        voice_config: Path = PIPER_CONFIG,
    ) -> None:
        self._binary = piper_binary
        self._voice = voice_model
        self._config = voice_config
        self._running = False
        self._is_real = False

    def start(self) -> None:
        """Verify Piper binary and voice model are available."""
        if self._running:
            return

        if self._binary.exists() and self._voice.exists():
            self._is_real = True
            log.info("Piper TTS ready: %s", self._voice.name)
        else:
            self._is_real = False
            log.warning("Piper TTS not found at %s — using mock TTS", self._binary)

        self._running = True

    def stop(self) -> None:
        self._running = False
        log.info("TTS engine stopped")

    def speak(self, text: str) -> TTSResult:
        """Synthesize text to speech.

        Args:
            text: Text to speak.

        Returns:
            TTSResult with PCM audio and amplitude envelope.
        """
        for literal, phonetic in TTS_SUBSTITUTIONS.items():
            text = text.replace(literal, phonetic)

        start_time = time.monotonic()

        if self._is_real:
            try:
                return self._speak_piper(text, start_time)
            except Exception as exc:
                log.warning("Piper TTS failed: %s — using mock", exc)

        return self._speak_mock(text, start_time)

    def _speak_piper(self, text: str, start_time: float) -> TTSResult:
        """Synthesize using Piper binary (subprocess, outputs raw PCM)."""
        cmd = [
            str(self._binary),
            "--model", str(self._voice),
            "--config", str(self._config),
            "--output_raw",
        ]
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Piper exited with {proc.returncode}: {proc.stderr.decode()}")

        audio_pcm = proc.stdout
        duration_s = len(audio_pcm) / (SAMPLE_RATE * 2)
        latency = time.monotonic() - start_time
        envelope = compute_amplitude_envelope(audio_pcm, SAMPLE_RATE)

        log.debug("TTS: '%s' → %.1fs audio in %.2fs", text[:50], duration_s, latency)
        return TTSResult(
            audio_pcm=audio_pcm,
            sample_rate=SAMPLE_RATE,
            duration_s=duration_s,
            latency_s=latency,
            amplitude_envelope=envelope,
        )

    def _speak_mock(self, text: str, start_time: float) -> TTSResult:
        """Generate silence with a mock amplitude envelope."""
        # ~100ms per word mock duration
        word_count = len(text.split())
        duration_s = max(0.5, word_count * 0.1)
        num_samples = int(duration_s * SAMPLE_RATE)
        audio_pcm = b"\x00\x00" * num_samples  # silence

        # Mock envelope: gentle pulse
        import math
        frames = int(duration_s * 30)
        envelope = [
            0.3 + 0.7 * abs(math.sin(i * math.pi / max(1, frames)))
            for i in range(frames)
        ]

        latency = time.monotonic() - start_time
        return TTSResult(
            audio_pcm=audio_pcm,
            sample_rate=SAMPLE_RATE,
            duration_s=duration_s,
            latency_s=latency,
            amplitude_envelope=envelope,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_real(self) -> bool:
        return self._is_real
