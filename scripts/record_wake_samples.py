"""Record wake word samples for training a custom "Hey KiSTI" model.

Captures 2-second mono 16kHz s16le clips via parecord and saves as WAV files.
Designed to run on the Jetson with the same audio pipeline as mic_capture.py.

Usage:
    python3 scripts/record_wake_samples.py --count 50
    python3 scripts/record_wake_samples.py --count 20 --output-dir /tmp/negatives --prefix neg
    python3 scripts/record_wake_samples.py --device alsa_input.usb-... --count 10
"""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import time
import wave

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
CLIP_DURATION_S = 2
CLIP_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * CLIP_DURATION_S
PAUSE_BETWEEN_S = 1


def find_pa_usb_source() -> str:
    """Auto-detect PulseAudio USB microphone source."""
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


def generate_filename(output_dir: str, prefix: str, index: int) -> str:
    """Generate a numbered WAV filename: {prefix}_NNNN.wav"""
    return os.path.join(output_dir, f"{prefix}_{index:04d}.wav")


def record_clip(device: str) -> bytes:
    """Record a single 2-second clip via parecord, return raw PCM bytes."""
    cmd = [
        "parecord", "--raw",
        "--rate", str(SAMPLE_RATE),
        "--channels", str(CHANNELS),
        "--format", "s16le",
    ]
    if device:
        cmd.extend(["--device", device])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    try:
        data = b""
        remaining = CLIP_BYTES
        while remaining > 0:
            chunk = proc.stdout.read(min(remaining, 4096))
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)
    finally:
        proc.terminate()
        proc.wait(timeout=3)

    return data


def save_wav(path: str, pcm_data: bytes) -> None:
    """Wrap raw PCM data in a WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Record wake word samples for training",
    )
    parser.add_argument(
        "--count", type=int, default=50,
        help="Number of samples to record (default: 50)",
    )
    parser.add_argument(
        "--output-dir", type=str,
        default="/tmp/kisti_wake_samples/real_positive/",
        help="Directory to save WAV files",
    )
    parser.add_argument(
        "--prefix", type=str, default="pos",
        help="Filename prefix (default: pos)",
    )
    parser.add_argument(
        "--device", type=str, default="",
        help="PulseAudio source device (default: auto-detect)",
    )
    return parser


def main(args: list[str] | None = None) -> None:
    """Run the recording session."""
    parser = build_parser()
    opts = parser.parse_args(args)

    # Resolve device
    device = opts.device
    if not device:
        device = find_pa_usb_source()
        if device:
            print(f"Auto-detected mic: {device}")
        else:
            print("No USB mic found, using PulseAudio default")

    # Create output directory
    os.makedirs(opts.output_dir, exist_ok=True)

    print(f"\nRecording {opts.count} x {CLIP_DURATION_S}s clips to {opts.output_dir}")
    print(f"Say 'Hey KiSTI' clearly after each prompt.\n")

    for i in range(1, opts.count + 1):
        print(f"Recording {i}/{opts.count}... speak now!", flush=True)
        pcm = record_clip(device)

        if len(pcm) < CLIP_BYTES:
            print(f"  WARNING: short capture ({len(pcm)} bytes), saving anyway")

        path = generate_filename(opts.output_dir, opts.prefix, i)
        save_wav(path, pcm)
        print(f"  Saved {os.path.basename(path)}")

        if i < opts.count:
            time.sleep(PAUSE_BETWEEN_S)

    print(f"\nDone! {opts.count} samples saved to {opts.output_dir}")


if __name__ == "__main__":
    main()
