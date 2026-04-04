"""KiSTI - Road Condition Rendering Utilities

Shared painting functions for per-zone road surface state visualization.
Used by all 3 SI-Drive screens (Intelligent, Sport, Sport Sharp).

Design principles (from aviation/motorsport research):
  - Dark cockpit: DRY is nearly invisible — don't waste attention on nominal
  - Discrete states: 4 action-relevant categories, not continuous gradients
  - Urgency escalation: opacity + pulse increase with threat level
  - Pre-attentive: color hue is primary, brightness is secondary (color-blind safe)
  - Edge glow: pulsing red border for LOW_GRIP — motion is strongest pop-out feature
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter

from model.vehicle_state import SurfaceState
from ui.theme import ROAD_BG_DRY, ROAD_BG_WET, ROAD_BG_COLD, ROAD_BG_LOW_GRIP

# Map SurfaceState → background tint RGB
_ROAD_BG = {
    SurfaceState.DRY: ROAD_BG_DRY,
    SurfaceState.WET: ROAD_BG_WET,
    SurfaceState.COLD: ROAD_BG_COLD,
    SurfaceState.LOW_GRIP: ROAD_BG_LOW_GRIP,
}

# Urgency-scaled opacity for zone bar fills.
# DRY is barely visible (dark cockpit). LOW_GRIP is full intensity.
_BAR_ALPHA = {
    SurfaceState.DRY: 100,       # Visible but calm — confirms sensor is working
    SurfaceState.WET: 170,       # Clearly visible
    SurfaceState.COLD: 200,      # Brighter — closer to danger
    SurfaceState.LOW_GRIP: 240,  # Maximum — demands attention
}

# Urgency-scaled background tint alpha multiplier (relative to screen's base alpha)
_TINT_SCALE = {
    SurfaceState.DRY: 0.0,       # No tint at all for DRY
    SurfaceState.WET: 0.7,
    SurfaceState.COLD: 0.85,
    SurfaceState.LOW_GRIP: 1.0,
}


def paint_zone_tint(
    p: QPainter, w: int, h: int, states: list[SurfaceState], alpha: int,
) -> None:
    """Paint per-zone background gradient from L/C/R surface states.

    Each vertical third of the screen gets a subtle tint based on that
    zone's surface classification. DRY zones get NO tint (dark cockpit).
    WET/COLD/LOW_GRIP shift the screen mood with escalating intensity.
    """
    zone_w = w / 3.0
    for i, ss in enumerate(states):
        scaled_alpha = int(alpha * _TINT_SCALE.get(ss, 0.0))
        if scaled_alpha <= 0:
            continue
        bg = _ROAD_BG.get(ss, ROAD_BG_DRY)
        col = QColor(bg[0], bg[1], bg[2], scaled_alpha)
        x = i * zone_w
        p.fillRect(QRectF(x, 0, zone_w, h), col)


def paint_edge_glow(
    p: QPainter, w: int, h: int, any_low_grip: bool, paint_count: int,
) -> None:
    """Pulsing red edge glow when LOW_GRIP in any zone.

    8px inner border, alpha oscillates 40→90→40 at ~1Hz (assuming 20Hz repaint).
    Motion/flicker is the strongest pre-attentive feature — impossible to miss
    in peripheral vision, even when focused on the road.
    """
    if not any_low_grip:
        return
    pulse = 40 + int(50 * abs(math.sin(paint_count * 0.05)))
    col = QColor(255, 20, 20, pulse)
    glow = 8
    p.fillRect(QRectF(0, 0, w, glow), col)
    p.fillRect(QRectF(0, h - glow, w, glow), col)
    p.fillRect(QRectF(0, 0, glow, h), col)
    p.fillRect(QRectF(w - glow, 0, glow, h), col)


def paint_zone_bar(
    p: QPainter,
    x: float,
    y: float,
    w: float,
    h: float,
    states: list[SurfaceState],
    paint_count: int = 0,
    show_labels: bool = False,
) -> None:
    """3-segment road condition bar with urgency escalation.

    Dark cockpit: DRY segments are barely visible (alpha 30).
    Escalating urgency: WET→COLD→LOW_GRIP increase in opacity.
    LOW_GRIP segments pulse (strongest pre-attentive feature).
    Color-blind safe: brightness ramp ensures discriminability.
    """
    gap = 4
    seg_w = (w - gap * 2) / 3.0
    labels = ["L", "C", "R"]
    for i, ss in enumerate(states):
        sx = x + i * (seg_w + gap)
        col = QColor(ss.color)

        # Urgency-scaled opacity
        base_alpha = _BAR_ALPHA.get(ss, 200)
        if ss == SurfaceState.LOW_GRIP:
            # Pulse: alpha oscillates for LOW_GRIP (motion = pop-out)
            pulse = int(30 * abs(math.sin(paint_count * 0.06)))
            base_alpha = min(255, base_alpha + pulse)
        col.setAlpha(base_alpha)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(sx, y, seg_w, h), 4, 4)

        # LOW_GRIP gets a bright border for extra emphasis
        if ss == SurfaceState.LOW_GRIP:
            border = QColor(255, 60, 60, 180)
            p.setPen(border)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(sx + 1, y + 1, seg_w - 2, h - 2), 3, 3)

        if show_labels:
            # Label color: dark on bright bars, light on dim bars
            if ss == SurfaceState.DRY:
                p.setPen(QColor(255, 255, 255, 50))
            else:
                p.setPen(QColor(0, 0, 0, 180))
            p.setFont(QFont("Helvetica", max(8, int(h * 0.35)), QFont.Weight.Bold))
            p.drawText(QRectF(sx, y, seg_w, h), Qt.AlignmentFlag.AlignCenter, labels[i])


def zone_states_from_snap(snap) -> list[SurfaceState]:
    """Extract [left, center, right] SurfaceState list from a DiffState snapshot."""
    if snap is None:
        return [SurfaceState.DRY, SurfaceState.DRY, SurfaceState.DRY]
    return [snap.surface_state_left, snap.surface_state_center, snap.surface_state_right]


def any_zone_low_grip(states: list[SurfaceState]) -> bool:
    """True if any zone is LOW_GRIP."""
    return any(s == SurfaceState.LOW_GRIP for s in states)


def worst_state_label(states: list[SurfaceState]) -> tuple[str, str]:
    """Return (label, hex_color) for the worst surface state across zones."""
    worst = max(states, key=lambda s: s.value)
    return worst.label, worst.color
