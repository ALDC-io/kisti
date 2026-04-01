"""KiSTI - Intelligent Mode Screen (SI-Drive = 0)

Calm / diagnostic / street display. Rich context, large fonts, low density.
Full QPainter rendering — no composite QWidget layouts.

Content area: 800x440 (status bar above, no softkey bar).
Color accent: MODE_I_ACCENT (#00AAFF) blue.

Layout:
  Top (0..120)    — Gear+Speed | Boost bar | Oil+Coolant
  Middle (120..300) — Sparklines | Weather card | Vehicle status
  Bottom (300..440)  — Lambda bar | Injector duty | GPS status
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
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
    FONT_BASE,
    FONT_HEADER,
    FONT_BIG,
    FONT_MEGA,
)

# ---------------------------------------------------------------------------
# Ring buffer size: 10 seconds at 20 Hz
# ---------------------------------------------------------------------------
_HISTORY_SIZE: int = 200

# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

# Boost bar range (kPa above atmospheric)
_BOOST_MAX_KPA: float = 200.0
_BOOST_WARN_KPA: float = 140.0
_BOOST_CRIT_KPA: float = 180.0

# Oil pressure thresholds (PSI)
_OIL_LOW_WARN: float = 25.0

# Coolant temperature thresholds (deg C)
_CLT_WARN: float = 105.0
_CLT_CRIT: float = 115.0

# Lambda bar range
_LAMBDA_MIN: float = 0.70
_LAMBDA_MAX: float = 1.30
_LAMBDA_TARGET: float = 1.0

# Injector duty thresholds (%)
_INJ_WARN: float = 80.0
_INJ_CRIT: float = 90.0

# Atmospheric pressure (kPa) for boost calculation
_ATM_KPA: float = 101.3

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _font(size: int, bold: bool = False) -> QFont:
    f = QFont("Helvetica", size)
    if bold:
        f.setWeight(QFont.Bold)
    return f


# ---------------------------------------------------------------------------
# IntelligentScreenWidget
# ---------------------------------------------------------------------------

class IntelligentScreenWidget(QWidget):
    """Full QPainter-based Intelligent mode display (SI-Drive = 0)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap: DiffState | None = None

        # 10-second ring buffers (pushed at 20 Hz)
        self._oil_history: deque[float] = deque(maxlen=_HISTORY_SIZE)
        self._coolant_history: deque[float] = deque(maxlen=_HISTORY_SIZE)
        self._boost_history: deque[float] = deque(maxlen=_HISTORY_SIZE)

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
        self._oil_history.append(snap.oil_psi)
        self._coolant_history.append(snap.coolant_temp)
        boost_kpa = max(0.0, snap.map_4bar_kpa - _ATM_KPA)
        self._boost_history.append(boost_kpa)
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

        # --- Top section (y=0..120): Primary vitals ---
        self._draw_top_section(p, w, snap, stale_engine)

        # Divider
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(0, 120, w, 120)

        # --- Middle section (y=120..300): Health overview ---
        self._draw_middle_section(p, w, snap, stale_engine, stale_diff)

        # Divider
        p.drawLine(0, 300, w, 300)

        # --- Bottom section (y=300..440): Status line ---
        self._draw_bottom_section(p, w, snap, stale_engine, stale_gps)

        p.end()

    # ==================================================================
    # TOP SECTION (y=0..120)
    # ==================================================================

    def _draw_top_section(
        self, p: QPainter, w: int, snap: DiffState | None, stale: bool
    ) -> None:
        """Gear+Speed (left), Boost bar (center), Oil+Coolant (right)."""
        # --- Left: Gear + Speed ---
        self._draw_gear_speed(p, snap, stale)
        # --- Center: Boost bar ---
        self._draw_boost_bar(p, w, snap, stale)
        # --- Right: Oil + Coolant ---
        self._draw_oil_coolant(p, w, snap, stale)

    def _draw_gear_speed(
        self, p: QPainter, snap: DiffState | None, stale: bool
    ) -> None:
        """Gear number (large) and speed below it."""
        # Gear
        gear_text = "N"
        if not stale and snap is not None and snap.gear > 0:
            gear_text = str(snap.gear)
        color = QColor(GRAY) if stale else QColor(WHITE)
        p.setFont(_font(FONT_MEGA, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRectF(12, 8, 80, 60), Qt.AlignCenter, gear_text)

        # Speed
        if stale or snap is None:
            speed_text = "---"
            speed_color = QColor(GRAY)
        else:
            speed_text = f"{snap.speed_kph:.0f}"
            speed_color = QColor(MODE_I_ACCENT)
        p.setFont(_font(22, bold=True))
        p.setPen(QPen(speed_color))
        p.drawText(QRectF(12, 68, 60, 28), Qt.AlignRight | Qt.AlignVCenter, speed_text)

        # "km/h" label
        p.setFont(_font(11))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(74, 72, 40, 22), Qt.AlignLeft | Qt.AlignVCenter, "km/h")

    def _draw_boost_bar(
        self, p: QPainter, w: int, snap: DiffState | None, stale: bool
    ) -> None:
        """Horizontal fill bar for boost pressure (center of top section)."""
        bar_x = 130
        bar_w = w - 320
        bar_y = 20
        bar_h = 32
        label_y = 4

        # Label
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(SILVER)))
        p.drawText(QRectF(bar_x, label_y, bar_w, 16), Qt.AlignLeft | Qt.AlignVCenter, "BOOST")

        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Compute boost
        if stale or snap is None:
            boost_kpa = 0.0
            value_text = "---"
        else:
            boost_kpa = max(0.0, snap.map_4bar_kpa - _ATM_KPA)
            value_text = f"{boost_kpa:.0f} kPa"

        # Fill
        fill_frac = min(boost_kpa / _BOOST_MAX_KPA, 1.0) if _BOOST_MAX_KPA > 0 else 0.0
        fill_w = bar_w * fill_frac

        if fill_w > 1:
            # Color by severity
            if boost_kpa >= _BOOST_CRIT_KPA:
                fill_color = QColor(RED)
            elif boost_kpa >= _BOOST_WARN_KPA:
                fill_color = QColor(YELLOW)
            else:
                fill_color = QColor(GREEN)

            # Gradient fill
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            base = QColor(fill_color)
            base.setAlphaF(0.6)
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, fill_color)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

        # Bar outline
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Value text (right-aligned inside bar)
        val_color = QColor(GRAY) if stale else QColor(WHITE)
        p.setFont(_font(FONT_HEADER, bold=True))
        p.setPen(QPen(val_color))
        p.drawText(
            QRectF(bar_x, bar_y, bar_w - 8, bar_h),
            Qt.AlignRight | Qt.AlignVCenter,
            value_text,
        )

        # Warn/Crit tick marks
        for threshold, tick_color in [
            (_BOOST_WARN_KPA, YELLOW),
            (_BOOST_CRIT_KPA, RED),
        ]:
            tick_x = bar_x + bar_w * (threshold / _BOOST_MAX_KPA)
            p.setPen(QPen(QColor(tick_color), 1, Qt.DashLine))
            p.drawLine(QPointF(tick_x, bar_y + 2), QPointF(tick_x, bar_y + bar_h - 2))

        # RPM line below boost bar
        rpm_y = bar_y + bar_h + 6
        if stale or snap is None:
            rpm_text = "--- RPM"
            rpm_col = QColor(GRAY)
        else:
            rpm_text = f"{snap.rpm:.0f} RPM"
            rpm_col = QColor(SILVER)
        p.setFont(_font(13))
        p.setPen(QPen(rpm_col))
        p.drawText(QRectF(bar_x, rpm_y, bar_w, 18), Qt.AlignLeft | Qt.AlignVCenter, rpm_text)

        # Throttle line
        if stale or snap is None:
            thr_text = "THR ---"
        else:
            thr_text = f"THR {snap.throttle_pct:.0f}%"
        p.drawText(
            QRectF(bar_x, rpm_y, bar_w, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            thr_text,
        )

        # MAP line
        map_y = rpm_y + 18
        if stale or snap is None:
            map_text = "MAP --- kPa"
        else:
            map_text = f"MAP {snap.map_kpa:.0f} kPa"
        p.setFont(_font(11))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(bar_x, map_y, bar_w, 16), Qt.AlignLeft | Qt.AlignVCenter, map_text)

        # TPS
        if stale or snap is None:
            tps_text = "TPS ---"
        else:
            tps_text = f"TPS {snap.tps:.0f}%"
        p.drawText(
            QRectF(bar_x, map_y, bar_w, 16),
            Qt.AlignRight | Qt.AlignVCenter,
            tps_text,
        )

    def _draw_oil_coolant(
        self, p: QPainter, w: int, snap: DiffState | None, stale: bool
    ) -> None:
        """Oil PSI/temp and coolant temp (right side of top section)."""
        rx = w - 180
        rw = 170

        # --- Oil line ---
        if stale or snap is None:
            oil_text = "OIL  --- PSI / ---\u00b0C"
            oil_color = QColor(GRAY)
        else:
            oil_psi = snap.oil_psi
            oil_temp = snap.oil_temp_c
            oil_text = f"OIL  {oil_psi:.0f} PSI / {oil_temp:.0f}\u00b0C"
            if oil_psi < _OIL_LOW_WARN:
                oil_color = QColor(RED)
            else:
                oil_color = QColor(GREEN)

        p.setFont(_font(14, bold=True))
        p.setPen(QPen(oil_color))
        p.drawText(QRectF(rx, 18, rw, 24), Qt.AlignLeft | Qt.AlignVCenter, oil_text)

        # --- Coolant line ---
        if stale or snap is None:
            clt_text = "CLT  ---\u00b0C"
            clt_color = QColor(GRAY)
        else:
            clt = snap.coolant_temp
            clt_text = f"CLT  {clt:.0f}\u00b0C"
            if clt >= _CLT_CRIT:
                clt_color = QColor(RED)
            elif clt >= _CLT_WARN:
                clt_color = QColor(YELLOW)
            else:
                clt_color = QColor(GREEN)

        p.setPen(QPen(clt_color))
        p.drawText(QRectF(rx, 46, rw, 24), Qt.AlignLeft | Qt.AlignVCenter, clt_text)

        # --- IAT line ---
        if stale or snap is None:
            iat_text = "IAT  ---\u00b0C"
            iat_color = QColor(GRAY)
        else:
            iat_text = f"IAT  {snap.iat_c:.0f}\u00b0C"
            iat_color = QColor(SILVER)

        p.setFont(_font(12))
        p.setPen(QPen(iat_color))
        p.drawText(QRectF(rx, 74, rw, 20), Qt.AlignLeft | Qt.AlignVCenter, iat_text)

        # --- Battery voltage ---
        if stale or snap is None:
            bat_text = "BAT  ---V"
            bat_color = QColor(GRAY)
        else:
            bat_text = f"BAT  {snap.battery_v:.1f}V"
            if snap.battery_v < 12.0:
                bat_color = QColor(RED)
            elif snap.battery_v < 13.0:
                bat_color = QColor(YELLOW)
            else:
                bat_color = QColor(GREEN)

        p.setPen(QPen(bat_color))
        p.drawText(QRectF(rx, 96, rw, 20), Qt.AlignLeft | Qt.AlignVCenter, bat_text)

    # ==================================================================
    # MIDDLE SECTION (y=120..300)
    # ==================================================================

    def _draw_middle_section(
        self,
        p: QPainter,
        w: int,
        snap: DiffState | None,
        stale_engine: bool,
        stale_diff: bool,
    ) -> None:
        """Sparklines (left), Weather + Vehicle status (right)."""
        # Left column: sparklines (x=0..350)
        self._draw_sparkline(
            p, x=10, y=128, sw=240, sh=36,
            label="OIL PSI",
            data=self._oil_history,
            color=GREEN,
            min_val=0.0, max_val=80.0,
        )
        self._draw_sparkline(
            p, x=10, y=172, sw=240, sh=36,
            label="CLT \u00b0C",
            data=self._coolant_history,
            color=GREEN,
            color_hi=RED,
            hi_threshold=_CLT_WARN,
            min_val=50.0, max_val=130.0,
        )
        self._draw_sparkline(
            p, x=10, y=216, sw=240, sh=36,
            label="BOOST",
            data=self._boost_history,
            color=CYAN,
            min_val=0.0, max_val=_BOOST_MAX_KPA,
        )

        # Current value beside each sparkline
        self._draw_sparkline_value(p, x=256, y=128, sh=36, data=self._oil_history,
                                   fmt="{:.0f}", unit="PSI", stale=stale_engine)
        self._draw_sparkline_value(p, x=256, y=172, sh=36, data=self._coolant_history,
                                   fmt="{:.0f}", unit="\u00b0C", stale=stale_engine)
        self._draw_sparkline_value(p, x=256, y=216, sh=36, data=self._boost_history,
                                   fmt="{:.0f}", unit="kPa", stale=stale_engine)

        # Vertical divider
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(340, 126, 340, 296)

        # Right column: weather card (top) + vehicle status (bottom)
        self._draw_weather_card(p, x=352, y=126, cw=w - 362, snap=snap)
        self._draw_vehicle_status(p, x=352, y=222, cw=w - 362, snap=snap,
                                  stale_engine=stale_engine, stale_diff=stale_diff)

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
        label_w = 62
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
            color = QColor(WHITE)

        p.setFont(_font(14, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRectF(x, y, 50, sh), Qt.AlignVCenter | Qt.AlignRight, text)

        p.setFont(_font(9))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(x + 52, y, 30, sh), Qt.AlignVCenter | Qt.AlignLeft, unit)

    # ------------------------------------------------------------------
    # Weather card
    # ------------------------------------------------------------------

    def _draw_weather_card(
        self, p: QPainter, x: int, y: int, cw: int, snap: DiffState | None
    ) -> None:
        """Ambient weather: temp, humidity, pressure, density altitude."""
        # Card background
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(QColor(BG_ACCENT))
        card_h = 88
        p.drawRoundedRect(QRectF(x, y, cw, card_h), 4, 4)

        # Header
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(x + 8, y + 2, cw - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, "WEATHER")

        available = snap is not None and snap.ambient_available
        row_h = 16
        row_y = y + 20
        lx = x + 10
        vx = x + cw // 2

        rows = [
            ("TEMP", f"{snap.ambient_temp_c:.1f}\u00b0C" if available else "---"),
            ("HUMIDITY", f"{snap.ambient_humidity_pct:.0f}%" if available else "---"),
            ("PRESSURE", f"{snap.ambient_pressure_hpa:.0f} hPa" if available else "---"),
            ("DENS ALT", f"{snap.density_altitude_ft:.0f} ft" if available else "---"),
        ]

        for i, (label, value) in enumerate(rows):
            ry = row_y + i * row_h
            p.setFont(_font(10))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(lx, ry, vx - lx, row_h), Qt.AlignLeft | Qt.AlignVCenter, label)
            val_color = QColor(WHITE) if available else QColor(GRAY)
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(val_color))
            p.drawText(QRectF(vx, ry, cw - (vx - x) - 8, row_h),
                       Qt.AlignRight | Qt.AlignVCenter, value)

    # ------------------------------------------------------------------
    # Vehicle status card
    # ------------------------------------------------------------------

    def _draw_vehicle_status(
        self,
        p: QPainter,
        x: int, y: int, cw: int,
        snap: DiffState | None,
        stale_engine: bool,
        stale_diff: bool,
    ) -> None:
        """DCCD lock, surface state, battery, ethanol, fuel pressure."""
        card_h = 74
        p.setPen(QPen(QColor(DIM), 1))
        p.setBrush(QColor(BG_ACCENT))
        p.drawRoundedRect(QRectF(x, y, cw, card_h), 4, 4)

        inner_x = x + 8
        inner_w = cw - 16

        # --- DCCD lock bar (top row) ---
        dccd_y = y + 6
        dccd_bar_h = 14
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(inner_x, dccd_y, 48, dccd_bar_h),
                   Qt.AlignLeft | Qt.AlignVCenter, "DCCD")

        bar_x = inner_x + 50
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

        # --- Surface state badge ---
        badge_y = dccd_y + dccd_bar_h + 6
        badge_h = 16
        if snap is not None:
            surface_label = snap.surface_state.label
            surface_color = QColor(snap.surface_state.color)
        else:
            surface_label = "---"
            surface_color = QColor(GRAY)

        p.setFont(_font(10, bold=True))
        # Badge pill
        badge_tw = p.fontMetrics().horizontalAdvance(surface_label) + 16
        p.setPen(Qt.NoPen)
        pill_bg = QColor(surface_color)
        pill_bg.setAlphaF(0.25)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(inner_x, badge_y, badge_tw, badge_h), 8, 8)
        p.setPen(QPen(surface_color))
        p.drawText(
            QRectF(inner_x, badge_y, badge_tw, badge_h),
            Qt.AlignCenter,
            surface_label,
        )

        # --- Ethanol + Fuel pressure (same row as surface badge) ---
        if stale_engine or snap is None:
            eth_text = "E85 ---"
            fuel_text = "FUEL ---kPa"
            row_color = QColor(GRAY)
        else:
            eth_text = f"E85 {snap.ethanol_pct:.0f}%"
            fuel_text = f"FUEL {snap.fuel_pressure_kpa:.0f}kPa"
            row_color = QColor(SILVER)

        p.setFont(_font(10))
        p.setPen(QPen(row_color))
        p.drawText(
            QRectF(inner_x + badge_tw + 12, badge_y, 80, badge_h),
            Qt.AlignLeft | Qt.AlignVCenter,
            eth_text,
        )
        p.drawText(
            QRectF(inner_x + inner_w - 110, badge_y, 110, badge_h),
            Qt.AlignRight | Qt.AlignVCenter,
            fuel_text,
        )

        # --- Warm-up state ---
        warmup_y = badge_y + badge_h + 6
        warmup_h = 16
        if snap is not None:
            warmup_label = snap.warmup_state.label
            warmup_color = QColor(snap.warmup_state.color)
        else:
            warmup_label = "---"
            warmup_color = QColor(GRAY)

        p.setFont(_font(10, bold=True))
        p.setPen(QPen(warmup_color))
        p.drawText(
            QRectF(inner_x, warmup_y, inner_w, warmup_h),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"ENGINE: {warmup_label}",
        )

    # ==================================================================
    # BOTTOM SECTION (y=300..440)
    # ==================================================================

    def _draw_bottom_section(
        self, p: QPainter, w: int, snap: DiffState | None,
        stale_engine: bool, stale_gps: bool,
    ) -> None:
        """Lambda bar (left), Injector duty (center), GPS (right)."""
        self._draw_lambda_bar(p, snap, stale_engine)
        self._draw_injector_duty(p, w, snap, stale_engine)
        self._draw_gps_status(p, w, snap, stale_gps)

    # ------------------------------------------------------------------
    # Lambda bar
    # ------------------------------------------------------------------

    def _draw_lambda_bar(
        self, p: QPainter, snap: DiffState | None, stale: bool
    ) -> None:
        """Horizontal bar centered on lambda 1.0. Rich=green (left), lean=red (right)."""
        bar_x = 16
        bar_w = 300
        bar_y = 320
        bar_h = 28
        label_y = 306

        # Label
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(SILVER)))
        p.drawText(QRectF(bar_x, label_y, bar_w, 14), Qt.AlignLeft | Qt.AlignVCenter, "LAMBDA")

        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Scale marks
        center_x = bar_x + bar_w * (_LAMBDA_TARGET - _LAMBDA_MIN) / (_LAMBDA_MAX - _LAMBDA_MIN)

        # Center line (1.0)
        p.setPen(QPen(QColor(GRAY), 1, Qt.DashLine))
        p.drawLine(QPointF(center_x, bar_y + 2), QPointF(center_x, bar_y + bar_h - 2))

        if not stale and snap is not None:
            lam = snap.lambda_1
            # Clamp to range for drawing
            lam_clamped = max(_LAMBDA_MIN, min(lam, _LAMBDA_MAX))
            indicator_x = bar_x + bar_w * (lam_clamped - _LAMBDA_MIN) / (_LAMBDA_MAX - _LAMBDA_MIN)

            # Color: green near 1.0, yellow slightly off, red far off
            deviation = abs(lam - _LAMBDA_TARGET)
            if deviation < 0.05:
                ind_color = QColor(GREEN)
            elif deviation < 0.15:
                ind_color = QColor(YELLOW)
            else:
                ind_color = QColor(RED)

            # Draw filled region from center to current value
            if lam_clamped < _LAMBDA_TARGET:
                # Rich side — fill from indicator to center
                fill_x = indicator_x
                fill_w = center_x - indicator_x
                fill_col = QColor(GREEN)
                fill_col.setAlphaF(0.4)
            else:
                # Lean side — fill from center to indicator
                fill_x = center_x
                fill_w = indicator_x - center_x
                fill_col = QColor(RED)
                fill_col.setAlphaF(0.4)

            if fill_w > 1:
                p.setPen(Qt.NoPen)
                p.setBrush(fill_col)
                p.drawRect(QRectF(fill_x, bar_y + 2, fill_w, bar_h - 4))

            # Indicator line
            p.setPen(QPen(ind_color, 3))
            p.drawLine(
                QPointF(indicator_x, bar_y + 1),
                QPointF(indicator_x, bar_y + bar_h - 1),
            )

            value_text = f"{lam:.3f}"
            value_color = ind_color
        else:
            value_text = "---"
            value_color = QColor(GRAY)

        # Bar outline
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Scale labels
        p.setFont(_font(9))
        p.setPen(QPen(QColor(DIM)))
        p.drawText(QRectF(bar_x, bar_y + bar_h + 1, 40, 14),
                   Qt.AlignLeft | Qt.AlignTop, "0.70")
        p.drawText(QRectF(bar_x + bar_w - 40, bar_y + bar_h + 1, 40, 14),
                   Qt.AlignRight | Qt.AlignTop, "1.30")
        p.drawText(QRectF(center_x - 15, bar_y + bar_h + 1, 30, 14),
                   Qt.AlignCenter | Qt.AlignTop, "1.0")

        # Rich / Lean labels
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GREEN)))
        p.drawText(QRectF(bar_x + 4, bar_y + 2, 40, 12),
                   Qt.AlignLeft | Qt.AlignTop, "RICH")
        p.setPen(QPen(QColor(RED)))
        p.drawText(QRectF(bar_x + bar_w - 44, bar_y + 2, 40, 12),
                   Qt.AlignRight | Qt.AlignTop, "LEAN")

        # Numeric value below bar
        p.setFont(_font(FONT_BASE, bold=True))
        p.setPen(QPen(value_color))
        p.drawText(
            QRectF(bar_x, bar_y + bar_h + 14, bar_w, 20),
            Qt.AlignCenter | Qt.AlignVCenter,
            f"\u03bb {value_text}",
        )

    # ------------------------------------------------------------------
    # Injector duty
    # ------------------------------------------------------------------

    def _draw_injector_duty(
        self, p: QPainter, w: int, snap: DiffState | None, stale: bool
    ) -> None:
        """Percentage bar for injector duty cycle."""
        bar_x = 340
        bar_w = w - 340 - 160
        bar_y = 320
        bar_h = 28
        label_y = 306

        # Label
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(SILVER)))
        p.drawText(QRectF(bar_x, label_y, bar_w, 14), Qt.AlignLeft | Qt.AlignVCenter, "INJ DUTY")

        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        if not stale and snap is not None:
            duty = snap.injector_duty
            fill_frac = min(duty / 100.0, 1.0)

            if duty >= _INJ_CRIT:
                fill_color = QColor(RED)
            elif duty >= _INJ_WARN:
                fill_color = QColor(YELLOW)
            else:
                fill_color = QColor(GREEN)

            fill_w = bar_w * fill_frac
            if fill_w > 1:
                grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
                base = QColor(fill_color)
                base.setAlphaF(0.5)
                grad.setColorAt(0.0, base)
                grad.setColorAt(1.0, fill_color)
                p.setBrush(grad)
                p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

            value_text = f"{duty:.0f}%"
            value_color = fill_color
        else:
            value_text = "---%"
            value_color = QColor(GRAY)

        # Warn/Crit tick marks
        for threshold, tick_color in [(_INJ_WARN, YELLOW), (_INJ_CRIT, RED)]:
            tick_x = bar_x + bar_w * (threshold / 100.0)
            p.setPen(QPen(QColor(tick_color), 1, Qt.DashLine))
            p.drawLine(QPointF(tick_x, bar_y + 2), QPointF(tick_x, bar_y + bar_h - 2))

        # Bar outline
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Value text inside bar
        p.setFont(_font(FONT_HEADER, bold=True))
        p.setPen(QPen(value_color))
        p.drawText(
            QRectF(bar_x, bar_y, bar_w - 6, bar_h),
            Qt.AlignRight | Qt.AlignVCenter,
            value_text,
        )

        # Scale
        p.setFont(_font(9))
        p.setPen(QPen(QColor(DIM)))
        p.drawText(QRectF(bar_x, bar_y + bar_h + 1, 30, 14),
                   Qt.AlignLeft | Qt.AlignTop, "0%")
        p.drawText(QRectF(bar_x + bar_w - 35, bar_y + bar_h + 1, 35, 14),
                   Qt.AlignRight | Qt.AlignTop, "100%")

    # ------------------------------------------------------------------
    # GPS status
    # ------------------------------------------------------------------

    def _draw_gps_status(
        self, p: QPainter, w: int, snap: DiffState | None, stale: bool
    ) -> None:
        """Satellite count + fix quality (bottom right)."""
        gps_x = w - 148
        gps_y = 306
        gps_w = 140
        gps_h = 130

        # Header
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(gps_x, gps_y, gps_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "GPS")

        row_y = gps_y + 18
        row_h = 18

        if stale or snap is None:
            sat_text = "SAT: ---"
            fix_text = "FIX: ---"
            sat_color = QColor(GRAY)
            fix_color = QColor(GRAY)
        else:
            sats = snap.gps_satellites
            fix_q = snap.gps_fix_quality
            sat_text = f"SAT: {sats}"
            fix_labels = {0: "NONE", 1: "2D", 2: "3D"}
            fix_text = f"FIX: {fix_labels.get(fix_q, '?')}"

            # Color by satellite count
            if sats >= 8:
                sat_color = QColor(GREEN)
            elif sats >= 4:
                sat_color = QColor(YELLOW)
            else:
                sat_color = QColor(RED)

            # Color by fix quality
            if fix_q >= 2:
                fix_color = QColor(GREEN)
            elif fix_q >= 1:
                fix_color = QColor(YELLOW)
            else:
                fix_color = QColor(RED)

        p.setFont(_font(12))
        p.setPen(QPen(sat_color))
        p.drawText(QRectF(gps_x, row_y, gps_w, row_h),
                   Qt.AlignLeft | Qt.AlignVCenter, sat_text)

        p.setPen(QPen(fix_color))
        p.drawText(QRectF(gps_x, row_y + row_h, gps_w, row_h),
                   Qt.AlignLeft | Qt.AlignVCenter, fix_text)

        # Speed from GPS (secondary)
        if not stale and snap is not None:
            gps_speed_kph = snap.gps_speed_mps * 3.6
            spd_text = f"{gps_speed_kph:.0f} km/h"
            spd_color = QColor(CYAN)
        else:
            spd_text = "--- km/h"
            spd_color = QColor(GRAY)

        p.setFont(_font(10))
        p.setPen(QPen(spd_color))
        p.drawText(QRectF(gps_x, row_y + row_h * 2, gps_w, row_h),
                   Qt.AlignLeft | Qt.AlignVCenter, f"GPS SPD: {spd_text}")

        # Heading
        if not stale and snap is not None:
            hdg_text = f"HDG: {snap.gps_heading:.0f}\u00b0"
            hdg_color = QColor(CYAN)
        else:
            hdg_text = "HDG: ---\u00b0"
            hdg_color = QColor(GRAY)

        p.setPen(QPen(hdg_color))
        p.drawText(QRectF(gps_x, row_y + row_h * 3, gps_w, row_h),
                   Qt.AlignLeft | Qt.AlignVCenter, hdg_text)

        # Altitude
        if not stale and snap is not None:
            alt_text = f"ALT: {snap.gps_altitude_m:.0f}m"
            alt_color = QColor(CYAN)
        else:
            alt_text = "ALT: ---m"
            alt_color = QColor(GRAY)

        p.setPen(QPen(alt_color))
        p.drawText(QRectF(gps_x, row_y + row_h * 4, gps_w, row_h),
                   Qt.AlignLeft | Qt.AlignVCenter, alt_text)
