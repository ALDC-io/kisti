"""KiSTI - Intelligent Mode Screen (SI-Drive = 0)

Calm / diagnostic / street display.  Rich context the AiM MXG Strada
cannot show: weather, FLIR brake temps, vehicle health, wheel deltas.

Full QPainter rendering — no composite QWidget layouts.

Content area: 800x440 (status bar above, no softkey bar).
Color accent: MODE_I_ACCENT (#00AAFF) blue.

Layout:
  Top (0..100)      — Weather expanded (left 400) | Warm-up + DCCD + Surface + GPS (right 400)
  Middle (100..300)  — FLIR brake temps (left 320) | Vehicle health + wheel overview (right 480)
  Bottom (300..440)  — Brake temp sparklines (left 400) | Wheel speed delta bars (right 400)
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
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
    MODE_I_ACCENT,
    FONT_HEADER,
    FONT_BIG,
)

# ---------------------------------------------------------------------------
# Ring buffer size: 10 seconds at 20 Hz
# ---------------------------------------------------------------------------
_HISTORY_SIZE: int = 200

# ---------------------------------------------------------------------------
# FLIR brake temp thresholds (deg C)
# ---------------------------------------------------------------------------
_FLIR_COLD: float = 150.0
_FLIR_GREEN: float = 300.0
_FLIR_YELLOW: float = 450.0
_FLIR_RED: float = 500.0

# ---------------------------------------------------------------------------
# Wheel speed delta thresholds (km/h)
# ---------------------------------------------------------------------------
_WS_MODERATE: float = 2.0
_WS_SEVERE: float = 5.0

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_W = 800
_H = 480


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _font(size: int, bold: bool = False) -> QFont:
    f = QFont("Helvetica", size)
    if bold:
        f.setWeight(QFont.Bold)
    return f


# ---------------------------------------------------------------------------
# Brake heat color: blue (<150) -> green (<300) -> yellow (<450) -> red (>500)
# ---------------------------------------------------------------------------

def _brake_heat_color(temp_c: float) -> QColor:
    """Blue (cold) -> Green (optimal) -> Yellow (warm) -> Red (hot)."""
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


def _wheel_delta_color(abs_delta: float) -> str:
    """Wheel speed delta color: cyan=small, yellow=moderate, red=severe."""
    if abs_delta > _WS_SEVERE:
        return RED
    if abs_delta > _WS_MODERATE:
        return YELLOW
    return CYAN


# ---------------------------------------------------------------------------
# IntelligentScreenWidget
# ---------------------------------------------------------------------------

class IntelligentScreenWidget(QWidget):
    """Full QPainter-based Intelligent mode display (SI-Drive = 0).

    Shows ONLY data the AiM MXG Strada 7" cannot:
      - Weather (Yoctopuce ambient)
      - FLIR brake temps (4-corner)
      - Vehicle health (DCCD, surface, warm-up, ABS/VDC, ethanol)
      - Wheel speed deltas + slip
      - GPS fix indicator
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap: DiffState | None = None

        # 10-second ring buffers for brake temp sparklines (pushed at 20 Hz)
        self._brake_fl_history: deque[float] = deque(maxlen=_HISTORY_SIZE)
        self._brake_fr_history: deque[float] = deque(maxlen=_HISTORY_SIZE)
        self._brake_rl_history: deque[float] = deque(maxlen=_HISTORY_SIZE)
        self._brake_rr_history: deque[float] = deque(maxlen=_HISTORY_SIZE)

        # Tell Qt we paint our entire rect every frame (compositorless X11)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

        # Force periodic repaint even without data (1 Hz)
        from PySide6.QtCore import QTimer
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(1000)
        self._repaint_timer.timeout.connect(self.update)
        self._repaint_timer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Called at 20 Hz from MainWindow with the latest DiffState snapshot."""
        self._snap = snap
        self._brake_fl_history.append(snap.brake_temp_fl)
        self._brake_fr_history.append(snap.brake_temp_fr)
        self._brake_rl_history.append(snap.brake_temp_rl)
        self._brake_rr_history.append(snap.brake_temp_rr)
        self.update()  # schedule repaint

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Full background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Mode label top-right
        p.setPen(QColor(MODE_I_ACCENT))
        p.setFont(QFont("Helvetica", 16, QFont.Bold))
        p.drawText(QRectF(w - 200, 2, 190, 30), Qt.AlignRight | Qt.AlignVCenter,
                   "INTELLIGENT")

        snap = self._snap
        stale_engine = snap is None or snap.is_engine_stale()
        stale_diff = snap is None or snap.is_diff_stale()
        stale_gps = snap is None or snap.is_gps_stale()
        stale_flir = snap is None or snap.is_flir_stale()
        stale_wheel = snap is None or snap.is_wheel_stale()

        # --- Top section (y=0..100): Weather + Vehicle State ---
        self._draw_top_section(p, snap, stale_gps, stale_diff, stale_engine)

        # Divider
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(0, 100, w, 100)

        # --- Middle section (y=100..300): FLIR + Health ---
        self._draw_middle_section(p, snap, stale_flir, stale_wheel, stale_engine,
                                  stale_diff)

        # Divider
        p.drawLine(0, 300, w, 300)

        # --- Bottom section (y=300..440): Sparklines + Wheel deltas ---
        self._draw_bottom_section(p, snap, stale_flir, stale_wheel)

        p.end()

    # ==================================================================
    # TOP SECTION (y=0..100): Weather (left) | Warm-up + DCCD + Surface + GPS (right)
    # ==================================================================

    def _draw_top_section(
        self, p: QPainter, snap: DiffState | None,
        stale_gps: bool, stale_diff: bool, stale_engine: bool,
    ) -> None:
        self._draw_weather_card(p, x=0, y=0, cw=400, ch=100, snap=snap)
        self._draw_vehicle_state_panel(p, x=400, y=0, cw=400, ch=100, snap=snap,
                                       stale_diff=stale_diff, stale_gps=stale_gps,
                                       stale_engine=stale_engine)

    # ------------------------------------------------------------------
    # Weather card (expanded, full top-left 400x100)
    # ------------------------------------------------------------------

    def _draw_weather_card(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        snap: DiffState | None,
    ) -> None:
        """Ambient weather: temp, humidity, pressure, density altitude, dew point."""
        # Card background
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(QColor(BG_ACCENT))
        p.drawRoundedRect(QRectF(x + 4, y + 4, cw - 8, ch - 8), 4, 4)

        # Header
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(x + 12, y + 6, cw - 24, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "WEATHER")

        available = snap is not None and snap.ambient_available
        row_h = 15
        row_y = y + 24

        # Two-column layout: left column and right column within the card
        col1_lx = x + 12
        col1_vx = x + 80
        col1_vw = 100

        col2_lx = x + 198
        col2_vx = x + 280
        col2_vw = 108

        # Column 1 rows
        rows_left = [
            ("TEMP", f"{snap.ambient_temp_c:.1f}\u00b0C" if available else "---"),
            ("HUMIDITY", f"{snap.ambient_humidity_pct:.0f}%" if available else "---"),
            ("PRESSURE", f"{snap.ambient_pressure_hpa:.0f} hPa" if available else "---"),
        ]

        # Column 2 rows
        rows_right = [
            ("DENS ALT", f"{snap.density_altitude_ft:.0f} ft" if available else "---"),
            ("DEW PT", f"{snap.dew_point_c:.1f}\u00b0C" if available else "---"),
        ]

        for i, (label, value) in enumerate(rows_left):
            ry = row_y + i * row_h
            p.setFont(_font(10))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(col1_lx, ry, col1_vx - col1_lx, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            val_color = QColor(WHITE) if available else QColor(GRAY)
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(val_color))
            p.drawText(QRectF(col1_vx, ry, col1_vw, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, value)

        for i, (label, value) in enumerate(rows_right):
            ry = row_y + i * row_h
            p.setFont(_font(10))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(col2_lx, ry, col2_vx - col2_lx, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            val_color = QColor(WHITE) if available else QColor(GRAY)
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(val_color))
            p.drawText(QRectF(col2_vx, ry, col2_vw, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, value)

        # "NO SENSOR" label if unavailable
        if not available:
            p.setFont(_font(9))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(col2_lx, row_y + 2 * row_h, col2_vw + 82, row_h),
                       Qt.AlignLeft | Qt.AlignVCenter, "NO SENSOR")

    # ------------------------------------------------------------------
    # Vehicle state panel (top-right 400x100)
    # Warm-up state, DCCD bar, Surface badge, GPS fix indicator
    # ------------------------------------------------------------------

    def _draw_vehicle_state_panel(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        snap: DiffState | None,
        stale_diff: bool, stale_gps: bool, stale_engine: bool,
    ) -> None:
        inner_x = x + 8
        inner_w = cw - 16

        # --- Row 1: Warm-up state (large + prominent) ---
        warmup_y = y + 8
        warmup_h = 22
        if snap is not None:
            warmup_label = snap.warmup_state.label
            warmup_color = QColor(snap.warmup_state.color)
        else:
            warmup_label = "---"
            warmup_color = QColor(GRAY)

        p.setFont(_font(FONT_HEADER, bold=True))
        p.setPen(QPen(warmup_color))
        p.drawText(
            QRectF(inner_x, warmup_y, inner_w // 2, warmup_h),
            Qt.AlignLeft | Qt.AlignVCenter,
            warmup_label,
        )

        # GPS fix indicator — right side of warm-up row
        gps_dot_x = x + cw - 80
        if stale_gps or snap is None:
            sat_text = "GPS ---"
            dot_color = QColor(GRAY)
        else:
            sats = snap.gps_satellites
            fix_q = snap.gps_fix_quality
            sat_text = f"GPS {sats}"
            if fix_q >= 2:
                dot_color = QColor(GREEN)
            elif fix_q >= 1:
                dot_color = QColor(YELLOW)
            else:
                dot_color = QColor(RED)

        # Fix quality dot
        dot_r = 5
        dot_cy = warmup_y + warmup_h // 2
        p.setPen(Qt.NoPen)
        p.setBrush(dot_color)
        p.drawEllipse(QPointF(gps_dot_x, dot_cy), dot_r, dot_r)

        # Satellite count text
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(dot_color))
        p.drawText(QRectF(gps_dot_x + 10, warmup_y, 60, warmup_h),
                   Qt.AlignLeft | Qt.AlignVCenter, sat_text)

        # --- Row 2: DCCD lock bar ---
        dccd_y = warmup_y + warmup_h + 6
        dccd_bar_h = 14
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(inner_x, dccd_y, 44, dccd_bar_h),
                   Qt.AlignLeft | Qt.AlignVCenter, "DCCD")

        bar_x = inner_x + 46
        bar_w = inner_w - 100
        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(bar_x, dccd_y, bar_w, dccd_bar_h), 3, 3)

        if not stale_diff and snap is not None:
            lock_frac = min(snap.dccd_command_pct / 100.0, 1.0)
            if lock_frac > 0.01:
                lock_color = QColor(MODE_I_ACCENT)
                if snap.dccd_command_pct > 80:
                    lock_color = QColor(YELLOW)
                p.setBrush(lock_color)
                p.drawRoundedRect(
                    QRectF(bar_x, dccd_y, bar_w * lock_frac, dccd_bar_h), 3, 3
                )
            pct_text = f"{snap.dccd_command_pct:.0f}%"
            pct_color = QColor(WHITE)
        else:
            pct_text = "---%"
            pct_color = QColor(GRAY)

        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, dccd_y, bar_w, dccd_bar_h), 3, 3)

        p.setFont(_font(10, bold=True))
        p.setPen(QPen(pct_color))
        p.drawText(
            QRectF(bar_x + bar_w + 4, dccd_y, 46, dccd_bar_h),
            Qt.AlignLeft | Qt.AlignVCenter,
            pct_text,
        )

        # --- Row 3: Surface badge ---
        badge_y = dccd_y + dccd_bar_h + 6
        badge_h = 18
        if snap is not None:
            surface_label = snap.surface_state.label
            surface_color = QColor(snap.surface_state.color)
        else:
            surface_label = "---"
            surface_color = QColor(GRAY)

        p.setFont(_font(10, bold=True))
        badge_tw = p.fontMetrics().horizontalAdvance(surface_label) + 16
        # Pill background
        p.setPen(Qt.NoPen)
        pill_bg = QColor(surface_color)
        pill_bg.setAlphaF(0.25)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(inner_x, badge_y, badge_tw, badge_h), 9, 9)
        p.setPen(QPen(surface_color))
        p.drawText(
            QRectF(inner_x, badge_y, badge_tw, badge_h),
            Qt.AlignCenter,
            surface_label,
        )

    # ==================================================================
    # MIDDLE SECTION (y=100..300): FLIR (left) | Health overview (right)
    # ==================================================================

    def _draw_middle_section(
        self, p: QPainter, snap: DiffState | None,
        stale_flir: bool, stale_wheel: bool, stale_engine: bool,
        stale_diff: bool,
    ) -> None:
        self._draw_flir_panel(p, x=0, y=100, cw=320, ch=200, snap=snap,
                              stale=stale_flir)
        # Vertical divider
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(320, 106, 320, 294)
        self._draw_health_panel(p, x=320, y=100, cw=480, ch=200, snap=snap,
                                stale_wheel=stale_wheel, stale_engine=stale_engine,
                                stale_diff=stale_diff)

    # ------------------------------------------------------------------
    # FLIR brake temp display (left, 320x200)
    # ------------------------------------------------------------------

    def _draw_flir_panel(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        snap: DiffState | None, stale: bool,
    ) -> None:
        """4-corner brake temp display with front-rear delta indicator."""
        flir_ok = snap is not None and snap.flir_available and not stale

        # Header
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(x + 10, y + 6, cw - 20, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "BRAKE TEMPS")

        if not flir_ok:
            # Not connected
            p.setFont(_font(12))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(x, y + 60, cw, 30), Qt.AlignCenter,
                       "FLIR NOT CONNECTED")
            return

        # 2x2 grid of brake temps
        grid_x = x + 16
        grid_y = y + 28
        cell_w = 135
        cell_h = 68

        corners = [
            ("FL", snap.brake_temp_fl, grid_x, grid_y),
            ("FR", snap.brake_temp_fr, grid_x + cell_w + 10, grid_y),
            ("RL", snap.brake_temp_rl, grid_x, grid_y + cell_h + 8),
            ("RR", snap.brake_temp_rr, grid_x + cell_w + 10, grid_y + cell_h + 8),
        ]

        for label, temp, cx, cy in corners:
            rect = QRectF(cx, cy, cell_w, cell_h)

            # Heat-colored background
            heat_col = _brake_heat_color(temp)
            bg = QColor(heat_col)
            bg.setAlpha(50)
            p.fillRect(rect, bg)

            # Border
            p.setPen(QPen(heat_col, 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 4, 4)

            # Corner label — small top-left
            p.setFont(_font(9, bold=True))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(int(cx) + 6, int(cy) + 14, label)

            # Temperature — large centered
            p.setFont(_font(FONT_BIG, bold=True))
            p.setPen(QPen(heat_col))
            p.drawText(rect, Qt.AlignCenter, f"{temp:.0f}\u00b0")

        # Front-rear delta indicator
        delta_y = grid_y + 2 * cell_h + 20
        front_avg = (snap.brake_temp_fl + snap.brake_temp_fr) / 2.0
        rear_avg = (snap.brake_temp_rl + snap.brake_temp_rr) / 2.0
        fr_delta = abs(front_avg - rear_avg)

        p.setFont(_font(10, bold=True))
        if fr_delta > 50.0:
            delta_color = QColor(YELLOW)
            delta_label = f"F/R \u0394 {fr_delta:.0f}\u00b0C  IMBALANCE"
        else:
            delta_color = QColor(GREEN)
            delta_label = f"F/R \u0394 {fr_delta:.0f}\u00b0C"
        p.setPen(QPen(delta_color))
        p.drawText(QRectF(x + 10, delta_y, cw - 20, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, delta_label)

    # ------------------------------------------------------------------
    # Vehicle health panel (right, 480x200)
    # ------------------------------------------------------------------

    def _draw_health_panel(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        snap: DiffState | None,
        stale_wheel: bool, stale_engine: bool, stale_diff: bool,
    ) -> None:
        """Wheel speeds, slip delta, service, ABS/VDC, E85."""
        inner_x = x + 10
        inner_w = cw - 20

        # --- Wheel speed overview (4 lines) ---
        ws_y = y + 8
        ws_h = 18
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(inner_x, ws_y, inner_w, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, "WHEEL SPEEDS")

        ws_row_y = ws_y + 18
        vehicle_speed = snap.speed_kph if snap is not None else 0.0

        wheels = [
            ("FL", snap.wheel_speed_fl if snap else 0.0),
            ("FR", snap.wheel_speed_fr if snap else 0.0),
            ("RL", snap.wheel_speed_rl if snap else 0.0),
            ("RR", snap.wheel_speed_rr if snap else 0.0),
        ]

        for i, (name, ws) in enumerate(wheels):
            ry = ws_row_y + i * ws_h
            delta = ws - vehicle_speed if not stale_wheel and snap is not None else 0.0

            # Label
            p.setFont(_font(10, bold=True))
            p.setPen(QPen(QColor(SILVER)))
            p.drawText(QRectF(inner_x, ry, 26, ws_h),
                       Qt.AlignLeft | Qt.AlignVCenter, name)

            # Speed value
            if stale_wheel or snap is None:
                spd_text = "---"
                val_color = QColor(GRAY)
            else:
                spd_text = f"{ws:.0f} km/h"
                val_color = QColor(WHITE)
            p.setFont(_font(10))
            p.setPen(QPen(val_color))
            p.drawText(QRectF(inner_x + 28, ry, 80, ws_h),
                       Qt.AlignLeft | Qt.AlignVCenter, spd_text)

            # Delta from vehicle speed
            if stale_wheel or snap is None:
                delta_text = ""
                delta_col = QColor(GRAY)
            else:
                sign = "+" if delta >= 0 else ""
                delta_text = f"{sign}{delta:.1f}"
                delta_col = QColor(_wheel_delta_color(abs(delta)))
            p.setFont(_font(10, bold=True))
            p.setPen(QPen(delta_col))
            p.drawText(QRectF(inner_x + 110, ry, 60, ws_h),
                       Qt.AlignLeft | Qt.AlignVCenter, delta_text)

        # --- Slip delta (right of wheel speeds) ---
        slip_x = inner_x + 200
        slip_y = ws_row_y
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(slip_x, slip_y, 120, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "SLIP \u0394")

        if snap is not None and snap.slip_delta is not None and not stale_wheel:
            slip_val = snap.slip_delta
            slip_color = QColor(_wheel_delta_color(abs(slip_val)))
            p.setFont(_font(FONT_BIG, bold=True))
            p.setPen(QPen(slip_color))
            p.drawText(QRectF(slip_x, slip_y + 18, 120, 36),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{slip_val:+.1f}")
            p.setFont(_font(10))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(slip_x + 80, slip_y + 26, 40, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, "km/h")
        else:
            p.setFont(_font(FONT_BIG, bold=True))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(slip_x, slip_y + 18, 120, 36),
                       Qt.AlignLeft | Qt.AlignVCenter, "---")

        # --- Service / engine info ---
        svc_y = ws_row_y + 4 * ws_h + 6
        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(inner_x, svc_y, inner_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "ENGINE: 0 km")

        # --- Status indicators row: ABS, VDC, BRK, HBRK ---
        ind_y = svc_y + 20
        ind_r = 5
        indicators = [
            ("ABS", snap.abs_active if snap else False),
            ("VDC", snap.vdc_tc if snap else False),
            ("BRK", snap.brake if snap else False),
            ("HBRK", snap.handbrake if snap else False),
        ]

        ind_x = inner_x
        for label, active in indicators:
            # Dot
            dot_color = QColor(RED) if active else QColor(DIM)
            p.setPen(Qt.NoPen)
            p.setBrush(dot_color)
            p.drawEllipse(QPointF(ind_x + ind_r, ind_y + ind_r), ind_r, ind_r)

            # Label
            p.setFont(_font(9))
            p.setPen(QPen(QColor(WHITE) if active else QColor(GRAY)))
            p.drawText(QRectF(ind_x + ind_r * 2 + 4, ind_y, 40, ind_r * 2),
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            ind_x += 60

        # --- E85 ethanol percentage ---
        eth_y = ind_y + 20
        if stale_engine or snap is None:
            eth_text = "E85: ---"
            eth_color = QColor(GRAY)
        else:
            eth_text = f"E85: {snap.ethanol_pct:.0f}%"
            eth_color = QColor(CYAN)

        p.setFont(_font(11, bold=True))
        p.setPen(QPen(eth_color))
        p.drawText(QRectF(inner_x, eth_y, inner_w, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, eth_text)

    # ==================================================================
    # BOTTOM SECTION (y=300..440): Sparklines (left) | Wheel delta bars (right)
    # ==================================================================

    def _draw_bottom_section(
        self, p: QPainter, snap: DiffState | None,
        stale_flir: bool, stale_wheel: bool,
    ) -> None:
        self._draw_brake_sparklines(p, x=0, y=300, cw=400, ch=140,
                                    stale=stale_flir)
        # Vertical divider
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(400, 306, 400, 434)
        self._draw_wheel_delta_bars(p, x=400, y=300, cw=400, ch=140,
                                    snap=snap, stale=stale_wheel)

    # ------------------------------------------------------------------
    # Brake temp sparklines (bottom-left 400x140)
    # ------------------------------------------------------------------

    def _draw_brake_sparklines(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        stale: bool,
    ) -> None:
        """4 sparklines: FL, FR, RL, RR brake temps with heat-colored lines."""
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(x + 10, y + 4, cw - 20, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, "BRAKE TEMP HISTORY")

        sparklines = [
            ("FL", self._brake_fl_history),
            ("FR", self._brake_fr_history),
            ("RL", self._brake_rl_history),
            ("RR", self._brake_rr_history),
        ]

        sp_y = y + 22
        sp_h = 26
        sp_gap = 2

        for i, (label, data) in enumerate(sparklines):
            sy = sp_y + i * (sp_h + sp_gap)
            # Determine heat color from latest value
            if len(data) > 0 and not stale:
                heat_color = _brake_heat_color(data[-1])
                color_str = heat_color.name()
            else:
                color_str = GRAY

            self._draw_sparkline(
                p, x=x + 10, y=sy, sw=290, sh=sp_h,
                label=label,
                data=data,
                color=color_str,
                min_val=0.0, max_val=600.0,
            )
            self._draw_sparkline_value(
                p, x=x + 306, y=sy, sh=sp_h,
                data=data,
                fmt="{:.0f}",
                unit="\u00b0C",
                stale=stale,
            )

    # ------------------------------------------------------------------
    # Wheel speed delta bars (bottom-right 400x140)
    # ------------------------------------------------------------------

    def _draw_wheel_delta_bars(
        self, p: QPainter, x: int, y: int, cw: int, ch: int,
        snap: DiffState | None, stale: bool,
    ) -> None:
        """4 horizontal bars centered on zero for wheel speed deltas."""
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(x + 10, y + 4, cw - 20, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, "WHEEL SPEED \u0394")

        bar_y0 = y + 24
        bar_h = 20
        row_gap = 6
        label_x = x + 10
        label_w = 28
        center_x = x + 60 + 130  # center of bar area
        bar_half_w = 130
        val_x = x + 60 + 260 + 6
        val_w = 60

        vehicle_speed = snap.speed_kph if snap is not None else 0.0

        wheels = [
            ("FL", snap.wheel_speed_fl if snap else 0.0),
            ("FR", snap.wheel_speed_fr if snap else 0.0),
            ("RL", snap.wheel_speed_rl if snap else 0.0),
            ("RR", snap.wheel_speed_rr if snap else 0.0),
        ]

        for i, (name, ws) in enumerate(wheels):
            ry = bar_y0 + i * (bar_h + row_gap)
            delta = ws - vehicle_speed if not stale and snap is not None else 0.0

            # Label
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(QColor(SILVER)))
            p.drawText(QRectF(label_x, ry, label_w, bar_h),
                       Qt.AlignLeft | Qt.AlignVCenter, name)

            # Bar background
            bar_bg_x = center_x - bar_half_w
            p.fillRect(int(bar_bg_x), int(ry + 2),
                       int(bar_half_w * 2), int(bar_h - 4),
                       QColor(BG_ACCENT))

            # Center line
            p.setPen(QPen(QColor(GRAY), 1))
            p.drawLine(int(center_x), int(ry + 2),
                       int(center_x), int(ry + bar_h - 2))

            if not stale and snap is not None:
                # Delta bar from center
                color = _wheel_delta_color(abs(delta))
                max_delta = 10.0
                frac = min(1.0, abs(delta) / max_delta)
                bar_px = int(bar_half_w * frac)

                if delta >= 0:
                    p.fillRect(int(center_x), int(ry + 2),
                               bar_px, int(bar_h - 4), QColor(color))
                else:
                    p.fillRect(int(center_x - bar_px), int(ry + 2),
                               bar_px, int(bar_h - 4), QColor(color))

                sign = "+" if delta >= 0 else ""
                val_str = f"{sign}{delta:.1f}"
            else:
                val_str = "---"

            # Value text
            p.setFont(_font(10, bold=True))
            val_color = QColor(_wheel_delta_color(abs(delta))) if (not stale and snap is not None) else QColor(GRAY)
            p.setPen(QPen(val_color))
            p.drawText(QRectF(val_x, ry, val_w, bar_h),
                       Qt.AlignLeft | Qt.AlignVCenter, val_str)

        # Slip delta — below bars, within content area (y<=440)
        slip_y = bar_y0 + 4 * (bar_h + row_gap) - 6
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(label_x, slip_y, 60, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, "SLIP \u0394")

        if snap is not None and snap.slip_delta is not None and not stale:
            slip_val = snap.slip_delta
            slip_color = QColor(_wheel_delta_color(abs(slip_val)))
            p.setFont(_font(FONT_HEADER, bold=True))
            p.setPen(QPen(slip_color))
            p.drawText(QRectF(label_x + 62, slip_y - 2, 80, 22),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{slip_val:+.1f}")
            p.setFont(_font(10))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(label_x + 130, slip_y, 40, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, "km/h")
        else:
            p.setFont(_font(FONT_HEADER, bold=True))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(label_x + 62, slip_y - 2, 80, 22),
                       Qt.AlignLeft | Qt.AlignVCenter, "---")

    # ------------------------------------------------------------------
    # Sparkline rendering (inline QPainter, no child widgets)
    # ------------------------------------------------------------------

    def _draw_sparkline(
        self,
        p: QPainter,
        x: int, y: int, sw: int, sh: int,
        label: str,
        data: deque[float],
        color: str,
        min_val: float = 0.0,
        max_val: float = 100.0,
        color_hi: str | None = None,
        hi_threshold: float = 0.0,
    ) -> None:
        """Draw a single sparkline chart at (x, y) with size (sw, sh)."""
        label_w = 30
        chart_x = x + label_w
        chart_w = sw - label_w
        chart_h = sh

        # Label
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(
            QRectF(x, y, label_w - 4, chart_h),
            Qt.AlignVCenter | Qt.AlignLeft,
            label,
        )

        # Chart background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(chart_x, y, chart_w, chart_h), 3, 3)

        n = len(data)
        if n < 2:
            # Border only
            p.setPen(QPen(QColor(DIM), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(chart_x, y, chart_w, chart_h), 3, 3)
            return

        # Y-axis range
        lo = min_val
        hi = max_val
        data_lo = min(data)
        data_hi = max(data)
        if data_lo < lo:
            lo = data_lo
        if data_hi > hi:
            hi = data_hi
        span = hi - lo if hi != lo else 1.0

        # Build points
        points: list[QPointF] = []
        for i, v in enumerate(data):
            px = chart_x + chart_w * i / (n - 1)
            py = y + chart_h - 1 - (v - lo) / span * (chart_h - 2)
            points.append(QPointF(px, py))

        # Filled area under curve
        fill_path = QPainterPath()
        fill_path.moveTo(QPointF(points[0].x(), y + chart_h - 1))
        for pt in points:
            fill_path.lineTo(pt)
        fill_path.lineTo(QPointF(points[-1].x(), y + chart_h - 1))
        fill_path.closeSubpath()

        fill_color = QColor(color)
        fill_color.setAlphaF(0.15)
        p.setPen(Qt.NoPen)
        p.setBrush(fill_color)
        p.drawPath(fill_path)

        # Signal line — segment coloring if hi threshold given
        line_color = QColor(color)
        line_hi = QColor(color_hi) if color_hi else line_color

        for i in range(len(points) - 1):
            val = list(data)[i + 1]
            c = line_hi if (color_hi and val >= hi_threshold) else line_color
            p.setPen(QPen(c, 1.5))
            p.drawLine(points[i], points[i + 1])

        # Border
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(chart_x, y, chart_w, chart_h), 3, 3)

    def _draw_sparkline_value(
        self,
        p: QPainter,
        x: int, y: int, sh: int,
        data: deque[float],
        fmt: str,
        unit: str,
        stale: bool,
    ) -> None:
        """Draw the current numeric value to the right of a sparkline."""
        if stale or len(data) == 0:
            text = "---"
            color = QColor(GRAY)
        else:
            text = fmt.format(data[-1])
            # Color by heat for brake temps
            color = _brake_heat_color(data[-1])

        p.setFont(_font(12, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRectF(x, y, 40, sh), Qt.AlignVCenter | Qt.AlignRight, text)

        p.setFont(_font(9))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x + 42, y, 30, sh), Qt.AlignVCenter | Qt.AlignLeft, unit)
