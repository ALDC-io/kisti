"""KiSTI - GPS Status Line Widget

Compact single-line GPS readout for STREET mode.
22px tall — shows lat/lon, heading, and speed source confirmation.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from ui.theme import BG_PANEL, CHROME_DARK, CYAN, GRAY, HIGHLIGHT


class GPSStatusLine(QWidget):
    """Compact GPS position readout — 22px tall."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self._lat = 0.0
        self._lon = 0.0
        self._heading = 0.0

    def update_data(self, gps_data):
        self._lat = gps_data.lat
        self._lon = gps_data.lon
        self._heading = gps_data.heading
        self.update()

    def _heading_label(self, deg):
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = int((deg + 22.5) / 45) % 8
        return dirs[idx]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # GPS label
        p.setFont(QFont("Helvetica", 8))
        p.setPen(QPen(QColor(HIGHLIGHT)))
        p.drawText(QRectF(4, 0, 28, h), Qt.AlignVCenter, "GPS")

        # Coordinates + heading
        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(CYAN)))
        hdg = self._heading_label(self._heading)
        text = f"{self._lat:.4f}, {self._lon:.4f}  {self._heading:.0f}\u00b0 {hdg}"
        p.drawText(QRectF(34, 0, w - 40, h), Qt.AlignVCenter, text)

        p.end()
