"""KiSTI - Text-to-Speech Engine (Piper TTS)

Wraps Piper TTS for offline speech synthesis on the Jetson Orin Nano.
Piper is a fast, lightweight neural TTS (~50 MB per voice model).

Produces PCM audio + amplitude envelope for LED waveform visualization
on the MXG Strada dash.
"""

from __future__ import annotations

import hashlib
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
    "AWD": "all wheel drive",
    "FMIC": "front mount intercooler",
    "TGV": "T G V",
    "ID1300": "I D thirteen hundred",
    "DW300C": "D W three hundred C",
    "EJ257": "E J two fifty seven",
    "CSF": "C S F",
    "ARP": "A R P",
    "GSC": "G S C",
    " 911": " nine eleven",
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
        cache_dir: Optional[Path] = None,
        cache_enabled: bool = True,
    ) -> None:
        self._binary = piper_binary
        self._voice = voice_model
        self._config = voice_config
        self._cache_dir = cache_dir or Path("data/tts_cache")
        self._cache_enabled = cache_enabled
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

        # Initialize cache directory
        if self._cache_enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._validate_cache_model()

        self._running = True

    def stop(self) -> None:
        self._running = False
        log.info("TTS engine stopped")

    def _cache_key(self, text: str) -> str:
        """SHA-256 hash of text as cache key."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_path(self, text: str) -> Path:
        """Path to cache file for given text."""
        return self._cache_dir / f"{self._cache_key(text)}.cache"

    def _validate_cache_model(self) -> None:
        """Invalidate cache if voice model changed."""
        meta_path = self._cache_dir / ".model_hash"
        model_hash = hashlib.sha256(str(self._voice).encode()).hexdigest()[:16]
        if meta_path.exists():
            stored = meta_path.read_text().strip()
            if stored != model_hash:
                log.info("Voice model changed — clearing TTS cache")
                self.clear_cache()
        meta_path.write_text(model_hash)

    def _load_cache(self, text: str) -> Optional[TTSResult]:
        """Load cached TTS result from disk."""
        path = self._cache_path(text)
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            # Header: sample_rate (4B) + envelope_len (4B)
            if len(data) < 8:
                return None
            sample_rate = struct.unpack_from("<I", data, 0)[0]
            envelope_len = struct.unpack_from("<I", data, 4)[0]
            offset = 8
            # Envelope: envelope_len * 4 bytes (floats)
            envelope_bytes = envelope_len * 4
            if len(data) < offset + envelope_bytes:
                return None
            envelope = list(struct.unpack_from(f"<{envelope_len}f", data, offset))
            offset += envelope_bytes
            # Remaining bytes are audio PCM
            audio_pcm = data[offset:]
            duration_s = len(audio_pcm) / (sample_rate * 2)
            log.debug("TTS cache hit: %s (%d bytes)", text[:40], len(audio_pcm))
            return TTSResult(
                audio_pcm=audio_pcm,
                sample_rate=sample_rate,
                duration_s=duration_s,
                latency_s=0.0,
                amplitude_envelope=envelope,
            )
        except Exception as exc:
            log.warning("TTS cache read failed: %s", exc)
            return None

    def _store_cache(self, text: str, result: TTSResult) -> None:
        """Store TTS result to disk cache."""
        try:
            path = self._cache_path(text)
            envelope = result.amplitude_envelope
            header = struct.pack("<II", result.sample_rate, len(envelope))
            envelope_data = struct.pack(f"<{len(envelope)}f", *envelope) if envelope else b""
            path.write_bytes(header + envelope_data + result.audio_pcm)
            log.debug("TTS cached: %s (%d bytes)", text[:40], len(result.audio_pcm))
        except Exception as exc:
            log.warning("TTS cache write failed: %s", exc)

    def clear_cache(self) -> int:
        """Clear all cached TTS files. Returns count of files removed."""
        count = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.glob("*.cache"):
                f.unlink()
                count += 1
        log.info("TTS cache cleared: %d files", count)
        return count

    def speak(self, text: str) -> TTSResult:
        """Synthesize text to speech.

        Args:
            text: Text to speak.

        Returns:
            TTSResult with PCM audio and amplitude envelope.
        """
        # Apply substitutions FIRST (cache key based on substituted text)
        for literal, phonetic in TTS_SUBSTITUTIONS.items():
            text = text.replace(literal, phonetic)

        # Check cache
        if self._cache_enabled and self._cache_dir:
            start_time = time.monotonic()
            cached = self._load_cache(text)
            if cached is not None:
                cached.latency_s = time.monotonic() - start_time
                return cached

        start_time = time.monotonic()

        if self._is_real:
            try:
                result = self._speak_piper(text, start_time)
                # Store in cache
                if self._cache_enabled and self._cache_dir:
                    self._store_cache(text, result)
                return result
            except Exception as exc:
                log.warning("Piper TTS failed: %s — using mock", exc)

        result = self._speak_mock(text, start_time)
        # Store mock results in cache too
        if self._cache_enabled and self._cache_dir:
            self._store_cache(text, result)
        return result

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
