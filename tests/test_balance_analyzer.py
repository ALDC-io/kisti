"""Tests for coaching.balance_analyzer — understeer/oversteer detection."""

import math
import pytest

from coaching.balance_analyzer import (
    WHEELBASE_M, STEERING_RATIO, SPEED_GATE_KPH,
    Balance, BalanceAnalyzer,
    expected_yaw_rate, balance_ratio, classify_balance,
)


# --- expected_yaw_rate ---

class TestExpectedYawRate:
    def test_zero_speed_returns_zero(self):
        assert expected_yaw_rate(0.0, 45.0) == 0.0

    def test_zero_steer_returns_zero(self):
        assert abs(expected_yaw_rate(20.0, 0.0)) < 0.01

    def test_positive_steer_positive_yaw(self):
        """Left steer → positive yaw rate."""
        yaw = expected_yaw_rate(15.0, 90.0)
        assert yaw > 0

    def test_negative_steer_negative_yaw(self):
        """Right steer → negative yaw rate."""
        yaw = expected_yaw_rate(15.0, -90.0)
        assert yaw < 0

    def test_higher_speed_higher_yaw(self):
        """Same steer angle, more speed → higher yaw rate."""
        slow = abs(expected_yaw_rate(10.0, 45.0))
        fast = abs(expected_yaw_rate(20.0, 45.0))
        assert fast > slow

    def test_typical_highway_turn(self):
        """30 m/s (~108 km/h), 45° steering wheel → reasonable yaw."""
        yaw = expected_yaw_rate(30.0, 45.0)
        assert 10.0 < abs(yaw) < 50.0

    def test_very_slow_not_zero(self):
        """Just above 0.1 m/s threshold."""
        yaw = expected_yaw_rate(0.2, 90.0)
        assert abs(yaw) > 0

    def test_symmetry(self):
        """Left and right should be symmetric."""
        left = expected_yaw_rate(15.0, 45.0)
        right = expected_yaw_rate(15.0, -45.0)
        assert abs(left + right) < 0.001


# --- balance_ratio ---

class TestBalanceRatio:
    def test_matching_yaw_returns_one(self):
        assert abs(balance_ratio(10.0, 10.0) - 1.0) < 0.01

    def test_understeer_less_than_one(self):
        """Actual yaw < expected → understeer → ratio < 1."""
        r = balance_ratio(5.0, 10.0)
        assert r < 1.0

    def test_oversteer_greater_than_one(self):
        """Actual yaw > expected → oversteer → ratio > 1."""
        r = balance_ratio(15.0, 10.0)
        assert r > 1.0

    def test_straight_line_returns_one(self):
        """Expected yaw near zero → return 1.0 (no comparison)."""
        assert balance_ratio(0.1, 0.1) == 1.0

    def test_clamp_low(self):
        assert balance_ratio(1.0, 10.0) == 0.5  # Would be 0.1, clamped to 0.5

    def test_clamp_high(self):
        assert balance_ratio(20.0, 10.0) == 2.0


# --- classify_balance ---

class TestClassifyBalance:
    def test_neutral(self):
        assert classify_balance(1.0) == Balance.NEUTRAL

    def test_neutral_border_low(self):
        assert classify_balance(0.97) == Balance.NEUTRAL

    def test_neutral_border_high(self):
        assert classify_balance(1.03) == Balance.NEUTRAL

    def test_understeer(self):
        assert classify_balance(0.90) == Balance.UNDERSTEER

    def test_oversteer(self):
        assert classify_balance(1.10) == Balance.OVERSTEER

    def test_extreme_understeer(self):
        assert classify_balance(0.5) == Balance.UNDERSTEER

    def test_extreme_oversteer(self):
        assert classify_balance(2.0) == Balance.OVERSTEER


# --- BalanceAnalyzer ---

class TestBalanceAnalyzer:
    def test_initial_state(self):
        ba = BalanceAnalyzer()
        assert ba.ratio == 1.0
        assert ba.balance == Balance.NEUTRAL

    def test_below_speed_gate_stays_neutral(self):
        ba = BalanceAnalyzer()
        ba.feed(20.0, 90.0, 5.0)  # 20 km/h < gate
        assert ba.balance == Balance.NEUTRAL

    def test_understeer_detection(self):
        ba = BalanceAnalyzer(window=1)
        speed = 80.0
        steer = 90.0
        speed_mps = speed / 3.6
        exp = expected_yaw_rate(speed_mps, steer)
        actual = exp * 0.7  # 70% of expected = understeer
        ba.feed(speed, steer, actual)
        assert ba.balance == Balance.UNDERSTEER

    def test_oversteer_detection(self):
        ba = BalanceAnalyzer(window=1)
        speed = 80.0
        steer = 90.0
        speed_mps = speed / 3.6
        exp = expected_yaw_rate(speed_mps, steer)
        actual = exp * 1.3  # 130% of expected = oversteer
        ba.feed(speed, steer, actual)
        assert ba.balance == Balance.OVERSTEER

    def test_rolling_average_smooths(self):
        """Window=5: one bad sample shouldn't flip classification."""
        ba = BalanceAnalyzer(window=5)
        speed = 80.0
        steer = 45.0
        speed_mps = speed / 3.6
        exp = expected_yaw_rate(speed_mps, steer)
        # 4 neutral samples
        for _ in range(4):
            ba.feed(speed, steer, exp)
        assert ba.balance == Balance.NEUTRAL
        # 1 oversteer sample
        ba.feed(speed, steer, exp * 1.5)
        # Rolling average should still be near neutral
        assert ba.ratio < 1.2

    def test_reset(self):
        ba = BalanceAnalyzer(window=1)
        ba.feed(80.0, 90.0, 0.0)
        ba.reset()
        assert ba.ratio == 1.0
        assert ba.balance == Balance.NEUTRAL

    def test_constants(self):
        assert WHEELBASE_M == 2.570
        assert STEERING_RATIO == 15.0
        assert SPEED_GATE_KPH == 30.0
