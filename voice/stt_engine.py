"""KiSTI - Speech-to-Text Engine (Whisper)

Supports two backends:
1. whisper.cpp HTTP server (preferred) — persistent CUDA process, ~130ms for 3s audio
2. PyTorch openai-whisper (fallback) — loads model in-process, ~380ms for 3s audio

On start(), tries whisper.cpp server at WHISPER_CPP_URL first. If unavailable,
falls back to PyTorch Whisper. Mock fallback for testing/development.
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
import threading
import time
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisti.voice.stt")

WHISPER_MODEL_NAME = "base.en"
WHISPER_CPP_URL = "http://127.0.0.1:8081"  # whisper.cpp server
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
    # Common hallucination phrases on silence/noise
    hallucinations = [
        "thank you for watching",
        "thanks for watching",
        "please subscribe",
        "i'm going to go ahead",
        "so i'm going to",
        "you",  # single word "You" on noise
        "okay",
        "okay.",
        "we'll see you tomorrow",
        "see you tomorrow",
        "see you next time",
        "bye",
        "goodbye",
        "thanks",
        "thank you",
        "i'll see you",
        "so",
        "yeah",
        "the end",
        "hey kisti, the ai co-driver",  # initial_prompt echo
        "hey kisti the ai co-driver",
        # Whisper tiny.en generates these from ambient noise
        "hi guys",
        "i'm going to",
        "i hope it's",
        "this example",
        "question",
        "question.",
        "oh",
        "oh.",
        "hmm",
        "hmm.",
        "uh",
        "um",
        "right",
        "right.",
        "well",
        "well.",
        "interesting",
        "interesting.",
        "i'm ready",
        "huh",
    ]
    for h in hallucinations:
        if lower == h:
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

    Tries whisper.cpp HTTP server first (faster, persistent CUDA process).
    Falls back to PyTorch openai-whisper if server is unavailable.

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
        server_url: str = WHISPER_CPP_URL,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._use_vad = use_vad
        self._server_url = server_url
        self._model = None
        self._backend: Optional[str] = None
        self._running = False

    def _check_server(self) -> bool:
        """Check if whisper.cpp HTTP server is reachable."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{self._server_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start(self) -> None:
        """Connect to whisper.cpp server or load PyTorch model."""
        if self._running:
            return

        # Try whisper.cpp server first (faster, no in-process GPU load)
        if self._check_server():
            self._backend = "whisper-cpp-server"
            log.info("whisper.cpp server connected at %s", self._server_url)
            self._running = True
            return

        # Fall back to PyTorch Whisper
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

    def _pcm_to_wav(self, audio_pcm: bytes) -> bytes:
        """Convert raw PCM to WAV bytes for whisper.cpp server."""
        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_pcm)
        return buf.getvalue()

    def _transcribe_server(self, audio_pcm: bytes, duration_s: float) -> Optional[TranscriptionResult]:
        """Transcribe via whisper.cpp HTTP server."""
        import json as _json
        import urllib.request
        start_time = time.monotonic()
        wav_data = self._pcm_to_wav(audio_pcm)

        # Build multipart form data
        boundary = "----KiSTIBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode() + wav_data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="temperature"\r\n\r\n0.0\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="response_format"\r\n\r\njson\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="language"\r\n\r\nen\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="initial_prompt"\r\n\r\n'
            f"Hey KiSTI, the AI co-driver. Boost, oil, brake, tire, RPM, ECU, turbo, PSI.\r\n"
            f"--{boundary}--\r\n"
        ).encode()

        try:
            req = urllib.request.Request(
                f"{self._server_url}/inference",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = _json.loads(resp.read().decode())
            text = result.get("text", "").strip()
            latency = time.monotonic() - start_time

            if _is_hallucination(text):
                log.debug("STT[cpp] hallucination filtered: '%s'", text[:60])
                return TranscriptionResult(
                    text="", duration_s=duration_s,
                    latency_s=latency, confidence=0.0, is_final=True,
                )

            log.debug("STT[cpp]: %.1fs audio -> '%.50s' in %.3fs", duration_s, text, latency)
            return TranscriptionResult(
                text=text, duration_s=duration_s,
                latency_s=latency, confidence=0.95, is_final=True,
            )
        except Exception as exc:
            log.warning("whisper.cpp server failed: %s — falling back", exc)
            return None

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

        # Try whisper.cpp server first (faster)
        if self._backend == "whisper-cpp-server":
            result = self._transcribe_server(audio_pcm, duration_s)
            if result is not None:
                return result

        # PyTorch Whisper fallback
        if self._model is not None:
            try:
                import numpy as np  # type: ignore[import-untyped]
                audio_np = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(
                    audio_np,
                    language=self._language,
                    fp16=self._backend == "whisper-cuda",
                    initial_prompt="Hey KiSTI, the AI co-driver.",
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
        """True if using real Whisper (not mock).

        whisper.cpp server mode sets _backend but not _model, so check _backend.
        """
        return self._backend is not None


class HybridSTTEngine(STTEngine):
    """Deepgram cloud when WiFi available, whisper.cpp when offline.

    Checks WiFi connectivity every 30s in background thread.
    Uses Deepgram API for cloud-quality transcription when online.
    Falls back to whisper.cpp (or PyTorch) when WiFi unavailable.

    Requires DEEPGRAM_API_KEY environment variable.

    Usage:
        engine = HybridSTTEngine()
        engine.start()
        result = engine.transcribe(audio_bytes)  # auto-selects Deepgram or whisper.cpp
        engine.stop()
    """

    DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
    WIFI_CHECK_INTERVAL_S = 30.0

    def __init__(
        self,
        model_name: str = WHISPER_MODEL_NAME,
        language: str = "en",
        use_vad: bool = True,
        server_url: str = WHISPER_CPP_URL,
    ) -> None:
        super().__init__(model_name, language, use_vad, server_url)
        self._deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
        self._wifi_available = False
        self._wifi_check_thread: Optional[threading.Thread] = None
        self._stop_wifi_check = False

    def _check_wifi(self) -> bool:
        """Check if WiFi (or any external) connectivity is available."""
        try:
            req = urllib.request.Request("https://www.google.com", method="HEAD")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    def _wifi_checker(self) -> None:
        """Background thread: check WiFi every 30s."""
        while not self._stop_wifi_check:
            self._wifi_available = self._check_wifi()
            status = "available" if self._wifi_available else "unavailable"
            log.debug("WiFi check: %s", status)
            time.sleep(self.WIFI_CHECK_INTERVAL_S)

    def start(self) -> None:
        """Start engines and WiFi checker thread."""
        if self._running:
            return

        # Start base STT engine (whisper.cpp or PyTorch)
        super().start()

        # Start WiFi checker if we have Deepgram API key
        if self._deepgram_key and not self._wifi_check_thread:
            self._stop_wifi_check = False
            self._wifi_check_thread = threading.Thread(target=self._wifi_checker, daemon=True)
            self._wifi_check_thread.start()
            log.info("Deepgram hybrid STT started (WiFi check every %.0fs)", self.WIFI_CHECK_INTERVAL_S)
        elif not self._deepgram_key:
            log.warning("Deepgram API key not set — using whisper.cpp only")

    def stop(self) -> None:
        """Stop base engine and WiFi checker."""
        self._stop_wifi_check = True
        if self._wifi_check_thread:
            self._wifi_check_thread.join(timeout=5)
            self._wifi_check_thread = None
        super().stop()

    def _transcribe_deepgram(self, audio_pcm: bytes, duration_s: float) -> Optional[TranscriptionResult]:
        """Transcribe via Deepgram cloud API."""
        if not self._wifi_available or not self._deepgram_key:
            return None

        start_time = time.monotonic()
        try:
            headers = {
                "Authorization": f"Token {self._deepgram_key}",
                "Content-Type": "audio/wav",
            }
            params = f"?model=nova-3&language={self._language}&smart_format=true"

            wav_data = self._pcm_to_wav(audio_pcm)
            req = urllib.request.Request(
                f"{self.DEEPGRAM_API_URL}{params}",
                data=wav_data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = _json.loads(resp.read().decode())

            # Extract transcript from Deepgram response
            try:
                transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
                text = transcript.strip()
            except (KeyError, IndexError):
                log.warning("Unexpected Deepgram response format: %s", result)
                return None

            latency = time.monotonic() - start_time

            if _is_hallucination(text):
                log.debug("STT[deepgram] hallucination filtered: '%s'", text[:60])
                return TranscriptionResult(
                    text="", duration_s=duration_s,
                    latency_s=latency, confidence=0.0, is_final=True,
                )

            log.debug("STT[deepgram]: %.1fs audio -> '%.50s' in %.3fs", duration_s, text, latency)
            return TranscriptionResult(
                text=text, duration_s=duration_s,
                latency_s=latency, confidence=0.98, is_final=True,
            )

        except Exception as exc:
            log.warning("Deepgram transcription failed: %s — falling back", exc)
            return None

    def transcribe(self, audio_pcm: bytes) -> TranscriptionResult:
        """Transcribe using Deepgram if WiFi available, else whisper.cpp.

        Args:
            audio_pcm: Raw PCM bytes (16-bit signed, 16kHz, mono).

        Returns:
            TranscriptionResult with transcribed text.
        """
        start_time = time.monotonic()
        duration_s = len(audio_pcm) / (SAMPLE_RATE * 2)

        # Reject very short clips
        if duration_s < MIN_AUDIO_S:
            return TranscriptionResult(
                text="", duration_s=duration_s,
                latency_s=time.monotonic() - start_time,
                confidence=0.0, is_final=True,
            )

        # Try Deepgram first if WiFi available
        if self._wifi_available and self._deepgram_key:
            result = self._transcribe_deepgram(audio_pcm, duration_s)
            if result is not None:
                return result
            log.debug("Deepgram unavailable — falling back to whisper.cpp")

        # Fall back to whisper.cpp/PyTorch chain (parent class)
        return super().transcribe(audio_pcm)
