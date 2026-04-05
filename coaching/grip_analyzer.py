"""KiSTI — Per-Axle Grip Analyzer

Traction loss detection via wheel slip ratio against GPS ground truth.
Advisory at 10% slip, warning at 20%.

  wheel_slip = |wheel_speed - gps_speed| / gps_speed

Uses worst wheel per axle (conservative — catches diagonal weight transfer).
"""

from __future__ import annotations

from typing import Optional

SPEED_GATE_KPH = 10.0  # Below this, slip ratio is noise
ADVISORY_PCT = 10.0
WARNING_PCT = 20.0


def wheel_slip_ratio(wheel_speed_kph: float, gps_speed_mps: float) -> float:
    """Slip ratio for a single wheel (0.0 = no slip, 1.0 = locked/spinning).

    Args:
        wheel_speed_kph: Individual wheel speed in km/h from ABS sensor.
        gps_speed_mps: GPS ground speed in m/s.

    Returns:
        Slip ratio [0.0, 1.0]. Returns 0.0 below speed gate.
    """
    gps_kph = gps_speed_mps * 3.6
    if gps_kph < SPEED_GATE_KPH:
        return 0.0
    return min(1.0, abs(wheel_speed_kph - gps_kph) / gps_kph)


def axle_grip_pct(fl: float, fr: float, rl: float, rr: float,
                  gps_speed_mps: float) -> tuple[float, float]:
    """Per-axle grip percentage (100% = no slip, 0% = full slip).

    Uses worst (highest slip) wheel per axle.

    Returns:
        (front_grip_pct, rear_grip_pct) each in [0, 100].
    """
    front_slip = max(
        wheel_slip_ratio(fl, gps_speed_mps),
        wheel_slip_ratio(fr, gps_speed_mps),
    )
    rear_slip = max(
        wheel_slip_ratio(rl, gps_speed_mps),
        wheel_slip_ratio(rr, gps_speed_mps),
    )
    return (
        max(0.0, min(100.0, (1.0 - front_slip) * 100.0)),
        max(0.0, min(100.0, (1.0 - rear_slip) * 100.0)),
    )


class GripAnalyzer:
    """Stateful grip analyzer — feed at 1Hz from coaching timer."""

    def __init__(self):
        self._front_grip: float = 100.0
        self._rear_grip: float = 100.0

    def feed(self, snap) -> None:
        """Feed a DiffState snapshot.

        Expects: snap.wheel_speed_fl/fr/rl/rr (km/h), snap.gps_speed_mps (m/s).
        """
        self._front_grip, self._rear_grip = axle_grip_pct(
            snap.wheel_speed_fl, snap.wheel_speed_fr,
            snap.wheel_speed_rl, snap.wheel_speed_rr,
            snap.gps_speed_mps,
        )

    @property
    def front_grip_pct(self) -> float:
        return self._front_grip

    @property
    def rear_grip_pct(self) -> float:
        return self._rear_grip

    def advisory(self) -> Optional[str]:
        """Return advisory string if grip is degraded, else None."""
        issues = []
        if self._front_grip < (100.0 - WARNING_PCT):
            issues.append(f"front {self._front_grip:.0f}%")
        elif self._front_grip < (100.0 - ADVISORY_PCT):
            issues.append(f"front {self._front_grip:.0f}%")
        if self._rear_grip < (100.0 - WARNING_PCT):
            issues.append(f"rear {self._rear_grip:.0f}%")
        elif self._rear_grip < (100.0 - ADVISORY_PCT):
            issues.append(f"rear {self._rear_grip:.0f}%")
        if issues:
            return "Grip: " + ", ".join(issues)
        return None

    def reset(self) -> None:
        self._front_grip = 100.0
        self._rear_grip = 100.0
