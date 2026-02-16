"""KiSTI - Front Sensor Suite Status Widget

Shows status of Teledyne IR, LiDAR, RGB, and Weather cameras.
Compact grid with connection dots and FPS readout.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_PANEL, HIGHLIGHT, RED, GREEN, YELLOW, WHITE, GRAY,
    CHROME_DARK, CYAN,
)


class SensorStatusWidget(QWidget):
    """Compact front sensor array status display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 70)
        self._cameras = []

    def update_data(self, sensor_suite):
        self._cameras = sensor_suite.all_cameras()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Header
        p.setPen(QColor(HIGHLIGHT))
        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        p.drawText(4, 12, "FRONT SENSORS")

        if not self._cameras:
            p.end()
            return

        # Camera rows
        row_h = (h - 18) / len(self._cameras)
        y = 18

        for cam in self._cameras:
            # Status dot
            dot_color = GREEN if cam.connected else RED
            p.setBrush(QColor(dot_color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(6, int(y + row_h / 2 - 3), 6, 6)

            # Camera name
            p.setPen(QColor(WHITE if cam.connected else GRAY))
            p.setFont(QFont("Helvetica", 9))
            p.drawText(16, int(y + row_h / 2 + 4), cam.name)

            # FPS
            if cam.connected:
                p.setPen(QColor(CYAN))
                p.setFont(QFont("Helvetica", 8))
                fps_text = f"{cam.fps:.0f}fps"
                p.drawText(w - 60, int(y + row_h / 2 + 4), fps_text)

                # Resolution
                p.setPen(QColor(GRAY))
                p.setFont(QFont("Helvetica", 7))
                p.drawText(w - 110, int(y + row_h / 2 + 4), cam.resolution)

            y += row_h

        p.end()
