"""KiSTI - 2014 STI Hatchback Schematic Heatmap Widget

Top-down 2014 Subaru WRX STI 5-door hatchback silhouette with thermal
heatmap overlay. Each sensor zone (FL/FR/RL/RR tires + brakes, engine)
rendered as radial gradient heat signatures — no numbers, pure visual.
Detailed readouts available in pit summary.
"""

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
    QRadialGradient, QLinearGradient,
)
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_DARK, BG_PANEL, HIGHLIGHT, CHERRY, WHITE, GRAY, DIM,
    CHROME_DARK, CHROME_MID,
    TIRE_BLUE, TIRE_GREEN, TIRE_YELLOW, TIRE_RED,
)
from config import (
    TIRE_TEMP_GREEN_MAX, TIRE_TEMP_YELLOW_MAX,
    BRAKE_TEMP_GREEN_MAX, BRAKE_TEMP_YELLOW_MAX,
    OIL_TEMP_WARN,
)


def _heat_color(temp_c, cold=70, optimal=90, warm=105, hot=120):
    """Return a heatmap color for a temperature value.

    Blue (cold) -> Green (optimal) -> Yellow (warm) -> Red (hot).
    Returns QColor with full opacity.
    """
    if temp_c <= cold:
        return QColor(80, 180, 255)  # Light blue for cold — visible on dark bg
    elif temp_c <= optimal:
        t = (temp_c - cold) / max(1, optimal - cold)
        r = int(80 * (1 - t) + 0 * t)
        g = int(180 * (1 - t) + 200 * t)
        b = int(255 * (1 - t) + 80 * t)
        return QColor(r, g, b)
    elif temp_c <= warm:
        t = (temp_c - optimal) / max(1, warm - optimal)
        r = int(0 * (1 - t) + 255 * t)
        g = int(200 * (1 - t) + 170 * t)
        b = int(80 * (1 - t) + 0 * t)
        return QColor(r, g, b)
    else:
        t = min(1.0, (temp_c - warm) / max(1, hot - warm))
        r = 255
        g = int(170 * (1 - t) + 30 * t)
        b = int(0 * (1 - t) + 0 * t)
        return QColor(r, g, b)


def _tire_heat_color(temp_c):
    """Tire-specific heat color. Blue when cold, red when overheating."""
    return _heat_color(temp_c, cold=75, optimal=TIRE_TEMP_GREEN_MAX,
                       warm=TIRE_TEMP_YELLOW_MAX, hot=TIRE_TEMP_YELLOW_MAX + 20)


def _brake_heat_color(temp_c):
    """Brake-specific heat color (higher range)."""
    return _heat_color(temp_c, cold=150, optimal=BRAKE_TEMP_GREEN_MAX,
                       warm=BRAKE_TEMP_YELLOW_MAX, hot=BRAKE_TEMP_YELLOW_MAX + 100)


def _oil_heat_color(temp_c):
    """Engine/oil heat color."""
    return _heat_color(temp_c, cold=70, optimal=100, warm=OIL_TEMP_WARN,
                       hot=OIL_TEMP_WARN + 20)


# Wheel center positions (normalized to car bbox) — shared by multiple methods
# These define where tires sit on the hatch body
_WHEEL_CENTERS = {
    "FL": (0.11, 0.16),
    "FR": (0.89, 0.16),
    "RL": (0.11, 0.74),
    "RR": (0.89, 0.74),
}


