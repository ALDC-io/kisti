"""KiSTI - Sport Sharp Screen (SI-Drive=2)

TRACK / ATTACK / MINIMAL — ultra-sparse, dark, high contrast numbers.
100% QPainter in paintEvent. No composite QWidget layouts.

MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport Sharp shows ONLY what the MXG cannot:
  - Lap timing + delta + sectors
  - Safety vitals (dim-until-warning)

"Am I faster?" — pure timing focus. Nothing else.

Layout (800x480):
  y=0..90    Delta bar (full width, green=faster, red=slower)
  y=90..280  Lap time (full width) — huge center number + lap count + best + theo
  y=280..380 Sector strip (colored blocks with times)
  y=380..480 Safety vitals (dim until warning) — 5 zones
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF
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
_H = 480

# Section Y boundaries
_DELTA_Y0 = 0
_DELTA_Y1 = 90
_MID_Y0 = 90
_MID_Y1 = 280
_SECTOR_Y0 = 280
_SECTOR_Y1 = 380
_VITALS_Y0 = 380
_VITALS_Y1 = 480

# Delta bar geometry
_BAR_MARGIN = 10
_BAR_H = 70
_BAR_Y = (_DELTA_Y1 - _BAR_H) // 2 + _DELTA_Y0
_BAR_X = _BAR_MARGIN
_BAR_W = _W - 2 * _BAR_MARGIN

# FLIR brake temp thresholds (°C) — used by _brake_heat_color and safety vitals
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
    """Sport Sharp (S#) full-screen QPainter widget — 800x480.

    "Am I faster?" — pure timing focus. Nothing else.
    Ultra-sparse dark layout for maximum attack driving.
    Data fed via update_state(snap) at 20 Hz from DiffStateBridge.
    Timing data fed via update_timing(timing_data) from TimingManager.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_W, _H)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        self._snap: Optional[DiffState] = None
        self._timing: dict = {}

        # Sector pulse animation
        self._paint_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Accept telemetry snapshot from DiffStateBridge (20 Hz)."""
        self._snap = snap
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
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))
        self._draw_delta_bar(p)
        self._draw_timing_panel(p)
        self._draw_sector_strip(p)
        self._draw_safety_vitals(p)
        p.end()

    # ------------------------------------------------------------------
    # Delta bar (y=0..90) — full width, big delta text
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
    # Timing panel (full width, y=90..280) — huge center lap time
    # ------------------------------------------------------------------

    def _draw_timing_panel(self, p: QPainter) -> None:
        timing = self._timing
        panel_h = _MID_Y1 - _MID_Y0  # 190px

        lap_count = timing.get("lap_count", 0)
        current_lap_ms = timing.get("current_lap_time_ms", 0)
        predicted_ms = timing.get("predicted_lap_ms", 0)
        best_ms = timing.get("best_lap_ms", 0)
        theoretical_ms = timing.get("theoretical_best_ms", 0)

        # --- Row 1: LAP label + track name (top) ---
        lap_label = f"LAP {lap_count}" if lap_count > 0 else "LAP --"
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 14, QFont.Bold))
        p.drawText(QRectF(20, _MID_Y0 + 4, 120, 24), Qt.AlignLeft | Qt.AlignVCenter, lap_label)

        track_name = timing.get("track_name", "")
        if track_name:
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", 12))
            p.drawText(QRectF(150, _MID_Y0 + 4, 400, 24), Qt.AlignLeft | Qt.AlignVCenter, track_name)

        # --- Row 2: Current lap time — HUGE, centered ---
        lap_time_str = _fmt_time_ms(current_lap_ms)
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Courier", FONT_MEGA + 12, QFont.Bold))  # 60pt for max visibility
        time_rect = QRectF(0, _MID_Y0 + 30, _W, 80)
        p.drawText(time_rect, Qt.AlignCenter, lap_time_str)

        # --- Row 3: Predicted lap — medium, centered ---
        if predicted_ms > 0:
            pred_str = f"PRED  {_fmt_time_ms(predicted_ms)}"
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Courier", FONT_BIG, QFont.Bold))
            pred_rect = QRectF(0, _MID_Y0 + 112, _W, 32)
            p.drawText(pred_rect, Qt.AlignCenter, pred_str)

        # --- Row 4: Best lap + Theoretical best — bottom, spread left/right ---
        info_y = _MID_Y0 + panel_h - 32

        if best_ms > 0:
            best_str = f"BEST  {_fmt_time_ms(best_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
            p.drawText(QRectF(20, info_y, 380, 24), Qt.AlignLeft | Qt.AlignVCenter, best_str)

        if theoretical_ms > 0:
            theo_str = f"THEO  {_fmt_time_ms(theoretical_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
            p.drawText(QRectF(400, info_y, 380, 24), Qt.AlignRight | Qt.AlignVCenter, theo_str)

    # ------------------------------------------------------------------
    # Sector strip (y=280..380) — taller colored blocks with times
    # ------------------------------------------------------------------

    def _draw_sector_strip(self, p: QPainter) -> None:
        sector_count = self._timing.get("sector_count", 0)
        strip_h = _SECTOR_Y1 - _SECTOR_Y0

        if sector_count <= 0:
            p.fillRect(QRectF(_BAR_X, _SECTOR_Y0, _BAR_W, strip_h), QColor(BG_PANEL))
            return

        self._paint_count += 1

        current_sector = self._timing.get("current_sector", 0)
        sector_times = self._timing.get("sector_times", [])
        best_sector_times = self._timing.get("best_sector_times", [])

        sector_w = _BAR_W / sector_count
        gap = 3

        for i in range(sector_count):
            sx = _BAR_X + i * sector_w
            rect = QRectF(sx + gap / 2, _SECTOR_Y0 + 3, sector_w - gap, strip_h - 6)

            if i < len(sector_times) and sector_times[i] is not None:
                sector_ms = sector_times[i]
                best_ms = best_sector_times[i] if i < len(best_sector_times) and best_sector_times[i] else None

                if best_ms is not None and sector_ms <= best_ms:
                    fill_color = QColor(GREEN)
                else:
                    fill_color = QColor(RED)

                p.fillRect(rect, fill_color)

                # Sector time — large and readable
                time_str = f"{sector_ms / 1000.0:.1f}"
                p.setPen(QColor(WHITE))
                p.setFont(QFont("Helvetica", FONT_HEADER, QFont.Bold))
                p.drawText(rect, Qt.AlignCenter, time_str)

                # Delta vs best — smaller, below the time
                if best_ms is not None:
                    diff_ms = sector_ms - best_ms
                    diff_str = _fmt_delta_ms(diff_ms)
                    diff_color = QColor(WHITE)
                    diff_color.setAlpha(200)
                    p.setPen(diff_color)
                    p.setFont(QFont("Helvetica", 10))
                    diff_rect = QRectF(rect.x(), rect.y() + rect.height() - 22, rect.width(), 18)
                    p.drawText(diff_rect, Qt.AlignCenter, diff_str)

            elif i == current_sector:
                # Active sector — pulsing border
                p.fillRect(rect, QColor(BG_PANEL))
                pulse_alpha = 120 + int(80 * (1.0 if self._paint_count % 20 < 10 else 0.4))
                pen_color = QColor(YELLOW)
                pen_color.setAlpha(pulse_alpha)
                p.setPen(QPen(pen_color, 2))
                p.drawRect(rect)

                # Sector number label
                p.setPen(QColor(DIM))
                p.setFont(QFont("Helvetica", 12))
                p.drawText(rect, Qt.AlignCenter, f"S{i + 1}")
            else:
                # Future sector — dim
                p.fillRect(rect, QColor(BG_PANEL))
                p.setPen(QPen(QColor(DIM), 1))
                p.drawRect(rect)

                # Sector number label
                p.setPen(QColor(DIM))
                p.setFont(QFont("Helvetica", 10))
                p.drawText(rect, Qt.AlignCenter, f"S{i + 1}")

    # ------------------------------------------------------------------
    # Safety vitals (y=380..480) — 5 zones, DIM until warning
    # ------------------------------------------------------------------

    def _draw_safety_vitals(self, p: QPainter) -> None:
        snap = self._snap
        strip_y = _VITALS_Y0
        strip_h = _VITALS_Y1 - _VITALS_Y0

        p.fillRect(QRectF(0, strip_y, _W, strip_h), QColor(BG_DARK))

        oil_psi = snap.oil_psi if snap else 0.0
        coolant = snap.coolant_temp if snap else 0.0
        oil_temp = snap.oil_temp_c if snap else 0.0
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

        # 4 safety zones (DCCD shown on Sport screen)
        zone_w = _W / 4

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
