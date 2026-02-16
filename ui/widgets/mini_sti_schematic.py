"""KiSTI - Mini STI Schematic Widget

Compact top-down 2014 STI hatchback with color-changing overlay nodes.
Tire temps at corners, brake discs inside wheels, oil PSI + temp at engine bay.
Numeric readouts on each node — designed for STREET mode right panel.
"""

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_DARK, HIGHLIGHT, CHERRY, WHITE, GRAY, DIM,
    CHROME_DARK, CHROME_MID,
    TIRE_GREEN, TIRE_YELLOW, TIRE_RED,
)
from config import (
    TIRE_TEMP_GREEN_MAX, TIRE_TEMP_YELLOW_MAX,
    BRAKE_TEMP_GREEN_MAX, BRAKE_TEMP_YELLOW_MAX,
    OIL_PSI_LOW_WARN, OIL_PSI_LOW_CRIT, OIL_PSI_HIGH_WARN,
    OIL_TEMP_WARN,
)


def _heat_color(temp_c, cold, optimal, warm, hot):
    if temp_c <= cold:
        return QColor(80, 180, 255)
    elif temp_c <= optimal:
        t = (temp_c - cold) / max(1, optimal - cold)
        return QColor(int(80 * (1 - t)), int(180 * (1 - t) + 200 * t), int(255 * (1 - t) + 80 * t))
    elif temp_c <= warm:
        t = (temp_c - optimal) / max(1, warm - optimal)
        return QColor(int(255 * t), int(200 * (1 - t) + 170 * t), int(80 * (1 - t)))
    else:
        t = min(1.0, (temp_c - warm) / max(1, hot - warm))
        return QColor(255, int(170 * (1 - t) + 30 * t), 0)


def _tire_heat_color(temp_c):
    return _heat_color(temp_c, 75, TIRE_TEMP_GREEN_MAX, TIRE_TEMP_YELLOW_MAX, TIRE_TEMP_YELLOW_MAX + 20)


def _brake_heat_color(temp_c):
    return _heat_color(temp_c, 150, BRAKE_TEMP_GREEN_MAX, BRAKE_TEMP_YELLOW_MAX, BRAKE_TEMP_YELLOW_MAX + 100)


def _oil_heat_color(temp_c):
    return _heat_color(temp_c, 70, 100, OIL_TEMP_WARN, OIL_TEMP_WARN + 20)


def _oil_psi_color(psi):
    if psi <= OIL_PSI_LOW_CRIT or psi >= 100:
        return QColor(TIRE_RED)
    if psi <= OIL_PSI_LOW_WARN or psi >= OIL_PSI_HIGH_WARN:
        return QColor(TIRE_YELLOW)
    return QColor(TIRE_GREEN)


_WHEEL_CENTERS = {
    "FL": (0.11, 0.16),
    "FR": (0.89, 0.16),
    "RL": (0.11, 0.74),
    "RR": (0.89, 0.74),
}


