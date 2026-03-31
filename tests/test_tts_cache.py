"""Tests for TTS disk cache."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import struct

from voice.tts_engine import TTSEngine, TTSResult, TTS_SUBSTITUTIONS


class TestTTSCache:
    """Test TTS caching behavior."""

    def test_cache_miss_synthesizes(self, tmp_path):
        """First call goes through synthesis."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        result = engine.speak("Hello world")
        assert result.audio_pcm
        assert result.duration_s > 0
        # Cache file should exist now
        cache_files = list(tmp_path.glob("*.cache"))
        assert len(cache_files) == 1

    def test_cache_hit_returns_same_audio(self, tmp_path):
        """Second call with same text returns identical audio."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        r1 = engine.speak("Hello world")
        r2 = engine.speak("Hello world")
        assert r1.audio_pcm == r2.audio_pcm
        assert r1.sample_rate == r2.sample_rate

    def test_cache_hit_faster(self, tmp_path):
        """Cache hit should have near-zero latency."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        engine.speak("Test phrase")
        r2 = engine.speak("Test phrase")
        # Cache hit latency should be very small
        assert r2.latency_s < 0.1  # generous bound for CI

    def test_different_text_different_cache(self, tmp_path):
        """Different text creates separate cache entries."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        engine.speak("Hello")
        engine.speak("Goodbye")
        cache_files = list(tmp_path.glob("*.cache"))
        assert len(cache_files) == 2

    def test_cache_survives_restart(self, tmp_path):
        """New engine instance finds existing cache."""
        e1 = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        e1.start()
        r1 = e1.speak("Persist this")
        e1.stop()

        e2 = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        e2.start()
        r2 = e2.speak("Persist this")
        assert r1.audio_pcm == r2.audio_pcm

    def test_cache_disabled(self, tmp_path):
        """cache_enabled=False skips caching."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()
        engine.speak("No cache")
        cache_files = list(tmp_path.glob("*.cache"))
        assert len(cache_files) == 0

    def test_clear_cache(self, tmp_path):
        """clear_cache() removes all cached files."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        engine.speak("One")
        engine.speak("Two")
        assert len(list(tmp_path.glob("*.cache"))) == 2
        count = engine.clear_cache()
        assert count == 2
        assert len(list(tmp_path.glob("*.cache"))) == 0

    def test_substitutions_applied_before_cache_key(self, tmp_path):
        """TTS_SUBSTITUTIONS are applied before computing cache key."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=True)
        engine.start()
        # "KiSTI" gets substituted to "Keesty Eye" before caching
        r1 = engine.speak("Hello KiSTI")
        # Speaking the substituted form should hit the same cache
        r2 = engine.speak("Hello Keesty Eye")
        assert r1.audio_pcm == r2.audio_pcm
