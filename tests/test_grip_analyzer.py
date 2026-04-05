"""Tests for coaching/grip_analyzer.py — per-axle traction analysis."""

import pytest

from coaching.grip_analyzer import (
    SLIP_ADVISORY,
    SLIP_WARNING,
    SPEED_GATE_MPS,
    GripAnalyzer,
    axle_grip_pct,
    wheel_slip_ratio,
)
from model.vehicle_state import DiffState


def _snap(
    gps_mps: float = 20.0,
    fl: float = 72.0,
    fr: float = 72.0,
    rl: float = 72.0,
    rr: float = 72.0,
) -> DiffState:
    """Build minimal DiffState for grip analysis.

    Default: 20 m/s GPS = 72 km/h, all wheels matching.
    """
    return DiffState(
        gps_speed_mps=gps_mps,
        wheel_speed_fl=fl,
        wheel_speed_fr=fr,
        wheel_speed_rl=rl,
        wheel_speed_rr=rr,
    )


# ---------- wheel_slip_ratio ----------

class TestWheelSlipRatio:
    def test_no_slip(self):
        """Matching wheel and GPS speed = zero slip."""
        assert wheel_slip_ratio(72.0, 20.0) == pytest.approx(0.0, abs=0.001)

    def test_wheelspin(self):
        """Wheel faster than GPS = positive slip."""
        ratio = wheel_slip_ratio(80.0, 20.0)
        # 80 vs 72 km/h GPS → (80 - 72) / 72 ≈ 0.111
        assert ratio > 0.10

    def test_lockup(self):
        """Wheel slower than GPS = positive slip (abs value)."""
        ratio = wheel_slip_ratio(60.0, 20.0)
        assert ratio > 0.0

    def test_below_speed_gate(self):
        """Low GPS speed returns zero regardless."""
        assert wheel_slip_ratio(50.0, SPEED_GATE_MPS - 0.1) == 0.0

    def test_at_speed_gate(self):
        """At speed gate, slip should be computed."""
        ratio = wheel_slip_ratio(50.0, SPEED_GATE_MPS + 0.1)
        assert ratio > 0.0

    def test_always_non_negative(self):
        """Slip ratio is always >= 0."""
        assert wheel_slip_ratio(10.0, 20.0) >= 0.0
        assert wheel_slip_ratio(80.0, 20.0) >= 0.0


# ---------- axle_grip_pct ----------

class TestAxleGripPct:
    def test_perfect_grip(self):
        """All wheels match GPS = 100% grip."""
        f, r = axle_grip_pct(72.0, 72.0, 72.0, 72.0, 20.0)
        assert f == pytest.approx(1.0, abs=0.01)
        assert r == pytest.approx(1.0, abs=0.01)

    def test_front_slip(self):
        """Front wheels spinning, rear matching."""
        f, r = axle_grip_pct(90.0, 90.0, 72.0, 72.0, 20.0)
        assert f < 0.9  # front has lost grip
        assert r > 0.95  # rear is fine

    def test_rear_slip(self):
        """Rear wheels spinning, front matching."""
        f, r = axle_grip_pct(72.0, 72.0, 90.0, 90.0, 20.0)
        assert f > 0.95
        assert r < 0.9

    def test_uses_worst_wheel(self):
        """Grip uses max slip on each axle (worst wheel)."""
        # One front wheel spinning, other fine
        f, r = axle_grip_pct(72.0, 90.0, 72.0, 72.0, 20.0)
        assert f < 0.9  # worst front wheel dominates

    def test_clamped_to_zero(self):
        """Extreme slip doesn't go below 0.0."""
        f, r = axle_grip_pct(200.0, 200.0, 200.0, 200.0, 20.0)
        assert f >= 0.0
        assert r >= 0.0

    def test_clamped_to_one(self):
        """Normal grip doesn't exceed 1.0."""
        f, r = axle_grip_pct(72.0, 72.0, 72.0, 72.0, 20.0)
        assert f <= 1.0
        assert r <= 1.0


# ---------- GripAnalyzer ----------

class TestGripAnalyzer:
    def test_default_full_grip(self):
        ga = GripAnalyzer()
        assert ga.front_grip_pct() == 1.0
        assert ga.rear_grip_pct() == 1.0

    def test_feed_updates_grip(self):
        ga = GripAnalyzer()
        ga.feed(_snap(gps_mps=20.0, rl=90.0, rr=90.0))
        assert ga.rear_grip_pct() < 0.9

    def test_no_advisory_normal(self):
        ga = GripAnalyzer()
        ga.feed(_snap())
        assert ga.advisory() is None

    def test_advisory_at_10pct_slip(self):
        """Advisory fires when slip exceeds 10%."""
        ga = GripAnalyzer()
        # 10% slip: wheel at 79.2 vs 72 GPS km/h
        ga.feed(_snap(gps_mps=20.0, rl=79.5, rr=79.5))
        adv = ga.advisory()
        assert adv is not None
        text, sentiment = adv
        assert "slip" in text.lower()
        assert sentiment == "amber"

    def test_advisory_escalates_at_20pct(self):
        """Warning text at 20% slip."""
        ga = GripAnalyzer()
        # 20% slip: wheel at 86.4 vs 72 GPS km/h
        ga.feed(_snap(gps_mps=20.0, rl=87.0, rr=87.0))
        adv = ga.advisory()
        assert adv is not None
        text, _ = adv
        assert "ease" in text.lower()

    def test_advisory_identifies_front(self):
        ga = GripAnalyzer()
        ga.feed(_snap(gps_mps=20.0, fl=87.0, fr=87.0))
        adv = ga.advisory()
        assert adv is not None
        assert "front" in adv[0].lower()

    def test_advisory_identifies_rear(self):
        ga = GripAnalyzer()
        ga.feed(_snap(gps_mps=20.0, rl=87.0, rr=87.0))
        adv = ga.advisory()
        assert adv is not None
        assert "rear" in adv[0].lower()

    def test_below_speed_gate_no_advisory(self):
        """Low speed should never fire advisory."""
        ga = GripAnalyzer()
        ga.feed(_snap(gps_mps=2.0, fl=50.0, fr=50.0, rl=50.0, rr=50.0))
        assert ga.advisory() is None
