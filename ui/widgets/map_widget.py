"""KiSTI - Street Navigation Map Widget

QPainter-based street map showing road network, current position,
threat-colored speed readout, and GPS coordinates.
"""

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget

from data.models import RadarState, RadarBand
from ui.theme import (
    DIM, CYAN, WHITE, SILVER, RED, HIGHLIGHT, BG_DARK, CHROME_DARK, GRAY,
    RADAR_KA, RADAR_K, RADAR_LASER,
)


class MapWidget(QWidget):
    """Street navigation map with road network, speed + GPS overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_x = 0.5
        self._pos_y = 0.5
        self._speed = 0.0
        self._heading = 0.0
        self._lat = 0.0
        self._lon = 0.0
        self._radar = RadarState()
        self._laser_flash = False

        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(300)
        self._flash_timer.timeout.connect(self._toggle_laser_flash)

    def update_position(self, gps_data):
        self._pos_y = (gps_data.lat - 36.57) / 0.01 + 0.5
        self._pos_x = (gps_data.lon + 121.95) / 0.01 + 0.5
        self._speed = gps_data.speed_kph
        self._heading = gps_data.heading
        self._lat = gps_data.lat
        self._lon = gps_data.lon
        self.update()

    def update_radar(self, radar_state):
        self._radar = radar_state
        alert = radar_state.priority_alert
        is_laser = alert and alert.band == RadarBand.LASER
        if is_laser and not self._flash_timer.isActive():
            self._flash_timer.start()
        elif not is_laser:
            self._flash_timer.stop()
            self._laser_flash = False
        self.update()

    def _toggle_laser_flash(self):
        self._laser_flash = not self._laser_flash
        self.update()

    def _threat_speed_color(self):
        """Return speed text color based on V1 radar threat."""
        if not self._radar.has_alerts:
            return QColor("#88CC88")
        alert = self._radar.priority_alert
        if not alert:
            return QColor("#88CC88")
        if alert.band == RadarBand.LASER:
            return QColor(WHITE) if self._laser_flash else QColor(RADAR_LASER)
        signal = max(alert.front_signal, alert.rear_signal)
        if alert.band == RadarBand.K:
            return QColor(RADAR_K)
        if signal >= 5:
            return QColor(RADAR_KA)
        return QColor("#FFCC00")

    def _heading_label(self, deg):
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[int((deg + 22.5) / 45) % 8]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = 10

        # Dark terrain background
        p.fillRect(0, 0, w, h, QColor("#0C1210"))

        # Chrome border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Draw road network (Laguna Seca area roads)
        # Main highway (Hwy 68)
        p.setPen(QPen(QColor("#2A2A2A"), 6))
        p.drawLine(m, int(h * 0.7), w - m, int(h * 0.3))

        p.setPen(QPen(QColor("#444444"), 4))
        p.drawLine(m, int(h * 0.7), w - m, int(h * 0.3))

        # Center line
        p.setPen(QPen(QColor("#665500"), 1, Qt.DashLine))
        p.drawLine(m, int(h * 0.7), w - m, int(h * 0.3))

        # Secondary road (Laureles Grade)
        p.setPen(QPen(QColor("#333333"), 3))
        path1 = QPainterPath()
        path1.moveTo(w * 0.3, m)
        path1.quadTo(w * 0.35, h * 0.3, w * 0.45, h * 0.45)
        path1.quadTo(w * 0.55, h * 0.6, w * 0.5, h - m)
        p.drawPath(path1)

        # Side road (York Rd)
        p.setPen(QPen(QColor("#2A2A2A"), 2))
        path2 = QPainterPath()
        path2.moveTo(w * 0.6, m)
        path2.quadTo(w * 0.65, h * 0.2, w * 0.55, h * 0.4)
        p.drawPath(path2)

        # Another connector
        p.setPen(QPen(QColor("#2A2A2A"), 2))
        p.drawLine(int(w * 0.2), int(h * 0.5), int(w * 0.4), int(h * 0.35))

        # Track access road
        p.setPen(QPen(QColor("#333333"), 2))
        path3 = QPainterPath()
        path3.moveTo(w * 0.55, h * 0.4)
        path3.lineTo(w * 0.75, h * 0.35)
        path3.quadTo(w * 0.85, h * 0.3, w * 0.8, h * 0.2)
        p.drawPath(path3)

        # Terrain features - subtle contour suggestions
        p.setPen(QPen(QColor("#141A18"), 1))
        for i in range(5):
            y_off = h * (0.15 + i * 0.15)
            path = QPainterPath()
            path.moveTo(m, y_off)
            path.quadTo(w * 0.3, y_off - 15, w * 0.5, y_off + 8)
            path.quadTo(w * 0.7, y_off + 20, w - m, y_off - 5)
            p.drawPath(path)

        # Road labels
        p.setPen(QColor("#555555"))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(int(w * 0.7), int(h * 0.38), "HWY 68")
        p.drawText(int(w * 0.28), int(h * 0.15), "LAURELES GR")

        # Position dot - STI red with glow, centered view
        px = m + self._pos_x * (w - 2 * m)
        py = m + self._pos_y * (h - 2 * m)

        # Clamp to visible area
        px = max(m + 10, min(w - m - 10, px))
        py = max(m + 10, min(h - m - 10, py))

        p.setPen(Qt.NoPen)
        # Outer glow
        p.setBrush(QBrush(QColor(255, 0, 0, 40)))
        p.drawEllipse(QPointF(px, py), 16, 16)
        p.setBrush(QBrush(QColor(255, 0, 0, 80)))
        p.drawEllipse(QPointF(px, py), 10, 10)
        # Inner dot
        p.setBrush(QBrush(QColor(HIGHLIGHT)))
        p.drawEllipse(QPointF(px, py), 5, 5)
        # White center
        p.setBrush(QBrush(QColor(WHITE)))
        p.drawEllipse(QPointF(px, py), 2, 2)

        # === Bottom overlay bar: speed (left) + GPS (right) ===
        bar_h = 38
        bar_y = h - bar_h

        # Semi-transparent background strip
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 180))
        p.drawRect(0, bar_y, w, bar_h)

        # Laser flash background
        alert = self._radar.priority_alert
        if alert and alert.band == RadarBand.LASER and self._laser_flash:
            p.setBrush(QColor(RADAR_LASER))
            p.drawRect(0, bar_y, w, bar_h)

        # Speed — threat-colored, left side
        speed_color = self._threat_speed_color()
        p.setPen(QPen(speed_color))
        p.setFont(QFont("Helvetica", 20, QFont.Bold))
        p.drawText(QRectF(m, bar_y, 80, bar_h), Qt.AlignVCenter, f"{self._speed:.0f}")

        p.setPen(QPen(QColor(GRAY)))
        p.setFont(QFont("Helvetica", 8))
        p.drawText(QRectF(m + 62, bar_y + 2, 30, bar_h), Qt.AlignVCenter, "km/h")

        # GPS coords + heading — right side
        p.setPen(QPen(QColor(CYAN)))
        p.setFont(QFont("Helvetica", 9))
        hdg = self._heading_label(self._heading)
        gps_text = f"{self._lat:.4f}, {self._lon:.4f}  {self._heading:.0f}\u00b0{hdg}"
        p.drawText(QRectF(m + 100, bar_y, w - m - 110, bar_h),
                   Qt.AlignVCenter | Qt.AlignRight, gps_text)

        # Compass indicator (top right)
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 8))
        p.drawText(w - m - 16, m + 14, "N")
        p.setPen(QPen(QColor(GRAY), 1))
        p.drawLine(w - m - 12, m + 18, w - m - 12, m + 28)
        p.drawLine(w - m - 12, m + 18, w - m - 15, m + 23)
        p.drawLine(w - m - 12, m + 18, w - m - 9, m + 23)

        p.end()
