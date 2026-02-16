"""KiSTI - Track Map Widget

QPainter circuit map - Laguna Seca inspired layout with the Corkscrew.
Main view: zoomed upcoming turn section. PIP: full track overview top-right.
"""

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget

from ui.theme import DIM, CHROME_DARK, CHROME_MID, HIGHLIGHT, RED, WHITE, GRAY, BG_DARK, CYAN

# Laguna Seca inspired circuit points (normalized 0-1)
_CIRCUIT = [
    (0.85, 0.75),  # Start/finish
    (0.70, 0.78),  # T1 approach
    (0.55, 0.82),  # T2 Andretti hairpin entry
    (0.48, 0.78),  # Hairpin apex
    (0.45, 0.70),  # Hairpin exit
    (0.50, 0.60),  # Short straight
    (0.55, 0.52),  # T3
    (0.58, 0.45),  # T4
    (0.55, 0.38),  # T5 entry (esses)
    (0.48, 0.32),  # T5 exit
    (0.40, 0.28),  # T6
    (0.32, 0.22),  # Corkscrew approach
    (0.28, 0.18),  # Corkscrew top (T8)
    (0.25, 0.25),  # Corkscrew drop
    (0.22, 0.35),  # Corkscrew exit
    (0.25, 0.45),  # Downhill
    (0.30, 0.55),  # T9 Rainey curve entry
    (0.38, 0.62),  # Rainey apex
    (0.48, 0.65),  # Rainey exit
    (0.58, 0.68),  # Back straight entry
    (0.70, 0.70),  # Back straight
    (0.85, 0.75),  # Start/finish (close loop)
]

# Turn labels with circuit segment index for proximity detection
_TURNS = [
    (0.52, 0.83, "T2", 2),    # Andretti hairpin
    (0.56, 0.48, "T4", 7),
    (0.42, 0.30, "T6", 10),
    (0.24, 0.16, "T8", 12),   # Corkscrew
    (0.34, 0.60, "T9", 16),   # Rainey
]

_NUM_SEGS = len(_CIRCUIT) - 1


def _interp_circuit(progress):
    """Interpolate XY position along circuit at 0-1 progress."""
    seg_float = progress * _NUM_SEGS
    seg_idx = int(seg_float) % _NUM_SEGS
    seg_frac = seg_float - int(seg_float)
    p0 = _CIRCUIT[seg_idx]
    p1 = _CIRCUIT[(seg_idx + 1) % len(_CIRCUIT)]
    return (p0[0] + (p1[0] - p0[0]) * seg_frac,
            p0[1] + (p1[1] - p0[1]) * seg_frac)


def _build_track_path(tx, ty):
    """Build smooth circuit QPainterPath using transform functions."""
    path = QPainterPath()
    path.moveTo(tx(_CIRCUIT[0][0]), ty(_CIRCUIT[0][1]))
    for i in range(1, len(_CIRCUIT)):
        curr = _CIRCUIT[i]
        if i + 1 < len(_CIRCUIT):
            nxt = _CIRCUIT[i + 1]
            path.quadTo(tx(curr[0]), ty(curr[1]),
                        tx((curr[0] + nxt[0]) / 2), ty((curr[1] + nxt[1]) / 2))
        else:
            path.lineTo(tx(curr[0]), ty(curr[1]))
    return path


