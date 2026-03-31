"""Tests for KiSTI car joke system — random selection from 500-joke pool."""

from data.car_jokes import CAR_JOKES, joke_count, category_counts
from voice.llm_engine import (
    _JOKE_SENTINEL,
    _match_persona,
    _match_safety_fast_path,
)


class TestCarJokes:
    """Verify joke keyword triggers and random selection."""

    def test_joke_pool_has_500_plus_entries(self):
        assert joke_count() >= 500

    def test_all_categories_have_jokes(self):
        counts = category_counts()
        for cat, count in counts.items():
            assert count >= 5, f"Category '{cat}' has only {count} jokes"

    def test_all_jokes_are_nonempty_strings(self):
        for joke in CAR_JOKES:
            assert isinstance(joke, str)
            assert len(joke) > 20

    def test_tell_me_a_joke_returns_from_pool(self):
        result = _match_persona("tell me a joke", "Intelligent")
        assert result is not None
        assert result in CAR_JOKES

    def test_make_me_laugh_triggers_joke(self):
        result = _match_persona("make me laugh", "Intelligent")
        assert result is not None
        assert result in CAR_JOKES

    def test_another_joke_triggers(self):
        result = _match_persona("another joke", "Intelligent")
        assert result is not None
        assert result in CAR_JOKES

    def test_different_joke_triggers(self):
        result = _match_persona("tell me a different joke", "Intelligent")
        assert result is not None
        assert result in CAR_JOKES

    def test_got_any_more_triggers(self):
        result = _match_persona("got any more", "Intelligent")
        assert result is not None
        assert result in CAR_JOKES

    def test_joke_variety_over_multiple_calls(self):
        """Multiple calls should produce at least 2 different jokes."""
        results = set()
        for _ in range(50):
            result = _match_persona("tell me a joke", "Intelligent")
            results.add(result)
        assert len(results) >= 2, "Expected variety — got same joke every time"

    def test_jokes_not_available_in_sport_mode(self):
        """Fun category jokes are filtered out in Sport mode."""
        result = _match_persona("tell me a joke", "Sport")
        assert result is None

    def test_jokes_not_available_in_sport_sharp_mode(self):
        result = _match_persona("tell me a joke", "Sport Sharp")
        assert result is None

    def test_sentinel_not_returned_directly(self):
        """The __JOKE__ sentinel should never be returned to the caller."""
        for _ in range(20):
            result = _match_persona("tell me a joke", "Intelligent")
            assert result != _JOKE_SENTINEL

    def test_joke_in_safety_fast_path(self):
        """Jokes should fire from the safety fast-path (instant, no API call)."""
        result = _match_safety_fast_path("tell me a joke", "Intelligent")
        assert result is not None
        assert result != "__JOKE__"  # Should be actual joke text, not sentinel
