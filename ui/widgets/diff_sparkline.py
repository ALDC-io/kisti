"""KiSTI - DIFF Sparkline Widget

Ring-buffer QPainter sparkline for 10-second rolling history.
200 samples at 20 Hz.  Lightweight: no plotting libs, no QPixmap cache.

Renders:
  - Dark background
  - Zero-line (for signed signals like SlipDelta)
  - Filled area under the curve with alpha
  - Signal line in configurable color
  - Label on the left
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

from ui.theme import BG_DARK, DIM, GRAY, WHITE

# 10 seconds at 20 Hz = 200 samples
BUFFER_SIZE: int = 200


class DiffSparkline(QWidget):
    """Compact sparkline with ring buffer, label, and optional zero-line.

    Args:
        label: Short text rendered at the left edge (e.g. "LOCK%").
        color: Hex color string for the signal line.
        min_val: Expected minimum value (for Y-axis scaling).
        max_val: Expected maximum value.
        show_zero_line: Draw a horizontal line at y=0 (for signed signals).
        parent: Parent widget.
    """

    def __init__(
        self,
        label: str = "",
        color: str = "#E60000",
        min_val: float = 0.0,
        max_val: float = 100.0,
        show_zero_line: bool = False,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._color = QColor(color)
        self._min_val = min_val
        self._max_val = max_val
        self._show_zero_line = show_zero_line
        self._compact = compact
        self._label_w = 36 if compact else 48
        self._buffer: deque[float] = deque(maxlen=BUFFER_SIZE)

        # Fill color = line color at 25% opacity
        self._fill_color = QColor(self._color)
        self._fill_color.setAlphaF(0.20)

        self.setMinimumHeight(22 if compact else 28)

    def push(self, value: float) -> None:
        """Append a sample to the ring buffer."""
        self._buffer.append(value)

    def clear_buffer(self) -> None:
        self._buffer.clear()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Label area
        label_w = self._label_w
        chart_x = label_w
        chart_w = w - label_w - 2  # 2px right margin

        # Draw label
        p.setPen(QPen(QColor(GRAY), 1))
        p.setFont(QFont("Helvetica", 8 if self._compact else 9, QFont.Bold))
        p.drawText(QRectF(2, 0, label_w - 4, h), Qt.AlignVCenter | Qt.AlignLeft, self._label)

        # Border around chart area
        p.setPen(QPen(QColor(DIM), 1))
        p.drawRect(chart_x, 0, chart_w, h - 1)

        n = len(self._buffer)
        if n < 2:
            p.end()
            return

        # Y-axis range — use configured min/max but auto-expand if data exceeds
        lo = self._min_val
        hi = self._max_val
        data_lo = min(self._buffer)
        data_hi = max(self._buffer)
        if data_lo < lo:
            lo = data_lo
        if data_hi > hi:
            hi = data_hi
        span = hi - lo if hi != lo else 1.0

        # Zero line
        if self._show_zero_line and lo < 0 < hi:
            zero_y = h - 1 - (0 - lo) / span * (h - 2)
            p.setPen(QPen(QColor(DIM), 1, Qt.DashLine))
            p.drawLine(QPointF(chart_x, zero_y), QPointF(chart_x + chart_w, zero_y))

        # Build point list
        points: list[QPointF] = []
        for i, v in enumerate(self._buffer):
            x = chart_x + chart_w * i / (n - 1)
            y = h - 1 - (v - lo) / span * (h - 2)
            points.append(QPointF(x, y))

        # Filled area under curve
        fill_path = QPainterPath()
        fill_path.moveTo(QPointF(points[0].x(), h - 1))
        for pt in points:
            fill_path.lineTo(pt)
        fill_path.lineTo(QPointF(points[-1].x(), h - 1))
        fill_path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(self._fill_color)
        p.drawPath(fill_path)

        # Signal line
        p.setPen(QPen(self._color, 1.5))
        p.setBrush(Qt.NoBrush)
        for i in range(len(points) - 1):
            p.drawLine(points[i], points[i + 1])

        p.end()
