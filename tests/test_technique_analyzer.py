"""Tests for coaching.technique_analyzer — brake quality + trail braking."""

import types
import pytest

from coaching.technique_analyzer import TechniqueAnalyzer


def _snap(lateral_g=0.0, imu_accel_x=0.0, steering_angle=0.0,
          speed_kph=80.0, brake=False):
    return types.SimpleNamespace(
        lateral_g=lateral_g,
        imu_accel_x=imu_accel_x,
        steering_angle=steering_angle,
        speed_kph=speed_kph,
        brake=brake,
    )


class TestTechniqueAnalyzer:
    def test_initial_state(self):
        ta = TechniqueAnalyzer()
        assert ta.peak_brake_g == 0.0
        assert ta.brake_consistency == 1.0
        assert ta.trail_brake_pct == 0.0

    def test_brake_g_tracking(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.8, brake=True))
        assert ta.peak_brake_g == pytest.approx(0.8)

    def test_peak_brake_g_updates(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.5, brake=True))
        ta.feed(_snap(imu_accel_x=-1.0, brake=True))
        assert ta.peak_brake_g == pytest.approx(1.0)

    def test_brake_consistency_perfect(self):
        ta = TechniqueAnalyzer()
        for _ in range(5):
            ta.feed(_snap(imu_accel_x=-0.8, brake=True))
        assert ta.brake_consistency == pytest.approx(1.0)

    def test_brake_consistency_varies(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.3, brake=True))
        ta.feed(_snap(imu_accel_x=-1.0, brake=True))
        ta.feed(_snap(imu_accel_x=-0.3, brake=True))
        ta.feed(_snap(imu_accel_x=-1.0, brake=True))
        assert ta.brake_consistency < 0.8

    def test_trail_brake_detection(self):
        ta = TechniqueAnalyzer()
        # Enter brake zone
        ta.feed(_snap(imu_accel_x=-0.5, brake=True))
        # Trail braking: decelerating AND turning
        ta.feed(_snap(imu_accel_x=-0.4, lateral_g=0.5, brake=True))
        assert ta.trail_brake_pct > 0

    def test_no_trail_brake_straight(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.8, brake=True))
        ta.feed(_snap(brake=False))
        ta.feed(_snap(imu_accel_x=-0.8, brake=True))
        # Strong braking but no lateral G → no trail brake
        assert ta._trail_brake_count == 0

    def test_brake_zone_counting(self):
        ta = TechniqueAnalyzer()
        # Zone 1
        ta.feed(_snap(brake=True))
        ta.feed(_snap(brake=False))
        # Zone 2
        ta.feed(_snap(brake=True))
        ta.feed(_snap(brake=False))
        assert ta._brake_zone_count == 2

    def test_brake_quality_summary(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.9, brake=True))
        summary = ta.brake_quality_summary()
        assert "peak_g" in summary
        assert "consistency" in summary
        assert "trail_pct" in summary
        assert "zones" in summary

    def test_reset(self):
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.9, brake=True))
        ta.reset()
        assert ta.peak_brake_g == 0.0
        assert ta._brake_zone_count == 0

    def test_low_g_ignored(self):
        """Brake G below 0.1 threshold (no IMU) should be ignored."""
        ta = TechniqueAnalyzer()
        ta.feed(_snap(imu_accel_x=-0.05, brake=True))
        assert ta.peak_brake_g == 0.0
        assert len(ta._brake_g_values) == 0
