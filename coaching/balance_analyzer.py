"""Understeer / oversteer detection via bicycle model.

Compares actual yaw rate (IMU gyro Z) against the expected yaw rate
computed from steering angle and vehicle speed using the single-track
(bicycle) model. The ratio reveals vehicle balance:

  ratio < 0.97  →  understeer (front washing out)
  ratio > 1.03  →  oversteer  (rear stepping out)
  0.97..1.03    →  neutral

Pure Python — no Qt, no numpy. 1Hz feed from coaching timer.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from model.vehicle_state import DiffState

# 2014 Subaru WRX STI (GR chassis)
WHEELBASE_M = 2.570
STEERING_RATIO = 15.0       # calibrate empirically on skidpad

# Speed gate: bicycle model unreliable below this
SPEED_GATE_MPS = 30.0 / 3.6  # 30 km/h

# Classification bands
NEUTRAL_LOW = 0.97
NEUTRAL_HIGH = 1.03


def expected_yaw_rate(speed_mps: float, steer_angle_deg: float) -> float:
    """Compute expected yaw rate from bicycle model.

    Returns yaw rate in deg/s. Positive = turning left (matching gyro Z convention).
    Returns 0.0 below speed gate.
    """
    if speed_mps < SPEED_GATE_MPS:
        return 0.0
    steer_rad = math.radians(steer_angle_deg / STEERING_RATIO)
    yaw_rad_per_s = speed_mps * math.tan(steer_rad) / WHEELBASE_M
    return math.degrees(yaw_rad_per_s)


def balance_ratio(actual_yaw: float, expected_yaw: float) -> float:
    """Ratio of actual to expected yaw rate.

    Returns 1.0 when expected yaw is near zero (straight line).
    Clamped to [0.5, 2.0] to avoid extreme values.
    """
    if abs(expected_yaw) < 3.0:
        return 1.0
    ratio = actual_yaw / expected_yaw
    return max(0.5, min(2.0, ratio))


def classify_balance(ratio: float) -> str:
    """Classify balance state from ratio."""
    if ratio < NEUTRAL_LOW:
        return "understeer"
    if ratio > NEUTRAL_HIGH:
        return "oversteer"
    return "neutral"


class BalanceAnalyzer:
    """Rolling-window balance analysis from 1Hz DiffState snapshots.

    Uses a 5-sample rolling average to detect sustained balance trends,
    not instantaneous events (the driver's feel is faster for those).
    """

    _WINDOW = 5

    def __init__(self) -> None:
        self._ratios: deque[float] = deque(maxlen=self._WINDOW)

    def feed(self, snap: DiffState) -> None:
        """Accept a 1Hz DiffState snapshot."""
        speed = snap.gps_speed_mps
        if speed < SPEED_GATE_MPS:
            self._ratios.append(1.0)
            return
        exp = expected_yaw_rate(speed, snap.steering_angle)
        ratio = balance_ratio(snap.imu_gyro_z, exp)
        self._ratios.append(ratio)

    def current_ratio(self) -> float:
        """Mean of rolling window. Default 1.0 (neutral)."""
        if not self._ratios:
            return 1.0
        return sum(self._ratios) / len(self._ratios)

    def current_classification(self) -> str:
        """Classify current rolling-average balance."""
        return classify_balance(self.current_ratio())

    def coaching_text(self) -> tuple[str, str]:
        """Return (text, sentiment) for coaching display.

        Only produces text for sustained (full window) non-neutral states.
        Returns ('', 'dim') when neutral or insufficient data.
        """
        if len(self._ratios) < self._WINDOW:
            return ("", "dim")
        ratio = self.current_ratio()
        cls = classify_balance(ratio)
        if cls == "understeer":
            return ("Car pushing wide — reduce entry speed or increase rear bias", "amber")
        if cls == "oversteer":
            return ("Rear stepping out — smooth throttle application", "amber")
        return ("", "dim")
