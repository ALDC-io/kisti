"""KiSTI - Tire & Brake Status Widget

Compact two-row widget for STREET mode.
Row 1: Tire temps (FL FR RL RR) — color-coded
Row 2: Brake temps (FL FR RL RR) — color-coded
44px tall total.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from ui.theme import BG_PANEL, CHROME_DARK, GREEN, YELLOW, RED, WHITE, GRAY, HIGHLIGHT

_TIRE_HOT = 105.0
_TIRE_CRIT = 115.0
_BRAKE_HOT = 400.0
_BRAKE_CRIT = 550.0


class TireStatusLine(QWidget):
    """Compact tire + brake temp readout — 44px, two rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self._corners = {}

    def update_data(self, corners_dict):
        self._corners = corners_dict
        self.update()

    def _temp_color(self, temp, hot, crit):
        if temp >= crit:
            return QColor(RED)
        if temp >= hot:
            return QColor(YELLOW)
        return QColor(GREEN)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        if not self._corners:
            p.end()
            return

        order = ["FL", "FR", "RL", "RR"]
        col_w = (w - 52) / 4  # space for label column + margins

        # Row labels
        label_font = QFont("Helvetica", 8)
        p.setFont(label_font)
        p.setPen(QPen(QColor(HIGHLIGHT)))
        p.drawText(QRectF(4, 2, 36, 18), Qt.AlignVCenter, "TIRE")
        p.drawText(QRectF(4, 22, 36, 18), Qt.AlignVCenter, "BRK")

        # Data columns
        data_font = QFont("Helvetica", 9)
        p.setFont(data_font)

        for i, label in enumerate(order):
            if label not in self._corners:
                continue
            corner = self._corners[label]
            cx = 42 + i * col_w

            # Corner label (tiny, above both values)
            # Tire temp
            tire_color = self._temp_color(corner.tire_temp_c, _TIRE_HOT, _TIRE_CRIT)
            p.setPen(QPen(tire_color))
            tire_text = f"{label} {corner.tire_temp_c:.0f}\u00b0"
            p.drawText(QRectF(cx, 2, col_w, 18), Qt.AlignVCenter, tire_text)

            # Brake temp
            brake_color = self._temp_color(corner.brake_temp_c, _BRAKE_HOT, _BRAKE_CRIT)
            p.setPen(QPen(brake_color))
            brake_text = f"{corner.brake_temp_c:.0f}\u00b0"
            p.drawText(QRectF(cx, 22, col_w, 18), Qt.AlignVCenter, brake_text)

        p.end()
