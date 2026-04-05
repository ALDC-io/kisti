"""Per-axle traction / grip analysis from wheel speeds vs GPS ground truth.

Computes slip ratio for each wheel by comparing ABS wheel speed sensors
against GPS speed (ground truth from GPS09 Pro). Returns per-axle grip
percentages that can be displayed alongside the DCCD lock indicator.

  slip_ratio = |wheel_speed - gps_speed| / gps_speed
  grip_pct   = 1.0 - max(left_slip, right_slip)

Pure Python — no Qt, no numpy. 1Hz feed from coaching timer.
"""

from __future__ import annotations

from typing import Optional

from model.vehicle_state import DiffState

# Speed gate: slip ratio unreliable below this (divide-by-near-zero)
SPEED_GATE_MPS = 10.0 / 3.6  # 10 km/h

# Advisory thresholds (slip ratio)
SLIP_ADVISORY = 0.10   # 10% slip
SLIP_WARNING = 0.20    # 20% slip


def wheel_slip_ratio(wheel_speed_kph: float, gps_speed_mps: float) -> float:
    """Compute slip ratio for a single wheel.

    Returns 0.0 below speed gate. Always non-negative.
    """
    if gps_speed_mps < SPEED_GATE_MPS:
        return 0.0
    gps_kph = gps_speed_mps * 3.6
    if gps_kph < 1.0:
        return 0.0
    return abs(wheel_speed_kph - gps_kph) / gps_kph


def axle_grip_pct(
    fl: float, fr: float, rl: float, rr: float, gps_speed_mps: float,
) -> tuple[float, float]:
    """Compute front and rear grip percentages.

    Returns (front_pct, rear_pct) where 1.0 = full grip, 0.0 = no grip.
    Uses the worst wheel on each axle (max slip).
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
        max(0.0, min(1.0, 1.0 - front_slip)),
        max(0.0, min(1.0, 1.0 - rear_slip)),
    )


class GripAnalyzer:
    """Per-axle grip analysis from 1Hz DiffState snapshots."""

    def __init__(self) -> None:
        self._front: float = 1.0
        self._rear: float = 1.0

    def feed(self, snap: DiffState) -> None:
        """Accept a 1Hz DiffState snapshot."""
        self._front, self._rear = axle_grip_pct(
            snap.wheel_speed_fl,
            snap.wheel_speed_fr,
            snap.wheel_speed_rl,
            snap.wheel_speed_rr,
            snap.gps_speed_mps,
        )

    def front_grip_pct(self) -> float:
        """Front axle grip (0.0-1.0)."""
        return self._front

    def rear_grip_pct(self) -> float:
        """Rear axle grip (0.0-1.0)."""
        return self._rear

    def advisory(self) -> Optional[tuple[str, str]]:
        """Return (text, sentiment) if any axle has significant slip.

        Returns None if grip is normal.
        """
        front_slip = 1.0 - self._front
        rear_slip = 1.0 - self._rear

        worst_slip = max(front_slip, rear_slip)
        if worst_slip < SLIP_ADVISORY:
            return None

        axle = "Front" if front_slip >= rear_slip else "Rear"
        pct = int(worst_slip * 100)

        if worst_slip >= SLIP_WARNING:
            return (f"{axle} slip {pct}% — ease inputs", "amber")
        return (f"{axle} slip {pct}% — monitor traction", "amber")
