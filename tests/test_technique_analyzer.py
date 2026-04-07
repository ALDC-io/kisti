"""Tests for TechniqueAnalyzer — driving technique coaching."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.vehicle_state import DiffState
from coaching.technique_analyzer import TechniqueAnalyzer


def _snap(brake=0.0, steering=0.0, speed=80.0, throttle=50.0,
          imu_y=0.0, brake_front=0.0, brake_rear=0.0,
          brake_bias=0.0, imu_x=0.0) -> DiffState:
    """Build a minimal DiffState for technique analysis."""
    return DiffState(
        brake_pressure=brake,
        steering_angle=steering,
        speed_kph=speed,
        throttle_pct=throttle,
        imu_accel_y=imu_y,
        imu_accel_x=imu_x,
        brake_pressure_front=brake_front,
        brake_pressure_rear=brake_rear,
        brake_bias_pct=brake_bias,
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

    # --- Brake bias tests ---

    def test_steady_bias_green(self):
        """Consistent ~65% front bias = green coaching (or smooth braking)."""
        ta = TechniqueAnalyzer()
        for _ in range(10):
            ta.feed(_snap(brake=40.0, brake_front=26.0, brake_rear=14.0,
                          brake_bias=65.0))
        text, sentiment = ta.analyze()
        # Both smooth braking and steady bias are green — either is correct
        assert sentiment == "green"
        assert "smooth" in text.lower() or "bias" in text.lower()

    def test_erratic_bias_amber(self):
        """Wildly varying bias = amber warning."""
        ta = TechniqueAnalyzer()
        # Alternate between extreme front-heavy and rear-heavy
        for i in range(10):
            bias = 50.0 if i % 2 == 0 else 80.0  # std dev ~15
            front = 40.0 * bias / 100
            rear = 40.0 * (100 - bias) / 100
            ta.feed(_snap(brake=40.0, brake_front=front, brake_rear=rear,
                          brake_bias=bias))
        text, sentiment = ta.analyze()
        assert "bias" in text.lower() or "erratic" in text.lower()
        assert sentiment == "amber"

    def test_rear_heavy_bias_amber(self):
        """Rear-heavy (<55% front) = amber warning."""
        ta = TechniqueAnalyzer()
        for _ in range(10):
            ta.feed(_snap(brake=40.0, brake_front=18.0, brake_rear=22.0,
                          brake_bias=45.0))
        text, sentiment = ta.analyze()
        assert "rear" in text.lower() or "bias" in text.lower()
        assert sentiment == "amber"

    def test_brake_quality_with_bias_penalty(self):
        """Erratic bias should downgrade brake_quality to red."""
        ta = TechniqueAnalyzer()
        # Alternate extreme bias to ensure std > 8
        for i in range(10):
            bias = 50.0 if i % 2 == 0 else 80.0
            ta.feed(_snap(brake=40.0, brake_front=40*bias/100,
                          brake_rear=40*(100-bias)/100,
                          brake_bias=bias, imu_x=-0.9))
        quality = ta.brake_quality()
        assert quality == "red"

    def test_no_bias_without_dual_sensors(self):
        """When front/rear are both 0 (no dual sensors), skip bias coaching."""
        ta = TechniqueAnalyzer()
        for _ in range(10):
            ta.feed(_snap(brake=40.0))  # no brake_front/rear
        text, _ = ta.analyze()
        assert "bias" not in text.lower()

    def test_fade_detection(self):
        """Pressure rising + decel dropping = possible fade."""
        ta = TechniqueAnalyzer()
        # Build up: pressure increasing, decel G decreasing
        for i in range(10):
            pressure = 30 + i * 3  # 30 → 57
            decel_g = -0.8 + i * 0.06  # -0.8 → -0.26 (getting weaker)
            front = pressure * 0.65
            rear = pressure * 0.35
            ta.feed(_snap(brake=pressure, brake_front=front, brake_rear=rear,
                          brake_bias=65.0, imu_x=decel_g))
        text, sentiment = ta.analyze()
        assert "fade" in text.lower()
        assert sentiment == "amber"
