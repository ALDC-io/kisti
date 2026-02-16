"""KiSTI - Radar Alert Widget

Valentine One Gen2-style radar display with QPainter custom rendering.
Shows: V1 header + connection dot, direction arrows, band badge,
frequency readout, signal strength bar (8 segments), alert count.

~80px tall, full panel width.
"""

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygonF
from PySide6.QtWidgets import QWidget

from data.models import RadarState, RadarBand, AlertDirection
from ui.theme import (
    BG_DARK, BG_PANEL, CHROME_DARK, GREEN, GRAY, WHITE, DIM,
    RADAR_KA, RADAR_K, RADAR_X, RADAR_LASER, RADAR_CLEAR,
)

_BAND_COLORS = {
    RadarBand.Ka: RADAR_KA,
    RadarBand.K: RADAR_K,
    RadarBand.X: RADAR_X,
    RadarBand.LASER: RADAR_LASER,
}


class RadarAlertWidget(QWidget):
    """V1-style radar alert display — QPainter rendered."""

    def __init__(self, parent=None, height=80):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._state = RadarState()

    def update_radar(self, radar_state):
        """Update with new RadarState and repaint."""
        self._state = radar_state
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))

        # Border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        alert = self._state.priority_alert
        connected = self._state.connected
        band_color = QColor(RADAR_CLEAR)
        if alert:
            band_color = QColor(_BAND_COLORS.get(alert.band, RADAR_CLEAR))

        # === Left section: V1 header + connection dot (60px wide) ===
        left_w = 55
        self._draw_header(p, 0, 0, left_w, h, connected, band_color)

        # === Center section: Direction arrows + Band/Freq (remaining space - right) ===
        right_w = 70
        center_x = left_w
        center_w = w - left_w - right_w
        self._draw_center(p, center_x, 0, center_w, h, alert, band_color)

        # === Right section: Signal bar + count ===
        self._draw_signal_bar(p, w - right_w, 0, right_w, h, alert)

        p.end()

    def _draw_header(self, p, x, y, w, h, connected, band_color):
        """V1 label and connection indicator."""
        # "V1" text
        font = QFont("Helvetica", 14, QFont.Bold)
        p.setFont(font)
        if self._state.has_alerts:
            p.setPen(QPen(band_color))
        else:
            p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x, y + 4, w, 24), Qt.AlignCenter, "V1")

        # Connection dot
        dot_r = 4
        dot_cx = x + w / 2
        dot_cy = y + 34
        dot_color = QColor(GREEN) if connected else QColor(GRAY)
        p.setPen(Qt.NoPen)
        p.setBrush(dot_color)
        p.drawEllipse(QPointF(dot_cx, dot_cy), dot_r, dot_r)

        # "GEN2" label
        small_font = QFont("Helvetica", 7)
        p.setFont(small_font)
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x, y + 42, w, 14), Qt.AlignCenter, "GEN2")

        # Alert count badge
        if self._state.alert_count > 0:
            badge_font = QFont("Helvetica", 9, QFont.Bold)
            p.setFont(badge_font)
            count_text = str(self._state.alert_count)
            badge_y = y + 58
            p.setPen(QPen(band_color))
            p.drawText(QRectF(x, badge_y, w, 16), Qt.AlignCenter, count_text)

    def _draw_center(self, p, x, y, w, h, alert, band_color):
        """Direction arrows, band badge, and frequency readout."""
        if not alert:
            # No alerts — show "CLEAR" centered
            font = QFont("Helvetica", 11)
            p.setFont(font)
            p.setPen(QPen(QColor(DIM)))
            p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, "CLEAR")
            return

        # Direction arrows row (top portion)
        arrow_y = y + 6
        arrow_h = 22
        arrow_w_each = w / 3
        directions = [
            (AlertDirection.FRONT, "FRONT"),
            (AlertDirection.SIDE, "SIDE"),
            (AlertDirection.REAR, "REAR"),
        ]
        for i, (direction, label) in enumerate(directions):
            ax = x + i * arrow_w_each
            active = alert.direction == direction
            self._draw_direction_arrow(
                p, ax, arrow_y, arrow_w_each, arrow_h,
                direction, active, band_color
            )

        # Band badge
        badge_y = y + 32
        badge_h = 20
        font = QFont("Helvetica", 12, QFont.Bold)
        p.setFont(font)
        band_text = alert.band.value
        p.setPen(Qt.NoPen)
        p.setBrush(band_color)

        # Measure text width for badge background
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(band_text)
        badge_w = tw + 16
        badge_x = x + (w - badge_w) / 2
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 3, 3)

        # Band text (white on colored badge)
        p.setPen(QPen(QColor(WHITE)))
        p.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignCenter, band_text)

        # Frequency readout
        freq_y = y + 56
        freq_font = QFont("Helvetica", 9)
        p.setFont(freq_font)
        p.setPen(QPen(QColor(GRAY)))
        if alert.band == RadarBand.LASER:
            freq_text = "LIDAR"
        else:
            ghz = alert.frequency_mhz / 1000.0
            freq_text = f"{ghz:.1f} GHz"
        p.drawText(QRectF(x, freq_y, w, 16), Qt.AlignCenter, freq_text)

    def _draw_direction_arrow(self, p, x, y, w, h, direction, active, band_color):
        """Draw a triangular direction indicator."""
        cx = x + w / 2
        cy = y + h / 2
        size = min(w, h) * 0.35

        if active:
            p.setPen(Qt.NoPen)
            p.setBrush(band_color)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(DIM))

        if direction == AlertDirection.FRONT:
            # Upward triangle
            poly = QPolygonF([
                QPointF(cx, cy - size),
                QPointF(cx - size * 0.7, cy + size * 0.5),
                QPointF(cx + size * 0.7, cy + size * 0.5),
            ])
        elif direction == AlertDirection.REAR:
            # Downward triangle
            poly = QPolygonF([
                QPointF(cx, cy + size),
                QPointF(cx - size * 0.7, cy - size * 0.5),
                QPointF(cx + size * 0.7, cy - size * 0.5),
            ])
        else:
            # Side — diamond
            poly = QPolygonF([
                QPointF(cx, cy - size * 0.6),
                QPointF(cx + size * 0.6, cy),
                QPointF(cx, cy + size * 0.6),
                QPointF(cx - size * 0.6, cy),
            ])

        p.drawPolygon(poly)

        # Tiny label below arrow
        label_font = QFont("Helvetica", 6)
        p.setFont(label_font)
        label_color = band_color if active else QColor(DIM)
        p.setPen(QPen(label_color))
        labels = {
            AlertDirection.FRONT: "FRT",
            AlertDirection.SIDE: "SDE",
            AlertDirection.REAR: "RER",
        }
        # No label text to keep it clean — the arrows speak for themselves

    def _draw_signal_bar(self, p, x, y, w, h, alert):
        """8-segment vertical signal strength bar + numeric."""
        num_segments = 8
        seg_gap = 2
        margin_x = 12
        margin_top = 8
        margin_bot = 18
        available_h = h - margin_top - margin_bot
        seg_h = (available_h - (num_segments - 1) * seg_gap) / num_segments
        bar_w = w - margin_x * 2

        signal = 0
        if alert:
            signal = max(alert.front_signal, alert.rear_signal)

        for i in range(num_segments):
            seg_idx = num_segments - 1 - i  # Draw from top (8) to bottom (1)
            sy = y + margin_top + i * (seg_h + seg_gap)
            lit = seg_idx < signal

            if lit:
                # Color: green 0-2, yellow 3-5, red 6-7
                if seg_idx < 3:
                    color = QColor("#00CC66")
                elif seg_idx < 6:
                    color = QColor("#FFAA00")
                else:
                    color = QColor("#FF3333")
            else:
                color = QColor(DIM)

            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x + margin_x, sy, bar_w, seg_h), 1, 1)

        # Signal number at bottom
        if alert and signal > 0:
            num_font = QFont("Helvetica", 9, QFont.Bold)
            p.setFont(num_font)
            p.setPen(QPen(QColor(WHITE)))
            p.drawText(
                QRectF(x, y + h - margin_bot + 2, w, margin_bot - 2),
                Qt.AlignCenter, str(signal)
            )
