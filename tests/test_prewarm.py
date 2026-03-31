"""Tests for TTS cache pre-warm script."""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.event_quotes import EVENT_QUOTES
from scripts.prewarm_tts_cache import collect_all_texts, prewarm
from voice.llm_engine import FALLBACK_RESPONSE, PERSONA_RESPONSES


def test_script_importable():
    """The prewarm module imports without error."""
    import scripts.prewarm_tts_cache  # noqa: F401


def test_collects_all_persona_texts():
    """collect_all_texts includes every persona response text."""
    texts = collect_all_texts()

    # Every persona response must appear
    for _keywords, response, _category in PERSONA_RESPONSES:
        assert response in texts, f"Missing persona response: {response[:60]}"

    # Every event quote must appear
    for event, quotes in EVENT_QUOTES.items():
        for quote in quotes:
            assert quote in texts, f"Missing event quote ({event}): {quote[:60]}"

    # Fallback must appear
    assert FALLBACK_RESPONSE in texts

    # No duplicates
    assert len(texts) == len(set(texts))


def test_dry_run_no_files():
    """Dry run creates no cache files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir) / "tts_cache"
        prewarm(cache_dir=cache_dir, dry_run=True)
        # Directory should not even be created in dry-run mode
        cache_files = list(cache_dir.glob("*.cache")) if cache_dir.exists() else []
        assert len(cache_files) == 0