class StiHeatmapWidget(QWidget):
    """Top-down 2014 STI hatchback silhouette with thermal heatmap overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Corner data: {name: (tire_temp, brake_temp, tire_wear)}
        self._corners = {
            "FL": (85.0, 250.0, 1.0),
            "FR": (85.0, 250.0, 1.0),
            "RL": (85.0, 250.0, 1.0),
            "RR": (85.0, 250.0, 1.0),
        }
        self._oil_temp = 95.0

    def update_data(self, vehicle_state):
        """Update from VehicleState."""
        for name in ("FL", "FR", "RL", "RR"):
            if name in vehicle_state.corners:
                cd = vehicle_state.corners[name]
                self._corners[name] = (cd.tire_temp_c, cd.brake_temp_c, cd.tire_wear_pct)
        self._oil_temp = vehicle_state.oil.temp_c
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Chrome border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Calculate car dimensions - centered, with padding
        pad = 16
        # Hatchback is slightly shorter than sedan — ~2.3:1 aspect
        avail_w = w - 2 * pad
        avail_h = h - 2 * pad - 16  # 16px for header
        car_aspect = 2.3

        # Fit car into available space
        if avail_h / avail_w > car_aspect:
            car_w = avail_w
            car_h = car_w * car_aspect
        else:
            car_h = avail_h
            car_w = car_h / car_aspect

        car_x = (w - car_w) / 2
        car_y = pad + 16 + (avail_h - car_h) / 2

        # Header label
        p.setPen(QColor(HIGHLIGHT))
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.drawText(pad, pad + 12, "THERMAL MAP")

        # -- Draw heatmap zones FIRST (behind the car) --
        self._draw_heat_zones(p, car_x, car_y, car_w, car_h)

        # -- Draw STI hatchback silhouette outline --
        self._draw_sti_hatch_body(p, car_x, car_y, car_w, car_h)

        # -- Draw wheel positions with brake discs inside --
        self._draw_wheels_and_brakes(p, car_x, car_y, car_w, car_h)

        # -- Corner labels --
        self._draw_corner_labels(p, car_x, car_y, car_w, car_h)

        p.end()

    def _draw_sti_hatch_body(self, p, cx, cy, cw, ch):
        """Draw 2014 STI 5-door hatchback top-down silhouette."""
        body = QPainterPath()

        # Front bumper — wider, aggressive nose
        body.moveTo(cx + cw * 0.25, cy + ch * 0.02)
        body.quadTo(cx + cw * 0.5, cy - cw * 0.03,
                    cx + cw * 0.75, cy + ch * 0.02)

        # Right side — front fender flare (STI wide body)
        body.lineTo(cx + cw * 0.82, cy + ch * 0.05)
        body.quadTo(cx + cw * 0.90, cy + ch * 0.10,
                    cx + cw * 0.87, cy + ch * 0.20)

        # Right side — door/B-pillar pinch
        body.quadTo(cx + cw * 0.83, cy + ch * 0.30,
                    cx + cw * 0.81, cy + ch * 0.42)

        # Right side — rear quarter panel flare (hatch is wide here)
        body.quadTo(cx + cw * 0.83, cy + ch * 0.55,
                    cx + cw * 0.90, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.92, cy + ch * 0.72,
                    cx + cw * 0.88, cy + ch * 0.80)

        # Rear — hatchback squared-off tail (shorter overhang than sedan)
        body.lineTo(cx + cw * 0.84, cy + ch * 0.90)
        body.quadTo(cx + cw * 0.78, cy + ch * 0.95,
                    cx + cw * 0.5, cy + ch * 0.96)
        body.quadTo(cx + cw * 0.22, cy + ch * 0.95,
                    cx + cw * 0.16, cy + ch * 0.90)

        # Left side — rear fender flare
        body.lineTo(cx + cw * 0.12, cy + ch * 0.80)
        body.quadTo(cx + cw * 0.08, cy + ch * 0.72,
                    cx + cw * 0.10, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.17, cy + ch * 0.55,
                    cx + cw * 0.19, cy + ch * 0.42)

        # Left side — door/B-pillar pinch
        body.quadTo(cx + cw * 0.17, cy + ch * 0.30,
                    cx + cw * 0.13, cy + ch * 0.20)

        # Left side — front fender flare
        body.quadTo(cx + cw * 0.10, cy + ch * 0.10,
                    cx + cw * 0.18, cy + ch * 0.05)

        body.closeSubpath()

        # Fill body with very dark semi-transparent
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 15, 15, 160))
        p.drawPath(body)

        # Body outline — chrome
        p.setPen(QPen(QColor(CHROME_MID), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(body)

        # -- Interior details --

        # Windshield (A-pillars converging forward)
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(int(cx + cw * 0.24), int(cy + ch * 0.20),
                   int(cx + cw * 0.30), int(cy + ch * 0.30))
        p.drawLine(int(cx + cw * 0.76), int(cy + ch * 0.20),
                   int(cx + cw * 0.70), int(cy + ch * 0.30))
        # Windshield top edge
        p.drawLine(int(cx + cw * 0.30), int(cy + ch * 0.30),
                   int(cx + cw * 0.70), int(cy + ch * 0.30))

        # Rear hatch window — wider and more steeply raked than sedan
        # D-pillars angle inward more aggressively on the hatch
        p.drawLine(int(cx + cw * 0.30), int(cy + ch * 0.68),
                   int(cx + cw * 0.32), int(cy + ch * 0.80))
        p.drawLine(int(cx + cw * 0.70), int(cy + ch * 0.68),
                   int(cx + cw * 0.68), int(cy + ch * 0.80))
        # Hatch glass bottom edge
        p.drawLine(int(cx + cw * 0.32), int(cy + ch * 0.80),
                   int(cx + cw * 0.68), int(cy + ch * 0.80))

        # Roof rails (hatch has them — C-pillar to D-pillar)
        p.setPen(QPen(QColor(DIM), 1, Qt.DashLine))
        p.drawLine(int(cx + cw * 0.30), int(cy + ch * 0.30),
                   int(cx + cw * 0.30), int(cy + ch * 0.68))
        p.drawLine(int(cx + cw * 0.70), int(cy + ch * 0.30),
                   int(cx + cw * 0.70), int(cy + ch * 0.68))

        # Hood scoop (iconic STI feature — centered on hood)
        scoop = QPainterPath()
        scoop.moveTo(cx + cw * 0.42, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.58, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.56, cy + ch * 0.17)
        scoop.lineTo(cx + cw * 0.44, cy + ch * 0.17)
        scoop.closeSubpath()
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(QColor(20, 20, 20))
        p.drawPath(scoop)

        # Rear spoiler / wing (STI hatch wing sits at roofline-tailgate junction)
        spoiler_y = cy + ch * 0.87
        p.setPen(QPen(QColor(CHROME_MID), 2))
        p.drawLine(int(cx + cw * 0.16), int(spoiler_y),
                   int(cx + cw * 0.84), int(spoiler_y))
        # Spoiler endplates (wider on hatch)
        p.setPen(QPen(QColor(CHROME_MID), 1.5))
        p.drawLine(int(cx + cw * 0.16), int(spoiler_y - 4),
                   int(cx + cw * 0.16), int(spoiler_y + 4))
        p.drawLine(int(cx + cw * 0.84), int(spoiler_y - 4),
                   int(cx + cw * 0.84), int(spoiler_y + 4))

        # Hatch seam line (where the hatch opens)
        p.setPen(QPen(QColor(DIM), 0.5))
        p.drawLine(int(cx + cw * 0.22), int(cy + ch * 0.84),
                   int(cx + cw * 0.78), int(cy + ch * 0.84))

        # Center line (subtle)
        p.setPen(QPen(QColor(DIM), 0.5, Qt.DotLine))
        p.drawLine(int(cx + cw * 0.5), int(cy + ch * 0.02),
                   int(cx + cw * 0.5), int(cy + ch * 0.96))

    def _draw_wheels_and_brakes(self, p, cx, cy, cw, ch):
        """Draw wheel outlines with brake disc indicators just inside each tire."""
        wheel_w = cw * 0.14
        wheel_h = cw * 0.26

        for name, (wcx_n, wcy_n) in _WHEEL_CENTERS.items():
            tire_t, brake_t, wear = self._corners[name]
            tire_color = _tire_heat_color(tire_t)
            brake_color = _brake_heat_color(brake_t)

            # Wheel top-left position from center
            wx = cx + wcx_n * cw - wheel_w / 2
            wy = cy + wcy_n * ch - wheel_h / 2

            # -- Tire outline --
            rect = QRectF(wx, wy, wheel_w, wheel_h)
            p.setPen(QPen(tire_color.darker(120), 1.5))
            p.setBrush(QColor(0, 0, 0, 80))
            p.drawRoundedRect(rect, 3, 3)

            # -- Brake disc inside tire (inboard side) --
            # Small circle/oval representing the brake rotor, inside the wheel
            disc_r = min(wheel_w, wheel_h) * 0.28
            disc_cx = wx + wheel_w / 2
            disc_cy = wy + wheel_h / 2

            # Brake disc glow
            disc_glow = QRadialGradient(QPointF(disc_cx, disc_cy), disc_r * 1.6)
            glow_color = QColor(brake_color)
            glow_color.setAlpha(100)
            disc_glow.setColorAt(0.0, glow_color)
            fade = QColor(brake_color)
            fade.setAlpha(0)
            disc_glow.setColorAt(1.0, fade)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(disc_glow))
            p.drawEllipse(QPointF(disc_cx, disc_cy), disc_r * 1.6, disc_r * 1.6)

            # Brake disc solid
            p.setPen(QPen(brake_color.darker(140), 1))
            p.setBrush(QColor(brake_color.red(), brake_color.green(), brake_color.blue(), 140))
            p.drawEllipse(QPointF(disc_cx, disc_cy), disc_r, disc_r)

            # Wear indicator — thin bar at bottom of wheel
            if wear < 0.5:
                warn_color = QColor(TIRE_YELLOW) if wear > 0.25 else QColor(TIRE_RED)
                warn_color.setAlpha(180)
                p.setPen(Qt.NoPen)
                p.setBrush(warn_color)
                p.drawRect(QRectF(wx + 1, wy + wheel_h - 3, wheel_w - 2, 2))

    def _draw_heat_zones(self, p, cx, cy, cw, ch):
        """Draw radial gradient heat signatures at each sensor point."""
        tire_radius = max(cw, ch) * 0.20

        for name, (wcx_n, wcy_n) in _WHEEL_CENTERS.items():
            tire_t, brake_t, wear = self._corners[name]
            center = QPointF(cx + wcx_n * cw, cy + wcy_n * ch)

            # -- Tire heat glow --
            color = _tire_heat_color(tire_t)
            intensity = min(200, max(80, int(80 + (tire_t - 70) * 2.4)))
            color.setAlpha(intensity)

            grad = QRadialGradient(center, tire_radius)
            grad.setColorAt(0.0, color)
            mid_color = QColor(color)
            mid_color.setAlpha(intensity // 2)
            grad.setColorAt(0.4, mid_color)
            fade_color = QColor(color)
            fade_color.setAlpha(0)
            grad.setColorAt(1.0, fade_color)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(center, tire_radius, tire_radius)

            # -- Brake heat glow (same center, tighter radius) --
            brake_radius = tire_radius * 0.5
            bcolor = _brake_heat_color(brake_t)
            b_intensity = min(180, max(30, int(50 + (brake_t - 150) * 0.5)))
            bcolor.setAlpha(b_intensity)

            bgrad = QRadialGradient(center, brake_radius)
            bgrad.setColorAt(0.0, bcolor)
            bmid = QColor(bcolor)
            bmid.setAlpha(b_intensity // 3)
            bgrad.setColorAt(0.5, bmid)
            bfade = QColor(bcolor)
            bfade.setAlpha(0)
            bgrad.setColorAt(1.0, bfade)

            p.setBrush(QBrush(bgrad))
            p.drawEllipse(center, brake_radius, brake_radius)

        # Engine bay heat zone — centered front
        engine_center = QPointF(cx + cw * 0.5, cy + ch * 0.12)
        engine_radius = max(cw, ch) * 0.14
        engine_color = _oil_heat_color(self._oil_temp)
        intensity = min(150, max(25, int(40 + (self._oil_temp - 70) * 1.8)))
        engine_color.setAlpha(intensity)

        grad = QRadialGradient(engine_center, engine_radius)
        grad.setColorAt(0.0, engine_color)
        mid_color = QColor(engine_color)
        mid_color.setAlpha(intensity // 3)
        grad.setColorAt(0.5, mid_color)
        fade_color = QColor(engine_color)
        fade_color.setAlpha(0)
        grad.setColorAt(1.0, fade_color)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(engine_center, engine_radius, engine_radius)

    def _draw_corner_labels(self, p, cx, cy, cw, ch):
        """Draw small corner name labels near each wheel."""
        p.setFont(QFont("Helvetica", 7, QFont.Bold))

        # Offset labels outside the wheels
        label_offsets = {
            "FL": (-0.06, -0.06),
            "FR": (0.03, -0.06),
            "RL": (-0.06, 0.06),
            "RR": (0.03, 0.06),
        }

        for name, (wcx_n, wcy_n) in _WHEEL_CENTERS.items():
            tire_t, brake_t, wear = self._corners[name]
            color = _tire_heat_color(tire_t)
            p.setPen(color)
            ox, oy = label_offsets[name]
            lx = cx + (wcx_n + ox) * cw
            ly = cy + (wcy_n + oy) * ch
            p.drawText(int(lx), int(ly), name)

        # Engine label
        p.setPen(QColor(_oil_heat_color(self._oil_temp)))
        p.setFont(QFont("Helvetica", 6))
        p.drawText(int(cx + cw * 0.43), int(cy + ch * 0.22), "ENG")
