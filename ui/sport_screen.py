"""KiSTI - Sport Mode Screen (SI-Drive = 1)

Performance / fast-road screen. Medium density: boost arc gauge,
G-force circle with trail, DCCD/brake/throttle bars, wheel speed
deltas, inline sparklines for oil + coolant.

800x440 content area, 100% QPainter — no composite QWidget layouts.
Designed for spirited driving: readable at a glance.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QConicalGradient,
)
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState
from ui.theme import (
    BG_DARK,
    BG_PANEL,
    BG_ACCENT,
    WHITE,
    SILVER,
    GRAY,
    DIM,
    GREEN,
    YELLOW,
    RED,
    CYAN,
    CHERRY,
    CHROME_DARK,
    MODE_S_ACCENT,
    FONT_BASE,
    FONT_HEADER,
    FONT_BIG,
    FONT_XLARGE,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Boost gauge range (kPa above atmosphere = gauge pressure)
_BOOST_MIN_KPA = -30.0
_BOOST_MAX_KPA = 200.0
_BOOST_RED_KPA = 180.0
_BOOST_TICKS = [0, 50, 100, 150, 200]

# G-force circle
_G_CENTER_X = 600
_G_CENTER_Y = 210
_G_RADIUS = 100          # pixels for 1.0g ring
_G_RING_05 = 50          # pixels for 0.5g ring
_G_MAX = 1.5             # clamp

# Wheel speed delta thresholds (km/h)
_WS_MODERATE = 2.0
_WS_SEVERE = 5.0

# Lambda display
_LAMBDA_RICH = 0.85
_LAMBDA_LEAN = 1.15
_LAMBDA_TARGET = 1.0

# Injector duty warning thresholds
_IDC_WARN = 80.0
_IDC_CRIT = 90.0

# Brake bar max
_BRAKE_MAX_BAR = 80.0

# Sparkline dimensions
_SPARK_W = 130
_SPARK_H = 16


class SportScreenWidget(QWidget):
    """Sport mode (SI-Drive=1): boost arc, G-force, performance bars."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._snap: Optional[DiffState] = None

        # History buffers — 5 seconds at 20 Hz
        self._oil_history: deque[float] = deque(maxlen=100)
        self._coolant_history: deque[float] = deque(maxlen=100)

        # G-force dot trail
        self._g_trail: deque[tuple[float, float]] = deque(maxlen=100)

        self.setMinimumSize(800, 440)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Called at 20 Hz from main timer with a DiffState snapshot."""
        self._snap = snap
        self._oil_history.append(snap.oil_psi)
        self._coolant_history.append(snap.coolant_temp)
        # lateral (Y axis on screen) = imu_accel_y, longitudinal (X on screen) = imu_accel_x
        self._g_trail.append((snap.imu_accel_y, snap.imu_accel_x))
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Use real snap or a default empty one for layout painting
        snap = self._snap if self._snap is not None else DiffState()
        engine_stale = True if self._snap is None else snap.is_engine_stale()
        diff_stale = True if self._snap is None else snap.is_diff_stale()

        # --- Top band (y=0..100) ---
        self._paint_gear_speed(p, snap, engine_stale)
        self._paint_boost_arc(p, snap, engine_stale)
        self._paint_oil_coolant_fuel(p, snap, engine_stale)

        # Separator
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, 100, w, 100)

        # --- Middle band (y=100..320) ---
        self._paint_performance_bars(p, snap, engine_stale, diff_stale)
        self._paint_g_force_circle(p, snap)

        # Separator
        p.drawLine(0, 320, w, 320)

        # --- Bottom band (y=320..440) ---
        self._paint_wheel_speeds(p, snap)

        p.end()

    # ------------------------------------------------------------------
    # Top band: Gear + Speed + RPM (left)
    # ------------------------------------------------------------------

    def _paint_gear_speed(
        self, p: QPainter, snap: DiffState, stale: bool
    ) -> None:
        text_color = QColor(GRAY) if stale else QColor(WHITE)
        dim_color = QColor(GRAY)

        # Gear — large bold
        gear_str = str(snap.gear) if snap.gear > 0 else "N"
        if stale:
            gear_str = "---"

        p.setFont(QFont("Helvetica", 56, QFont.Weight.Bold))
        p.setPen(QPen(text_color))
        p.drawText(QRectF(8, 2, 150, 60), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, gear_str)

        # Speed — cyan
        speed_str = f"{snap.speed_kph:.0f}" if not stale else "---"
        p.setFont(QFont("Helvetica", 24, QFont.Weight.Bold))
        p.setPen(QPen(QColor(CYAN) if not stale else dim_color))
        p.drawText(QRectF(8, 58, 100, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, speed_str)

        # km/h unit
        p.setFont(QFont("Helvetica", 11))
        p.setPen(QPen(dim_color))
        p.drawText(QRectF(80, 58, 50, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "km/h")

        # RPM
        rpm_str = f"{snap.rpm:.0f}" if not stale else "---"
        p.setFont(QFont("Helvetica", 14))
        p.setPen(QPen(dim_color))
        p.drawText(QRectF(8, 84, 120, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{rpm_str} rpm")

    # ------------------------------------------------------------------
    # Top band: Boost arc gauge (center, 160..500)
    # ------------------------------------------------------------------

    def _paint_boost_arc(
        self, p: QPainter, snap: DiffState, stale: bool
    ) -> None:
        # Arc geometry — semicircle opening upward (180 deg)
        arc_cx = 330.0
        arc_cy = 82.0
        arc_r = 68.0
        arc_rect = QRectF(arc_cx - arc_r, arc_cy - arc_r, arc_r * 2, arc_r * 2)

        # Boost gauge pressure: map_4bar_kpa minus ~101 kPa atmosphere
        boost_kpa = snap.map_4bar_kpa - 101.3 if not stale else 0.0

        # Arc spans from 180 deg (left) to 0 deg (right) = semicircle top half
        # Qt arcs: 0 = 3 o'clock, 90 = 12 o'clock, angles in 1/16th degree
        start_angle_16 = 180 * 16   # left
        full_span_16 = -180 * 16    # sweep clockwise to right

        # Background arc (dim)
        p.setPen(QPen(QColor(DIM), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(arc_rect, start_angle_16, full_span_16)

        if not stale:
            # Value arc — proportion of range
            clamped = max(_BOOST_MIN_KPA, min(_BOOST_MAX_KPA, boost_kpa))
            frac = (clamped - _BOOST_MIN_KPA) / (_BOOST_MAX_KPA - _BOOST_MIN_KPA)
            value_span_16 = int(full_span_16 * frac)

            # Split into normal (cyan) and red zone
            red_frac = (_BOOST_RED_KPA - _BOOST_MIN_KPA) / (_BOOST_MAX_KPA - _BOOST_MIN_KPA)

            if frac <= red_frac:
                # All cyan
                p.setPen(QPen(QColor(CYAN), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                p.drawArc(arc_rect, start_angle_16, value_span_16)
            else:
                # Cyan up to red zone
                cyan_span_16 = int(full_span_16 * red_frac)
                p.setPen(QPen(QColor(CYAN), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                p.drawArc(arc_rect, start_angle_16, cyan_span_16)

                # Red for the rest
                red_start = start_angle_16 + cyan_span_16
                red_span = value_span_16 - cyan_span_16
                p.setPen(QPen(QColor(RED), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                p.drawArc(arc_rect, red_start, red_span)

        # Tick marks
        p.setFont(QFont("Helvetica", 8))
        for tick_val in _BOOST_TICKS:
            tick_frac = (tick_val - _BOOST_MIN_KPA) / (_BOOST_MAX_KPA - _BOOST_MIN_KPA)
            angle_rad = math.pi - tick_frac * math.pi  # 180..0 degrees
            # Outer tick
            ox = arc_cx + (arc_r + 6) * math.cos(angle_rad)
            oy = arc_cy - (arc_r + 6) * math.sin(angle_rad)
            ix = arc_cx + (arc_r - 4) * math.cos(angle_rad)
            iy = arc_cy - (arc_r - 4) * math.sin(angle_rad)
            p.setPen(QPen(QColor(GRAY), 1))
            p.drawLine(QPointF(ix, iy), QPointF(ox, oy))
            # Label
            lx = arc_cx + (arc_r + 16) * math.cos(angle_rad) - 10
            ly = arc_cy - (arc_r + 16) * math.sin(angle_rad) - 5
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(lx, ly, 24, 12), Qt.AlignmentFlag.AlignCenter, str(tick_val))

        # Center value
        if stale:
            val_str = "---"
            val_color = QColor(GRAY)
        else:
            val_str = f"{boost_kpa:.0f}"
            val_color = QColor(RED) if boost_kpa >= _BOOST_RED_KPA else QColor(CYAN)

        p.setFont(QFont("Helvetica", FONT_BIG, QFont.Weight.Bold))
        p.setPen(QPen(val_color))
        p.drawText(QRectF(arc_cx - 40, arc_cy - 18, 80, 30),
                   Qt.AlignmentFlag.AlignCenter, val_str)

        # "kPa" unit
        p.setFont(QFont("Helvetica", 10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(arc_cx - 20, arc_cy + 10, 40, 14),
                   Qt.AlignmentFlag.AlignCenter, "kPa")

        # "BOOST" label above
        p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
        p.setPen(QPen(QColor(MODE_S_ACCENT)))
        p.drawText(QRectF(arc_cx - 30, 2, 60, 14),
                   Qt.AlignmentFlag.AlignCenter, "BOOST")

    # ------------------------------------------------------------------
    # Top band: Oil + Coolant + Fuel (right, 500..800)
    # ------------------------------------------------------------------

    def _paint_oil_coolant_fuel(
        self, p: QPainter, snap: DiffState, stale: bool
    ) -> None:
        x0 = 510
        row_h = 30

        rows = [
            ("OIL", f"{snap.oil_psi:.0f}", "PSI", self._oil_history,
             self._oil_color(snap.oil_psi), snap.oil_psi),
            ("CLT", f"{snap.coolant_temp:.0f}", "\u00b0C", self._coolant_history,
             self._coolant_color(snap.coolant_temp), snap.coolant_temp),
        ]

        for i, (label, val_str, unit, history, color, _raw) in enumerate(rows):
            y = 6 + i * row_h

            if stale:
                val_str = "---"
                color = QColor(GRAY)
            else:
                color = QColor(color)

            # Label
            p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(x0, y, 32, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

            # Value
            p.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
            p.setPen(QPen(color))
            p.drawText(QRectF(x0 + 34, y, 52, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, val_str)

            # Unit
            p.setFont(QFont("Helvetica", 9))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(x0 + 88, y, 30, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, unit)

            # Sparkline
            if len(history) > 1 and not stale:
                self._draw_sparkline(p, x0 + 122, y + 7, _SPARK_W, _SPARK_H, history, color)

        # Fuel pressure row (no sparkline, color indicator)
        y = 6 + 2 * row_h
        fuel_kpa = snap.fuel_pressure_kpa
        fuel_color = self._fuel_color(fuel_kpa)

        if stale:
            fuel_str = "---"
            fuel_color = QColor(GRAY)
        else:
            fuel_str = f"{fuel_kpa:.0f}"
            fuel_color = QColor(fuel_color)

        p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x0, y, 35, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "FUEL")

        p.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        p.setPen(QPen(fuel_color))
        p.drawText(QRectF(x0 + 34, y, 52, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, fuel_str)

        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x0 + 88, y, 30, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "kPa")

        # Color indicator dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fuel_color)
        p.drawEllipse(QPointF(x0 + 130, y + row_h / 2), 5, 5)

    # ------------------------------------------------------------------
    # Middle band: DCCD + Brake + Throttle + Lambda + IDC (left, 0..400)
    # ------------------------------------------------------------------

    def _paint_performance_bars(
        self,
        p: QPainter,
        snap: DiffState,
        engine_stale: bool,
        diff_stale: bool,
    ) -> None:
        bar_x = 8
        bar_w = 280
        bar_h = 18
        label_w = 55
        val_w = 52
        y_start = 110

        bars = self._build_bar_list(snap, engine_stale, diff_stale)

        for i, (label, value, max_val, fill_frac, fill_color, val_str, badge) in enumerate(bars):
            y = y_start + i * (bar_h + 8)

            # Label
            p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(
                QRectF(bar_x, y, label_w, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            # Bar background
            bx = bar_x + label_w
            p.fillRect(int(bx), int(y + 2), int(bar_w), int(bar_h - 4), QColor(BG_ACCENT))

            # Bar fill
            if fill_frac is not None and fill_frac > 0:
                fw = int(bar_w * min(1.0, abs(fill_frac)))
                p.fillRect(int(bx), int(y + 2), fw, int(bar_h - 4), QColor(fill_color))

            # Value text
            p.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            p.setPen(QPen(QColor(fill_color) if val_str != "---" else QColor(GRAY)))
            p.drawText(
                QRectF(bx + bar_w + 4, y, val_w, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                val_str,
            )

            # Badge (surface state for DCCD row)
            if badge:
                self._draw_badge(p, bx + bar_w + val_w + 8, y, bar_h, badge)

    def _build_bar_list(
        self, snap: DiffState, engine_stale: bool, diff_stale: bool
    ) -> list:
        """Return list of (label, value, max, frac, color, val_str, badge)."""
        bars = []

        # DCCD
        if diff_stale:
            bars.append(("DCCD", 0, 100, None, CYAN, "---", None))
        else:
            frac = snap.dccd_command_pct / 100.0
            badge_text = snap.surface_state.label
            badge_color = snap.surface_state.color
            bars.append((
                "DCCD", snap.dccd_command_pct, 100, frac, CYAN,
                f"{snap.dccd_command_pct:.0f}%",
                (badge_text, badge_color),
            ))

        # Brake pressure
        stale = diff_stale
        if stale:
            bars.append(("BRAKE", 0, _BRAKE_MAX_BAR, None, RED, "---", None))
        else:
            frac = min(1.0, snap.brake_pressure / _BRAKE_MAX_BAR)
            bars.append((
                "BRAKE", snap.brake_pressure, _BRAKE_MAX_BAR, frac, RED,
                f"{snap.brake_pressure:.0f} bar", None,
            ))

        # Throttle
        if engine_stale:
            bars.append(("THR", 0, 100, None, GREEN, "---", None))
        else:
            frac = snap.throttle_pct / 100.0
            bars.append((
                "THR", snap.throttle_pct, 100, frac, GREEN,
                f"{snap.throttle_pct:.0f}%", None,
            ))

        # Lambda — centered on 1.0
        if engine_stale:
            bars.append(("AFR", 0, 1, None, GREEN, "---", None))
        else:
            lam = snap.lambda_1
            if lam < _LAMBDA_TARGET:
                color = GREEN   # rich
                frac = (_LAMBDA_TARGET - lam) / (_LAMBDA_TARGET - _LAMBDA_RICH)
            else:
                color = RED     # lean
                frac = (lam - _LAMBDA_TARGET) / (_LAMBDA_LEAN - _LAMBDA_TARGET)
            frac = min(1.0, max(0.0, frac))
            bars.append((
                "AFR", lam, 1, frac, color,
                f"\u03bb {lam:.2f}", None,
            ))

        # Injector duty
        if engine_stale:
            bars.append(("IDC", 0, 100, None, CYAN, "---", None))
        else:
            idc = snap.injector_duty
            if idc >= _IDC_CRIT:
                color = RED
            elif idc >= _IDC_WARN:
                color = YELLOW
            else:
                color = CYAN
            frac = idc / 100.0
            bars.append((
                "IDC", idc, 100, frac, color,
                f"{idc:.0f}%", None,
            ))

        return bars

    def _draw_badge(
        self, p: QPainter, x: float, y: float, h: float, badge: tuple[str, str]
    ) -> None:
        """Draw a small colored badge (e.g. surface state)."""
        text, color = badge
        p.setFont(QFont("Helvetica", 8, QFont.Weight.Bold))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text) + 8
        bh = 14
        by = y + (h - bh) / 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(x, by, tw, bh), 3, 3)

        p.setPen(QPen(QColor(BG_DARK)))
        p.drawText(QRectF(x, by, tw, bh), Qt.AlignmentFlag.AlignCenter, text)

    # ------------------------------------------------------------------
    # Middle band: G-force circle (right, 400..800)
    # ------------------------------------------------------------------

    def _paint_g_force_circle(self, p: QPainter, snap: DiffState) -> None:
        cx = _G_CENTER_X
        cy = _G_CENTER_Y
        r1 = _G_RADIUS
        r05 = _G_RING_05

        # Background panel
        p.fillRect(400, 100, 400, 220, QColor(BG_DARK))

        # Concentric rings
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r05, r05)
        p.drawEllipse(QPointF(cx, cy), r1, r1)

        # Ring labels
        p.setFont(QFont("Helvetica", 7))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cx + r05 + 2, cy - 10, 24, 12), Qt.AlignmentFlag.AlignLeft, "0.5g")
        p.drawText(QRectF(cx + r1 + 2, cy - 10, 24, 12), Qt.AlignmentFlag.AlignLeft, "1.0g")

        # Crosshair lines
        p.setPen(QPen(QColor(DIM), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(cx - r1, cy), QPointF(cx + r1, cy))
        p.drawLine(QPointF(cx, cy - r1), QPointF(cx, cy + r1))

        # Axis labels
        p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cx - 20, cy - r1 - 16, 40, 14), Qt.AlignmentFlag.AlignCenter, "BRAKE")
        p.drawText(QRectF(cx - 20, cy + r1 + 4, 40, 14), Qt.AlignmentFlag.AlignCenter, "ACCEL")
        p.drawText(QRectF(cx - r1 - 14, cy - 7, 14, 14), Qt.AlignmentFlag.AlignCenter, "L")
        p.drawText(QRectF(cx + r1 + 2, cy - 7, 14, 14), Qt.AlignmentFlag.AlignCenter, "R")

        # Trail dots — fading from dim to bright
        trail_len = len(self._g_trail)
        if trail_len > 1:
            for i, (lat_g, lon_g) in enumerate(self._g_trail):
                # Skip the last one — drawn as the main dot
                if i == trail_len - 1:
                    continue

                alpha = int(30 + 180 * (i / trail_len))
                dot_color = QColor(CYAN)
                dot_color.setAlpha(alpha)
                px, py = self._g_to_pixel(lat_g, lon_g, cx, cy, r1)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot_color)
                p.drawEllipse(QPointF(px, py), 2, 2)

        # Current G dot — bright cyan
        lat_g = snap.imu_accel_y
        lon_g = snap.imu_accel_x
        px, py = self._g_to_pixel(lat_g, lon_g, cx, cy, r1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CYAN))
        p.drawEllipse(QPointF(px, py), 5, 5)

        # Current G magnitude below circle
        g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
        p.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
        p.setPen(QPen(QColor(WHITE)))
        p.drawText(
            QRectF(cx - 40, cy + r1 + 20, 80, 22),
            Qt.AlignmentFlag.AlignCenter,
            f"{g_mag:.2f}g",
        )

    @staticmethod
    def _g_to_pixel(
        lat_g: float, lon_g: float, cx: float, cy: float, r_px: float
    ) -> tuple[float, float]:
        """Convert G values to pixel coordinates, clamped to max radius."""
        # Lateral: positive = right on screen
        # Longitudinal: positive = acceleration = down on screen (inverted for display)
        g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
        if g_mag > _G_MAX:
            scale = _G_MAX / g_mag
            lat_g *= scale
            lon_g *= scale

        px = cx + (lat_g / _G_MAX) * r_px
        py = cy - (lon_g / _G_MAX) * r_px  # negative = braking = up
        return px, py

    # ------------------------------------------------------------------
    # Bottom band: Wheel speed deltas + slip (y=320..440)
    # ------------------------------------------------------------------

    def _paint_wheel_speeds(self, p: QPainter, snap: DiffState) -> None:
        y0 = 330
        bar_h = 20
        row_gap = 6
        center_x = 220
        bar_half_w = 160
        label_x = 8
        label_w = 30
        val_x = center_x + bar_half_w + 10
        val_w = 60
        vehicle_speed = snap.speed_kph

        wheels = [
            ("FL", snap.wheel_speed_fl),
            ("FR", snap.wheel_speed_fr),
            ("RL", snap.wheel_speed_rl),
            ("RR", snap.wheel_speed_rr),
        ]

        wheel_stale = snap.is_wheel_stale()

        for i, (name, ws) in enumerate(wheels):
            y = y0 + i * (bar_h + row_gap)
            delta = ws - vehicle_speed if not wheel_stale else 0.0

            # Label
            p.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            p.setPen(QPen(QColor(SILVER)))
            p.drawText(
                QRectF(label_x, y, label_w, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                name,
            )

            # Bar background
            p.fillRect(
                int(center_x - bar_half_w), int(y + 2),
                int(bar_half_w * 2), int(bar_h - 4),
                QColor(BG_ACCENT),
            )

            # Center line
            p.setPen(QPen(QColor(GRAY), 1))
            p.drawLine(int(center_x), int(y + 2), int(center_x), int(y + bar_h - 2))

            if not wheel_stale:
                # Delta bar — from center
                color = self._wheel_delta_color(abs(delta))
                max_delta = 10.0  # km/h full scale
                frac = min(1.0, abs(delta) / max_delta)
                bar_px = int(bar_half_w * frac)

                if delta >= 0:
                    # Faster — bar extends right
                    p.fillRect(int(center_x), int(y + 2), bar_px, int(bar_h - 4), QColor(color))
                else:
                    # Slower — bar extends left
                    p.fillRect(int(center_x - bar_px), int(y + 2), bar_px, int(bar_h - 4), QColor(color))

                # Value
                sign = "+" if delta >= 0 else ""
                val_str = f"{sign}{delta:.1f}"
            else:
                val_str = "---"

            p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            val_color = QColor(self._wheel_delta_color(abs(delta))) if not wheel_stale else QColor(GRAY)
            p.setPen(QPen(val_color))
            p.drawText(
                QRectF(val_x, y, val_w, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                val_str,
            )

        # Slip delta — large value right side
        slip_x = 560
        slip_y = 340
        p.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        p.setPen(QPen(QColor(MODE_S_ACCENT)))
        p.drawText(
            QRectF(slip_x, slip_y, 120, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "SLIP \u0394",
        )

        if snap.slip_delta is not None and not wheel_stale:
            slip_val = snap.slip_delta
            slip_color = self._wheel_delta_color(abs(slip_val))
            p.setFont(QFont("Helvetica", 36, QFont.Weight.Bold))
            p.setPen(QPen(QColor(slip_color)))
            p.drawText(
                QRectF(slip_x, slip_y + 20, 180, 50),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                f"{slip_val:+.1f}",
            )

            p.setFont(QFont("Helvetica", 12))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(
                QRectF(slip_x + 130, slip_y + 36, 60, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "km/h",
            )
        else:
            p.setFont(QFont("Helvetica", 36, QFont.Weight.Bold))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(
                QRectF(slip_x, slip_y + 20, 180, 50),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                "---",
            )

    # ------------------------------------------------------------------
    # Sparkline helper
    # ------------------------------------------------------------------

    def _draw_sparkline(
        self,
        p: QPainter,
        x: float,
        y: float,
        w: float,
        h: float,
        history: deque,
        color: QColor,
    ) -> None:
        """Draw a mini line chart from a deque of float values."""
        n = len(history)
        if n < 2:
            return

        vals = list(history)
        lo = min(vals)
        hi = max(vals)
        span = hi - lo if hi != lo else 1.0

        path = QPainterPath()
        for i, v in enumerate(vals):
            px = x + (i / (n - 1)) * w
            py = y + h - ((v - lo) / span) * h
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        p.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _oil_color(psi: float) -> str:
        """Oil pressure color: green=good, yellow=low, red=critical."""
        if psi < 15:
            return RED
        if psi < 30:
            return YELLOW
        return GREEN

    @staticmethod
    def _coolant_color(temp_c: float) -> str:
        """Coolant temp color: green=good, yellow=warm, red=hot."""
        if temp_c > 105:
            return RED
        if temp_c > 95:
            return YELLOW
        return GREEN

    @staticmethod
    def _fuel_color(kpa: float) -> str:
        """Fuel pressure color: green=good, yellow=low, red=critical."""
        if kpa < 200:
            return RED
        if kpa < 280:
            return YELLOW
        return GREEN

    @staticmethod
    def _wheel_delta_color(abs_delta: float) -> str:
        """Wheel speed delta color: cyan=small, yellow=moderate, red=severe."""
        if abs_delta > _WS_SEVERE:
            return RED
        if abs_delta > _WS_MODERATE:
            return YELLOW
        return CYAN