class MiniStiSchematic(QWidget):
    """Compact STI top-down schematic with color-changing sensor nodes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._corners = {
            "FL": (85.0, 250.0, 1.0),
            "FR": (85.0, 250.0, 1.0),
            "RL": (85.0, 250.0, 1.0),
            "RR": (85.0, 250.0, 1.0),
        }
        self._oil_psi = 45.0
        self._oil_temp = 95.0

    def update_data(self, vehicle_state):
        for name in ("FL", "FR", "RL", "RR"):
            if name in vehicle_state.corners:
                cd = vehicle_state.corners[name]
                self._corners[name] = (cd.tire_temp_c, cd.brake_temp_c, cd.tire_wear_pct)
        self._oil_psi = vehicle_state.oil.psi
        self._oil_temp = vehicle_state.oil.temp_c
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # Fit car — 2.3:1 aspect, with padding for readouts
        pad_x, pad_top, pad_bot = 6, 6, 6
        avail_w = w - pad_x * 2
        avail_h = h - pad_top - pad_bot
        car_aspect = 2.3

        if avail_h / avail_w > car_aspect:
            car_w = avail_w
            car_h = car_w * car_aspect
        else:
            car_h = avail_h
            car_w = car_h / car_aspect

        car_x = (w - car_w) / 2
        car_y = pad_top + (avail_h - car_h) / 2

        # Heat zones (behind car)
        self._draw_heat_zones(p, car_x, car_y, car_w, car_h)

        # Car body
        self._draw_body(p, car_x, car_y, car_w, car_h)

        # Wheels with brake discs
        self._draw_wheels(p, car_x, car_y, car_w, car_h)

        # Numeric readouts at each corner
        self._draw_readouts(p, car_x, car_y, car_w, car_h)

        # Engine bay readout
        self._draw_engine(p, car_x, car_y, car_w, car_h)

        p.end()

    def _draw_body(self, p, cx, cy, cw, ch):
        """Simplified STI hatch silhouette."""
        body = QPainterPath()

        # Front bumper
        body.moveTo(cx + cw * 0.25, cy + ch * 0.02)
        body.quadTo(cx + cw * 0.5, cy - cw * 0.03, cx + cw * 0.75, cy + ch * 0.02)

        # Right side
        body.lineTo(cx + cw * 0.82, cy + ch * 0.05)
        body.quadTo(cx + cw * 0.90, cy + ch * 0.10, cx + cw * 0.87, cy + ch * 0.20)
        body.quadTo(cx + cw * 0.83, cy + ch * 0.30, cx + cw * 0.81, cy + ch * 0.42)
        body.quadTo(cx + cw * 0.83, cy + ch * 0.55, cx + cw * 0.90, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.92, cy + ch * 0.72, cx + cw * 0.88, cy + ch * 0.80)

        # Rear
        body.lineTo(cx + cw * 0.84, cy + ch * 0.90)
        body.quadTo(cx + cw * 0.78, cy + ch * 0.95, cx + cw * 0.5, cy + ch * 0.96)
        body.quadTo(cx + cw * 0.22, cy + ch * 0.95, cx + cw * 0.16, cy + ch * 0.90)

        # Left side
        body.lineTo(cx + cw * 0.12, cy + ch * 0.80)
        body.quadTo(cx + cw * 0.08, cy + ch * 0.72, cx + cw * 0.10, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.17, cy + ch * 0.55, cx + cw * 0.19, cy + ch * 0.42)
        body.quadTo(cx + cw * 0.17, cy + ch * 0.30, cx + cw * 0.13, cy + ch * 0.20)
        body.quadTo(cx + cw * 0.10, cy + ch * 0.10, cx + cw * 0.18, cy + ch * 0.05)

        body.closeSubpath()

        # Fill
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 15, 15, 160))
        p.drawPath(body)

        # Outline
        p.setPen(QPen(QColor(CHROME_MID), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(body)

        # Windshield
        p.setPen(QPen(QColor(CHROME_DARK), 0.8))
        p.drawLine(int(cx + cw * 0.26), int(cy + ch * 0.20), int(cx + cw * 0.32), int(cy + ch * 0.30))
        p.drawLine(int(cx + cw * 0.74), int(cy + ch * 0.20), int(cx + cw * 0.68), int(cy + ch * 0.30))
        p.drawLine(int(cx + cw * 0.32), int(cy + ch * 0.30), int(cx + cw * 0.68), int(cy + ch * 0.30))

        # Rear hatch window
        p.drawLine(int(cx + cw * 0.32), int(cy + ch * 0.68), int(cx + cw * 0.34), int(cy + ch * 0.80))
        p.drawLine(int(cx + cw * 0.68), int(cy + ch * 0.68), int(cx + cw * 0.66), int(cy + ch * 0.80))
        p.drawLine(int(cx + cw * 0.34), int(cy + ch * 0.80), int(cx + cw * 0.66), int(cy + ch * 0.80))

        # Hood scoop
        scoop = QPainterPath()
        scoop.moveTo(cx + cw * 0.42, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.58, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.56, cy + ch * 0.17)
        scoop.lineTo(cx + cw * 0.44, cy + ch * 0.17)
        scoop.closeSubpath()
        p.setPen(QPen(QColor(CHROME_DARK), 0.8))
        p.setBrush(QColor(20, 20, 20))
        p.drawPath(scoop)

        # Rear spoiler
        p.setPen(QPen(QColor(CHROME_MID), 1.5))
        p.drawLine(int(cx + cw * 0.18), int(cy + ch * 0.87), int(cx + cw * 0.82), int(cy + ch * 0.87))

        # Center line
        p.setPen(QPen(QColor(DIM), 0.5, Qt.DotLine))
        p.drawLine(int(cx + cw * 0.5), int(cy + ch * 0.02), int(cx + cw * 0.5), int(cy + ch * 0.96))

    def _draw_wheels(self, p, cx, cy, cw, ch):
        """Draw wheel outlines with brake disc glow."""
        wheel_w = cw * 0.14
        wheel_h = cw * 0.26

        for name, (wcx_n, wcy_n) in _WHEEL_CENTERS.items():
            tire_t, brake_t, wear = self._corners[name]
            tire_color = _tire_heat_color(tire_t)
            brake_color = _brake_heat_color(brake_t)

            wx = cx + wcx_n * cw - wheel_w / 2
            wy = cy + wcy_n * ch - wheel_h / 2

            # Tire outline
            rect = QRectF(wx, wy, wheel_w, wheel_h)
            p.setPen(QPen(tire_color.darker(120), 1.2))
            p.setBrush(QColor(0, 0, 0, 80))
            p.drawRoundedRect(rect, 3, 3)

            # Brake disc glow
            disc_r = min(wheel_w, wheel_h) * 0.28
            disc_cx = wx + wheel_w / 2
            disc_cy = wy + wheel_h / 2

            glow = QRadialGradient(QPointF(disc_cx, disc_cy), disc_r * 1.4)
            gc = QColor(brake_color)
            gc.setAlpha(90)
            glow.setColorAt(0.0, gc)
            gf = QColor(brake_color)
            gf.setAlpha(0)
            glow.setColorAt(1.0, gf)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(disc_cx, disc_cy), disc_r * 1.4, disc_r * 1.4)

            # Disc solid
            p.setPen(QPen(brake_color.darker(140), 0.8))
            p.setBrush(QColor(brake_color.red(), brake_color.green(), brake_color.blue(), 130))
            p.drawEllipse(QPointF(disc_cx, disc_cy), disc_r, disc_r)

            # Low wear indicator
            if wear < 0.5:
                wc = QColor(TIRE_YELLOW) if wear > 0.25 else QColor(TIRE_RED)
                wc.setAlpha(180)
                p.setPen(Qt.NoPen)
                p.setBrush(wc)
                p.drawRect(QRectF(wx + 1, wy + wheel_h - 2, wheel_w - 2, 1.5))

    def _draw_heat_zones(self, p, cx, cy, cw, ch):
        """Radial heat glow behind each sensor point."""
        tire_r = max(cw, ch) * 0.16

        for name, (wcx_n, wcy_n) in _WHEEL_CENTERS.items():
            tire_t, brake_t, _ = self._corners[name]
            center = QPointF(cx + wcx_n * cw, cy + wcy_n * ch)

            # Tire heat
            color = _tire_heat_color(tire_t)
            intensity = min(180, max(60, int(60 + (tire_t - 70) * 2.4)))
            color.setAlpha(intensity)

            grad = QRadialGradient(center, tire_r)
            grad.setColorAt(0.0, color)
            mid = QColor(color)
            mid.setAlpha(intensity // 3)
            grad.setColorAt(0.5, mid)
            fade = QColor(color)
            fade.setAlpha(0)
            grad.setColorAt(1.0, fade)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(center, tire_r, tire_r)

        # Engine heat
        ec = QPointF(cx + cw * 0.5, cy + ch * 0.12)
        er = max(cw, ch) * 0.12
        ecolor = _oil_heat_color(self._oil_temp)
        ei = min(130, max(20, int(30 + (self._oil_temp - 70) * 1.6)))
        ecolor.setAlpha(ei)

        eg = QRadialGradient(ec, er)
        eg.setColorAt(0.0, ecolor)
        em = QColor(ecolor)
        em.setAlpha(ei // 3)
        eg.setColorAt(0.5, em)
        ef = QColor(ecolor)
        ef.setAlpha(0)
        eg.setColorAt(1.0, ef)
        p.setBrush(QBrush(eg))
        p.drawEllipse(ec, er, er)

    def _draw_readouts(self, p, cx, cy, cw, ch):
        """Numeric readouts next to each wheel — tire temp + brake temp."""
        # Left corners: readout to the left, right corners: readout to the right
        positions = {
            "FL": ("left", 0.11, 0.16),
            "FR": ("right", 0.89, 0.16),
            "RL": ("left", 0.11, 0.74),
            "RR": ("right", 0.89, 0.74),
        }

        for name, (side, wcx_n, wcy_n) in positions.items():
            tire_t, brake_t, _ = self._corners[name]
            tire_color = _tire_heat_color(tire_t)
            brake_color = _brake_heat_color(brake_t)

            # Position readout box
            box_w = cw * 0.30
            box_h = cw * 0.30
            wy = cy + wcy_n * ch - box_h / 2

            if side == "left":
                # Left of car body — far left
                bx = cx - box_w + cw * 0.04
            else:
                # Right of car body — far right
                bx = cx + cw * 0.96

            # Corner label
            p.setFont(QFont("Helvetica", 7, QFont.Bold))
            p.setPen(QPen(QColor(WHITE)))
            align = Qt.AlignLeft if side == "right" else Qt.AlignRight
            p.drawText(QRectF(bx, wy - 2, box_w, 12), align | Qt.AlignBottom, name)

            # Tire temp
            p.setFont(QFont("Helvetica", 11, QFont.Bold))
            p.setPen(QPen(tire_color))
            p.drawText(QRectF(bx, wy + 10, box_w, 16), align | Qt.AlignVCenter,
                       f"{tire_t:.0f}\u00b0")

            # Brake temp (smaller, below)
            p.setFont(QFont("Helvetica", 8))
            p.setPen(QPen(brake_color))
            p.drawText(QRectF(bx, wy + 26, box_w, 14), align | Qt.AlignVCenter,
                       f"B {brake_t:.0f}\u00b0")

    def _draw_engine(self, p, cx, cy, cw, ch):
        """Oil PSI + temp readout at engine bay."""
        psi_color = _oil_psi_color(self._oil_psi)
        temp_color = _oil_heat_color(self._oil_temp)

        # Engine bay area — centered, below hood scoop
        ex = cx + cw * 0.32
        ew = cw * 0.36
        ey = cy + ch * 0.20

        # "OIL" label
        p.setFont(QFont("Helvetica", 7, QFont.Bold))
        p.setPen(QPen(QColor(HIGHLIGHT)))
        p.drawText(QRectF(ex, ey, ew, 12), Qt.AlignCenter, "OIL")

        # PSI
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        p.setPen(QPen(psi_color))
        p.drawText(QRectF(ex, ey + 11, ew / 2, 16), Qt.AlignCenter,
                   f"{self._oil_psi:.0f}")

        # Temp
        p.setFont(QFont("Helvetica", 10))
        p.setPen(QPen(temp_color))
        p.drawText(QRectF(ex + ew / 2, ey + 12, ew / 2, 16), Qt.AlignCenter,
                   f"{self._oil_temp:.0f}\u00b0")

        # Units (tiny)
        p.setFont(QFont("Helvetica", 6))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(ex, ey + 27, ew / 2, 10), Qt.AlignCenter, "PSI")
        p.drawText(QRectF(ex + ew / 2, ey + 27, ew / 2, 10), Qt.AlignCenter, "\u00b0C")
