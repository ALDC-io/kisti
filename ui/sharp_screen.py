"""KiSTI - Sport Sharp Screen (SI-Drive=2)

TRACK / ATTACK / MINIMAL — ultra-sparse, dark, high contrast numbers.
100% QPainter in paintEvent. No composite QWidget layouts.

Layout (800x440):
  y=0..80    Delta bar (full width, green=faster, red=slower)
  y=80..280  Lap time (left) + Gear/Speed/RPM (right)
  y=280..320 Sector strip (colored blocks)
  y=320..380 Brake/throttle trace (scrolling strip chart)
  y=380..440 Safety vitals (dim until warning)
"""

from __future__ import annotations

from collections import deque
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

# Brake trace ring buffer size (20s at 20Hz)
_TRACE_LEN = 400

# RPM color thresholds (BCP X400 build, 7500 effective redline)
_RPM_YELLOW = 5500.0
_RPM_RED = 6500.0
_RPM_REDLINE = 7500.0

# Safety thresholds — sourced from data/build_record.py BASELINES
_OIL_WARN_LOW = 15.0   # PSI — below this at idle is concern
_OIL_CRIT_LOW = 10.0   # PSI — immediate danger
_OIL_NORMAL_HIGH = 90.0
_COOL_WARN = 100.0      # Celsius
_COOL_CRIT = 105.0      # Celsius — baseline alert threshold
_COOL_NORMAL_LOW = 85.0


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


def _rpm_color(rpm: float) -> QColor:
    """White -> Yellow -> Red as RPM approaches redline."""
    if rpm < _RPM_YELLOW:
        return QColor(WHITE)
    if rpm < _RPM_RED:
        # Lerp white -> yellow
        t = (rpm - _RPM_YELLOW) / (_RPM_RED - _RPM_YELLOW)
        r = 255
        g = int(255 - t * (255 - 170))   # 255 -> 170 (0xAA)
        b = int(255 - t * 255)            # 255 -> 0
        return QColor(r, g, b)
    # Lerp yellow -> red
    t = min(1.0, (rpm - _RPM_RED) / (_RPM_REDLINE - _RPM_RED))
    r = 255
    g = int(170 - t * 170)  # 170 -> 0
    b = 0
    return QColor(r, g, b)


def _oil_color(psi: float) -> QColor:
    """Green/Yellow/Red for oil pressure."""
    if psi <= _OIL_CRIT_LOW:
        return QColor(RED)
    if psi <= _OIL_WARN_LOW:
        return QColor(YELLOW)
    return QColor(GREEN)