class TrackMapWidget(QWidget):
    """Laguna Seca circuit — zoomed upcoming turn + PIP overview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0

    def update_position(self, gps_data):
        self._progress = (self._progress + 0.008) % 1.0
        self.update()

    def set_progress(self, value):
        self._progress = value % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Main view: zoomed upcoming section
        self._draw_zoomed_view(p, 0, 0, w, h)

        # PIP overview: top-right corner
        pip_w = int(w * 0.30)
        pip_h = int(h * 0.35)
        pip_x = w - pip_w - 6
        pip_y = 6
        self._draw_pip_overview(p, pip_x, pip_y, pip_w, pip_h)

        # Upcoming turn label — bottom left
        self._draw_turn_info(p, w, h)

        p.end()

    def _draw_zoomed_view(self, p, x, y, w, h):
        """Draw zoomed-in view centered on upcoming track section."""
        # Look-ahead: center view between car and ~20% ahead
        car_pos = _interp_circuit(self._progress)
        look_ahead = 0.18
        ahead_pos = _interp_circuit((self._progress + look_ahead) % 1.0)

        # View center: slightly ahead of car
        vcx = car_pos[0] + (ahead_pos[0] - car_pos[0]) * 0.4
        vcy = car_pos[1] + (ahead_pos[1] - car_pos[1]) * 0.4

        # Zoom window in normalized coords (show ~30% of track extent)
        zoom = 0.28
        vx0 = vcx - zoom / 2
        vy0 = vcy - zoom / 2

        m = 12

        def tx(nx):
            return x + m + ((nx - vx0) / zoom) * (w - 2 * m)

        def ty(ny):
            return y + m + ((ny - vy0) / zoom) * (h - 2 * m)

        # Clip to widget area
        p.save()
        p.setClipRect(QRectF(x, y, w, h))

        # Track surface
        track_path = _build_track_path(tx, ty)
        p.setPen(QPen(QColor("#282828"), 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(track_path)

        # Track edges
        p.setPen(QPen(QColor(CHROME_MID), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(track_path)

        # Center line
        p.setPen(QPen(QColor("#444400"), 1, Qt.DashLine))
        p.drawPath(track_path)

        # Turn markers and labels
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        for cx_n, cy_n, label, _ in _TURNS:
            sx = tx(cx_n)
            sy = ty(cy_n)
            # Only draw if in view
            if x - 20 < sx < x + w + 20 and y - 20 < sy < y + h + 20:
                # Turn marker
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(HIGHLIGHT))
                p.drawEllipse(QPointF(sx, sy), 4, 4)
                # Label
                p.setPen(QColor(WHITE))
                p.drawText(int(sx) + 8, int(sy) + 4, label)

        # Start/finish line
        sf_x = tx(_CIRCUIT[0][0])
        sf_y = ty(_CIRCUIT[0][1])
        if x - 20 < sf_x < x + w + 20 and y - 20 < sf_y < y + h + 20:
            p.setPen(QPen(QColor(HIGHLIGHT), 3))
            p.drawLine(int(sf_x), int(sf_y) - 14, int(sf_x), int(sf_y) + 14)

        # Car dot (larger in zoomed view)
        car_sx = tx(car_pos[0])
        car_sy = ty(car_pos[1])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 0, 0, 40)))
        p.drawEllipse(QPointF(car_sx, car_sy), 18, 18)
        p.setBrush(QBrush(QColor(255, 0, 0, 100)))
        p.drawEllipse(QPointF(car_sx, car_sy), 10, 10)
        p.setBrush(QBrush(QColor(HIGHLIGHT)))
        p.drawEllipse(QPointF(car_sx, car_sy), 6, 6)
        p.setBrush(QBrush(QColor(WHITE)))
        p.drawEllipse(QPointF(car_sx, car_sy), 2, 2)

        # Look-ahead direction line (subtle)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.DashLine))
        ahead_sx = tx(ahead_pos[0])
        ahead_sy = ty(ahead_pos[1])
        p.drawLine(int(car_sx), int(car_sy), int(ahead_sx), int(ahead_sy))

        p.restore()

    def _draw_pip_overview(self, p, x, y, w, h):
        """Draw mini full-circuit overview in a PIP box."""
        # Semi-transparent background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 200))
        p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)

        # Border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)

        m = 6

        def tx(nx):
            return x + m + nx * (w - 2 * m)

        def ty(ny):
            return y + m + ny * (h - 2 * m)

        # Track path
        track_path = _build_track_path(tx, ty)
        p.setPen(QPen(QColor("#383838"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(track_path)
        p.setPen(QPen(QColor(CHROME_DARK), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(track_path)

        # Turn dots
        for cx_n, cy_n, label, _ in _TURNS:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(GRAY))
            p.drawEllipse(QPointF(tx(cx_n), ty(cy_n)), 1.5, 1.5)

        # Car dot
        car_pos = _interp_circuit(self._progress)
        car_sx = tx(car_pos[0])
        car_sy = ty(car_pos[1])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 0, 0, 80)))
        p.drawEllipse(QPointF(car_sx, car_sy), 5, 5)
        p.setBrush(QBrush(QColor(HIGHLIGHT)))
        p.drawEllipse(QPointF(car_sx, car_sy), 3, 3)
        p.setBrush(QBrush(QColor(WHITE)))
        p.drawEllipse(QPointF(car_sx, car_sy), 1, 1)

        # "LAGUNA SECA" label
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 6))
        p.drawText(x + m, y + h - m + 1, "LAGUNA SECA")

    def _draw_turn_info(self, p, w, h):
        """Show upcoming turn name and distance estimate at bottom-left."""
        # Find next turn ahead of current position
        car_seg = self._progress * _NUM_SEGS
        next_turn = None
        min_dist = _NUM_SEGS + 1

        for cx_n, cy_n, label, seg_idx in _TURNS:
            # Distance ahead (wrapping around)
            dist = (seg_idx - car_seg) % _NUM_SEGS
            if 0 < dist < min_dist:
                min_dist = dist
                next_turn = label

        if next_turn:
            p.setPen(QColor(CYAN))
            p.setFont(QFont("Helvetica", 14, QFont.Bold))
            p.drawText(12, h - 28, next_turn)

            p.setPen(QColor(GRAY))
            p.setFont(QFont("Helvetica", 8))
            p.drawText(12, h - 14, "UPCOMING")
