"""KiSTI - Brake Strip Widget

Horizontal brake timeline - STI style: black face, red/amber markers, chrome trim.
"""

import time

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from ui.theme import RED, YELLOW, GREEN, DIM, WHITE, GRAY, CHROME_DARK, BG_DARK


class BrakeStripWidget(QWidget):
    """Horizontal brake event timeline with STI gauge styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []
        self._window_s = 60
        self.setFixedHeight(30)

    def add_event(self, severity="warning"):
        self._events.append((time.monotonic(), severity))
        cutoff = time.monotonic() - self._window_s * 2
        self._events = [(t, s) for t, s in self._events if t > cutoff]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        now = time.monotonic()

        # Black face
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Chrome border bottom
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, h - 1, w, h - 1)

        # Timeline axis - subtle
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(0, h - 2, w, h - 2)

        # Label
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        p.drawText(4, 13, "BRAKE")

        # Event markers
        colors = {"info": GREEN, "warning": YELLOW, "critical": RED}
        for ts, sev in self._events:
            age = now - ts
            if age > self._window_s:
                continue
            x = w - (age / self._window_s) * w
            color = colors.get(sev, YELLOW)
            p.setPen(QPen(QColor(color), 2))
            p.drawLine(QPointF(x, 3), QPointF(x, h - 3))

        p.end()
