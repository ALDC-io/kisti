"""KiSTI - Speech-to-Text Engine (Whisper)

Wraps OpenAI Whisper for offline STT on the Jetson Orin Nano.
Uses PyTorch CUDA (not TensorRT) to share GPU context with Ollama.
Falls back to a mock for testing/development.

tiny.en on Orin Nano: ~12x real-time with CUDA, ~0.16s for 2s audio.
"""

from __future__ import annotations

import logging
import re
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisti.voice.stt")

WHISPER_MODEL_NAME = "tiny.en"
SAMPLE_RATE = 16000
CHUNK_DURATION_S = 2.0  # VAD chunk size
MIN_AUDIO_S = 0.5       # reject clips shorter than this


def _is_hallucination(text: str) -> bool:
    """Detect common Whisper hallucination patterns."""
    lower = text.lower().strip()
    if not lower:
        return True
    # Repeated words/phrases: "Okay. Okay. Okay." or "Thank you. Thank you."
    words = re.findall(r'\b\w+\b', lower)
    if len(words) >= 4:
        unique = set(words)
        if len(unique) <= 2:
            return True
    # Common hallucination phrases on silence
    hallucinations = [
        "thank you for watching",
        "thanks for watching",
        "please subscribe",
        "i'm going to go ahead",
        "so i'm going to",
        "you",  # single word "You" on noise
    ]
    for h in hallucinations:
        if lower == h or lower.startswith(h):
            return True
    return False


@dataclass
class TranscriptionResult:
    """Result from STT engine."""
    text: str
    duration_s: float      # audio duration processed
    latency_s: float       # processing time
    confidence: float      # 0.0-1.0 estimated confidence
    is_final: bool         # True if this is a final result (not interim)


class STTEngine:
    """Whisper-based speech-to-text engine for Jetson.

    Uses openai-whisper with CUDA (shares GPU context with Ollama).
    TensorRT engines use a separate CUDA context that conflicts with
    Ollama's llama.cpp, causing illegal memory access errors.

    Usage:
        engine = STTEngine()
        engine.start()
        result = engine.transcribe(audio_bytes)  # 16kHz mono PCM
        engine.stop()
    """

    def __init__(
        self,
        model_name: str = WHISPER_MODEL_NAME,
        language: str = "en",
        use_vad: bool = True,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._use_vad = use_vad
        self._model = None
        self._backend: Optional[str] = None
        self._running = False

    def start(self) -> None:
        """Load Whisper model into GPU memory."""
        if self._running:
            return

        try:
            import whisper  # type: ignore[import-untyped]
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = whisper.load_model(self._model_name, device=device)
            self._backend = f"whisper-{device}"
            log.info("Whisper %s loaded on %s", self._model_name, device)
        except ImportError:
            log.warning("openai-whisper not available — using mock STT")
            self._model = None
        except Exception as exc:
            log.warning("Failed to load Whisper: %s — using mock STT", exc)
            self._model = None

        self._running = True

    def stop(self) -> None:
        """Unload model from GPU memory."""
        self._model = None
        self._backend = None
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

        # Reject very short clips (cause Whisper errors)
        if duration_s < MIN_AUDIO_S:
            return TranscriptionResult(
                text="", duration_s=duration_s,
                latency_s=time.monotonic() - start_time,
                confidence=0.0, is_final=True,
            )

        if self._model is not None:
            try:
                import numpy as np  # type: ignore[import-untyped]
                audio_np = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(
                    audio_np,
                    language=self._language,
                    fp16=self._backend == "whisper-cuda",
                )
                text = result.get("text", "").strip()
                latency = time.monotonic() - start_time

                if _is_hallucination(text):
                    log.debug("STT hallucination filtered: '%s'", text[:60])
                    return TranscriptionResult(
                        text="", duration_s=duration_s,
                        latency_s=latency, confidence=0.0, is_final=True,
                    )

                log.debug("STT: %.1fs audio -> '%.50s' in %.2fs", duration_s, text, latency)
                return TranscriptionResult(
                    text=text,
                    duration_s=duration_s,
                    latency_s=latency,
                    confidence=0.9,
                    is_final=True,
                )
            except Exception as exc:
                log.warning("Whisper transcription failed: %s", exc)

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
        """True if using real Whisper (not mock)."""
        return self._model is not None
