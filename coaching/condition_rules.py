"""Condition-to-action coaching rules for Intelligent mode.

Deterministic rule engine: evaluates DiffState telemetry + ambient
conditions, returns a coaching insight filtered by CoachingLevel.

CoachingLevel:
  0 = MINIMAL — safety alerts only
  1 = MODERATE — + observations
  2 = FULL — + proactive tips
"""

from __future__ import annotations

from typing import Optional

from model.vehicle_state import DiffState, SurfaceState


def evaluate(
    snap: DiffState,
    coaching_level: int,
) -> Optional[tuple[str, str]]:
    """Return (text, sentiment) for the highest-priority matching rule.

    Returns None if no rule matches at the given coaching level.
    Rules with level <= coaching_level are included.
    """
    # Each rule: (level, priority, text, sentiment)
    # Lower priority number = more urgent
    candidates: list[tuple[int, int, str, str]] = []

    # --- Safety / always-on (level 0) ---
    if snap.flir_available and not snap.is_flir_stale():
        road_temp = snap.brake_temp_fl
        if road_temp < 3:
            candidates.append((
                0, 0,
                "Ice risk — reduce corner speed, grip down ~25%",
                "amber",
            ))
        elif road_temp < 5:
            candidates.append((
                2, 4,
                f"Road {road_temp:.0f}\u00b0C — grip down ~15%",
                "amber",
            ))
        elif road_temp < 10:
            candidates.append((
                2, 8,
                f"Road {road_temp:.0f}\u00b0C — surface cool, grip building",
                "dim",
            ))

    if snap.surface_state == SurfaceState.LOW_GRIP:
        candidates.append((
            0, 1,
            "Low grip — extend braking zones, smooth throttle",
            "amber",
        ))

    # --- Moderate (level 1) ---
    if snap.surface_state == SurfaceState.WET:
        candidates.append((
            1, 2,
            "Wet surface — brake earlier, gentler inputs",
            "amber",
        ))

    if snap.surface_state == SurfaceState.COLD:
        candidates.append((
            1, 5,
            "Cold surface — tires need warm-up laps",
            "amber",
        ))

    # Oil temp rising (simple heuristic: high oil temp)
    if snap.oil_temp_c > 130:
        candidates.append((
            1, 3,
            f"Oil {snap.oil_temp_c:.0f}\u00b0C — running hot, ease off",
            "amber",
        ))
    elif snap.oil_temp_c > 115:
        candidates.append((
            2, 7,
            f"Oil {snap.oil_temp_c:.0f}\u00b0C — warming up, monitor",
            "dim",
        ))

    # --- Full (level 2) ---
    if snap.ambient_available:
        if snap.ambient_temp_c < 5:
            candidates.append((
                2, 6,
                f"Ambient {snap.ambient_temp_c:.0f}\u00b0C — cold tires, extra warm-up",
                "dim",
            ))
        if snap.ambient_humidity_pct > 85:
            candidates.append((
                2, 9,
                f"Humidity {snap.ambient_humidity_pct:.0f}% — condensation risk",
                "dim",
            ))

    # DRY + warm = positive feedback
    if (snap.surface_state == SurfaceState.DRY
            and snap.flir_available
            and not snap.is_flir_stale()
            and snap.brake_temp_fl >= 15):
        candidates.append((
            2, 20,
            "Good conditions — push it",
            "green",
        ))

    # Filter by coaching level
    filtered = [(p, t, s) for lvl, p, t, s in candidates if lvl <= coaching_level]
    if not filtered:
        return None

    # Return highest priority (lowest number)
    filtered.sort(key=lambda x: x[0])
    _, text, sentiment = filtered[0]
    return (text, sentiment)
