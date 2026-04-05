"""Tests for Phase 6 coaching integration — analyzer wiring logic."""

import types
import pytest

from coaching.balance_analyzer import BalanceAnalyzer, Balance
from coaching.grip_analyzer import GripAnalyzer
from coaching.technique_analyzer import TechniqueAnalyzer


def _snap(**kwargs):
    """Create a minimal DiffState-like object."""
    defaults = dict(
        speed_kph=80.0, steering_angle=45.0, yaw_rate=10.0,
        lateral_g=0.3, imu_accel_x=-0.2,
        wheel_speed_fl=80.0, wheel_speed_fr=80.0,
        wheel_speed_rl=80.0, wheel_speed_rr=80.0,
        gps_speed_mps=22.22,
        brake=False, oil_temp_c=90.0, coolant_temp=88.0,
        battery_v=14.2, oil_psi=55.0,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestCoachingIntegration:
    """Test the coaching pipeline: snap → analyzers → screen updates."""

    def test_full_pipeline(self):
        """Feed a snap through all three analyzers and verify outputs."""
        ba = BalanceAnalyzer(window=1)
        ga = GripAnalyzer()
        ta = TechniqueAnalyzer()

        snap = _snap(speed_kph=80.0, steering_angle=45.0, yaw_rate=10.0,
                     brake=True, imu_accel_x=-0.8)

        ba.feed(snap.speed_kph, snap.steering_angle, snap.yaw_rate)
        ga.feed(snap)
        ta.feed(snap)

        assert ba.ratio != 0.0
        assert ba.balance in (Balance.UNDERSTEER, Balance.NEUTRAL, Balance.OVERSTEER)
        assert ga.front_grip_pct > 0
        assert ga.rear_grip_pct > 0
        assert ta.peak_brake_g > 0

    def test_analyzers_reset_cleanly(self):
        ba = BalanceAnalyzer()
        ga = GripAnalyzer()
        ta = TechniqueAnalyzer()

        snap = _snap(brake=True, imu_accel_x=-0.9)
        ba.feed(snap.speed_kph, snap.steering_angle, snap.yaw_rate)
        ga.feed(snap)
        ta.feed(snap)

        ba.reset()
        ga.reset()
        ta.reset()

        assert ba.ratio == 1.0
        assert ga.front_grip_pct == 100.0
        assert ta.peak_brake_g == 0.0

    def test_multiple_samples_stable(self):
        """10 identical samples should give stable results."""
        ba = BalanceAnalyzer()
        ga = GripAnalyzer()

        snap = _snap()
        for _ in range(10):
            ba.feed(snap.speed_kph, snap.steering_angle, snap.yaw_rate)
            ga.feed(snap)

        # Should be stable, not drifting
        r1 = ba.ratio
        ba.feed(snap.speed_kph, snap.steering_angle, snap.yaw_rate)
        r2 = ba.ratio
        assert abs(r2 - r1) < 0.05

    def test_brake_quality_summary_complete(self):
        ta = TechniqueAnalyzer()
        for _ in range(5):
            ta.feed(_snap(brake=True, imu_accel_x=-0.9))
        ta.feed(_snap(brake=False))
        for _ in range(3):
            ta.feed(_snap(brake=True, imu_accel_x=-0.85))

        summary = ta.brake_quality_summary()
        assert summary["peak_g"] == pytest.approx(0.9)
        assert 0.0 <= summary["consistency"] <= 1.0
        assert summary["zones"] >= 2
