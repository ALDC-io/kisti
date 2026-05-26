#!/usr/bin/env python3
"""KiSTI - Custom "Hey KiSTI" Wake Word Training Script

Generates synthetic audio samples using Piper TTS and trains a custom
openwakeword model for the "Hey KiSTI" wake phrase.

Two training paths are supported:

1. CUSTOM VERIFIER (recommended, runs locally on Jetson):
   Uses openwakeword's custom_verifier_model to train a lightweight logistic
   regression classifier on top of existing speech embeddings. Fast (~5 min),
   small output (~50 KB .pkl), works with ~50-100 positive samples.

2. FULL TRAINING (requires Colab or GPU workstation):
   Uses openwakeword's train.py with YAML config for end-to-end model training.
   Produces a proper ONNX model but requires ~30K hours of negative audio data
   and significant compute. This script generates the YAML config and positive
   samples; actual training runs via:
     python3 -m openwakeword.train --training_config hey_kisti_config.yaml

Usage:
    # Generate samples + train custom verifier (default, recommended):
    python3 scripts/train_wake_word.py

    # Generate samples only (for Colab full training):
    python3 scripts/train_wake_word.py --samples-only

    # Specify output model path:
    python3 scripts/train_wake_word.py --output /data/models/hey_kisti.onnx

    # Use specific Piper voices directory:
    python3 scripts/train_wake_word.py --piper-dir /data/piper
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train_wake_word")

# Piper TTS defaults (Jetson paths)
DEFAULT_PIPER_DIR = Path("/data/piper")
DEFAULT_PIPER_BINARY = DEFAULT_PIPER_DIR / "piper"
DEFAULT_OUTPUT = Path("/data/models/hey_kisti.onnx")

# Wake phrase variations for synthetic training data.
# Includes the primary phrase plus common pronunciation variants that
# a real user might say. These cover accent/speed variations.
WAKE_PHRASES = [
    "Hey KiSTI",
    "Hey Keesty",
    "Hey Kisti",
    "Hey, KiSTI",
    "Hey, Keesty",
    "Hey KiSTI!",
    "Hey, Keesty Eye",
]

# Piper voice models to use for sample generation (if available).
# Danny is the default KiSTI voice; others add speaker diversity.
PIPER_VOICES = [
    "en_US-danny-low.onnx",
    "en_US-lessac-medium.onnx",
    "en_US-amy-medium.onnx",
    "en_US-joe-medium.onnx",
    "en_GB-alba-medium.onnx",
    "en_GB-cori-medium.onnx",
]

# Speed factors for length_scale (Piper: <1 = faster, >1 = slower)
SPEED_FACTORS = [0.8, 0.9, 1.0, 1.1, 1.2]

# Negative phrases — things that sound vaguely similar or are common speech
# that should NOT trigger the wake word.
NEGATIVE_PHRASES = [
    "Hey Siri",
    "Hey Google",
    "Hey Alexa",
    "OK Google",
    "Hey Christy",
    "Hey Kristy",
    "Hey misty",
    "Hey history",
    "The key is to",
    "Keys to success",
    "Hey listen",
    "Keeps to himself",
    "That's a mystery",
    "She is feisty",
    "Hey Christie",
    "Hey Mr T",
    "Hey, can you hear me",
    "Hey, what's that",
    "How's the weather",
    "What's the temperature",
    "Check the oil pressure",
    "Turn left here",
    "How fast are we going",
    "What time is it",
    "Play some music",
    "The highway is busy",
    "That car is rusty",
    "It's getting misty",
    "Hey there",
    "Hey buddy",
]

SAMPLE_RATE = 16000  # openwakeword expects 16kHz


def find_available_voices(piper_dir: Path) -> list[Path]:
    """Find Piper voice ONNX files available on disk."""
    available = []
    for voice_name in PIPER_VOICES:
        voice_path = piper_dir / voice_name
        if voice_path.exists():
            available.append(voice_path)
    if not available:
        log.warning("No Piper voice models found in %s", piper_dir)
    return available


def generate_wav_piper(
    piper_binary: Path,
    voice_model: Path,
    text: str,
    output_path: Path,
    length_scale: float = 1.0,
) -> bool:
    """Generate a WAV file using Piper TTS.

    Args:
        piper_binary: Path to the piper binary.
        voice_model: Path to the .onnx voice model.
        text: Text to synthesize.
        output_path: Where to write the output WAV.
        length_scale: Speed factor (<1 faster, >1 slower).

    Returns:
        True if generation succeeded.
    """
    config_path = voice_model.parent / f"{voice_model.name}.json"

    cmd = [
        str(piper_binary),
        "--model", str(voice_model),
        "--output_file", str(output_path),
    ]
    if config_path.exists():
        cmd.extend(["--config", str(config_path)])
    if length_scale != 1.0:
        cmd.extend(["--length_scale", str(length_scale)])

    try:
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            log.warning("Piper failed for '%s': %s", text, proc.stderr.decode()[:200])
            return False
        return output_path.exists() and output_path.stat().st_size > 100
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.warning("Piper error: %s", exc)
        return False


def generate_silence_wav(output_path: Path, duration_s: float = 2.0) -> None:
    """Generate a WAV file of silence (negative sample)."""
    n_samples = int(SAMPLE_RATE * duration_s)
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * n_samples)


def generate_noise_wav(output_path: Path, duration_s: float = 2.0) -> None:
    """Generate a WAV file of synthetic noise (engine-like rumble).

    Simulates low-frequency engine noise by summing sine waves at
    typical engine harmonics (50-200 Hz) with random amplitude.
    """
    n_samples = int(SAMPLE_RATE * duration_s)
    samples = []
    # Engine-like frequencies: fundamental + harmonics
    freqs = [55, 110, 165, 220]
    amplitudes = [random.uniform(500, 2000) for _ in freqs]
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        val = sum(a * math.sin(2 * math.pi * f * t) for f, a in zip(freqs, amplitudes))
        # Add random noise component
        val += random.gauss(0, 300)
        val = max(-32768, min(32767, int(val)))
        samples.append(struct.pack("<h", val))

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(samples))


def generate_positive_samples(
    piper_binary: Path,
    voices: list[Path],
    output_dir: Path,
    target_count: int = 100,
) -> int:
    """Generate positive wake word samples using Piper TTS.

    Creates variations by combining:
    - Multiple wake phrases (pronunciation variants)
    - Multiple Piper voices (speaker diversity)
    - Multiple speed factors (tempo variation)

    Args:
        piper_binary: Path to Piper binary.
        voices: List of available voice model paths.
        output_dir: Directory for output WAV files.
        target_count: Minimum number of samples to generate.

    Returns:
        Number of successfully generated samples.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    # Calculate how many rounds we need
    combos = [(phrase, voice, speed)
              for phrase in WAKE_PHRASES
              for voice in voices
              for speed in SPEED_FACTORS]
    random.shuffle(combos)

    for phrase, voice, speed in combos:
        if count >= target_count:
            break
        voice_name = voice.stem.replace("-", "_")
        speed_label = str(speed).replace(".", "")
        fname = f"pos_{count:04d}_{voice_name}_s{speed_label}.wav"
        out_path = output_dir / fname

        if generate_wav_piper(piper_binary, voice, phrase, out_path, length_scale=speed):
            count += 1
            if count % 20 == 0:
                log.info("Generated %d/%d positive samples", count, target_count)

    log.info("Generated %d positive samples in %s", count, output_dir)
    return count


