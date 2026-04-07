"""Driving technique analyzer — 1Hz sample rate, 30s rolling window.

Pure Python (no Qt). Receives DiffState snapshots, computes technique
metrics, returns a single coaching string + sentiment color.

Metrics:
  - Brake consistency: std dev of brake pressure during braking events
  - Steering smoothness: std dev of steering rate (jerk proxy)
  - Trail braking quality: % of braking samples with simultaneous steering
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

from model.vehicle_state import DiffState


@dataclass
class _Sample:
    speed_kph: float
    brake_pressure: float
    steering_angle: float
    steering_rate: float
    lateral_g: float
    throttle_pct: float
    longitudinal_g: float = 0.0  # imu_accel_x (negative = braking)
    brake_front: float = 0.0     # front axle pressure (bar)
    brake_rear: float = 0.0      # rear axle pressure (bar)
    brake_bias_pct: float = 0.0  # front % (0-100)


# Thresholds
_BRAKE_ACTIVE = 5.0       # bar — minimum to count as braking
_STEER_ACTIVE = 20.0      # deg — minimum to count as cornering
_TRAIL_STEER = 30.0       # deg — steering threshold for trail braking
_MIN_SAMPLES = 5          # need at least this many for analysis
_WINDOW = 10              # 10s at 1Hz — real-time feedback, not forensics


class TechniqueAnalyzer:
    """Analyze driving technique from a rolling window of telemetry."""

    def __init__(self) -> None:
        self._samples: deque[_Sample] = deque(maxlen=_WINDOW)
        self._prev_steering: float = 0.0

    def feed(self, snap: DiffState) -> None:
        """Accept a 1Hz DiffState snapshot."""
        steering_rate = snap.steering_angle - self._prev_steering
        self._samples.append(_Sample(
            speed_kph=snap.speed_kph,
            brake_pressure=snap.brake_pressure,
            steering_angle=snap.steering_angle,
            steering_rate=steering_rate,
            lateral_g=snap.imu_accel_y,
            throttle_pct=snap.throttle_pct,
            longitudinal_g=snap.imu_accel_x,
            brake_front=snap.brake_pressure_front,
            brake_rear=snap.brake_pressure_rear,
            brake_bias_pct=snap.brake_bias_pct,
        ))
        self._prev_steering = snap.steering_angle

    def analyze(self) -> tuple[str, str]:
        """Return (coaching_text, sentiment) from the rolling window.

        sentiment: 'green' | 'amber' | 'dim'
        Returns ('', 'dim') if insufficient data.
        """
        if len(self._samples) < _MIN_SAMPLES:
            return ("", "dim")

        issues: list[tuple[int, str, str]] = []  # (priority, text, sentiment)

        # --- Brake consistency ---
        braking = [s for s in self._samples if s.brake_pressure > _BRAKE_ACTIVE]
        if len(braking) >= 3:
            pressures = [s.brake_pressure for s in braking]
            std = _std_dev(pressures)
            if std > 12:
                issues.append((0, "Inconsistent brake pressure", "amber"))
            elif std > 8:
                issues.append((1, "Brake pressure varies — try smoother inputs", "amber"))
            elif std <= 4:
                issues.append((10, "Smooth braking", "green"))

        # --- Steering smoothness ---
        cornering = [s for s in self._samples if abs(s.steering_angle) > _STEER_ACTIVE]
        if len(cornering) >= 3:
            rates = [s.steering_rate for s in cornering]
            std = _std_dev(rates)
            if std > 30:
                issues.append((0, "Abrupt steering corrections", "amber"))
            elif std > 20:
                issues.append((2, "Tighten steering inputs", "amber"))
            elif std <= 12:
                issues.append((10, "Smooth steering", "green"))

        # --- Trail braking (enhanced: steering angle OR G-based) ---
        if len(braking) >= 5:
            trail_count = sum(
                1 for s in braking
                if abs(s.steering_angle) > _TRAIL_STEER
                or (s.longitudinal_g < -0.3 and abs(s.lateral_g) > 0.3)
            )
            trail_ratio = trail_count / len(braking)
            if trail_ratio > 0.3:
                issues.append((10, "Good trail braking", "green"))
            elif trail_ratio < 0.1 and len(cornering) >= 3:
                issues.append((3, "Try trail braking at corner entry", "dim"))

        # --- Brake G quality (longitudinal G during braking) ---
        # Only analyze if IMU is reporting actual braking G (> 0.1g)
        if len(braking) >= 3:
            brake_gs = [abs(s.longitudinal_g) for s in braking]
            peak_g = max(brake_gs)
            if peak_g > 0.1:
                g_std = _std_dev(brake_gs)
                if peak_g > 0.8 and g_std < 0.15:
                    issues.append((10, "Strong consistent braking", "green"))
                elif peak_g < 0.5 and any(s.speed_kph > 60 for s in braking):
                    issues.append((2, "Brake harder — more grip available", "amber"))

        # --- Brake bias consistency (front/rear sensors) ---
        bias_samples = [s for s in braking if s.brake_bias_pct > 0]
        if len(bias_samples) >= 3:
            biases = [s.brake_bias_pct for s in bias_samples]
            bias_std = _std_dev(biases)
            avg_bias = sum(biases) / len(biases)
            if bias_std > 8:
                issues.append((1, "Erratic brake bias — check pedal feel", "amber"))
            elif avg_bias < 55:
                issues.append((1, "Rear-heavy bias — lock-up risk", "amber"))
            elif bias_std <= 3 and 60 <= avg_bias <= 70:
                issues.append((10, f"Brake bias steady F{avg_bias:.0f}/R{100-avg_bias:.0f}", "green"))

        # --- Brake fade detection (pressure up, decel G down) ---
        if len(braking) >= 5:
            has_front_rear = any(s.brake_front > 0 for s in braking)
            if has_front_rear:
                recent = list(braking)[-5:]
                pressures_trend = [s.brake_front + s.brake_rear for s in recent]
                gs_trend = [abs(s.longitudinal_g) for s in recent]
                if (pressures_trend[-1] > pressures_trend[0] * 1.2
                        and gs_trend[-1] < gs_trend[0] * 0.7
                        and gs_trend[0] > 0.3):
                    issues.append((0, "Possible brake fade — pressure up, decel down", "amber"))

        if not issues:
            return ("", "dim")

        # Return highest priority (lowest number = most urgent)
        issues.sort(key=lambda x: x[0])
        _, text, sentiment = issues[0]
        return (text, sentiment)

    def brake_quality(self) -> str:
        """Return overall brake quality as 'green'/'yellow'/'red' for sector dots.

        Based on rolling window peak G and consistency — same quality applied
        to all sectors (per-sector tracking requires AiM sector boundary events).
        """
        braking = [s for s in self._samples if s.brake_pressure > _BRAKE_ACTIVE]
        if len(braking) < 3:
            return "yellow"  # insufficient data — neutral

        brake_gs = [abs(s.longitudinal_g) for s in braking]
        peak_g = max(brake_gs)
        if peak_g <= 0.1:
            return "yellow"  # IMU not reporting — neutral

        g_std = _std_dev(brake_gs)
        pressures = [s.brake_pressure for s in braking]
        p_std = _std_dev(pressures)

        # Bias consistency (if dual sensors available)
        bias_samples = [s for s in braking if s.brake_bias_pct > 0]
        bias_penalty = False
        if len(bias_samples) >= 3:
            bias_std = _std_dev([s.brake_bias_pct for s in bias_samples])
            avg_bias = sum(s.brake_bias_pct for s in bias_samples) / len(bias_samples)
            if bias_std > 8 or avg_bias < 55:
                bias_penalty = True

        if peak_g > 0.8 and g_std < 0.15 and p_std < 8 and not bias_penalty:
            return "green"
        if peak_g < 0.5 and any(s.speed_kph > 60 for s in braking):
            return "red"
        if p_std > 12 or bias_penalty:
            return "red"
        return "yellow"


def _std_dev(values: list[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)
