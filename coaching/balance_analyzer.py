"""KiSTI — Understeer/Oversteer Balance Analyzer

Bicycle model primary (ADR-3): compares expected yaw rate from steering
geometry to actual yaw rate from VDC/IMU. Rolling 5-sample average at 1Hz
reveals sustained balance shifts.

  expected_yaw = (speed * tan(steer_angle / ratio)) / wheelbase

Balance ratio:
  ratio = actual_yaw / expected_yaw
  < 0.97 = understeer, 0.97-1.03 = neutral, > 1.03 = oversteer
"""

from __future__ import annotations

import math
from collections import deque
from enum import Enum
from typing import Optional


# 2014 WRX STI geometry
WHEELBASE_M = 2.570
STEERING_RATIO = 15.0
SPEED_GATE_KPH = 30.0  # Below this, yaw comparison is meaningless


class Balance(Enum):
    """Vehicle balance classification."""
    UNDERSTEER = "understeer"
    NEUTRAL = "neutral"
    OVERSTEER = "oversteer"


def expected_yaw_rate(speed_mps: float, steer_angle_deg: float) -> float:
    """Bicycle model expected yaw rate (deg/s).

    Args:
        speed_mps: Vehicle speed in m/s.
        steer_angle_deg: Steering wheel angle in degrees (positive = left).

    Returns:
        Expected yaw rate in deg/s. Positive = turning left.
    """
    if abs(speed_mps) < 0.1:
        return 0.0
    wheel_angle_rad = math.radians(steer_angle_deg / STEERING_RATIO)
    yaw_rad_s = (speed_mps * math.tan(wheel_angle_rad)) / WHEELBASE_M
    return math.degrees(yaw_rad_s)


def balance_ratio(actual_yaw_dps: float, expected_yaw_dps: float) -> float:
    """Ratio of actual to expected yaw rate, clamped [0.5, 2.0].

    Returns:
        1.0 = neutral, < 1.0 = understeer, > 1.0 = oversteer.
    """
    if abs(expected_yaw_dps) < 0.5:
        return 1.0  # Straight line — no meaningful comparison
    ratio = actual_yaw_dps / expected_yaw_dps
    return max(0.5, min(2.0, ratio))


def classify_balance(ratio: float) -> Balance:
    """Classify balance ratio into understeer/neutral/oversteer."""
    if ratio < 0.97:
        return Balance.UNDERSTEER
    elif ratio > 1.03:
        return Balance.OVERSTEER
    return Balance.NEUTRAL


class BalanceAnalyzer:
    """Rolling balance analyzer — feed at 1Hz from coaching timer.

    Maintains a 5-sample rolling average to filter transients.
    Speed gate: ignores samples below 30 km/h.
    """

    def __init__(self, window: int = 5):
        self._window = window
        self._ratios: deque[float] = deque(maxlen=window)
        self._last_ratio: float = 1.0
        self._last_balance: Balance = Balance.NEUTRAL

    def feed(self, speed_kph: float, steer_angle_deg: float,
             actual_yaw_dps: float) -> None:
        """Feed a new sample. Below speed gate, ratio resets toward neutral."""
        if speed_kph < SPEED_GATE_KPH:
            self._ratios.append(1.0)
        else:
            speed_mps = speed_kph / 3.6
            exp = expected_yaw_rate(speed_mps, steer_angle_deg)
            r = balance_ratio(actual_yaw_dps, exp)
            self._ratios.append(r)

        self._last_ratio = sum(self._ratios) / len(self._ratios)
        self._last_balance = classify_balance(self._last_ratio)

    @property
    def ratio(self) -> float:
        """Current rolling average balance ratio."""
        return self._last_ratio

    @property
    def balance(self) -> Balance:
        """Current balance classification."""
        return self._last_balance

    def reset(self) -> None:
        """Clear history (e.g. session start)."""
        self._ratios.clear()
        self._last_ratio = 1.0
        self._last_balance = Balance.NEUTRAL
