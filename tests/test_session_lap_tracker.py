"""Tests for SessionLapTracker — within-session lap trend voice coaching.

TDD red phase: written before implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coaching.session_lap_tracker import SessionLapTracker


class TestSessionLapTracker:
    def test_insufficient_ticks_returns_empty(self):
        """Fewer than 3 ticks → complete_lap returns empty string."""
        tracker = SessionLapTracker()
        tracker.record_tick("Smooth braking", "green")
        tracker.record_tick("Smooth braking", "green")
        result = tracker.complete_lap(1, 62.4)
        assert result == ""

    def test_first_lap_amber_surfaces_issue(self):
        """First lap with >30% amber ticks → returns issue text (short)."""
        tracker = SessionLapTracker()
        # 4 amber ticks out of 10 = 40% amber
        for _ in range(6):
            tracker.record_tick("Smooth entry", "green")
        for _ in range(4):
            tracker.record_tick("Extend braking zones, smooth throttle", "amber")
        result = tracker.complete_lap(1, 65.0)
        assert result != ""
        assert len(result.split()) <= 8

    def test_first_lap_clean_returns_empty(self):
        """First lap with <10% amber → empty (nothing useful to say)."""
        tracker = SessionLapTracker()
        for _ in range(10):
            tracker.record_tick("Smooth entry", "green")
        result = tracker.complete_lap(1, 61.0)
        assert result == ""

    def test_improving_green_fraction(self):
        """Green fraction rises by >15 points lap-over-lap → 'Technique improving.'"""
        tracker = SessionLapTracker()
        # Lap 1: 50% green
        for _ in range(5):
            tracker.record_tick("Good", "green")
        for _ in range(5):
            tracker.record_tick("Watch braking", "amber")
        tracker.complete_lap(1, 63.0)

        # Lap 2: 80% green → delta = +30 points
        for _ in range(8):
            tracker.record_tick("Good", "green")
        for _ in range(2):
            tracker.record_tick("Watch braking", "amber")
        result = tracker.complete_lap(2, 62.0)
        assert "improving" in result.lower()

    def test_regression_amber_increases(self):
        """Amber fraction rises by >15 points → regression message."""
        tracker = SessionLapTracker()
        # Lap 1: 10% amber
        for _ in range(9):
            tracker.record_tick("Smooth entry", "green")
        for _ in range(1):
            tracker.record_tick("Watch braking", "amber")
        tracker.complete_lap(1, 61.5)

        # Lap 2: 50% amber → delta = +40 points
        for _ in range(5):
            tracker.record_tick("Smooth entry", "green")
        for _ in range(5):
            tracker.record_tick("Watch braking", "amber")
        result = tracker.complete_lap(2, 62.5)
        assert "rougher" in result.lower() or "watch" in result.lower()

    def test_clean_lap(self):
        """amber_frac < 10% on any lap after lap 1 → 'Clean lap. Keep it.'"""
        tracker = SessionLapTracker()
        # Lap 1: mediocre
        for _ in range(6):
            tracker.record_tick("Good", "green")
        for _ in range(4):
            tracker.record_tick("Watch braking", "amber")
        tracker.complete_lap(1, 63.0)

        # Lap 2: very clean (<10% amber)
        for _ in range(10):
            tracker.record_tick("Smooth", "green")
        result = tracker.complete_lap(2, 62.0)
        assert "clean" in result.lower()

    def test_complete_resets_state(self):
        """After complete_lap, accumulators reset — next lap starts fresh."""
        tracker = SessionLapTracker()
        for _ in range(5):
            tracker.record_tick("Good", "green")
        for _ in range(5):
            tracker.record_tick("Watch braking", "amber")
        tracker.complete_lap(1, 63.0)

        # Add only 2 ticks to lap 2 (below min threshold)
        tracker.record_tick("Good", "green")
        tracker.record_tick("Good", "green")
        result = tracker.complete_lap(2, 62.0)
        # Should return "" because only 2 ticks accumulated after reset
        assert result == ""
