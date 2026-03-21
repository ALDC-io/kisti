"""KiSTI - Speech-to-Text Engine (WhisperTRT)

Wraps WhisperTRT (NVIDIA TensorRT-optimized Whisper) for offline STT
on the Jetson Orin Nano. Falls back to a mock for testing/development.

WhisperTRT base.en: 23x real-time on Orin Nano, 439 MB VRAM.
"""

from __future__ import annotations

import asyncio
import logging
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("kisti.voice.stt")

# Default paths on Jetson
WHISPER_MODEL_PATH = Path("/data/whisper/base.en")
SAMPLE_RATE = 16000
CHUNK_DURATION_S = 2.0  # VAD chunk size


@dataclass
class TranscriptionResult:
    """Result from STT engine."""
    text: str
    duration_s: float      # audio duration processed
    latency_s: float       # processing time
    confidence: float      # 0.0-1.0 estimated confidence
    is_final: bool         # True if this is a final result (not interim)


class STTEngine:
    """WhisperTRT-based speech-to-text engine for Jetson.

    Usage:
        engine = STTEngine()
        engine.start()
        result = engine.transcribe(audio_bytes)  # 16kHz mono PCM
        engine.stop()
    """

    def __init__(
        self,
        model_path: Path = WHISPER_MODEL_PATH,
        language: str = "en",
        use_vad: bool = True,
    ) -> None:
        self._model_path = model_path
        self._language = language
        self._use_vad = use_vad
        self._model = None
        self._running = False

    def start(self) -> None:
        """Load WhisperTRT model into GPU memory."""
        if self._running:
            return

        try:
            # Try to import whisper_trt (NVIDIA's TensorRT Whisper)
            from whisper_trt import load_trt_model  # type: ignore[import-untyped]
            self._model = load_trt_model(str(self._model_path))
            log.info("WhisperTRT loaded from %s", self._model_path)
        except ImportError:
            log.warning("whisper_trt not available — using mock STT")
            self._model = None
        except Exception as exc:
            log.warning("Failed to load WhisperTRT: %s — using mock STT", exc)
            self._model = None

        self._running = True

    def stop(self) -> None:
        """Unload model from GPU memory."""
        self._model = None
        self._running = False
        log.info("STT engine stopped")

    def transcribe(self, audio_pcm: bytes) -> TranscriptionResult:
        """Transcribe raw 16kHz mono PCM audio.

        Args:
            audio_pcm: Raw PCM bytes (16-bit signed, 16kHz, mono).

        Returns:
            TranscriptionResult with transcribed text.
        """
        start_time = time.monotonic()
        duration_s = len(audio_pcm) / (SAMPLE_RATE * 2)  # 16-bit = 2 bytes/sample

        if self._model is not None:
            try:
                import numpy as np  # type: ignore[import-untyped]
                audio_np = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(audio_np)
                text = result.get("text", "").strip()
                latency = time.monotonic() - start_time
                log.debug("STT: %.1fs audio → '%.50s' in %.2fs", duration_s, text, latency)
                return TranscriptionResult(
                    text=text,
                    duration_s=duration_s,
                    latency_s=latency,
                    confidence=0.9,
                    is_final=True,
                )
            except Exception as exc:
                log.warning("WhisperTRT transcription failed: %s", exc)

        # Mock fallback
        latency = time.monotonic() - start_time
        return TranscriptionResult(
            text="[mock transcription]",
            duration_s=duration_s,
            latency_s=latency,
            confidence=0.0,
            is_final=True,
        )

    def transcribe_file(self, wav_path: str | Path) -> TranscriptionResult:
        """Transcribe a WAV file (16kHz mono expected)."""
        with wave.open(str(wav_path), "rb") as wf:
            audio_pcm = wf.readframes(wf.getnframes())
        return self.transcribe(audio_pcm)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_real(self) -> bool:
        """True if using real WhisperTRT (not mock)."""
        return self._model is not None
