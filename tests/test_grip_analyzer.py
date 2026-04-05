"""Tests for coaching.grip_analyzer — per-axle traction detection."""

import types
import pytest

from coaching.grip_analyzer import (
    SPEED_GATE_KPH, ADVISORY_PCT, WARNING_PCT,
    wheel_slip_ratio, axle_grip_pct, GripAnalyzer,
)


def _snap(fl=60, fr=60, rl=60, rr=60, gps_mps=16.67):
    """Helper: create a minimal snap-like object."""
    return types.SimpleNamespace(
        wheel_speed_fl=fl, wheel_speed_fr=fr,
        wheel_speed_rl=rl, wheel_speed_rr=rr,
        gps_speed_mps=gps_mps,
    )


# --- wheel_slip_ratio ---

class TestWheelSlipRatio:
    def test_no_slip(self):
        """Wheel speed matches GPS → zero slip."""
        assert wheel_slip_ratio(60.0, 16.67) == pytest.approx(0.0, abs=0.01)

    def test_below_speed_gate(self):
        assert wheel_slip_ratio(5.0, 1.0) == 0.0

    def test_locked_wheel(self):
        """Wheel stopped, car moving → high slip."""
        slip = wheel_slip_ratio(0.0, 16.67)
        assert slip > 0.9

    def test_spinning_wheel(self):
        """Wheel faster than ground → slip."""
        slip = wheel_slip_ratio(80.0, 16.67)
        assert slip > 0.1

    def test_clamp_at_one(self):
        """Extreme mismatch should clamp to 1.0."""
        assert wheel_slip_ratio(0.0, 30.0) == 1.0

    def test_moderate_slip(self):
        """10% faster wheel speed → ~10% slip."""
        gps_kph = 16.67 * 3.6  # ~60 km/h
        slip = wheel_slip_ratio(gps_kph * 1.1, 16.67)
        assert 0.05 < slip < 0.15


# --- axle_grip_pct ---

class TestAxleGripPct:
    def test_full_grip(self):
        """All wheels matching → 100% grip."""
        f, r = axle_grip_pct(60.0, 60.0, 60.0, 60.0, 16.67)
        assert f > 99.0
        assert r > 99.0

    def test_front_slip(self):
        """Front left locked → low front grip."""
        f, r = axle_grip_pct(0.0, 60.0, 60.0, 60.0, 16.67)
        assert f < 10.0
        assert r > 90.0

    def test_rear_slip(self):
        """Rear right spinning → low rear grip."""
        f, r = axle_grip_pct(60.0, 60.0, 60.0, 120.0, 16.67)
        assert r < f

    def test_worst_wheel_per_axle(self):
        """Uses worst wheel — one bad wheel drags the axle down."""
        f1, _ = axle_grip_pct(50.0, 60.0, 60.0, 60.0, 16.67)
        f2, _ = axle_grip_pct(60.0, 60.0, 60.0, 60.0, 16.67)
        assert f1 < f2

    def test_below_speed_gate(self):
        """Below gate → 100% grip (can't measure)."""
        f, r = axle_grip_pct(0.0, 0.0, 0.0, 0.0, 1.0)
        assert f == 100.0
        assert r == 100.0


# --- GripAnalyzer ---

class TestGripAnalyzer:
    def test_initial_state(self):
        ga = GripAnalyzer()
        assert ga.front_grip_pct == 100.0
        assert ga.rear_grip_pct == 100.0

    def test_feed_full_grip(self):
        ga = GripAnalyzer()
        ga.feed(_snap())
        assert ga.front_grip_pct > 99.0
        assert ga.rear_grip_pct > 99.0

    def test_feed_front_loss(self):
        ga = GripAnalyzer()
        ga.feed(_snap(fl=0.0))
        assert ga.front_grip_pct < 10.0

    def test_advisory_none_when_good(self):
        ga = GripAnalyzer()
        ga.feed(_snap())
        assert ga.advisory() is None

    def test_advisory_on_slip(self):
        ga = GripAnalyzer()
        ga.feed(_snap(rl=0.0))
        adv = ga.advisory()
        assert adv is not None
        assert "rear" in adv

    def test_reset(self):
        ga = GripAnalyzer()
        ga.feed(_snap(fl=0.0))
        ga.reset()
        assert ga.front_grip_pct == 100.0

    def test_both_axles_slipping(self):
        ga = GripAnalyzer()
        ga.feed(_snap(fl=0.0, rl=0.0))
        adv = ga.advisory()
        assert "front" in adv
        assert "rear" in adv

    def test_constants(self):
        assert SPEED_GATE_KPH == 10.0
        assert ADVISORY_PCT == 10.0
        assert WARNING_PCT == 20.0
