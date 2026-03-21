"""KiSTI - Audio Player with Waveform Sync

Generates TTS audio via Piper, pre-computes the amplitude envelope,
then plays audio while providing frame-accurate amplitude data for
the KITT waveform visualization.

Sync approach: envelope is pre-computed and delivered to the UI BEFORE
playback starts. A Qt timer on the main thread indexes into the envelope
at 30 Hz, perfectly synchronized with the audio start time.
"""

from __future__ import annotations

import logging
import struct
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("kisti.voice.player")

PIPER_BINARY = Path("/data/piper/piper")
PIPER_VOICE = Path("/data/piper/en_GB-alba-medium.onnx")
PIPER_SAMPLE_RATE = 22050
ENVELOPE_FPS = 40  # Higher resolution to capture syllable-level cadence


class AudioPlayer(QObject):
    """Generates TTS audio and plays it with frame-accurate waveform sync.

    Signals:
        ready(list, float): Pre-computed envelope + duration. Emitted BEFORE
                            playback starts so the UI can prepare.
        playback_started(): Audio is now actually playing — start waveform timer.
        playback_finished(): Audio has finished playing.
    """

    ready = Signal(list, float)       # (envelope: list[float], duration_s: float)
    playback_started = Signal()
    playback_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._playing = False
        self._piper_available = PIPER_BINARY.exists() and PIPER_VOICE.exists()
        if self._piper_available:
            log.info("AudioPlayer: Piper TTS available")
        else:
            log.info("AudioPlayer: Piper not found, waveform will use typewriter timing")

    def speak(self, text: str, urgency: str = "normal") -> None:
        """Generate and play speech in a background thread.

        Args:
            text: Text to speak.
            urgency: "normal" (composed), "alert" (firm), "critical" (fast, sharp).

        Emits ready() with the envelope before playback, then
        playback_started() when audio begins, playback_finished() when done.
        """
        if not text.strip():
            log.debug("speak(): empty text, skipping")
            return
        if self._playing:
            log.debug("speak(): already playing, skipping: %s", text[:30])
            return
        if not self._piper_available:
            log.debug("speak(): Piper not available")
            return

        text = self._expand_abbreviations(text)
        log.info("speak(): generating audio [%s]: %s", urgency, text[:50])
        self._playing = True
        thread = threading.Thread(
            target=self._generate_and_play,
            args=(text, urgency),
            daemon=True,
            name="kisti-audio-player",
        )
        thread.start()

    # Speech speed by urgency: lower = faster
    _URGENCY_SCALES = {
        "normal": "1.1",     # Composed, slightly slow
        "alert": "0.7",      # Quick, clipped, purposeful
        "critical": "0.6",   # Fast, sharp, urgent
    }

    def _generate_and_play(self, text: str, urgency: str = "normal") -> None:
        """Background: Piper → envelope → signal ready → play → signal done."""
        try:
            length_scale = self._URGENCY_SCALES.get(urgency, "1.1")

            # Step 1: Synthesize audio via Piper
            proc = subprocess.run(
                [str(PIPER_BINARY), "--model", str(PIPER_VOICE),
                 "--length_scale", length_scale,
                 "--sentence_silence", "0.1" if urgency != "normal" else "0.3",
                 "--output_raw"],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0 or len(proc.stdout) < 100:
                log.warning("Piper failed or empty output")
                self._playing = False
                return

            audio_pcm = proc.stdout

            # Prepend 250ms silence to prevent ALSA device wake cutoff
            silence = b"\x00\x00" * int(PIPER_SAMPLE_RATE * 0.25)
            audio_pcm = silence + audio_pcm

            duration_s = len(audio_pcm) / (PIPER_SAMPLE_RATE * 2)

            # Step 2: Pre-compute full amplitude envelope
            envelope = self._compute_envelope(audio_pcm, PIPER_SAMPLE_RATE, ENVELOPE_FPS)

            # Step 3: Write WAV
            wav_path = "/tmp/kisti_speech.wav"
            self._write_wav(audio_pcm, PIPER_SAMPLE_RATE, wav_path)

            # Step 4: Signal ready with envelope — UI prepares waveform
            log.info("Audio ready: %.1fs, %d envelope frames", duration_s, len(envelope))
            self.ready.emit(envelope, duration_s)

            # Step 5: Start playback — signal the exact moment audio begins
            log.info("Starting aplay...")
            play_proc = subprocess.Popen(
                ["aplay", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.playback_started.emit()
            log.info("playback_started emitted")

            # Step 6: Wait for playback to finish
            play_proc.wait(timeout=60)
            stderr = play_proc.stderr.read().decode() if play_proc.stderr else ""
            if stderr:
                log.warning("aplay stderr: %s", stderr[:200])

            self._playing = False  # Reset BEFORE emitting signal
            log.info("Playback finished")
            self.playback_finished.emit()

        except Exception as exc:
            log.warning("Audio playback error: %s", exc)
            self._playing = False
            self.playback_finished.emit()

    @staticmethod
    def _compute_envelope(
        audio_pcm: bytes, sample_rate: int, fps: int,
    ) -> list[float]:
        """Compute normalized RMS amplitude envelope from raw PCM."""
        samples_per_frame = sample_rate // fps
        num_samples = len(audio_pcm) // 2
        num_frames = max(1, num_samples // samples_per_frame)

        envelope = []
        max_amp = 1.0

        for i in range(num_frames):
            start = i * samples_per_frame * 2
            end = min(start + samples_per_frame * 2, len(audio_pcm))
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

        # No artificial tail — trust the natural envelope duration

        return envelope

    @staticmethod
    def _write_wav(pcm: bytes, sample_rate: int, path: str) -> None:
        """Write raw PCM to a WAV file."""
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)

    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        """Expand abbreviations so Piper pronounces them naturally."""
        import re
        # Numbers + M/K/B → million/thousand/billion
        text = re.sub(r'(\d+\.?\d*)\s*M\b', r'\1 million', text)
        text = re.sub(r'(\d+\.?\d*)\s*K\b', r'\1 thousand', text)
        text = re.sub(r'(\d+\.?\d*)\s*B\b', r'\1 billion', text)
        # Common units
        text = re.sub(r'\bkph\b', 'kilometres per hour', text, flags=re.IGNORECASE)
        text = re.sub(r'\bkm/h\b', 'kilometres per hour', text, flags=re.IGNORECASE)
        text = re.sub(r'\bmph\b', 'miles per hour', text, flags=re.IGNORECASE)
        text = re.sub(r'\bPSI\b', 'P S I', text)
        text = re.sub(r'\bRPM\b', 'R P M', text)
        text = re.sub(r'\bGHz\b', 'gigahertz', text)
        text = re.sub(r'\bHz\b', 'hertz', text)
        text = re.sub(r'\bAFR\b', 'A F R', text)
        text = re.sub(r'\bEGT\b', 'E G T', text)
        text = re.sub(r'\bECU\b', 'E C U', text)
        text = re.sub(r'\bAWD\b', 'all wheel drive', text)
        text = re.sub(r'\bDCCD\b', 'D C C D', text)
        text = re.sub(r'\bFLIR\b', 'fleer', text)
        text = re.sub(r'\bLiDAR\b', 'lie-dar', text)
        text = re.sub(r'\bNVMe\b', 'N V M E', text)
        text = re.sub(r'\bKa\b', 'K A', text)
        text = re.sub(r'°F\b', ' degrees fahrenheit', text)
        text = re.sub(r'°C\b', ' degrees celsius', text)
        text = re.sub(r'°\b', ' degrees', text)
        return text

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def is_available(self) -> bool:
        return self._piper_available