def generate_negative_samples(
    piper_binary: Path,
    voices: list[Path],
    output_dir: Path,
    target_count: int = 200,
) -> int:
    """Generate negative samples: speech that is NOT the wake word, plus noise.

    Mix of:
    - TTS-generated confusable phrases (~60%)
    - Silence samples (~20%)
    - Synthetic engine noise (~20%)

    Args:
        piper_binary: Path to Piper binary.
        voices: List of available voice model paths.
        output_dir: Directory for output WAV files.
        target_count: Minimum number of samples to generate.

    Returns:
        Number of successfully generated samples.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    # Speech negatives (~60%)
    speech_target = int(target_count * 0.6)
    combos = [(phrase, voice, speed)
              for phrase in NEGATIVE_PHRASES
              for voice in voices
              for speed in [0.9, 1.0, 1.1]]
    random.shuffle(combos)

    for phrase, voice, speed in combos:
        if count >= speech_target:
            break
        voice_name = voice.stem.replace("-", "_")
        fname = f"neg_{count:04d}_{voice_name}.wav"
        out_path = output_dir / fname

        if generate_wav_piper(piper_binary, voice, phrase, out_path, length_scale=speed):
            count += 1

    # Silence negatives (~20%)
    silence_target = int(target_count * 0.2)
    for i in range(silence_target):
        fname = f"neg_silence_{i:04d}.wav"
        generate_silence_wav(output_dir / fname, duration_s=random.uniform(1.0, 3.0))
        count += 1

    # Engine noise negatives (~20%)
    noise_target = int(target_count * 0.2)
    for i in range(noise_target):
        fname = f"neg_noise_{i:04d}.wav"
        generate_noise_wav(output_dir / fname, duration_s=random.uniform(1.0, 3.0))
        count += 1

    log.info("Generated %d negative samples in %s", count, output_dir)
    return count


def train_custom_verifier(
    positive_dir: Path,
    negative_dir: Path,
    output_path: Path,
    base_model: str = "hey_jarvis",
) -> bool:
    """Train a custom verifier model using openwakeword's built-in API.

    This uses logistic regression on top of openwakeword's pre-trained
    speech embeddings. Fast and lightweight — runs on Jetson in ~2 minutes.

    The verifier produces a .pkl file that openwakeword loads alongside
    the base model for two-stage detection: base model proposes candidates,
    verifier confirms/rejects.

    Args:
        positive_dir: Directory containing positive WAV samples.
        negative_dir: Directory containing negative WAV samples.
        output_path: Where to save the trained model.
        base_model: Base openwakeword model to build upon.

    Returns:
        True if training succeeded.
    """
    try:
        from openwakeword.custom_verifier_model import train_custom_verifier as _train
    except ImportError:
        log.error(
            "openwakeword custom_verifier_model not available. "
            "Install: pip install openwakeword>=0.6.0"
        )
        return False

    pos_clips = sorted(str(p) for p in positive_dir.glob("*.wav"))
    neg_clips = sorted(str(p) for p in negative_dir.glob("*.wav"))

    if len(pos_clips) < 5:
        log.error("Need at least 5 positive samples, found %d", len(pos_clips))
        return False
    if len(neg_clips) < 5:
        log.error("Need at least 5 negative samples, found %d", len(neg_clips))
        return False

    log.info(
        "Training custom verifier: %d positive, %d negative clips",
        len(pos_clips), len(neg_clips),
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # The verifier output is a .pkl file alongside the ONNX
    verifier_path = output_path.with_suffix(".pkl")

    try:
        _train(
            positive_reference_clips=pos_clips,
            negative_reference_clips=neg_clips,
            output_path=str(verifier_path),
            model_name=base_model,
        )
        log.info("Custom verifier saved to %s", verifier_path)
        return verifier_path.exists()
    except Exception as exc:
        log.error("Custom verifier training failed: %s", exc)
        return False


def generate_full_training_config(
    positive_dir: Path,
    negative_dir: Path,
    output_dir: Path,
) -> Path:
    """Generate a YAML config for openwakeword full training.

    This config can be used with:
        python3 -m openwakeword.train --training_config <config.yaml>

    Full training requires additional resources:
    - Background noise dataset (~30K hours, e.g. MUSAN or AudioSet)
    - Room impulse responses (e.g. MIT IR dataset)
    - GPU with 8+ GB VRAM (or Google Colab)
    - ~1-2 hours training time

    Args:
        positive_dir: Directory with positive WAV samples.
        negative_dir: Directory with negative WAV samples.
        output_dir: Where to write config and output model.

    Returns:
        Path to the generated YAML config file.
    """
    config = {
        "target_phrase": "hey kisti",
        "model_name": "hey_kisti",
        "n_samples": 5000,
        "n_samples_val": 500,
        "target_accuracy": 0.95,
        "n_epochs": 50,
        "max_steps": 50000,
        "learning_rate": 0.001,
        "batch_size": 256,
        "false_positive_rate_target": 0.5,  # Per hour
        "output_dir": str(output_dir),
        "positive_clips_dir": str(positive_dir),
        "negative_clips_dir": str(negative_dir),
    }

    config_path = output_dir / "hey_kisti_config.yaml"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write as YAML (manual to avoid pyyaml dependency)
    lines = ["# openwakeword training config for 'Hey KiSTI'",
             "# Generated by scripts/train_wake_word.py",
             "#",
             "# Usage: python3 -m openwakeword.train \\",
             "#          --training_config hey_kisti_config.yaml \\",
             "#          --generate_clips --augment_clips --train_model",
             ""]
    for key, value in config.items():
        if isinstance(value, str):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")

    config_path.write_text("\n".join(lines) + "\n")
    log.info("Full training config written to %s", config_path)
    return config_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train custom 'Hey KiSTI' wake word model",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output model path (default: %(default)s)",
    )
    parser.add_argument(
        "--piper-dir",
        type=Path,
        default=DEFAULT_PIPER_DIR,
        help="Piper TTS directory (default: %(default)s)",
    )
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=None,
        help="Sample output directory (default: /tmp/kisti_wake_samples/)",
    )
    parser.add_argument(
        "--positive-count",
        type=int,
        default=100,
        help="Number of positive samples to generate (default: %(default)s)",
    )
    parser.add_argument(
        "--negative-count",
        type=int,
        default=200,
        help="Number of negative samples to generate (default: %(default)s)",
    )
    parser.add_argument(
        "--samples-only",
        action="store_true",
        help="Generate samples only (skip training, for Colab full training)",
    )
    parser.add_argument(
        "--full-config",
        action="store_true",
        help="Also generate YAML config for full openwakeword training",
    )
    args = parser.parse_args()

    piper_binary = args.piper_dir / "piper"
    if not piper_binary.exists():
        log.error("Piper binary not found at %s", piper_binary)
        log.error("Install Piper or specify --piper-dir")
        return 1

    voices = find_available_voices(args.piper_dir)
    if not voices:
        log.error("No Piper voice models found in %s", args.piper_dir)
        return 1
    log.info("Found %d Piper voices: %s", len(voices), [v.name for v in voices])

    # Set up sample directories
    samples_dir = args.samples_dir or Path("/tmp/kisti_wake_samples")
    positive_dir = samples_dir / "positive"
    negative_dir = samples_dir / "negative"

    # Generate samples
    log.info("=== Generating positive samples ===")
    n_pos = generate_positive_samples(
        piper_binary, voices, positive_dir,
        target_count=args.positive_count,
    )
    if n_pos < 5:
        log.error("Too few positive samples generated (%d). Check Piper setup.", n_pos)
        return 1

    log.info("=== Generating negative samples ===")
    n_neg = generate_negative_samples(
        piper_binary, voices, negative_dir,
        target_count=args.negative_count,
    )

    log.info("Samples: %d positive, %d negative in %s", n_pos, n_neg, samples_dir)

    if args.samples_only:
        log.info("--samples-only: skipping training")
        if args.full_config:
            generate_full_training_config(
                positive_dir, negative_dir, args.output.parent,
            )
        return 0

    # Train custom verifier (lightweight, runs locally)
    log.info("=== Training custom verifier ===")
    success = train_custom_verifier(
        positive_dir, negative_dir, args.output,
    )

    if args.full_config:
        generate_full_training_config(
            positive_dir, negative_dir, args.output.parent,
        )

    if success:
        log.info("Training complete! Model at %s", args.output.with_suffix(".pkl"))
        log.info(
            "To use: export KISTI_WAKE_MODEL=%s",
            args.output.with_suffix(".pkl"),
        )
        return 0
    else:
        log.warning(
            "Custom verifier training failed. Samples are saved at %s. "
            "You can use these with the openwakeword Colab notebook for "
            "full model training: "
            "https://github.com/dscripka/openwakeword",
            samples_dir,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
