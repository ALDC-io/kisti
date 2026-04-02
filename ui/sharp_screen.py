"""KiSTI - Sport Sharp Screen (SI-Drive=2)

TRACK / ATTACK / MINIMAL — ultra-sparse, dark, high contrast numbers.
100% QPainter in paintEvent. No composite QWidget layouts.

MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport Sharp shows ONLY what the MXG cannot:
  - Lap timing + delta + sectors
  - FLIR brake temps (4-corner)
  - G-force micro circle (IMU)
  - AWD status (DCCD + surface + ABS/VDC)
  - Brake + steering trace (trail-brake analysis)
  - Safety vitals (dim-until-warning)

Layout (800x440):
  y=0..80    Delta bar (full width, green=faster, red=slower)
  y=80..280  Lap time (left 400px) + Dynamics panel (right 400px)
  y=280..320 Sector strip (colored blocks)
  y=320..380 Brake/steering trace (scrolling strip chart)
  y=380..440 Safety vitals (dim until warning) — 5 zones
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState
from ui.theme import (
    BG_DARK,
    BG_PANEL,
    WHITE,
    GRAY,
    DIM,
    GREEN,
    YELLOW,
    RED,
    CYAN,
    MODE_SS_ACCENT,
    FONT_BASE,
    FONT_HEADER,
    FONT_BIG,
    FONT_XLARGE,
    FONT_MEGA,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_W = 800
_H = 440

# Section Y boundaries
_DELTA_Y0 = 0
_DELTA_Y1 = 80
_MID_Y0 = 80
_MID_Y1 = 280
_SECTOR_Y0 = 280
_SECTOR_Y1 = 320
_BRAKE_Y0 = 320
_BRAKE_Y1 = 380
_VITALS_Y0 = 380
_VITALS_Y1 = 440

# Delta bar geometry
_BAR_MARGIN = 10
_BAR_H = 60
_BAR_Y = (_DELTA_Y1 - _BAR_H) // 2 + _DELTA_Y0
_BAR_X = _BAR_MARGIN
_BAR_W = _W - 2 * _BAR_MARGIN

# Brake/steering trace ring buffer size (20s at 20Hz)
_TRACE_LEN = 400

# Mid-section split
_MID_SPLIT_X = 400

# G-force micro circle
_G_CX = 600
_G_CY = 200
_G_RADIUS = 40
_G_RING_05 = 20
_G_MAX = 1.5
_G_TRAIL_LEN = 5

# FLIR brake temp thresholds (°C)
_FLIR_COLD = 150.0
_FLIR_GREEN = 300.0
_FLIR_YELLOW = 450.0
_FLIR_RED = 500.0

# Safety thresholds — sourced from data/build_record.py BASELINES
_OIL_WARN_LOW = 15.0   # PSI
_OIL_CRIT_LOW = 10.0   # PSI
_COOL_WARN = 100.0      # Celsius
_COOL_CRIT = 105.0      # Celsius
_OILT_WARN = 130.0      # Celsius
_OILT_CRIT = 140.0      # Celsius
_BRKT_WARN = 450.0      # Celsius
_BRKT_CRIT = 500.0      # Celsius

# Steering range for trace
_STEER_MAX = 450.0      # degrees, full lock


def _fmt_time_ms(ms: int) -> str:
    """Format milliseconds as MM:SS.xxx — zero-padded."""
    if ms <= 0:
        return "--:--.---"
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def _fmt_delta_ms(ms: int) -> str:
    """Format delta with sign and 3 decimal places."""
    sign = "+" if ms >= 0 else "-"
    abs_ms = abs(ms)
    seconds = abs_ms // 1000
    frac = abs_ms % 1000
    return f"{sign}{seconds}.{frac:03d}"


def _brake_heat_color(temp_c: float) -> QColor:
    """Blue (cold) -> Green (optimal) -> Yellow (warm) -> Red (hot) for brake temps."""
    if temp_c <= _FLIR_COLD:
        return QColor(80, 180, 255)     # Light blue
    elif temp_c <= _FLIR_GREEN:
        t = (temp_c - _FLIR_COLD) / max(1, _FLIR_GREEN - _FLIR_COLD)
        r = int(80 * (1 - t))
        g = int(180 * (1 - t) + 200 * t)
        b = int(255 * (1 - t) + 80 * t)
        return QColor(r, g, b)
    elif temp_c <= _FLIR_YELLOW:
        t = (temp_c - _FLIR_GREEN) / max(1, _FLIR_YELLOW - _FLIR_GREEN)
        r = int(255 * t)
        g = int(200 * (1 - t) + 170 * t)
        b = int(80 * (1 - t))
        return QColor(r, g, b)
    else:
        t = min(1.0, (temp_c - _FLIR_YELLOW) / max(1, _FLIR_RED - _FLIR_YELLOW))
        r = 255
        g = int(170 * (1 - t) + 30 * t)
        return QColor(r, g, 0)


def _oil_color(psi: float) -> QColor:
    if psi <= _OIL_CRIT_LOW:
        return QColor(RED)
    if psi <= _OIL_WARN_LOW:
        return QColor(YELLOW)
    return QColor(GREEN)


def _coolant_color(temp: float) -> QColor:
    if temp >= _COOL_CRIT:
        return QColor(RED)
    if temp >= _COOL_WARN:
        return QColor(YELLOW)
    return QColor(GREEN)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SportSharpScreenWidget(QWidget):
    """Sport Sharp (S#) full-screen QPainter widget — 800x440.

    Ultra-sparse dark layout for maximum attack driving.
    Shows ONLY data the MXG Strada cannot: timing, FLIR, G-force, AWD, traces.
    Data fed via update_state(snap) at 20 Hz from DiffStateBridge.
    Timing data fed via update_timing(timing_data) from TimingManager.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_W, _H)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        self._snap: Optional[DiffState] = None
        self._timing: dict = {}

        # Ring buffers for brake/steering trace (20s at 20Hz)
        self._brake_history: deque[float] = deque(maxlen=_TRACE_LEN)
        self._steering_history: deque[float] = deque(maxlen=_TRACE_LEN)

        # G-force mini trail
        self._g_trail: deque[tuple[float, float]] = deque(maxlen=_G_TRAIL_LEN)

        # Sector pulse animation
        self._paint_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Accept telemetry snapshot from DiffStateBridge (20 Hz)."""
        self._snap = snap
        self._brake_history.append(snap.brake_pressure)
        self._steering_history.append(snap.steering_angle)
        self._g_trail.append((snap.imu_accel_y, snap.imu_accel_x))
        self.update()

    def update_timing(self, timing_data: dict) -> None:
        """Accept timing data from TimingManager.

        Expected keys: lap_count, current_lap_time_ms, delta_ms,
        predicted_lap_ms, sector_times, current_sector, sector_count,
        best_lap_ms, best_sector_times, track_name, theoretical_best_ms
        """
        self._timing = timing_data
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Full black background
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))

        self._paint_count += 1

        self._draw_delta_bar(p)
        self._draw_timing_panel(p)
        self._draw_dynamics_panel(p)
        self._draw_sector_strip(p)
        self._draw_brake_steering_trace(p)
        self._draw_safety_vitals(p)

        p.end()

    # ------------------------------------------------------------------
    # Delta bar (y=0..80) — UNCHANGED
    # ------------------------------------------------------------------

    def _draw_delta_bar(self, p: QPainter) -> None:
        has_timing = bool(self._timing.get("current_lap_time_ms"))
        delta_ms = self._timing.get("delta_ms", 0)

        bar_rect = QRectF(_BAR_X, _BAR_Y, _BAR_W, _BAR_H)
        p.fillRect(bar_rect, QColor(BG_PANEL))

        p.setPen(QPen(QColor(DIM), 1))
        p.drawRect(bar_rect)

        if not has_timing:
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Helvetica", FONT_HEADER, QFont.Bold))
            p.drawText(bar_rect, Qt.AlignCenter, "NO TIMING")
            return

        center_x = _BAR_X + _BAR_W / 2.0
        max_delta_ms = 5000.0
        clamped = max(-max_delta_ms, min(max_delta_ms, float(delta_ms)))
        fill_frac = clamped / max_delta_ms

        if abs(fill_frac) > 0.001:
            fill_w = abs(fill_frac) * (_BAR_W / 2.0)
            inner_margin = 2
            fill_h = _BAR_H - 2 * inner_margin
            fill_y = _BAR_Y + inner_margin

            if fill_frac > 0:
                fill_color = QColor(RED)
                fill_rect = QRectF(center_x, fill_y, fill_w, fill_h)
            else:
                fill_color = QColor(GREEN)
                fill_rect = QRectF(center_x - fill_w, fill_y, fill_w, fill_h)

            p.fillRect(fill_rect, fill_color)

        p.setPen(QPen(QColor(WHITE), 1))
        p.drawLine(int(center_x), _BAR_Y + 2, int(center_x), _BAR_Y + _BAR_H - 2)

        delta_text = _fmt_delta_ms(delta_ms)
        text_color = QColor(GREEN) if delta_ms < 0 else QColor(RED) if delta_ms > 0 else QColor(WHITE)
        p.setPen(text_color)
        p.setFont(QFont("Helvetica", FONT_XLARGE, QFont.Bold))
        p.drawText(bar_rect, Qt.AlignCenter, delta_text)

    # ------------------------------------------------------------------
    # Timing panel (left half, x=0..400, y=80..280)
    # ------------------------------------------------------------------

    def _draw_timing_panel(self, p: QPainter) -> None:
        timing = self._timing

        lap_count = timing.get("lap_count", 0)
        current_lap_ms = timing.get("current_lap_time_ms", 0)
        predicted_ms = timing.get("predicted_lap_ms", 0)
        best_ms = timing.get("best_lap_ms", 0)
        theoretical_ms = timing.get("theoretical_best_ms", 0)

        # "LAP X" label
        lap_label = f"LAP {lap_count}" if lap_count > 0 else "LAP --"
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 12))
        p.drawText(20, _MID_Y0 + 28, lap_label)

        # Track name
        track_name = timing.get("track_name", "")
        if track_name:
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(120, _MID_Y0 + 28, track_name)

        # Current lap time — large
        lap_time_str = _fmt_time_ms(current_lap_ms)
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Courier", FONT_MEGA, QFont.Bold))
        p.drawText(16, _MID_Y0 + 90, lap_time_str)

        # Predicted lap
        if predicted_ms > 0:
            pred_str = f"PRED {_fmt_time_ms(predicted_ms)}"
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Courier", 30, QFont.Bold))
            p.drawText(20, _MID_Y0 + 138, pred_str)

        # Best lap reference
        if best_ms > 0:
            best_str = f"BEST {_fmt_time_ms(best_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE))
            p.drawText(24, _MID_Y0 + 170, best_str)

        # Theoretical best — NEW
        if theoretical_ms > 0:
            theo_str = f"THEO {_fmt_time_ms(theoretical_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE))
            p.drawText(24, _MID_Y0 + 192, theo_str)

    # ------------------------------------------------------------------
    # Dynamics panel (right half, x=400..800, y=80..280)
    # Replaces gear/speed/RPM — shows FLIR, G-force micro, AWD strip
    # ------------------------------------------------------------------

    def _draw_dynamics_panel(self, p: QPainter) -> None:
        snap = self._snap
        self._draw_flir_temps(p, snap)
        self._draw_g_force_micro(p, snap)
        self._draw_awd_strip(p, snap)

    # --- FLIR 4-corner brake temps (x=400..800, y=80..170) ---

    def _draw_flir_temps(self, p: QPainter, snap: Optional[DiffState]) -> None:
        flir_ok = snap is not None and snap.flir_available and not snap.is_flir_stale()

        # Header label — above the grid
        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        p.setPen(QColor(MODE_SS_ACCENT) if flir_ok else QColor(DIM))
        p.drawText(QRectF(410, _MID_Y0 - 14, 380, 14), Qt.AlignCenter,
                   "BRAKE TEMPS" if flir_ok else "FLIR NOT CONNECTED")

        # 2x2 grid: FL/FR top row, RL/RR bottom row
        cells = [
            ("FL", 410, _MID_Y0 + 2, snap.brake_temp_fl if snap else 0.0),
            ("FR", 602, _MID_Y0 + 2, snap.brake_temp_fr if snap else 0.0),
            ("RL", 410, _MID_Y0 + 46, snap.brake_temp_rl if snap else 0.0),
            ("RR", 602, _MID_Y0 + 46, snap.brake_temp_rr if snap else 0.0),
        ]
        cell_w = 186
        cell_h = 40

        for label, cx, cy, temp in cells:
            rect = QRectF(cx, cy, cell_w, cell_h)

            if flir_ok:
                # Heat-colored background fill
                heat_col = _brake_heat_color(temp)
                heat_col.setAlpha(60)
                p.fillRect(rect, heat_col)

                # Border matches heat color
                border_col = _brake_heat_color(temp)
                p.setPen(QPen(border_col, 1))
                p.drawRect(rect)

                # Temperature value — large
                p.setFont(QFont("Courier", 22, QFont.Bold))
                p.setPen(_brake_heat_color(temp))
                p.drawText(rect, Qt.AlignCenter, f"{temp:.0f}\u00b0")

                # Corner label — tiny top-left
                p.setFont(QFont("Helvetica", 8))
                p.setPen(QColor(GRAY))
                p.drawText(int(cx) + 4, int(cy) + 12, label)
            else:
                # No FLIR
                p.fillRect(rect, QColor(BG_PANEL))
                p.setPen(QPen(QColor(DIM), 1))
                p.drawRect(rect)
                p.setFont(QFont("Helvetica", 10))
                p.setPen(QColor(DIM))
                p.drawText(rect, Qt.AlignCenter, f"{label} ---")

    # --- G-force micro circle (x=500..700, y=170..250) ---

    def _draw_g_force_micro(self, p: QPainter, snap: Optional[DiffState]) -> None:
        cx = _G_CX
        cy = _G_CY
        r1 = _G_RADIUS
        r05 = _G_RING_05

        # Concentric rings
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r05, r05)
        p.drawEllipse(QPointF(cx, cy), r1, r1)

        # Crosshair
        p.setPen(QPen(QColor(DIM), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(cx - r1, cy), QPointF(cx + r1, cy))
        p.drawLine(QPointF(cx, cy - r1), QPointF(cx, cy + r1))

        # Trail dots
        trail_len = len(self._g_trail)
        if trail_len > 1:
            for i, (lat_g, lon_g) in enumerate(self._g_trail):
                if i == trail_len - 1:
                    continue
                alpha = int(60 + 150 * (i / trail_len))
                dot_color = QColor(CYAN)
                dot_color.setAlpha(alpha)
                px, py = self._g_to_pixel(lat_g, lon_g, cx, cy, r1)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot_color)
                p.drawEllipse(QPointF(px, py), 2, 2)

        # Current G dot
        lat_g = snap.imu_accel_y if snap else 0.0
        lon_g = snap.imu_accel_x if snap else 0.0
        px, py = self._g_to_pixel(lat_g, lon_g, cx, cy, r1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CYAN))
        p.drawEllipse(QPointF(px, py), 4, 4)

        # G magnitude — below circle, above AWD strip
        g_mag = math.sqrt(lat_g ** 2 + lon_g ** 2)
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        p.setPen(QColor(WHITE))
        p.drawText(
            QRectF(cx - 30, cy + r1 + 2, 60, 16),
            Qt.AlignCenter,
            f"{g_mag:.2f}g",
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

    # --- AWD status strip (x=400..800, y=250..280) ---

    def _draw_awd_strip(self, p: QPainter, snap: Optional[DiffState]) -> None:
        strip_y = 260
        strip_h = 18
        stale = snap is None or snap.is_diff_stale()

        # DCCD label
        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        p.setPen(QColor(GRAY))
        p.drawText(412, strip_y + 14, "DCCD")

        # DCCD bar
        bar_x = 450
        bar_w = 240
        bar_h = 14
        bar_y = strip_y + 4

        p.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor(BG_PANEL))

        dccd = snap.dccd_command_pct if snap and not stale else 0.0
        if not stale and dccd > 0.01:
            fill_w = (dccd / 100.0) * bar_w
            if dccd > 70:
                fill_col = QColor(MODE_SS_ACCENT)
            elif dccd > 40:
                fill_col = QColor(YELLOW)
            else:
                fill_col = QColor(GREEN)
            p.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), fill_col)

        # DCCD percentage
        dccd_str = f"{dccd:.0f}%" if not stale else "---%"
        p.setFont(QFont("Helvetica", 11, QFont.Bold))
        p.setPen(QColor(WHITE) if not stale and dccd > 50 else QColor(DIM))
        p.drawText(QRectF(bar_x + bar_w + 4, bar_y - 2, 50, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, dccd_str)

        # Surface state badge
        if snap and not stale:
            surface_label = snap.surface_state.label
            surface_color = QColor(snap.surface_state.color)
        else:
            surface_label = "---"
            surface_color = QColor(DIM)

        p.setFont(QFont("Helvetica", 9, QFont.Bold))
        badge_tw = p.fontMetrics().horizontalAdvance(surface_label) + 12
        badge_x = 750 - badge_tw
        badge_y = bar_y
        pill_bg = QColor(surface_color)
        pill_bg.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_tw, bar_h), 4, 4)
        p.setPen(surface_color)
        p.drawText(QRectF(badge_x, badge_y, badge_tw, bar_h), Qt.AlignCenter, surface_label)

        # ABS/VDC indicator dots
        dot_y = strip_y + strip_h - 6
        if snap and not stale:
            if snap.abs_active:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(RED))
                p.drawEllipse(QPointF(748, dot_y), 4, 4)
                p.setFont(QFont("Helvetica", 7))
                p.setPen(QColor(RED))
                p.drawText(QRectF(756, dot_y - 5, 38, 12),
                           Qt.AlignLeft | Qt.AlignVCenter, "ABS")

            if snap.vdc_tc:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(YELLOW))
                p.drawEllipse(QPointF(748, dot_y - 14), 4, 4)
                p.setFont(QFont("Helvetica", 7))
                p.setPen(QColor(YELLOW))
                p.drawText(QRectF(756, dot_y - 19, 38, 12),
                           Qt.AlignLeft | Qt.AlignVCenter, "VDC")

    # ------------------------------------------------------------------
    # Sector strip (y=280..320) — UNCHANGED
    # ------------------------------------------------------------------

    def _draw_sector_strip(self, p: QPainter) -> None:
        sector_count = self._timing.get("sector_count", 0)
        if sector_count <= 0:
            p.fillRect(QRectF(_BAR_X, _SECTOR_Y0, _BAR_W, _SECTOR_Y1 - _SECTOR_Y0), QColor(BG_PANEL))
            return

        current_sector = self._timing.get("current_sector", 0)
        sector_times = self._timing.get("sector_times", [])
        best_sector_times = self._timing.get("best_sector_times", [])

        sector_w = _BAR_W / sector_count
        strip_h = _SECTOR_Y1 - _SECTOR_Y0
        gap = 2

        for i in range(sector_count):
            sx = _BAR_X + i * sector_w
            rect = QRectF(sx + gap / 2, _SECTOR_Y0 + 2, sector_w - gap, strip_h - 4)

            if i < len(sector_times) and sector_times[i] is not None:
                sector_ms = sector_times[i]
                best_ms = best_sector_times[i] if i < len(best_sector_times) and best_sector_times[i] else None

                if best_ms is not None and sector_ms <= best_ms:
                    fill_color = QColor(GREEN)
                else:
                    fill_color = QColor(RED)

                p.fillRect(rect, fill_color)

                time_str = f"{sector_ms / 1000.0:.1f}"
                p.setPen(QColor(WHITE))
                p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
                p.drawText(rect, Qt.AlignCenter, time_str)

            elif i == current_sector:
                p.fillRect(rect, QColor(BG_PANEL))
                pulse_alpha = 120 + int(80 * (1.0 if self._paint_count % 20 < 10 else 0.4))
                pen_color = QColor(YELLOW)
                pen_color.setAlpha(pulse_alpha)
                p.setPen(QPen(pen_color, 2))
                p.drawRect(rect)
            else:
                p.fillRect(rect, QColor(BG_PANEL))
                p.setPen(QPen(QColor(DIM), 1))
                p.drawRect(rect)

    # ------------------------------------------------------------------
    # Brake/steering trace (y=320..380) — steering replaces throttle
    # ------------------------------------------------------------------

    def _draw_brake_steering_trace(self, p: QPainter) -> None:
        strip_x = _BAR_X
        strip_w = _BAR_W
        strip_y = _BRAKE_Y0
        strip_h = _BRAKE_Y1 - _BRAKE_Y0

        p.fillRect(QRectF(strip_x, strip_y, strip_w, strip_h), QColor(BG_PANEL))

        brake_count = len(self._brake_history)

        if brake_count == 0:
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(QRectF(strip_x, strip_y, strip_w, strip_h),
                       Qt.AlignCenter, "BRAKE / STEERING TRACE")
            return

        sample_w = strip_w / _TRACE_LEN
        max_brake = 80.0
        center_y = strip_y + strip_h / 2.0

        # Draw steering first (behind brake) — blue fill from center line
        # Steering: 0 = straight, positive = left, negative = right
        # Map to half-height from center: full lock = fills to edge
        p.setPen(Qt.NoPen)
        for idx, steer in enumerate(self._steering_history):
            offset = _TRACE_LEN - len(self._steering_history) + idx
            x = strip_x + offset * sample_w
            # Normalize: -1..+1 range
            norm = max(-1.0, min(1.0, steer / _STEER_MAX))
            steer_h = abs(norm) * (strip_h / 2.0)
            steer_color = QColor(CYAN)
            steer_color.setAlpha(50)

            if norm >= 0:
                # Left turn — fill upward from center
                p.fillRect(QRectF(x, center_y - steer_h, max(sample_w, 1.0), steer_h), steer_color)
            else:
                # Right turn — fill downward from center
                p.fillRect(QRectF(x, center_y, max(sample_w, 1.0), steer_h), steer_color)

        # Center line for steering
        p.setPen(QPen(QColor(DIM), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(strip_x, center_y), QPointF(strip_x + strip_w, center_y))

        # Draw brake — solid red fill from bottom
        for idx, brk in enumerate(self._brake_history):
            offset = _TRACE_LEN - brake_count + idx
            x = strip_x + offset * sample_w
            brk_h = (min(brk, max_brake) / max_brake) * strip_h
            brk_y = strip_y + strip_h - brk_h
            brk_color = QColor(RED)
            brk_color.setAlpha(180)
            p.fillRect(QRectF(x, brk_y, max(sample_w, 1.0), brk_h), brk_color)

        # Subtle border
        p.setPen(QPen(QColor(DIM), 1))
        p.drawRect(QRectF(strip_x, strip_y, strip_w, strip_h))

    # ------------------------------------------------------------------
    # Safety vitals (y=380..440) — 5 zones, DIM until warning
    # ------------------------------------------------------------------

    def _draw_safety_vitals(self, p: QPainter) -> None:
        snap = self._snap
        strip_y = _VITALS_Y0
        strip_h = _VITALS_Y1 - _VITALS_Y0

        p.fillRect(QRectF(0, strip_y, _W, strip_h), QColor(BG_DARK))

        oil_psi = snap.oil_psi if snap else 0.0
        coolant = snap.coolant_temp if snap else 0.0
        oil_temp = snap.oil_temp_c if snap else 0.0
        dccd = snap.dccd_command_pct if snap else 0.0
        stale = snap.is_engine_stale() if snap else True

        # FLIR hottest corner
        flir_ok = snap is not None and snap.flir_available and not snap.is_flir_stale()
        if flir_ok:
            corners = [
                ("FL", snap.brake_temp_fl), ("FR", snap.brake_temp_fr),
                ("RL", snap.brake_temp_rl), ("RR", snap.brake_temp_rr),
            ]
            hottest_label, hottest_temp = max(corners, key=lambda c: c[1])
        else:
            hottest_label, hottest_temp = "---", 0.0

        # 5 zones
        zone_w = _W / 5

        # --- OIL PSI ---
        oil_warn = oil_psi <= _OIL_WARN_LOW and not stale
        oil_crit = oil_psi <= _OIL_CRIT_LOW and not stale
        if oil_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif oil_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        self._draw_vital(p, 0, zone_w, "OIL", f"{oil_psi:.0f}", "PSI",
                         lc, vc if not stale else QColor(DIM), large=oil_warn)

        # --- COOLANT ---
        cool_warn = coolant >= _COOL_WARN and not stale
        cool_crit = coolant >= _COOL_CRIT and not stale
        if cool_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif cool_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        self._draw_vital(p, zone_w, zone_w, "COOL", f"{coolant:.0f}", "\u00b0C",
                         lc, vc if not stale else QColor(DIM), large=cool_warn)

        # --- OIL TEMP ---
        oil_t_warn = oil_temp > _OILT_WARN and not stale
        oil_t_crit = oil_temp > _OILT_CRIT and not stale
        if oil_t_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif oil_t_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        self._draw_vital(p, zone_w * 2, zone_w, "OIL T", f"{oil_temp:.0f}", "\u00b0C",
                         lc, vc if not stale else QColor(DIM), large=oil_t_warn)

        # --- BRAKE TEMP (hottest corner) ---
        brk_warn = hottest_temp > _BRKT_WARN and flir_ok
        brk_crit = hottest_temp > _BRKT_CRIT and flir_ok
        if brk_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif brk_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        brk_val = f"{hottest_label} {hottest_temp:.0f}" if flir_ok else "---"
        self._draw_vital(p, zone_w * 3, zone_w, "BRK T", brk_val, "\u00b0C",
                         lc, vc if flir_ok else QColor(DIM), large=brk_warn)

        # --- DCCD (compact bar) ---
        dccd_x = zone_w * 4
        dccd_w = zone_w - 20
        stale_diff = snap is None or snap.is_diff_stale()

        p.setPen(QColor(DIM))
        p.setFont(QFont("Helvetica", 10))
        p.drawText(int(dccd_x) + 10, strip_y + 18, "DCCD")

        bar_x = int(dccd_x) + 10
        bar_y = strip_y + 22
        bar_w = int(dccd_w) - 10
        bar_h = 10

        p.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor(DIM))

        if not stale_diff:
            fill_w = (dccd / 100.0) * bar_w
            if dccd > 70:
                fill_col = QColor(MODE_SS_ACCENT)
            elif dccd > 40:
                fill_col = QColor(YELLOW)
            else:
                fill_col = QColor(GREEN)
            p.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), fill_col)

        dccd_col = QColor(DIM) if dccd < 50 else QColor(WHITE)
        if stale_diff:
            dccd_col = QColor(DIM)
        p.setPen(dccd_col)
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        p.drawText(QRectF(bar_x, bar_y + bar_h + 2, bar_w, 18), Qt.AlignCenter, f"{dccd:.0f}%")

    def _draw_vital(
        self,
        p: QPainter,
        x: float,
        w: float,
        label: str,
        value: str,
        unit: str,
        label_color: QColor,
        value_color: QColor,
        large: bool = False,
    ) -> None:
        """Draw a single safety vital — label above, value + unit below."""
        # Label
        p.setPen(label_color)
        p.setFont(QFont("Helvetica", 10))
        label_rect = QRectF(x, _VITALS_Y0 + 2, w, 14)
        p.drawText(label_rect, Qt.AlignCenter, label)

        # Value
        font_size = FONT_BIG if large else FONT_HEADER
        p.setPen(value_color)
        p.setFont(QFont("Courier", font_size, QFont.Bold))
        value_rect = QRectF(x, _VITALS_Y0 + 18, w, 30)
        p.drawText(value_rect, Qt.AlignCenter, f"{value}{unit}")
