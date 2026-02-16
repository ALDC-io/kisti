"""KiSTI - Oil Pressure Gauge Widget

Compact oil pressure gauge with STI styling.
Shows PSI value, oil temp, and pressure trend sparkline.
"""

import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QConicalGradient
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_DARK, BG_PANEL, HIGHLIGHT, RED, GREEN, YELLOW, WHITE, GRAY,
    CHROME_DARK, CHROME_MID,
)
from config import OIL_PSI_LOW_WARN, OIL_PSI_LOW_CRIT, OIL_PSI_HIGH_WARN, OIL_TEMP_WARN


class OilGaugeWidget(QWidget):
    """Compact oil pressure + temp gauge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 55)
        self._psi = 45.0
        self._temp_c = 95.0
        self._trend = [45.0] * 30

    def update_data(self, oil_data):
        self._psi = oil_data.psi
        self._temp_c = oil_data.temp_c
        self._trend = list(oil_data.trend)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Label
        p.setPen(QColor(HIGHLIGHT))
        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        p.drawText(4, 12, "OIL")

        # PSI value - color coded
        if self._psi < OIL_PSI_LOW_CRIT:
            color = RED
        elif self._psi < OIL_PSI_LOW_WARN:
            color = YELLOW
        elif self._psi > OIL_PSI_HIGH_WARN:
            color = YELLOW
        else:
            color = GREEN

        p.setPen(QColor(color))
        p.setFont(QFont("Helvetica", 18, QFont.Bold))
        p.drawText(4, 36, f"{self._psi:.0f}")

        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 9))
        p.drawText(50, 36, "PSI")

        # Oil temp
        temp_color = RED if self._temp_c > OIL_TEMP_WARN else WHITE
        p.setPen(QColor(temp_color))
        p.setFont(QFont("Helvetica", 10))
        p.drawText(4, 50, f"{self._temp_c:.0f}\u00b0C")

        # Mini sparkline (right side)
        if len(self._trend) >= 2:
            sx = w - 50
            sy = 8
            sw = 44
            sh = h - 16
            mn = min(self._trend)
            mx = max(self._trend)
            rng = mx - mn if mx != mn else 1.0

            p.setPen(QPen(QColor(color), 1.5))
            pts = []
            for i, v in enumerate(self._trend):
                x = sx + (i / (len(self._trend) - 1)) * sw
                y = sy + sh - ((v - mn) / rng) * sh
                pts.append((x, y))
            for i in range(len(pts) - 1):
                p.drawLine(int(pts[i][0]), int(pts[i][1]),
                           int(pts[i + 1][0]), int(pts[i + 1][1]))

        p.end()
