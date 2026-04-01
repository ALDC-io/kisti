"""KiSTI - Critical Flash Overlay

Transparent QPainter overlay that flashes a colored border for
WARNING and CRITICAL alerts in Sport Sharp mode.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from alerts.alert_engine import AlertSeverity
from ui import theme


# Flash config
_FLASH_INITIAL_ALPHA = 200
_FLASH_DECAY_STEP = 8       # alpha reduction per tick
_FLASH_TICK_MS = 40          # ~25 fps fade
_BORDER_WIDTH = 8


class CriticalFlashOverlay(QWidget):
    """Transparent overlay that flashes a colored border on alerts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._flash_alpha: int = 0
        self._flash_color: QColor = QColor(theme.RED)

        self._timer = QTimer(self)
        self._timer.setInterval(_FLASH_TICK_MS)
        self._timer.timeout.connect(self._decay)

    def flash(self, severity: AlertSeverity, message: str = "") -> None:
        """Trigger a visual flash. Auto-fades."""
        if severity >= AlertSeverity.CRITICAL:
            self._flash_color = QColor(theme.RED)
        elif severity >= AlertSeverity.WARNING:
            self._flash_color = QColor(theme.YELLOW)
        else:
            return  # No flash for INFO/ADVISORY

        self._flash_alpha = _FLASH_INITIAL_ALPHA
        self._timer.start()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._flash_alpha <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self._flash_color)
        color.setAlpha(self._flash_alpha)

        pen = QPen(color, _BORDER_WIDTH)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        half = _BORDER_WIDTH // 2
        p.drawRect(half, half, self.width() - _BORDER_WIDTH, self.height() - _BORDER_WIDTH)
        p.end()

    def _decay(self) -> None:
        self._flash_alpha = max(0, self._flash_alpha - _FLASH_DECAY_STEP)
        self.update()
        if self._flash_alpha <= 0:
            self._timer.stop()
