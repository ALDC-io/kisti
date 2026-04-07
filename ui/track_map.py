"""Track map — module-level QPainter function for rendering a GPS circuit outline.

Follows the pattern of ui/g_force_ellipse.py and ui/road_condition.py:
a pure function called from paintEvent, no QWidget subclass.

Usage in a screen's paintEvent:
    from ui.track_map import paint_track_map
    paint_track_map(p, x=480, y=90, w=320, h=190, outline=self._track_outline,
                    progress=self._lap_progress, track_name="Mission Raceway")
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush

from ui.theme import BG_DARK, CHROME_DARK, CHROME_MID, DIM, GRAY, HIGHLIGHT, WHITE

# Car dot colours
_CAR_OUTER = QColor(255, 80, 0, 60)
_CAR_MID = QColor(255, 80, 0, 140)
_CAR_INNER = QColor(255, 160, 0)
_CAR_CENTER = QColor(255, 255, 255)

# Schematic style (current default) — thin white-ish line on dark BG
_TRACK_FILL = QColor("#252525")
_TRACK_EDGE = QColor(CHROME_MID)
_SF_LINE = QColor(HIGHLIGHT)

# GT style — road surface as thick band (white curb lines + dark asphalt)
_GT_CURB = QColor(220, 220, 220)    # white edge/kerb line (wide stroke)
_GT_ASPHALT = QColor(75, 75, 75)    # dark gray road surface (narrow stroke)
_GT_SF = QColor(255, 200, 0)        # yellow start/finish line


def paint_track_map(
    p: QPainter,
    x: int,
    y: int,
    w: int,
    h: int,
    outline: list[tuple[float, float]],
    progress: float = 0.0,
    track_name: str = "",
    style: str = "schematic",
) -> None:
    """Draw a circuit outline in the given screen rectangle.

    Args:
        p: Active QPainter (caller holds begin/end).
        x, y, w, h: Target rectangle in screen pixels.
        outline: Normalized (0-1) track outline points from track_outline.py.
        progress: 0-1 lap progress (positions the car dot along outline).
        track_name: Shown in dim gray at bottom of the panel.
        style: "schematic" (thin outline) or "gt" (Gran Turismo thick road band).
    """
    if len(outline) < 3:
        _draw_no_track(p, x, y, w, h, track_name)
        return

    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setClipRect(QRectF(x, y, w, h))

    # Background fill
    p.fillRect(x, y, w, h, QColor(BG_DARK))

    # Margin so track doesn't touch edges
    mx, my = 12, 10

    def sx(nx: float) -> float:
        return x + mx + nx * (w - 2 * mx)

    def sy(ny: float) -> float:
        return y + my + ny * (h - 2 * my)

    # Build circuit path
    path = _build_path(outline, sx, sy)

    if style == "gt":
        # Gran Turismo style: thick road band — white kerb border + dark asphalt surface
        # Draw wider white stroke first → creates the kerb/edge lines
        p.setPen(QPen(_GT_CURB, 22, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        # Narrower dark asphalt on top → leaves 3px white on each side
        p.setPen(QPen(_GT_ASPHALT, 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    else:
        # Schematic style: dark fill band + thin bright edge line
        p.setPen(QPen(_TRACK_FILL, 10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(_TRACK_EDGE, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)

    # Start/finish line at outline[0]
    sf = outline[0]
    sf_x, sf_y = sx(sf[0]), sy(sf[1])
    sf_color = _GT_SF if style == "gt" else _SF_LINE
    # Draw a short perpendicular tick across the track
    if len(outline) >= 2:
        nxt = outline[1]
        dx = sx(nxt[0]) - sf_x
        dy = sy(nxt[1]) - sf_y
        length = math.hypot(dx, dy) or 1.0
        perp_x, perp_y = -dy / length, dx / length
        tick = 10 if style == "gt" else 8
        p.setPen(QPen(sf_color, 2 if style == "schematic" else 3))
        p.drawLine(
            QPointF(sf_x - perp_x * tick, sf_y - perp_y * tick),
            QPointF(sf_x + perp_x * tick, sf_y + perp_y * tick),
        )

    # Car position dot
    car_pt = _interpolate_outline(outline, progress)
    car_x, car_y = sx(car_pt[0]), sy(car_pt[1])

    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_CAR_OUTER))
    p.drawEllipse(QPointF(car_x, car_y), 9, 9)
    p.setBrush(QBrush(_CAR_MID))
    p.drawEllipse(QPointF(car_x, car_y), 5, 5)
    p.setBrush(QBrush(_CAR_INNER))
    p.drawEllipse(QPointF(car_x, car_y), 3, 3)
    p.setBrush(QBrush(_CAR_CENTER))
    p.drawEllipse(QPointF(car_x, car_y), 1.2, 1.2)

    # Track name — dim gray at bottom left
    if track_name:
        label = track_name.upper()
        p.setPen(QColor(DIM))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(x + 6, y + h - 5, label)

    p.restore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_path(
    outline: list[tuple[float, float]],
    sx,
    sy,
) -> QPainterPath:
    """Build a smooth QPainterPath from normalized outline points."""
    path = QPainterPath()
    path.moveTo(sx(outline[0][0]), sy(outline[0][1]))

    n = len(outline)
    for i in range(1, n):
        curr = outline[i]
        if i + 1 < n:
            nxt = outline[i + 1]
            # Quadratic bezier: control=curr, end=midpoint(curr, nxt)
            mx_ = (curr[0] + nxt[0]) / 2
            my_ = (curr[1] + nxt[1]) / 2
            path.quadTo(sx(curr[0]), sy(curr[1]), sx(mx_), sy(my_))
        else:
            path.lineTo(sx(curr[0]), sy(curr[1]))

    # Close back to start
    path.lineTo(sx(outline[0][0]), sy(outline[0][1]))
    return path


def _interpolate_outline(
    outline: list[tuple[float, float]],
    progress: float,
) -> tuple[float, float]:
    """Return (x, y) on the outline at 0-1 progress along the polyline."""
    if not outline:
        return (0.5, 0.5)
    n = len(outline)
    seg_float = (progress % 1.0) * n
    idx = int(seg_float) % n
    frac = seg_float - int(seg_float)
    p0 = outline[idx]
    p1 = outline[(idx + 1) % n]
    return (
        p0[0] + (p1[0] - p0[0]) * frac,
        p0[1] + (p1[1] - p0[1]) * frac,
    )


def _draw_no_track(
    p: QPainter,
    x: int,
    y: int,
    w: int,
    h: int,
    track_name: str,
) -> None:
    """Placeholder when no outline is loaded yet."""
    p.fillRect(x, y, w, h, QColor(BG_DARK))
    p.setPen(QColor(DIM))
    p.setFont(QFont("Helvetica", 8))
    cx, cy = x + w // 2, y + h // 2
    label = track_name.upper() if track_name else "NO TRACK OUTLINE"
    fm_w = len(label) * 5  # rough estimate
    p.drawText(cx - fm_w // 2, cy, label)
