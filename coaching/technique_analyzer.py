"""KiSTI — Driving Technique Analyzer

Per-session technique metrics:
  - Brake quality: peak longitudinal G, consistency
  - Trail braking: G-based detection (longitudinal_g < -0.3 AND lateral_g > 0.3)
  - Smoothness: steering rate variance (future)

Fed at 1Hz from coaching timer. Accumulates per-session stats.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _Sample:
    """Single 1Hz coaching sample."""
    lateral_g: float = 0.0
    longitudinal_g: float = 0.0
    steering_angle: float = 0.0
    speed_kph: float = 0.0
    brake: bool = False


class TechniqueAnalyzer:
    """Accumulates driving technique metrics over a session."""

    def __init__(self, window: int = 30):
        self._window = window
        self._samples: deque[_Sample] = deque(maxlen=window)
        self._peak_brake_g: float = 0.0
        self._brake_g_values: list[float] = []
        self._trail_brake_count: int = 0
        self._brake_zone_count: int = 0
        self._was_braking: bool = False

    def feed(self, snap) -> None:
        """Feed a DiffState snapshot at 1Hz."""
        s = _Sample(
            lateral_g=getattr(snap, 'lateral_g', 0.0),
            longitudinal_g=getattr(snap, 'imu_accel_x', 0.0),
            steering_angle=getattr(snap, 'steering_angle', 0.0),
            speed_kph=getattr(snap, 'speed_kph', 0.0),
            brake=getattr(snap, 'brake', False),
        )
        self._samples.append(s)

        # Track brake zones
        if s.brake and not self._was_braking:
            self._brake_zone_count += 1
        self._was_braking = s.brake

        # Brake G quality (only when braking and IMU available)
        if s.brake and abs(s.longitudinal_g) > 0.1:
            g = abs(s.longitudinal_g)
            self._brake_g_values.append(g)
            if g > self._peak_brake_g:
                self._peak_brake_g = g

        # Trail brake detection: decelerating AND turning simultaneously
        if s.longitudinal_g < -0.3 and abs(s.lateral_g) > 0.3:
            self._trail_brake_count += 1

    @property
    def peak_brake_g(self) -> float:
        return self._peak_brake_g

    @property
    def brake_consistency(self) -> float:
        """Brake G consistency (0-1, 1 = perfectly consistent)."""
        if len(self._brake_g_values) < 2:
            return 1.0
        mean = sum(self._brake_g_values) / len(self._brake_g_values)
        if mean < 0.1:
            return 1.0
        variance = sum((v - mean) ** 2 for v in self._brake_g_values) / len(self._brake_g_values)
        std = math.sqrt(variance)
        # Normalize: 0 std = 1.0 consistency, high std = low consistency
        return max(0.0, min(1.0, 1.0 - (std / mean)))

    @property
    def trail_brake_pct(self) -> float:
        """Percentage of brake zones with trail braking detected."""
        if self._brake_zone_count == 0:
            return 0.0
        return min(100.0, (self._trail_brake_count / max(1, self._brake_zone_count)) * 100.0)

    def brake_quality_summary(self) -> dict:
        """Summary dict for UI display."""
        return {
            "peak_g": self._peak_brake_g,
            "consistency": self.brake_consistency,
            "trail_pct": self.trail_brake_pct,
            "zones": self._brake_zone_count,
        }

    def reset(self) -> None:
        """Clear session data."""
        self._samples.clear()
        self._peak_brake_g = 0.0
        self._brake_g_values.clear()
        self._trail_brake_count = 0
        self._brake_zone_count = 0
        self._was_braking = False
