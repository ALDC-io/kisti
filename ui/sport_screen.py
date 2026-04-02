"""KiSTI - Sport Mode Screen (SI-Drive = 1)

Performance / fast-road screen. Medium density.
MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport shows ONLY what the MXG cannot:
  - DCCD + surface + slip (AWD dynamics)
  - FLIR brake temps (4-corner)
  - G-force circle with trail (IMU)
  - Steering angle + yaw rate bars
  - Brake pressure bar
  - Wheel speed deltas + brake/steering trace

800x440 content area, 100% QPainter — no composite QWidget layouts.

Layout:
  y=0..100   DCCD bar + surface + slip (left) | FLIR 2x2 (right)
  y=100..320 Performance bars (left 350px) | G-force circle (right)
  y=320..440 Wheel speed deltas (left 500px) | Brake+steering trace (right)
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
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
    CHROME_DARK,
    MODE_S_ACCENT,
    FONT_BIG,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# G-force circle
_G_CENTER_X = 600
_G_CENTER_Y = 210
_G_RADIUS = 100
_G_RING_05 = 50
_G_MAX = 1.5

# Wheel speed delta thresholds (km/h)
_WS_MODERATE = 2.0
_WS_SEVERE = 5.0

# Brake bar max
_BRAKE_MAX_BAR = 80.0

# Lateral G range for bar
_G_MAX_BAR = 1.5

# Steering range
_STEER_MAX = 450.0

# Yaw rate range
_YAW_MAX = 60.0

# FLIR thresholds
_FLIR_COLD = 150.0
_FLIR_GREEN = 300.0
_FLIR_YELLOW = 450.0
_FLIR_RED = 500.0

# Trace buffer
_TRACE_LEN = 200


def _brake_heat_color(temp_c: float) -> QColor:
    """Blue → green → yellow → red for brake temps."""
    if temp_c <= _FLIR_COLD:
        return QColor(80, 180, 255)
    elif temp_c <= _FLIR_GREEN:
        t = (temp_c - _FLIR_COLD) / max(1, _FLIR_GREEN - _FLIR_COLD)
        return QColor(int(80 * (1 - t)), int(180 * (1 - t) + 200 * t), int(255 * (1 - t) + 80 * t))
    elif temp_c <= _FLIR_YELLOW:
        t = (temp_c - _FLIR_GREEN) / max(1, _FLIR_YELLOW - _FLIR_GREEN)
        return QColor(int(255 * t), int(200 * (1 - t) + 170 * t), int(80 * (1 - t)))
    else:
        t = min(1.0, (temp_c - _FLIR_YELLOW) / max(1, _FLIR_RED - _FLIR_YELLOW))
        return QColor(255, int(170 * (1 - t) + 30 * t), 0)


class SportScreenWidget(QWidget):
    """Sport mode (SI-Drive=1): AWD dynamics, G-force, FLIR, traces."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._snap: Optional[DiffState] = None

        # G-force dot trail
        self._g_trail: deque[tuple[float, float]] = deque(maxlen=100)

        # Brake/steering trace buffers (10s at 20Hz)
        self._brake_trace: deque[float] = deque(maxlen=_TRACE_LEN)
        self._steering_trace: deque[float] = deque(maxlen=_TRACE_LEN)

        self.setMinimumSize(800, 440)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Called at 20 Hz from main timer with a DiffState snapshot."""
        self._snap = snap
        self._g_trail.append((snap.imu_accel_y, snap.imu_accel_x))
        self._brake_trace.append(snap.brake_pressure)
        self._steering_trace.append(snap.steering_angle)
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        snap = self._snap if self._snap is not None else DiffState()
        diff_stale = True if self._snap is None else snap.is_diff_stale()
        dynamics_stale = True if self._snap is None else snap.is_dynamics_stale()

        # --- Top band (y=0..100) ---
        self._paint_dccd_strip(p, snap, diff_stale)
        self._paint_flir_summary(p, snap)

        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, 100, w, 100)

        # --- Middle band (y=100..320) ---
        self._paint_performance_bars(p, snap, diff_stale, dynamics_stale)
        self._paint_g_force_circle(p, snap)

        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, 320, w, 320)

        # --- Bottom band (y=320..440) ---
        self._paint_wheel_speeds(p, snap)
        self._paint_brake_steering_trace(p)

        p.end()

    # ------------------------------------------------------------------
    # Top band: DCCD + Surface + Slip (left, 0..500)
    # ------------------------------------------------------------------

    def _paint_dccd_strip(
        self, p: QPainter, snap: DiffState, stale: bool
    ) -> None:
        # DCCD label
        p.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        p.setPen(QPen(QColor(MODE_S_ACCENT)))
        p.drawText(QRectF(8, 4, 60, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "DCCD")

        # DCCD bar
        bar_x = 70
        bar_w = 320
        bar_y = 8
        bar_h = 24

        p.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor(BG_ACCENT))

        dccd = snap.dccd_command_pct if not stale else 0.0
        if not stale and dccd > 0.01:
            fill_w = (dccd / 100.0) * bar_w
            if dccd > 70:
                fill_col = QColor(RED)
            elif dccd > 40:
                fill_col = QColor(YELLOW)
            else:
                fill_col = QColor(GREEN)
            p.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), fill_col)

        # Percentage
        pct_str = f"{dccd:.0f}%" if not stale else "---%"
        p.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        p.setPen(QPen(QColor(WHITE) if not stale else QColor(GRAY)))
        p.drawText(QRectF(bar_x + bar_w + 6, bar_y, 60, bar_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pct_str)

        # Surface state badge
        if not stale:
            surface_label = snap.surface_state.label
            surface_color = QColor(snap.surface_state.color)
        else:
            surface_label = "---"
            surface_color = QColor(GRAY)

        p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
        badge_tw = p.fontMetrics().horizontalAdvance(surface_label) + 14
        badge_x = 8
        badge_y = 40
        row2_h = 22  # shared height for badge + slip on this row
        pill_bg = QColor(surface_color)
        pill_bg.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_tw, 18), 6, 6)
        p.setPen(QPen(surface_color))
        p.drawText(QRectF(badge_x, badge_y, badge_tw, 18), Qt.AlignmentFlag.AlignCenter, surface_label)

        # Slip delta — same row as badge, vertically aligned
        slip_x = badge_x + badge_tw + 16
        if snap.slip_delta is not None and not stale:
            slip_color = self._wheel_delta_color(abs(snap.slip_delta))
            p.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
            p.setPen(QPen(QColor(slip_color)))
            p.drawText(QRectF(slip_x, badge_y - 2, 160, row2_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"SLIP \u0394 {snap.slip_delta:+.1f} km/h")
        else:
            p.setFont(QFont("Helvetica", 12))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(slip_x, badge_y - 2, 120, row2_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "SLIP \u0394 ---")

        # ABS/VDC indicators
        ind_y = 68
        if not stale and snap.abs_active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(RED))
            p.drawEllipse(QPointF(16, ind_y), 5, 5)
            p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
            p.setPen(QPen(QColor(RED)))
            p.drawText(26, int(ind_y) + 4, "ABS")

        if not stale and snap.vdc_tc:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(YELLOW))
            p.drawEllipse(QPointF(70, ind_y), 5, 5)
            p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
            p.setPen(QPen(QColor(YELLOW)))
            p.drawText(80, int(ind_y) + 4, "VDC")

    # ------------------------------------------------------------------
    # Top band: FLIR 2x2 summary (right, 500..800)
    # ------------------------------------------------------------------

    def _paint_flir_summary(self, p: QPainter, snap: DiffState) -> None:
        flir_ok = snap.flir_available and not snap.is_flir_stale()

        cells = [
            ("FL", 510, 6, snap.brake_temp_fl),
            ("FR", 658, 6, snap.brake_temp_fr),
            ("RL", 510, 52, snap.brake_temp_rl),
            ("RR", 658, 52, snap.brake_temp_rr),
        ]
        cell_w = 140
        cell_h = 40

        for label, cx, cy, temp in cells:
            rect = QRectF(cx, cy, cell_w, cell_h)
            if flir_ok:
                heat_col = _brake_heat_color(temp)
                bg = QColor(heat_col)
                bg.setAlpha(50)
                p.fillRect(rect, bg)
                p.setPen(QPen(heat_col, 1))
                p.drawRect(rect)

                p.setFont(QFont("Courier", 18, QFont.Weight.Bold))
                p.setPen(heat_col)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{temp:.0f}\u00b0")

                p.setFont(QFont("Helvetica", 8))
                p.setPen(QColor(GRAY))
                p.drawText(int(cx) + 4, int(cy) + 12, label)
            else:
                p.fillRect(rect, QColor(BG_PANEL))
                p.setPen(QPen(QColor(DIM), 1))
                p.drawRect(rect)
                p.setFont(QFont("Helvetica", 10))
                p.setPen(QColor(DIM))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{label} ---")

    # ------------------------------------------------------------------
    # Middle band: Performance bars (left, 0..350)
    # ------------------------------------------------------------------

    def _paint_performance_bars(
        self, p: QPainter, snap: DiffState,
        diff_stale: bool, dynamics_stale: bool,
    ) -> None:
        bar_x = 8
        bar_w = 220
        bar_h = 20
        label_w = 60
        val_w = 60
        y_start = 116

        bars = []

        # Lateral G — centered bar
        if dynamics_stale:
            bars.append(("LAT G", 0, _G_MAX_BAR, None, CYAN, "---"))
        else:
            norm = max(-1.0, min(1.0, snap.imu_accel_y / _G_MAX_BAR))
            bars.append(("LAT G", snap.imu_accel_y, _G_MAX_BAR, norm, CYAN, f"{snap.imu_accel_y:+.2f}g"))

        # Brake pressure
        if dynamics_stale:
            bars.append(("BRAKE", 0, _BRAKE_MAX_BAR, None, RED, "---"))
        else:
            frac = min(1.0, snap.brake_pressure / _BRAKE_MAX_BAR)
            bars.append(("BRAKE", snap.brake_pressure, _BRAKE_MAX_BAR, frac, RED, f"{snap.brake_pressure:.0f} bar"))

        # Steering angle — centered bar
        if dynamics_stale:
            bars.append(("STEER", 0, _STEER_MAX, None, CYAN, "---"))
        else:
            # Normalize to -1..+1
            norm = max(-1.0, min(1.0, snap.steering_angle / _STEER_MAX))
            bars.append(("STEER", snap.steering_angle, _STEER_MAX, norm, CYAN, f"{snap.steering_angle:.0f}\u00b0"))

        # Yaw rate — centered bar
        if dynamics_stale:
            bars.append(("YAW", 0, _YAW_MAX, None, CYAN, "---"))
        else:
            norm = max(-1.0, min(1.0, snap.yaw_rate / _YAW_MAX))
            bars.append(("YAW", snap.yaw_rate, _YAW_MAX, norm, CYAN, f"{snap.yaw_rate:.1f}\u00b0/s"))

        spacing = 44
        for i, (label, _value, _max_val, frac, fill_color, val_str) in enumerate(bars):
            y = y_start + i * spacing

            # Label
            p.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(bar_x, y, label_w, bar_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

            bx = bar_x + label_w

            if label in ("STEER", "YAW"):
                # Centered bar
                p.fillRect(int(bx), int(y + 2), int(bar_w), int(bar_h - 4), QColor(BG_ACCENT))
                center = bx + bar_w / 2
                p.setPen(QPen(QColor(GRAY), 1))
                p.drawLine(int(center), int(y + 2), int(center), int(y + bar_h - 2))

                if frac is not None:
                    fill_px = int(abs(frac) * (bar_w / 2))
                    if frac >= 0:
                        p.fillRect(int(center), int(y + 2), fill_px, int(bar_h - 4), QColor(fill_color))
                    else:
                        p.fillRect(int(center - fill_px), int(y + 2), fill_px, int(bar_h - 4), QColor(fill_color))
            else:
                # Standard bar
                p.fillRect(int(bx), int(y + 2), int(bar_w), int(bar_h - 4), QColor(BG_ACCENT))
                if frac is not None and frac > 0:
                    fw = int(bar_w * min(1.0, abs(frac)))
                    p.fillRect(int(bx), int(y + 2), fw, int(bar_h - 4), QColor(fill_color))

            # Value text
            p.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            p.setPen(QPen(QColor(fill_color) if val_str != "---" else QColor(GRAY)))
            p.drawText(QRectF(bx + bar_w + 4, y, val_w, bar_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, val_str)

    # ------------------------------------------------------------------
    # Middle band: G-force circle (right, 350..800) — PRESERVED
    # ------------------------------------------------------------------

    def _paint_g_force_circle(self, p: QPainter, snap: DiffState) -> None:
        cx = _G_CENTER_X
        cy = _G_CENTER_Y
        r1 = _G_RADIUS
        r05 = _G_RING_05

        p.fillRect(350, 100, 450, 220, QColor(BG_DARK))

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
            Qt.AlignmentFlag.AlignCenter, f"{g_mag:.2f}g",
        )

    @staticmethod
    def _g_to_pixel(
        lat_g: float, lon_g: float, cx: float, cy: float, r_px: float
    ) -> tuple[float, float]:
        """Convert G values to pixel coordinates, clamped to max radius."""
        g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
        if g_mag > _G_MAX:
            scale = _G_MAX / g_mag
            lat_g *= scale
            lon_g *= scale
        px = cx + (lat_g / _G_MAX) * r_px
        py = cy - (lon_g / _G_MAX) * r_px
        return px, py

    # ------------------------------------------------------------------
    # Bottom band: Wheel speed deltas (left, 0..500)
    # ------------------------------------------------------------------

    def _paint_wheel_speeds(self, p: QPainter, snap: DiffState) -> None:
        y0 = 330
        bar_h = 20
        row_gap = 6
        center_x = 180
        bar_half_w = 130
        label_x = 8
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

            p.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            p.setPen(QPen(QColor(SILVER)))
            p.drawText(QRectF(label_x, y, 30, bar_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

            p.fillRect(int(center_x - bar_half_w), int(y + 2),
                       int(bar_half_w * 2), int(bar_h - 4), QColor(BG_ACCENT))

            p.setPen(QPen(QColor(GRAY), 1))
            p.drawLine(int(center_x), int(y + 2), int(center_x), int(y + bar_h - 2))

            if not wheel_stale:
                color = self._wheel_delta_color(abs(delta))
                max_delta = 10.0
                frac = min(1.0, abs(delta) / max_delta)
                bar_px = int(bar_half_w * frac)

                if delta >= 0:
                    p.fillRect(int(center_x), int(y + 2), bar_px, int(bar_h - 4), QColor(color))
                else:
                    p.fillRect(int(center_x - bar_px), int(y + 2), bar_px, int(bar_h - 4), QColor(color))

                sign = "+" if delta >= 0 else ""
                val_str = f"{sign}{delta:.1f}"
            else:
                val_str = "---"

            p.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            val_color = QColor(self._wheel_delta_color(abs(delta))) if not wheel_stale else QColor(GRAY)
            p.setPen(QPen(val_color))
            p.drawText(QRectF(val_x, y, val_w, bar_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, val_str)

    # ------------------------------------------------------------------
    # Bottom band: Brake + steering trace (right, 500..800)
    # ------------------------------------------------------------------

    def _paint_brake_steering_trace(self, p: QPainter) -> None:
        strip_x = 510
        strip_w = 280
        strip_y = 325
        strip_h = 110

        p.fillRect(QRectF(strip_x, strip_y, strip_w, strip_h), QColor(BG_PANEL))

        # Header label
        p.setFont(QFont("Helvetica", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(strip_x + 4, strip_y + 2, 100, 12),
                   Qt.AlignmentFlag.AlignLeft, "BRAKE TRACE")

        if len(self._brake_trace) == 0:
            return

        sample_w = strip_w / _TRACE_LEN

        # Brake — red fill from bottom
        for idx, brk in enumerate(self._brake_trace):
            offset = _TRACE_LEN - len(self._brake_trace) + idx
            x = strip_x + offset * sample_w
            brk_h = (min(brk, _BRAKE_MAX_BAR) / _BRAKE_MAX_BAR) * strip_h
            brk_y = strip_y + strip_h - brk_h
            brk_color = QColor(RED)
            brk_color.setAlpha(180)
            p.fillRect(QRectF(x, brk_y, max(sample_w, 1.0), brk_h), brk_color)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(DIM), 1))
        p.drawRect(QRectF(strip_x, strip_y, strip_w, strip_h))

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wheel_delta_color(abs_delta: float) -> str:
        if abs_delta > _WS_SEVERE:
            return RED
        if abs_delta > _WS_MODERATE:
            return YELLOW
        return CYAN
