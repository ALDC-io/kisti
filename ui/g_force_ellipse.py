"""KiSTI - Friction Ellipse Rendering

Shared paint function for G-force visualization with asymmetric grip
envelope, fading trail, color-coded dot, and understeer/oversteer tint.

Used by Sport and Sport Sharp screens. Follows the same module-level
paint function pattern as road_condition.py.

Design principles:
  - Friction ELLIPSE (not circle): 1.0g lateral, 1.2g brake, 0.7g accel
  - Trail dots fade alpha over 0.5-1.0 seconds
  - Dot color = G% of envelope at current angle (green/yellow/red)
  - Understeer/oversteer shown as subtle background tint
  - Dark cockpit: envelope barely visible, only dot + magnitude draw eye
"""

from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath

from ui.theme import (
    BG_DARK,
    WHITE,
    GRAY,
    DIM,
    GREEN,
    YELLOW,
    RED,
    CYAN,
)

# Asymmetric grip envelope (g)
LAT_MAX = 1.0      # lateral (left/right)
BRAKE_MAX = 1.2     # braking (top of display = negative accel_x)
ACCEL_MAX = 0.7     # acceleration (bottom of display = positive accel_x)

# Clamp: max G for display scaling
G_DISPLAY_MAX = 1.5

# Color thresholds (% of envelope)
_GREEN_PCT = 0.60
_YELLOW_PCT = 0.85


def paint_g_ellipse(
    p: QPainter,
    cx: float,
    cy: float,
    radius: float,
    snap,
    trail: deque,
    balance_ratio: float = 1.0,
    max_trail_dots: int = 20,
    accent_color: str = CYAN,
) -> None:
    """Paint a friction ellipse with trail, dot, envelope, and balance tint.

    Args:
        p: Active QPainter
        cx, cy: Center of the ellipse in widget coords
        radius: Radius in pixels for the 1.0g lateral reference
        snap: DiffState snapshot (or None)
        trail: deque of (lat_g, lon_g) tuples — owned by caller
        balance_ratio: From BalanceAnalyzer (1.0 = neutral)
        max_trail_dots: How many trail dots to paint (0 = none)
        accent_color: Hex color for trail dots
    """
    # Scale factors: how many pixels per g on each axis
    px_per_g_lat = radius / LAT_MAX
    # Brake uses more of the vertical space (asymmetric)
    px_per_g_brake = radius * (BRAKE_MAX / LAT_MAX) / BRAKE_MAX
    px_per_g_accel = radius * (ACCEL_MAX / LAT_MAX) / ACCEL_MAX

    # --- Background: understeer/oversteer tint ---
    _paint_balance_tint(p, cx, cy, radius, balance_ratio)

    # --- Envelope (90% capability) ---
    _paint_envelope(p, cx, cy, radius)

    # --- Concentric reference rings ---
    _paint_rings(p, cx, cy, radius)

    # --- Crosshair ---
    p.setPen(QPen(QColor(DIM), 1, Qt.PenStyle.DotLine))
    p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
    p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))

    # --- Axis labels ---
    p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
    p.setPen(QPen(QColor(GRAY)))
    p.drawText(QRectF(cx - 20, cy - radius - 16, 40, 14), Qt.AlignCenter, "BRAKE")
    p.drawText(QRectF(cx - radius - 14, cy - 7, 14, 14), Qt.AlignCenter, "L")
    p.drawText(QRectF(cx + radius + 2, cy - 7, 14, 14), Qt.AlignCenter, "R")

    # --- Trail dots ---
    trail_len = len(trail)
    if trail_len > 1 and max_trail_dots > 0:
        start = max(0, trail_len - max_trail_dots)
        for i in range(start, trail_len - 1):
            lat_g, lon_g = trail[i]
            progress = (i - start) / max(1, trail_len - 1 - start)
            alpha = int(30 + 180 * progress)
            dot_color = QColor(accent_color)
            dot_color.setAlpha(alpha)
            px, py = _g_to_pixel(lat_g, lon_g, cx, cy, radius)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(dot_color)
            p.drawEllipse(QPointF(px, py), 2, 2)

    # --- Current dot ---
    if snap is not None:
        lat_g = snap.imu_accel_y
        lon_g = snap.imu_accel_x
    else:
        lat_g, lon_g = 0.0, 0.0

    g_pct = _g_pct_of_envelope(lat_g, lon_g)
    dot_color = _dot_color(g_pct)
    px, py = _g_to_pixel(lat_g, lon_g, cx, cy, radius)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(dot_color)
    dot_r = 5 if radius >= 100 else 4
    p.drawEllipse(QPointF(px, py), dot_r, dot_r)

    # --- G magnitude text ---
    g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
    font_size = 18 if radius >= 100 else 14
    p.setFont(QFont("Helvetica", font_size, QFont.Weight.Bold))
    p.setPen(QPen(QColor(WHITE)))
    p.drawText(
        QRectF(cx - 50, cy + radius + 4, 100, 24),
        Qt.AlignCenter, f"{g_mag:.2f}g",
    )