def _coolant_color(temp: float) -> QColor:
    """Green/Yellow/Red for coolant temperature."""
    if temp >= _COOL_CRIT:
        return QColor(RED)
    if temp >= _COOL_WARN:
        return QColor(YELLOW)
    if temp < _COOL_NORMAL_LOW:
        return QColor(CYAN)  # Still cold
    return QColor(GREEN)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SportSharpScreenWidget(QWidget):
    """Sport Sharp (S#) full-screen QPainter widget — 800x440.

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

        # Ring buffers for brake/throttle trace (20s at 20Hz)
        self._brake_history: deque[float] = deque(maxlen=_TRACE_LEN)
        self._throttle_history: deque[float] = deque(maxlen=_TRACE_LEN)

        # Sector pulse animation
        self._paint_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Accept telemetry snapshot from DiffStateBridge (20 Hz)."""
        self._snap = snap
        self._brake_history.append(snap.brake_pressure)
        self._throttle_history.append(snap.throttle_pct)
        self.update()

    def update_timing(self, timing_data: dict) -> None:
        """Accept timing data from TimingManager.

        Expected keys: lap_count, current_lap_time_ms, delta_ms,
        predicted_lap_ms, sector_times, current_sector, sector_count,
        best_lap_ms, track_name
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
        self._draw_mid_section(p)
        self._draw_sector_strip(p)
        self._draw_brake_trace(p)
        self._draw_safety_vitals(p)

        p.end()

    # ------------------------------------------------------------------
    # Delta bar (y=0..80)
    # ------------------------------------------------------------------

    def _draw_delta_bar(self, p: QPainter) -> None:
        has_timing = bool(self._timing.get("current_lap_time_ms"))
        delta_ms = self._timing.get("delta_ms", 0)

        # Dark bar background
        bar_rect = QRectF(_BAR_X, _BAR_Y, _BAR_W, _BAR_H)
        p.fillRect(bar_rect, QColor(BG_PANEL))

        # Thin border
        p.setPen(QPen(QColor(DIM), 1))
        p.drawRect(bar_rect)

        if not has_timing:
            # "NO TIMING" centered in gray
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Helvetica", FONT_HEADER, QFont.Bold))
            p.drawText(bar_rect, Qt.AlignCenter, "NO TIMING")
            return

        # Fill from center: left = faster (green), right = slower (red)
        center_x = _BAR_X + _BAR_W / 2.0
        # Max delta display range: +/- 5 seconds
        max_delta_ms = 5000.0
        clamped = max(-max_delta_ms, min(max_delta_ms, float(delta_ms)))
        fill_frac = clamped / max_delta_ms  # -1..+1

        if abs(fill_frac) > 0.001:
            fill_w = abs(fill_frac) * (_BAR_W / 2.0)
            inner_margin = 2
            fill_h = _BAR_H - 2 * inner_margin
            fill_y = _BAR_Y + inner_margin

            if fill_frac > 0:
                # Slower — red, fills rightward from center
                fill_color = QColor(RED)
                fill_rect = QRectF(center_x, fill_y, fill_w, fill_h)
            else:
                # Faster — green, fills leftward from center
                fill_color = QColor(GREEN)
                fill_rect = QRectF(center_x - fill_w, fill_y, fill_w, fill_h)

            p.fillRect(fill_rect, fill_color)

        # Center line
        p.setPen(QPen(QColor(WHITE), 1))
        p.drawLine(int(center_x), _BAR_Y + 2, int(center_x), _BAR_Y + _BAR_H - 2)

        # Delta text centered
        delta_text = _fmt_delta_ms(delta_ms)
        text_color = QColor(GREEN) if delta_ms < 0 else QColor(RED) if delta_ms > 0 else QColor(WHITE)
        p.setPen(text_color)
        p.setFont(QFont("Helvetica", FONT_XLARGE, QFont.Bold))
        p.drawText(bar_rect, Qt.AlignCenter, delta_text)

    # ------------------------------------------------------------------
    # Mid section (y=80..280) — Lap time left, Gear/Speed/RPM right
    # ------------------------------------------------------------------

    def _draw_mid_section(self, p: QPainter) -> None:
        snap = self._snap
        timing = self._timing
        mid_w = _W // 2

        # --- Left half: Lap time ---
        left_rect = QRectF(0, _MID_Y0, mid_w, _MID_Y1 - _MID_Y0)

        lap_count = timing.get("lap_count", 0)
        current_lap_ms = timing.get("current_lap_time_ms", 0)
        predicted_ms = timing.get("predicted_lap_ms", 0)
        best_ms = timing.get("best_lap_ms", 0)

        # "LAP X" label
        lap_label = f"LAP {lap_count}" if lap_count > 0 else "LAP --"
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 12))
        p.drawText(int(left_rect.x()) + 20, _MID_Y0 + 28, lap_label)

        # Track name (small, right of lap label)
        track_name = timing.get("track_name", "")
        if track_name:
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(int(left_rect.x()) + 120, _MID_Y0 + 28, track_name)

        # Current lap time — large monospaced feel
        lap_time_str = _fmt_time_ms(current_lap_ms)
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Courier", FONT_MEGA, QFont.Bold))
        p.drawText(int(left_rect.x()) + 16, _MID_Y0 + 90, lap_time_str)

        # Predicted lap
        if predicted_ms > 0:
            pred_str = f"PRED {_fmt_time_ms(predicted_ms)}"
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Courier", 30, QFont.Bold))
            p.drawText(int(left_rect.x()) + 20, _MID_Y0 + 138, pred_str)

        # Best lap reference
        if best_ms > 0:
            best_str = f"BEST {_fmt_time_ms(best_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE))
            p.drawText(int(left_rect.x()) + 24, _MID_Y0 + 170, best_str)

        # --- Right half: Gear + Speed + RPM ---
        right_cx = mid_w + mid_w // 2  # center x of right half
        right_top = _MID_Y0

        gear = snap.gear if snap else 0
        speed = snap.speed_kph if snap else 0.0
        rpm = snap.rpm if snap else 0.0
        stale = snap.is_engine_stale() if snap else True

        # Gear — MASSIVE
        gear_str = "N" if gear == 0 else str(gear)
        gear_color = QColor(DIM) if stale else QColor(WHITE)
        p.setPen(gear_color)
        p.setFont(QFont("Helvetica", 120, QFont.Bold))
        gear_rect = QRectF(mid_w, right_top, mid_w, 150)
        p.drawText(gear_rect, Qt.AlignCenter, gear_str)

        # Speed below gear
        speed_str = f"{speed:.0f}"
        speed_unit = "km/h"
        p.setPen(QColor(CYAN) if not stale else QColor(DIM))
        p.setFont(QFont("Helvetica", 24, QFont.Bold))
        speed_rect = QRectF(mid_w, right_top + 140, mid_w, 36)
        p.drawText(speed_rect, Qt.AlignCenter, f"{speed_str} {speed_unit}")

        # RPM below speed — color shifts approaching redline
        rpm_str = f"{rpm:.0f} RPM"
        rpm_col = _rpm_color(rpm) if not stale else QColor(DIM)
        p.setPen(rpm_col)
        p.setFont(QFont("Helvetica", FONT_BASE))
        rpm_rect = QRectF(mid_w, right_top + 172, mid_w, 22)
        p.drawText(rpm_rect, Qt.AlignCenter, rpm_str)

    # ------------------------------------------------------------------
    # Sector strip (y=280..320)
    # ------------------------------------------------------------------

    def _draw_sector_strip(self, p: QPainter) -> None:
        sector_count = self._timing.get("sector_count", 0)
        if sector_count <= 0:
            # Empty dark strip
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
                # Completed sector
                sector_ms = sector_times[i]
                best_ms = best_sector_times[i] if i < len(best_sector_times) and best_sector_times[i] else None

                if best_ms is not None and sector_ms <= best_ms:
                    fill_color = QColor(GREEN)
                else:
                    fill_color = QColor(RED)

                p.fillRect(rect, fill_color)

                # Time text in white
                time_str = f"{sector_ms / 1000.0:.1f}"
                p.setPen(QColor(WHITE))
                p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
                p.drawText(rect, Qt.AlignCenter, time_str)

            elif i == current_sector:
                # Current sector — pulsing amber outline
                p.fillRect(rect, QColor(BG_PANEL))
                pulse_alpha = 120 + int(80 * (1.0 if self._paint_count % 20 < 10 else 0.4))
                pen_color = QColor(YELLOW)
                pen_color.setAlpha(pulse_alpha)
                p.setPen(QPen(pen_color, 2))
                p.drawRect(rect)
            else:
                # Future sector — dark
                p.fillRect(rect, QColor(BG_PANEL))
                p.setPen(QPen(QColor(DIM), 1))
                p.drawRect(rect)

    # ------------------------------------------------------------------
    # Brake/throttle trace (y=320..380)
    # ------------------------------------------------------------------

    def _draw_brake_trace(self, p: QPainter) -> None:
        strip_x = _BAR_X
        strip_w = _BAR_W
        strip_y = _BRAKE_Y0
        strip_h = _BRAKE_Y1 - _BRAKE_Y0

        # Dark background
        p.fillRect(QRectF(strip_x, strip_y, strip_w, strip_h), QColor(BG_PANEL))

        brake_count = len(self._brake_history)
        throttle_count = len(self._throttle_history)

        if brake_count == 0:
            # Label only
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(QRectF(strip_x, strip_y, strip_w, strip_h), Qt.AlignCenter, "BRAKE / THROTTLE TRACE")
            return

        # Each sample gets a vertical slice
        # Newest on right, oldest on left
        sample_w = strip_w / _TRACE_LEN
        max_brake = 80.0   # AP Racing front brakes, 0-80 bar range
        max_throttle = 100.0

        # Draw throttle first (behind brake) — thin green fill
        p.setPen(Qt.NoPen)
        for idx, thr in enumerate(self._throttle_history):
            offset = _TRACE_LEN - throttle_count + idx
            x = strip_x + offset * sample_w
            thr_h = (min(thr, max_throttle) / max_throttle) * strip_h
            thr_y = strip_y + strip_h - thr_h
            thr_color = QColor(GREEN)
            thr_color.setAlpha(60)
            p.fillRect(QRectF(x, thr_y, max(sample_w, 1.0), thr_h), thr_color)

        # Draw brake — solid red fill
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
    # Safety vitals (y=380..440) — DIM until warning
    # ------------------------------------------------------------------

    def _draw_safety_vitals(self, p: QPainter) -> None:
        snap = self._snap
        strip_y = _VITALS_Y0
        strip_h = _VITALS_Y1 - _VITALS_Y0

        # Background
        p.fillRect(QRectF(0, strip_y, _W, strip_h), QColor(BG_DARK))

        oil_psi = snap.oil_psi if snap else 0.0
        coolant = snap.coolant_temp if snap else 0.0
        oil_temp = snap.oil_temp_c if snap else 0.0
        dccd = snap.dccd_command_pct if snap else 0.0
        stale = snap.is_engine_stale() if snap else True

        # Divide into 4 zones
        zone_w = _W / 4
        cy = strip_y + strip_h // 2

        # --- Oil PSI ---
        oil_warn = oil_psi <= _OIL_WARN_LOW and not stale
        oil_crit = oil_psi <= _OIL_CRIT_LOW and not stale
        oil_col = _oil_color(oil_psi) if not stale else QColor(DIM)
        label_col = QColor(DIM) if (not oil_warn and not stale) else oil_col
        value_col = oil_col if oil_warn else (QColor(DIM) if not stale else QColor(DIM))

        # If warning/critical, make it loud
        if oil_crit:
            label_col = QColor(RED)
            value_col = QColor(RED)
        elif oil_warn:
            label_col = QColor(YELLOW)
            value_col = QColor(YELLOW)

        self._draw_vital(
            p, 0, zone_w, cy, "OIL", f"{oil_psi:.0f}", "PSI",
            label_col, value_col if not stale else QColor(DIM),
            large=oil_warn,
        )

        # --- Coolant ---
        cool_warn = coolant >= _COOL_WARN and not stale
        cool_crit = coolant >= _COOL_CRIT and not stale
        cool_col = _coolant_color(coolant) if not stale else QColor(DIM)

        if cool_crit:
            lc = QColor(RED)
            vc = QColor(RED)
        elif cool_warn:
            lc = QColor(YELLOW)
            vc = QColor(YELLOW)
        else:
            lc = QColor(DIM)
            vc = QColor(DIM) if not stale else QColor(DIM)

        self._draw_vital(
            p, zone_w, zone_w, cy, "COOL", f"{coolant:.0f}", "\u00b0C",
            lc, vc if not stale else QColor(DIM),
            large=cool_warn,
        )

        # --- Oil Temp ---
        # Oil temp warning: > 130C concern, > 140C critical
        oil_t_warn = oil_temp > 130.0 and not stale
        oil_t_crit = oil_temp > 140.0 and not stale
        if oil_t_crit:
            otl = QColor(RED)
            otv = QColor(RED)
        elif oil_t_warn:
            otl = QColor(YELLOW)
            otv = QColor(YELLOW)
        else:
            otl = QColor(DIM)
            otv = QColor(DIM)

        self._draw_vital(
            p, zone_w * 2, zone_w, cy, "OIL T", f"{oil_temp:.0f}", "\u00b0C",
            otl, otv if not stale else QColor(DIM),
            large=oil_t_warn,
        )

        # --- DCCD Lock % (compact bar) ---
        dccd_x = zone_w * 3
        dccd_w = zone_w - 20

        # Label
        p.setPen(QColor(DIM))
        p.setFont(QFont("Helvetica", 10))
        p.drawText(int(dccd_x) + 10, strip_y + 18, "DCCD")

        # Bar background
        bar_x = int(dccd_x) + 10
        bar_y = cy - 4
        bar_w = int(dccd_w) - 10
        bar_h = 10

        p.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor(DIM))

        # Fill
        if not stale:
            fill_w = (dccd / 100.0) * bar_w
            # Color: dim at low lock, MODE_SS_ACCENT at high lock
            if dccd > 70:
                fill_col = QColor(MODE_SS_ACCENT)
            elif dccd > 40:
                fill_col = QColor(YELLOW)
            else:
                fill_col = QColor(GREEN)
            p.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), fill_col)

        # Percentage text
        dccd_col = QColor(DIM) if dccd < 50 else QColor(WHITE)
        if stale:
            dccd_col = QColor(DIM)
        p.setPen(dccd_col)
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        p.drawText(QRectF(bar_x, bar_y + bar_h + 2, bar_w, 18), Qt.AlignCenter, f"{dccd:.0f}%")

    def _draw_vital(
        self,
        p: QPainter,
        x: float,
        w: float,
        cy: int,
        label: str,
        value: str,
        unit: str,
        label_color: QColor,
        value_color: QColor,
        large: bool = False,
    ) -> None:
        """Draw a single safety vital — label above, value + unit below."""
        cx = int(x + w / 2)

        # Label
        p.setPen(label_color)
        p.setFont(QFont("Helvetica", 10))
        label_rect = QRectF(x, _VITALS_Y0 + 4, w, 16)
        p.drawText(label_rect, Qt.AlignCenter, label)

        # Value
        font_size = FONT_BIG if large else FONT_HEADER
        p.setPen(value_color)
        p.setFont(QFont("Courier", font_size, QFont.Bold))
        value_rect = QRectF(x, _VITALS_Y0 + 18, w, 28)
        p.drawText(value_rect, Qt.AlignCenter, f"{value}{unit}")
