"""KiSTI - Audio Player with Waveform Sync

Generates TTS audio via Piper and plays it while providing real-time
amplitude data for the KITT waveform visualization.

Runs Piper + aplay in background threads so the Qt UI stays responsive.
"""

from __future__ import annotations

import logging
import math
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("kisti.voice.player")

PIPER_BINARY = Path("/data/piper/piper")
PIPER_VOICE = Path("/data/piper/en_US-lessac-medium.onnx")
PIPER_SAMPLE_RATE = 22050


class AudioPlayer(QObject):
    """Generates TTS audio and plays it with real-time amplitude feedback.

    Signals:
        playback_started(): Audio playback has begun
        playback_finished(): Audio playback has ended
        amplitude_update(float): Current amplitude 0.0-1.0, emitted at ~30 Hz
    """

    playback_started = Signal()
    playback_finished = Signal()
    amplitude_update = Signal(float)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._playing = False
        self._piper_available = PIPER_BINARY.exists() and PIPER_VOICE.exists()
        if self._piper_available:
            log.info("AudioPlayer: Piper TTS available")
        else:
            log.info("AudioPlayer: Piper not found, waveform will use typewriter timing")

    def speak(self, text: str) -> Optional[float]:
        """Generate and play speech for the given text.

        Starts audio playback in a background thread. Emits amplitude_update
        signals at ~30 Hz during playback for waveform visualization.

        Returns estimated audio duration in seconds (or None if Piper unavailable).
        """
        if not text.strip():
            return None

        if self._playing:
            log.debug("Already playing, skipping: %s", text[:30])
            return None

        if not self._piper_available:
            return None

        self._playing = True
        thread = threading.Thread(
            target=self._generate_and_play,
            args=(text,),
            daemon=True,
            name="kisti-audio-player",
        )
        thread.start()

        # Estimate duration: ~100ms per word
        return max(0.5, len(text.split()) * 0.12)

    def _generate_and_play(self, text: str) -> None:
        """Background thread: Piper TTS → amplitude analysis → aplay."""
        try:
            # Generate raw PCM via Piper
            proc = subprocess.run(
                [
                    str(PIPER_BINARY),
                    "--model", str(PIPER_VOICE),
                    "--output_raw",
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                log.warning("Piper failed: %s", proc.stderr.decode()[:100])
                self._playing = False
                return

            audio_pcm = proc.stdout
            if len(audio_pcm) < 100:
                self._playing = False
                return

            # Compute amplitude envelope at 30 Hz
            envelope = self._compute_envelope(audio_pcm, PIPER_SAMPLE_RATE, fps=30)

            # Write to temp WAV for aplay
            wav_path = "/tmp/kisti_speech.wav"
            self._write_wav(audio_pcm, PIPER_SAMPLE_RATE, wav_path)

            # Start playback
            self.playback_started.emit()

            play_proc = subprocess.Popen(
                ["aplay", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Emit amplitude updates during playback at ~30 Hz
            frame_interval = 1.0 / 30.0
            for amp in envelope:
                if play_proc.poll() is not None:
                    break
                self.amplitude_update.emit(amp)
                time.sleep(frame_interval)

            # Wait for playback to finish
            play_proc.wait(timeout=30)

            # Signal zero amplitude and finished
            self.amplitude_update.emit(0.0)
            self.playback_finished.emit()

        except Exception as exc:
            log.warning("Audio playback error: %s", exc)
            self.amplitude_update.emit(0.0)
            self.playback_finished.emit()
        finally:
            self._playing = False

    @staticmethod
    def _compute_envelope(audio_pcm: bytes, sample_rate: int, fps: int = 30) -> list[float]:
        """Compute normalized amplitude envelope from raw PCM."""
        samples_per_frame = sample_rate // fps
        num_samples = len(audio_pcm) // 2
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

            n = len(chunk) // 2
            total = 0.0
            for j in range(0, len(chunk) - 1, 2):
                sample = struct.unpack_from("<h", chunk, j)[0]
                total += sample * sample
            rms = (total / max(1, n)) ** 0.5
            envelope.append(rms)
            if rms > max_amp:
                max_amp = rms

        if max_amp > 0:
            envelope = [v / max_amp for v in envelope]

        return envelope

    @staticmethod
    def _write_wav(pcm: bytes, sample_rate: int, path: str) -> None:
        """Write raw PCM to a WAV file."""
        import wave
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def is_available(self) -> bool:
        return self._piper_available