def _paint_envelope(p: QPainter, cx: float, cy: float, radius: float) -> None:
    """Paint the 90% friction ellipse envelope — barely visible."""
    # Build elliptical path (asymmetric top/bottom)
    scale = 0.90  # 90% of capability
    steps = 72
    path = QPainterPath()
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        # Determine G limit at this angle
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        # Horizontal = lateral, vertical = longitudinal
        lat_limit = LAT_MAX
        if sin_a > 0:
            lon_limit = BRAKE_MAX  # top half = braking
        else:
            lon_limit = ACCEL_MAX  # bottom half = acceleration
        # Elliptical radius at this angle
        gx = cos_a * lat_limit * scale
        gy = sin_a * lon_limit * scale
        px = cx + (gx / G_DISPLAY_MAX) * radius
        py = cy - (gy / G_DISPLAY_MAX) * radius
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()

    # Fill
    fill = QColor(CYAN)
    fill.setAlpha(12)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)

    # Border
    border = QColor(CYAN)
    border.setAlpha(30)
    p.setPen(QPen(border, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


def _paint_rings(p: QPainter, cx: float, cy: float, radius: float) -> None:
    """Concentric reference rings at 0.5g and 1.0g."""
    p.setPen(QPen(QColor(DIM), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 0.5g ring
    r05 = radius * 0.5 / G_DISPLAY_MAX * LAT_MAX
    p.drawEllipse(QPointF(cx, cy), r05, r05)

    # 1.0g ring
    r10 = radius * 1.0 / G_DISPLAY_MAX * LAT_MAX
    p.drawEllipse(QPointF(cx, cy), r10, r10)

    # Ring labels
    p.setFont(QFont("Helvetica", 7))
    p.setPen(QPen(QColor(GRAY)))
    p.drawText(QRectF(cx + r05 + 2, cy - 10, 24, 12), Qt.AlignLeft, "0.5g")
    p.drawText(QRectF(cx + r10 + 2, cy - 10, 24, 12), Qt.AlignLeft, "1.0g")


def _paint_balance_tint(
    p: QPainter, cx: float, cy: float, radius: float, ratio: float,
) -> None:
    """Subtle background tint for understeer/oversteer.

    Blue tint = understeer (front washing out).
    Red tint = oversteer (rear stepping out).
    No tint when neutral (0.95-1.05).
    """
    if 0.95 <= ratio <= 1.05:
        return

    if ratio < 0.95:
        # Understeer — blue tint, intensity scales with severity
        severity = min(1.0, (0.95 - ratio) / 0.3)
        alpha = int(15 + 15 * severity)
        tint = QColor(40, 80, 200, alpha)
    else:
        # Oversteer — red tint
        severity = min(1.0, (ratio - 1.05) / 0.3)
        alpha = int(15 + 15 * severity)
        tint = QColor(200, 40, 40, alpha)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(tint)
    p.drawEllipse(QPointF(cx, cy), radius + 4, radius + 4)


def _g_to_pixel(
    lat_g: float, lon_g: float, cx: float, cy: float, radius: float,
) -> tuple[float, float]:
    """Convert G values to pixel coordinates, clamped to display max."""
    g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
    if g_mag > G_DISPLAY_MAX:
        scale = G_DISPLAY_MAX / g_mag
        lat_g *= scale
        lon_g *= scale
    px = cx + (lat_g / G_DISPLAY_MAX) * radius
    py = cy - (lon_g / G_DISPLAY_MAX) * radius
    return px, py


def _g_pct_of_envelope(lat_g: float, lon_g: float) -> float:
    """Return 0.0-1.0+ indicating how close to the friction limit.

    Accounts for the asymmetric envelope (brake vs accel).
    """
    g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
    if g_mag < 0.01:
        return 0.0

    # Determine the envelope radius at this angle
    angle = math.atan2(lon_g, lat_g)  # lon_g is "up" (braking)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    lat_limit = LAT_MAX
    lon_limit = BRAKE_MAX if sin_a > 0 else ACCEL_MAX

    # Elliptical radius at this angle
    if abs(cos_a) < 0.001:
        envelope_g = lon_limit
    elif abs(sin_a) < 0.001:
        envelope_g = lat_limit
    else:
        # Parametric ellipse radius
        envelope_g = 1.0 / math.sqrt(
            (cos_a / lat_limit) ** 2 + (sin_a / lon_limit) ** 2
        )

    return g_mag / envelope_g


def _dot_color(g_pct: float) -> QColor:
    """Green / yellow / red based on G percentage of envelope."""
    if g_pct < _GREEN_PCT:
        return QColor(GREEN)
    if g_pct < _YELLOW_PCT:
        return QColor(YELLOW)
    return QColor(RED)
