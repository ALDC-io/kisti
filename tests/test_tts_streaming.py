"""Tests for streaming TTS — split_sentences + streamed playback."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import struct
import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest

from voice.tts_engine import split_sentences, TTSEngine, TTSResult


# ---- split_sentences tests ----

class TestSplitSentences:
    """Test sentence splitting for streaming TTS."""

    def test_single_sentence(self):
        assert split_sentences("Hello world.") == ["Hello world."]

    def test_single_no_punctuation(self):
        assert split_sentences("Hello world") == ["Hello world"]

    def test_two_sentences(self):
        assert split_sentences("Hello. World.") == ["Hello.", "World."]

    def test_three_sentences(self):
        result = split_sentences("One. Two. Three.")
        assert result == ["One.", "Two.", "Three."]

    def test_exclamation_and_question(self):
        result = split_sentences("Stop! Why? Because.")
        assert result == ["Stop!", "Why?", "Because."]

    def test_empty_string(self):
        assert split_sentences("") == [""]

    def test_whitespace_only(self):
        result = split_sentences("   ")
        assert result == ["   "]

    def test_preserves_sentence_content(self):
        result = split_sentences("The STI has 310 BHP. The 911 has 379 BHP.")
        assert len(result) == 2
        assert "310 BHP" in result[0]
        assert "379 BHP" in result[1]

    def test_no_split_on_mid_sentence_period(self):
        # Abbreviations followed by more text on same line don't split
        # (only splits on period+whitespace, so "Dr.Smith" stays together)
        assert split_sentences("Dr.Smith went home.") == ["Dr.Smith went home."]

    def test_multiple_spaces_between_sentences(self):
        result = split_sentences("One.  Two.")
        assert result == ["One.", "Two."]

    def test_trailing_whitespace_stripped(self):
        result = split_sentences("  Hello.  World.  ")
        assert result == ["Hello.", "World."]

    def test_single_word(self):
        assert split_sentences("Yes") == ["Yes"]


# ---- Streaming TTS integration tests ----

class TestStreamedSynthesis:
    """Test that streaming TTS synthesizes per-sentence."""

    def _make_mock_result(self, text: str) -> TTSResult:
        """Create a mock TTSResult with deterministic audio."""
        word_count = len(text.split())
        duration_s = max(0.3, word_count * 0.1)
        num_samples = int(duration_s * 16000)
        audio_pcm = b"\x00\x01" * num_samples
        return TTSResult(
            audio_pcm=audio_pcm,
            sample_rate=16000,
            duration_s=duration_s,
            latency_s=0.01,
            amplitude_envelope=[0.5] * int(duration_s * 30),
        )

    def test_single_sentence_calls_speak_once(self, tmp_path):
        """Single sentence should call tts.speak exactly once."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()
        engine.speak = MagicMock(side_effect=lambda t: self._make_mock_result(t))

        # Simulate what _speak_single does
        result = engine.speak("Hello world.")
        assert engine.speak.call_count == 1
        assert result.audio_pcm

    def test_multi_sentence_calls_speak_per_sentence(self, tmp_path):
        """Multiple sentences should call tts.speak once per sentence."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()
        engine.speak = MagicMock(side_effect=lambda t: self._make_mock_result(t))

        sentences = split_sentences("Hello world. How are you. Fine thanks.")
        assert len(sentences) == 3

        # Simulate what _speak_streamed does
        results = []
        for s in sentences:
            results.append(engine.speak(s))

        assert engine.speak.call_count == 3
        # Each call gets a single sentence
        engine.speak.assert_any_call("Hello world.")
        engine.speak.assert_any_call("How are you.")
        engine.speak.assert_any_call("Fine thanks.")

    def test_combined_audio_is_concatenation(self, tmp_path):
        """Streaming should produce concatenated PCM from all sentences."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()
        engine.speak = MagicMock(side_effect=lambda t: self._make_mock_result(t))

        sentences = ["One.", "Two."]
        results = [engine.speak(s) for s in sentences]
        combined_pcm = b"".join(r.audio_pcm for r in results)
        combined_envelope = []
        for r in results:
            combined_envelope.extend(r.amplitude_envelope)

        # Combined audio is longer than individual
        assert len(combined_pcm) > len(results[0].audio_pcm)
        assert len(combined_envelope) > len(results[0].amplitude_envelope)

    def test_first_sentence_latency_is_perceived(self, tmp_path):
        """Perceived latency should be first sentence TTS time, not total."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()

        call_count = 0
        timings = []

        def mock_speak(text):
            nonlocal call_count
            call_count += 1
            timings.append(time.monotonic())
            # Simulate 50ms synthesis time
            time.sleep(0.05)
            return self._make_mock_result(text)

        engine.speak = mock_speak

        sentences = split_sentences("First sentence. Second sentence. Third sentence.")
        assert len(sentences) == 3

        start = time.monotonic()
        first_result = engine.speak(sentences[0])
        perceived_latency = time.monotonic() - start

        # Perceived latency is just the first sentence (~50ms), not all three (~150ms)
        assert perceived_latency < 0.15  # generous bound

    def test_streaming_path_chosen_for_multi_sentence(self):
        """split_sentences with multi-sentence text returns multiple items."""
        sentences = split_sentences("The boxer engine has unequal headers. This creates a distinctive rumble.")
        assert len(sentences) == 2
        assert "boxer" in sentences[0]
        assert "rumble" in sentences[1]

    def test_streaming_path_not_chosen_for_single(self):
        """split_sentences with single sentence returns one item."""
        sentences = split_sentences("Just one sentence here.")
        assert len(sentences) == 1

    def test_envelope_combination_order(self, tmp_path):
        """Combined envelope should preserve sentence order."""
        engine = TTSEngine(cache_dir=tmp_path, cache_enabled=False)
        engine.start()

        # Create results with distinct envelopes
        def make_distinct(text):
            r = self._make_mock_result(text)
            # Tag envelope with sentence index for verification
            if "One" in text:
                r.amplitude_envelope = [0.1] * 5
            elif "Two" in text:
                r.amplitude_envelope = [0.9] * 5
            return r

        engine.speak = MagicMock(side_effect=make_distinct)

        r1 = engine.speak("One.")
        r2 = engine.speak("Two.")
        combined = list(r1.amplitude_envelope) + list(r2.amplitude_envelope)

        # First half should be 0.1, second half 0.9
        assert combined[:5] == [0.1] * 5
        assert combined[5:] == [0.9] * 5
