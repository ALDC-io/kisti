"""KiSTI — Friction Ellipse Paint Function (ADR-1: paint function, not QWidget)

Asymmetric G-force envelope: 1.0g lateral, 1.2g braking, 0.7g acceleration.
Trail 0.5-1.0s. Color-coded dot by G% of envelope. US/OS background tint.

Usage:
    paint_g_ellipse(painter, cx, cy, radius, snap, trail, balance_ratio)
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath

from ui.theme import DIM, GRAY, GREEN, YELLOW, RED, CYAN, WHITE


# Asymmetric grip envelope (90% of peak capability for street driving margin)
MAX_LAT_G = 1.0      # Lateral limit
MAX_BRAKE_G = 1.2     # Braking limit (longitudinal negative)
MAX_ACCEL_G = 0.7     # Acceleration limit (longitudinal positive)


def _g_to_pixel(g_lat: float, g_lon: float, cx: float, cy: float,
                radius: float) -> tuple[float, float]:
    """Convert G values to pixel coordinates within the ellipse area.

    Lateral G: positive = right → pixel right of center.
    Longitudinal G: positive = accel → pixel UP (screen Y is inverted).
    """
    # Normalize to [-1, 1] range based on asymmetric limits
    nx = g_lat / MAX_LAT_G if MAX_LAT_G else 0.0
    if g_lon >= 0:
        ny = g_lon / MAX_ACCEL_G if MAX_ACCEL_G else 0.0
    else:
        ny = g_lon / MAX_BRAKE_G if MAX_BRAKE_G else 0.0

    # Clamp to unit circle
    mag = math.sqrt(nx * nx + ny * ny)
    if mag > 1.0:
        nx /= mag
        ny /= mag

    px = cx + nx * radius
    py = cy - ny * radius  # Screen Y inverted
    return px, py


def _g_pct_of_envelope(g_lat: float, g_lon: float) -> float:
    """How much of the grip envelope is being used (0.0-1.0+)."""
    nx = g_lat / MAX_LAT_G if MAX_LAT_G else 0.0
    if g_lon >= 0:
        ny = g_lon / MAX_ACCEL_G if MAX_ACCEL_G else 0.0
    else:
        ny = g_lon / MAX_BRAKE_G if MAX_BRAKE_G else 0.0
    return math.sqrt(nx * nx + ny * ny)


def _dot_color(g_pct: float) -> QColor:
    """Color-coded dot: green < 60%, yellow 60-85%, red > 85%."""
    if g_pct < 0.60:
        return QColor(GREEN)
    elif g_pct < 0.85:
        return QColor(YELLOW)
    return QColor(RED)


def paint_g_ellipse(
    p: QPainter,
    cx: float,
    cy: float,
    radius: float,
    snap,
    trail: list,
    balance_ratio: float = 1.0,
    max_trail_dots: int = 20,
    accent_color: str = CYAN,
) -> None:
    """Paint friction ellipse with current G position and trail.

    Args:
        p: Active QPainter (caller manages begin/end).
        cx, cy: Center pixel coordinates.
        radius: Radius in pixels for the envelope.
        snap: DiffState snapshot (needs .lateral_g, .imu_accel_x/.imu_accel_y).
        trail: List of (lateral_g, longitudinal_g) tuples, oldest first.
        balance_ratio: From BalanceAnalyzer (1.0 = neutral).
        max_trail_dots: Max trail points to render.
        accent_color: Hex color for reference elements.
    """
    p.setRenderHint(QPainter.Antialiasing)

    # --- Understeer/Oversteer background tint ---
    if balance_ratio < 0.95:
        # Understeer = blue tint
        alpha = min(30, int((0.95 - balance_ratio) * 200))
        p.fillRect(
            int(cx - radius), int(cy - radius),
            int(radius * 2), int(radius * 2),
            QColor(0, 100, 255, alpha),
        )
    elif balance_ratio > 1.05:
        # Oversteer = red tint
        alpha = min(30, int((balance_ratio - 1.05) * 200))
        p.fillRect(
            int(cx - radius), int(cy - radius),
            int(radius * 2), int(radius * 2),
            QColor(255, 50, 0, alpha),
        )

    # --- Asymmetric envelope path (72-step parametric) ---
    envelope = QPainterPath()
    steps = 72
    for i in range(steps + 1):
        angle = (2 * math.pi * i) / steps
        # Parametric: lateral = cos, longitudinal = sin
        lat = math.cos(angle)
        lon = math.sin(angle)
        # Scale by asymmetric limits (90% of capability)
        if lon >= 0:
            r_lon = MAX_ACCEL_G * 0.9
        else:
            r_lon = MAX_BRAKE_G * 0.9
        r_lat = MAX_LAT_G * 0.9
        # Normalize to pixel space
        px = cx + (lat * r_lat / MAX_LAT_G) * radius
        py = cy - (lon * r_lon / (MAX_BRAKE_G if lon < 0 else MAX_ACCEL_G)) * radius
        if i == 0:
            envelope.moveTo(px, py)
        else:
            envelope.lineTo(px, py)

    p.setPen(QPen(QColor(DIM), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(envelope)

    # --- Reference rings at 0.5g and 1.0g ---
    for g_ref in (0.5, 1.0):
        ref_r = (g_ref / MAX_LAT_G) * radius
        if ref_r < radius:
            p.setPen(QPen(QColor(DIM), 1, Qt.DotLine))
            p.drawEllipse(QPointF(cx, cy), ref_r, ref_r)

    # --- Crosshair ---
    p.setPen(QPen(QColor(DIM), 1))
    p.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
    p.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

    # --- Axis labels ---
    from PySide6.QtGui import QFont
    p.setFont(QFont("Helvetica", 7))
    p.setPen(QPen(QColor(GRAY)))
    p.drawText(int(cx + radius + 2), int(cy + 4), "R")
    p.drawText(int(cx - radius - 10), int(cy + 4), "L")
    p.drawText(int(cx - 4), int(cy - radius - 2), "B")  # Brake = top (negative lon)
    p.drawText(int(cx - 4), int(cy + radius + 10), "A")  # Accel = bottom

    # --- Trail dots (fading) ---
    trail_slice = trail[-max_trail_dots:] if len(trail) > max_trail_dots else trail
    n = len(trail_slice)
    for i, (t_lat, t_lon) in enumerate(trail_slice):
        alpha = int(30 + (210 - 30) * (i / max(1, n - 1)))
        tx, ty = _g_to_pixel(t_lat, t_lon, cx, cy, radius)
        g_pct = _g_pct_of_envelope(t_lat, t_lon)
        c = _dot_color(g_pct)
        c.setAlpha(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(tx, ty), 2, 2)

    # --- Current G dot (larger, solid) ---
    g_lat = getattr(snap, 'lateral_g', 0.0) if snap else 0.0
    g_lon = getattr(snap, 'imu_accel_x', 0.0) if snap else 0.0
    gx, gy = _g_to_pixel(g_lat, g_lon, cx, cy, radius)
    g_pct = _g_pct_of_envelope(g_lat, g_lon)
    dot_color = _dot_color(g_pct)
    p.setPen(QPen(QColor(WHITE), 1))
    p.setBrush(QBrush(dot_color))
    p.drawEllipse(QPointF(gx, gy), 5, 5)
