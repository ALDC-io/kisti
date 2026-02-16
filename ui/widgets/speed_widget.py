"""KiSTI - Speed Widget

Compact radar-threat-colored speed display for STREET mode.
36px tall — speed number + unit, border/text colored by V1 threat level.
"""

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from data.models import RadarBand
from ui.theme import (
    BG_PANEL, CHROME_DARK, GRAY, WHITE,
    RADAR_KA, RADAR_K, RADAR_LASER,
)

_THREAT_CLEAR = "clear"
_THREAT_K = "k_band"
_THREAT_KA_LOW = "ka_low"
_THREAT_KA_HIGH = "ka_high"
_THREAT_LASER = "laser"


class SpeedWidget(QWidget):
    """Compact speed readout with radar-threat-responsive coloring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._speed_kph = 0.0
        self._threat = _THREAT_CLEAR
        self._laser_flash = False

        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(300)
        self._flash_timer.timeout.connect(self._toggle_laser_flash)

    def update_data(self, gps_data, radar_state):
        """Update speed and radar threat level."""
        self._speed_kph = gps_data.speed_kph
        self._threat = self._classify_threat(radar_state)

        if self._threat == _THREAT_LASER:
            if not self._flash_timer.isActive():
                self._flash_timer.start()
        else:
            self._flash_timer.stop()
            self._laser_flash = False

        self.update()

    def _classify_threat(self, radar):
        if not radar.has_alerts:
            return _THREAT_CLEAR
        alert = radar.priority_alert
        if not alert:
            return _THREAT_CLEAR
        if alert.band == RadarBand.LASER:
            return _THREAT_LASER
        signal = max(alert.front_signal, alert.rear_signal)
        if alert.band == RadarBand.K:
            return _THREAT_K
        if signal >= 5:
            return _THREAT_KA_HIGH
        return _THREAT_KA_LOW

    def _toggle_laser_flash(self):
        self._laser_flash = not self._laser_flash
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        bg_color = QColor(BG_PANEL)
        border_color = QColor(CHROME_DARK)
        speed_color = QColor(WHITE)
        border_width = 1
        laser_label = False

        if self._threat == _THREAT_CLEAR:
            speed_color = QColor("#88CC88")
        elif self._threat == _THREAT_K:
            border_color = QColor(RADAR_K)
            border_width = 2
        elif self._threat == _THREAT_KA_LOW:
            border_color = QColor("#FFCC00")
            speed_color = QColor("#FFCC00")
            border_width = 2
        elif self._threat == _THREAT_KA_HIGH:
            border_color = QColor(RADAR_KA)
            speed_color = QColor(RADAR_KA)
            border_width = 2
        elif self._threat == _THREAT_LASER:
            border_width = 2
            border_color = QColor(RADAR_LASER)
            if self._laser_flash:
                bg_color = QColor(RADAR_LASER)
                speed_color = QColor(WHITE)
                laser_label = True
            else:
                bg_color = QColor("#440022")
                speed_color = QColor(RADAR_LASER)

        # Background
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(0, 0, w, h, 4, 4)

        # Border
        p.setPen(QPen(border_color, border_width))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        # Speed number — left side, large
        speed_text = f"{self._speed_kph:.0f}"
        p.setFont(QFont("Helvetica", 20, QFont.Bold))
        p.setPen(QPen(speed_color))
        p.drawText(QRectF(8, 0, 80, h), Qt.AlignVCenter | Qt.AlignLeft, speed_text)

        # "km/h" — right of speed number
        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(88, 0, 40, h), Qt.AlignVCenter | Qt.AlignLeft, "km/h")

        # LASER label on right side when flashing
        if laser_label:
            p.setFont(QFont("Helvetica", 11, QFont.Bold))
            p.setPen(QPen(QColor(WHITE)))
            p.drawText(QRectF(w - 70, 0, 64, h), Qt.AlignVCenter | Qt.AlignRight, "LASER")

        p.end()
