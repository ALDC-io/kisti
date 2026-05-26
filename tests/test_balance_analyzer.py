"""Tests for coaching/balance_analyzer.py — understeer/oversteer detection."""

import math

import pytest

from coaching.balance_analyzer import (
    BalanceAnalyzer,
    NEUTRAL_HIGH,
    NEUTRAL_LOW,
    SPEED_GATE_MPS,
    WHEELBASE_M,
    STEERING_RATIO,
    balance_ratio,
    classify_balance,
    expected_yaw_rate,
)
from model.vehicle_state import DiffState


def _snap(
    speed_mps: float = 20.0,
    steering: float = 0.0,
    gyro_z: float = 0.0,
) -> DiffState:
    """Build minimal DiffState for balance analysis."""
    return DiffState(
        gps_speed_mps=speed_mps,
        steering_angle=steering,
        imu_gyro_z=gyro_z,
    )


# ---------- expected_yaw_rate ----------

class TestExpectedYawRate:
    def test_straight_line_returns_zero(self):
        assert expected_yaw_rate(20.0, 0.0) == 0.0

    def test_below_speed_gate_returns_zero(self):
        assert expected_yaw_rate(SPEED_GATE_MPS - 0.1, 45.0) == 0.0

    def test_at_speed_gate_returns_nonzero(self):
        result = expected_yaw_rate(SPEED_GATE_MPS + 0.1, 45.0)
        assert result != 0.0

    def test_positive_steer_positive_yaw(self):
        """Positive steering angle should produce positive yaw rate."""
        result = expected_yaw_rate(20.0, 90.0)
        assert result > 0.0

    def test_negative_steer_negative_yaw(self):
        """Negative steering angle should produce negative yaw rate."""
        result = expected_yaw_rate(20.0, -90.0)
        assert result < 0.0

    def test_known_geometry(self):
        """Verify against hand-calculated value.

        At 20 m/s, 45 deg steering (3 deg at wheel = 45/15):
        yaw = (20 * tan(3°)) / 2.570 = (20 * 0.05241) / 2.570 = 0.4079 rad/s = 23.37 deg/s
        """
        result = expected_yaw_rate(20.0, 45.0)
        expected = math.degrees(20.0 * math.tan(math.radians(45.0 / STEERING_RATIO)) / WHEELBASE_M)
        assert abs(result - expected) < 0.01

    def test_higher_speed_higher_yaw(self):
        """Same steering angle at higher speed produces higher yaw rate."""
        slow = expected_yaw_rate(15.0, 45.0)
        fast = expected_yaw_rate(25.0, 45.0)
        assert fast > slow


# ---------- balance_ratio ----------

class TestBalanceRatio:
    def test_matching_yaw_returns_one(self):
        assert balance_ratio(10.0, 10.0) == pytest.approx(1.0)

    def test_near_zero_expected_returns_one(self):
        """Straight line (low expected yaw) should return neutral."""
        assert balance_ratio(0.5, 1.0) == 1.0

    def test_understeer_below_one(self):
        """Actual less than expected = car turns less than commanded."""
        ratio = balance_ratio(5.0, 10.0)
        assert ratio < 1.0

    def test_oversteer_above_one(self):
        """Actual greater than expected = car rotates more than commanded."""
        ratio = balance_ratio(15.0, 10.0)
        assert ratio > 1.0

    def test_clamped_low(self):
        """Extreme understeer clamped to 0.5."""
        assert balance_ratio(0.1, 10.0) == 0.5

    def test_clamped_high(self):
        """Extreme oversteer clamped to 2.0."""
        assert balance_ratio(30.0, 10.0) == 2.0


# ---------- classify_balance ----------

class TestClassifyBalance:
    def test_neutral_at_one(self):
        assert classify_balance(1.0) == "neutral"

    def test_neutral_at_low_bound(self):
        assert classify_balance(NEUTRAL_LOW) == "neutral"

    def test_neutral_at_high_bound(self):
        assert classify_balance(NEUTRAL_HIGH) == "neutral"

    def test_understeer(self):
        assert classify_balance(0.90) == "understeer"

    def test_oversteer(self):
        assert classify_balance(1.15) == "oversteer"


# ---------- BalanceAnalyzer ----------

class TestBalanceAnalyzer:
    def test_empty_returns_neutral(self):
        ba = BalanceAnalyzer()
        assert ba.current_ratio() == 1.0
        assert ba.current_classification() == "neutral"

    def test_straight_line_neutral(self):
        ba = BalanceAnalyzer()
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=0.0, gyro_z=0.0))
        assert ba.current_classification() == "neutral"

    def test_below_speed_gate_neutral(self):
        """Low speed should always report neutral regardless of yaw."""
        ba = BalanceAnalyzer()
        for _ in range(5):
            ba.feed(_snap(speed_mps=5.0, steering=90.0, gyro_z=50.0))
        assert ba.current_ratio() == pytest.approx(1.0)

    def test_sustained_understeer_detected(self):
        ba = BalanceAnalyzer()
        exp = expected_yaw_rate(20.0, 90.0)
        # Actual yaw is 70% of expected
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=90.0, gyro_z=exp * 0.7))
        assert ba.current_classification() == "understeer"

    def test_sustained_oversteer_detected(self):
        ba = BalanceAnalyzer()
        exp = expected_yaw_rate(20.0, 90.0)
        # Actual yaw is 130% of expected
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=90.0, gyro_z=exp * 1.3))
        assert ba.current_classification() == "oversteer"

    def test_rolling_window_smoothing(self):
        """Single mild outlier shouldn't flip classification."""
        ba = BalanceAnalyzer()
        exp = expected_yaw_rate(20.0, 45.0)
        # 4 neutral + 1 mild understeer → average stays neutral
        # ratio 0.9 → avg = (4*1.0 + 0.9)/5 = 0.98 → still neutral
        for _ in range(4):
            ba.feed(_snap(speed_mps=20.0, steering=45.0, gyro_z=exp))
        ba.feed(_snap(speed_mps=20.0, steering=45.0, gyro_z=exp * 0.9))
        assert ba.current_classification() == "neutral"

    def test_coaching_text_insufficient_data(self):
        ba = BalanceAnalyzer()
        ba.feed(_snap())
        text, sentiment = ba.coaching_text()
        assert text == ""
        assert sentiment == "dim"

    def test_coaching_text_neutral(self):
        ba = BalanceAnalyzer()
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=0.0, gyro_z=0.0))
        text, sentiment = ba.coaching_text()
        assert text == ""

    def test_coaching_text_understeer(self):
        ba = BalanceAnalyzer()
        exp = expected_yaw_rate(20.0, 90.0)
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=90.0, gyro_z=exp * 0.7))
        text, sentiment = ba.coaching_text()
        assert "pushing" in text.lower() or "wide" in text.lower()
        assert sentiment == "amber"

    def test_coaching_text_oversteer(self):
        ba = BalanceAnalyzer()
        exp = expected_yaw_rate(20.0, 90.0)
        for _ in range(5):
            ba.feed(_snap(speed_mps=20.0, steering=90.0, gyro_z=exp * 1.3))
        text, sentiment = ba.coaching_text()
        assert "rear" in text.lower() or "stepping" in text.lower()
        assert sentiment == "amber"
