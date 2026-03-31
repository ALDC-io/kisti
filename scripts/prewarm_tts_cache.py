#!/usr/bin/env python3
"""KiSTI - TTS Cache Pre-Warm Script

Synthesizes all persona responses, event quotes, and the fallback response
ahead of time so the TTS cache is fully populated before the first drive.

Usage:
    python3 -m scripts.prewarm_tts_cache
    python3 -m scripts.prewarm_tts_cache --cache-dir /tmp/tts_cache
    python3 -m scripts.prewarm_tts_cache --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add repo root to path so imports work when run as script
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from data.event_quotes import EVENT_QUOTES
from voice.llm_engine import FALLBACK_RESPONSE, PERSONA_RESPONSES
from voice.tts_engine import TTSEngine


def collect_all_texts() -> list[str]:
    """Collect all unique texts that should be pre-cached.

    Returns deduplicated list of persona responses + event quotes + fallback.
    """
    texts: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> None:
        if text not in seen:
            seen.add(text)
            texts.append(text)

    # Persona responses (index 1 is the response text)
    for _keywords, response, _category in PERSONA_RESPONSES:
        _add(response)

    # Event quotes (each key maps to a list of strings)
    for quotes in EVENT_QUOTES.values():
        for quote in quotes:
            _add(quote)

    # Fallback
    _add(FALLBACK_RESPONSE)

    return texts


def prewarm(cache_dir: Path, dry_run: bool = False) -> None:
    """Pre-warm the TTS cache by synthesizing all known texts.

    Args:
        cache_dir: Directory for TTS cache files.
        dry_run: If True, just count texts without synthesizing.
    """
    texts = collect_all_texts()
    total = len(texts)

    if dry_run:
        print(f"Dry run: {total} texts to cache (no synthesis)")
        return

    engine = TTSEngine(cache_dir=cache_dir)
    engine.start()

    total_bytes = 0
    t0 = time.monotonic()

    for i, text in enumerate(texts, 1):
        truncated = text[:50] + ("..." if len(text) > 50 else "")
        print(f"Cached {i}/{total}: '{truncated}'")
        result = engine.speak(text)
        total_bytes += len(result.audio_pcm)

    elapsed = time.monotonic() - t0
    engine.stop()

    print(f"\nDone: {total} texts cached, {total_bytes:,} bytes, {elapsed:.1f}s elapsed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm TTS cache for KiSTI")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/tts_cache"),
        help="TTS cache directory (default: data/tts_cache/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count texts without synthesizing",
    )
    args = parser.parse_args()
    prewarm(cache_dir=args.cache_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
