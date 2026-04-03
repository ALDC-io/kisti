"""Tests for TechniqueAnalyzer — driving technique coaching."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.vehicle_state import DiffState
from coaching.technique_analyzer import TechniqueAnalyzer


def _snap(brake=0.0, steering=0.0, speed=80.0, throttle=50.0,
          imu_y=0.0) -> DiffState:
    """Build a minimal DiffState for technique analysis."""
    return DiffState(
        brake_pressure=brake,
        steering_angle=steering,
        speed_kph=speed,
        throttle_pct=throttle,
        imu_accel_y=imu_y,
    )


class TestTechniqueAnalyzer:
    def test_insufficient_data(self):
        ta = TechniqueAnalyzer()
        for _ in range(5):
            ta.feed(_snap())
        text, sentiment = ta.analyze()
        assert text == ""
        assert sentiment == "dim"

    def test_consistent_braking_positive(self):
        ta = TechniqueAnalyzer()
        for _ in range(30):
            ta.feed(_snap(brake=40.0, steering=0.0))
        text, sentiment = ta.analyze()
        assert "smooth" in text.lower() or "braking" in text.lower()
        assert sentiment == "green"

    def test_inconsistent_braking_warning(self):
        ta = TechniqueAnalyzer()
        import random
        random.seed(42)
        for i in range(30):
            # Wild variation: 10-80 bar
            pressure = 10 + random.random() * 70
            ta.feed(_snap(brake=pressure))
        text, sentiment = ta.analyze()
        assert "inconsistent" in text.lower() or "varies" in text.lower()
        assert sentiment == "amber"

    def test_smooth_steering_positive(self):
        ta = TechniqueAnalyzer()
        for i in range(30):
            # Gentle consistent cornering
            ta.feed(_snap(steering=45.0))
        text, sentiment = ta.analyze()
        assert "smooth" in text.lower() or "steering" in text.lower()
        assert sentiment == "green"

    def test_abrupt_steering_warning(self):
        ta = TechniqueAnalyzer()
        for i in range(30):
            # Alternating hard left/right = huge steering rate
            angle = 60.0 if i % 2 == 0 else -60.0
            ta.feed(_snap(steering=angle))
        text, sentiment = ta.analyze()
        assert "steering" in text.lower() or "abrupt" in text.lower()
        assert sentiment == "amber"

    def test_trail_braking_detected(self):
        ta = TechniqueAnalyzer()
        for _ in range(30):
            # Braking while turning — trail braking
            ta.feed(_snap(brake=30.0, steering=45.0))
        text, sentiment = ta.analyze()
        # Should get positive feedback for either braking or trail braking
        assert sentiment in ("green",)

    def test_no_trail_braking_suggestion(self):
        ta = TechniqueAnalyzer()
        for i in range(30):
            # Alternating: brake straight, then steer without brakes
            if i % 2 == 0:
                ta.feed(_snap(brake=40.0, steering=5.0))
            else:
                ta.feed(_snap(brake=0.0, steering=50.0))
        text, sentiment = ta.analyze()
        # Should suggest trail braking or flag braking issue
        assert text != ""

    def test_window_rolls(self):
        ta = TechniqueAnalyzer()
        # Feed 30 bad samples then 30 good
        for _ in range(30):
            ta.feed(_snap(brake=10 + 70 * (_ % 2)))
        for _ in range(30):
            ta.feed(_snap(brake=40.0))
        text, sentiment = ta.analyze()
        # Window should only see the last 30 good samples
        assert sentiment == "green"
