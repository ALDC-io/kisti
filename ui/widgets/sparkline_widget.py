"""KiSTI - Sparkline Widget

Mini QPainter line chart - STI style: red line on black face.
"""

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

from ui.theme import RED, DIM, BG_DARK


class SparklineWidget(QWidget):
    """Compact sparkline chart - STI red needle style."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self.setFixedSize(60, 20)

    def update_data(self, values):
        self._data = list(values)
        self.update()

    def paintEvent(self, event):
        if len(self._data) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Black face
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        lo = min(self._data)
        hi = max(self._data)
        span = hi - lo if hi != lo else 1.0

        # Baseline
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(0, h // 2, w, h // 2)

        # Sparkline - red like a needle trace
        p.setPen(QPen(QColor(RED), 1.5))
        n = len(self._data)
        points = []
        for i, v in enumerate(self._data):
            x = w * i / (n - 1)
            y = h - (h - 2) * (v - lo) / span - 1
            points.append(QPointF(x, y))
        for i in range(len(points) - 1):
            p.drawLine(points[i], points[i + 1])

        p.end()
