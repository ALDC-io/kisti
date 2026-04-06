"""KiSTI - Sport Sharp Screen (SI-Drive=2)

TRACK / ATTACK / CANYON — timing + intensity feedback.
100% QPainter in paintEvent. No composite QWidget layouts.

MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport Sharp shows ONLY what the MXG cannot:
  - Lap timing + delta + sectors (track)
  - G-force circle (canyon intensity / cornering commitment)
  - Safety vitals (dim-until-warning)

"Am I faster?" — timing for track, G-force for canyons. Dual-mode.

Layout (800x480):
  y=0..90    Delta bar (full width, green=faster, red=slower)
  y=90..280  LEFT (0..480): Lap time + lap count + best + theo
             RIGHT (480..800): G-force circle with trail
  y=280..380 Sector strip (colored blocks with times)
  y=380..480 Safety vitals (dim until warning) — 4 zones
"""

from __future__ import annotations

from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState
from ui.g_force_ellipse import paint_g_ellipse
from ui.road_condition import (
    paint_zone_tint,
    paint_edge_glow,
    zone_states_from_snap,
    any_zone_low_grip,
)
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
_H = 480

# Section Y boundaries
_DELTA_Y0 = 0
_DELTA_Y1 = 90
_MID_Y0 = 90
_MID_Y1 = 280
_SECTOR_Y0 = 280
_SECTOR_Y1 = 380
_VITALS_Y0 = 380
_VITALS_Y1 = 460  # Shortened to leave room for alert bar at y=460..480

# Delta bar geometry
_BAR_MARGIN = 10
_BAR_H = 70
_BAR_Y = (_DELTA_Y1 - _BAR_H) // 2 + _DELTA_Y0
_BAR_X = _BAR_MARGIN
_BAR_W = _W - 2 * _BAR_MARGIN

# Timing / G-force split in mid panel (y=90..280)
_TIMING_W = 480       # Left side: timing data
_G_PANEL_X = 480      # Right side: G-force circle
_G_CENTER_X = 640     # Circle center X (midpoint of 480..800)
_G_CENTER_Y = 170     # Circle center Y (raised to fit magnitude label above sector strip)
_G_RADIUS = 80        # Outer ring = 1.0g

# Road surface temp thresholds (forward-facing grill FLIR)
_FLIR_COLD = 5.0      # Ice risk
_FLIR_GREEN = 15.0    # Cool but safe
_FLIR_YELLOW = 40.0   # Warm/optimal
_FLIR_RED = 55.0      # Very hot pavement

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

    "Am I faster?" — timing for track, G-force for canyons.
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

        # G-force dot trail (canyon intensity feedback)
        self._g_trail: deque[tuple[float, float]] = deque(maxlen=40)

        # Sector pulse animation
        self._paint_count: int = 0

        # Voice ticker (fed from main.py at 1Hz)
        self._voice_ticker: list[str] = []

        # Balance / grip / brake quality (fed from coaching analyzers)
        self._balance_ratio: float = 1.0
        self._front_grip_pct: float = 100.0
        self._rear_grip_pct: float = 100.0
        self._sector_brake_quality: list[str] = []  # "green"/"yellow"/"red" per sector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Accept telemetry snapshot from DiffStateBridge (20 Hz)."""
        self._snap = snap
        self._g_trail.append((snap.imu_accel_y, snap.imu_accel_x))
        self.update()

    def update_voice_ticker(self, lines: list[str]) -> None:
        """Cache voice ticker lines (called at 1Hz from main.py)."""
        self._voice_ticker = lines

    def update_timing(self, timing_data: dict) -> None:
        """Accept timing data from TimingManager.

        Expected keys: lap_count, current_lap_time_ms, delta_ms,
        predicted_lap_ms, sector_times, current_sector, sector_count,
        best_lap_ms, best_sector_times, track_name, theoretical_best_ms
        """
        self._timing = timing_data
        self.update()

    def update_balance(self, ratio: float, text: str, sentiment: str) -> None:
        """Accept balance ratio from BalanceAnalyzer."""
        self._balance_ratio = ratio

    def update_grip(self, front_pct: float, rear_pct: float) -> None:
        """Accept grip percentages from GripAnalyzer."""
        self._front_grip_pct = front_pct
        self._rear_grip_pct = rear_pct

    def update_brake_quality(self, sector_qualities: list[str]) -> None:
        """Accept brake quality ratings per sector from TechniqueAnalyzer."""
        self._sector_brake_quality = sector_qualities

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))

        # Per-zone road condition background tint (minimal on race screen)
        snap = self._snap
        zones = zone_states_from_snap(snap)
        if snap is not None and not snap.is_road_surface_stale():
            paint_zone_tint(p, _W, _H, zones, alpha=12)

        self._draw_delta_bar(p)
        self._draw_timing_panel(p)
        self._draw_g_force_circle(p)
        self._draw_sector_strip(p)
        self._draw_safety_vitals(p)
        self._draw_weather_indicator(p)
        self._paint_voice_ticker(p)

        # Edge glow for LOW_GRIP only (can't distract during laps)
        if snap is not None and not snap.is_road_surface_stale():
            paint_edge_glow(p, _W, _H, any_zone_low_grip(zones), self._paint_count)

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
        tw = _TIMING_W  # Left side only (480px)

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
            p.drawText(QRectF(150, _MID_Y0 + 4, 300, 24), Qt.AlignLeft | Qt.AlignVCenter, track_name)

        # --- Row 2: Current lap time — large, left-side centered ---
        lap_time_str = _fmt_time_ms(current_lap_ms)
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Courier", FONT_MEGA, QFont.Bold))  # 48pt — still big, fits left panel
        time_rect = QRectF(0, _MID_Y0 + 30, tw, 70)
        p.drawText(time_rect, Qt.AlignCenter, lap_time_str)

        # --- Row 3: Predicted lap — medium ---
        if predicted_ms > 0:
            pred_str = f"PRED  {_fmt_time_ms(predicted_ms)}"
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Courier", FONT_BIG, QFont.Bold))
            pred_rect = QRectF(0, _MID_Y0 + 102, tw, 28)
            p.drawText(pred_rect, Qt.AlignCenter, pred_str)

        # --- Row 4: Best lap + Theoretical best — stacked left ---
        info_y = _MID_Y0 + panel_h - 42

        if best_ms > 0:
            best_str = f"BEST  {_fmt_time_ms(best_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
            p.drawText(QRectF(20, info_y, tw - 40, 20), Qt.AlignLeft | Qt.AlignVCenter, best_str)

        if theoretical_ms > 0:
            theo_str = f"THEO  {_fmt_time_ms(theoretical_ms)}"
            p.setPen(QColor(DIM))
            p.setFont(QFont("Helvetica", FONT_BASE, QFont.Bold))
            p.drawText(QRectF(20, info_y + 20, tw - 40, 20), Qt.AlignLeft | Qt.AlignVCenter, theo_str)

    # ------------------------------------------------------------------
    # G-force circle (right side of mid panel, 480..800, y=90..280)
    # Canyon intensity feedback — smaller than Sport's but same data.
    # ------------------------------------------------------------------

    def _draw_g_force_circle(self, p: QPainter) -> None:
        # Clear the right panel area
        p.fillRect(_G_PANEL_X, _MID_Y0, _W - _G_PANEL_X, _MID_Y1 - _MID_Y0, QColor(BG_DARK))
        paint_g_ellipse(p, _G_CENTER_X, _G_CENTER_Y, 80, self._snap, self._g_trail,
                        balance_ratio=self._balance_ratio, max_trail_dots=10,
                        accent_color=MODE_SS_ACCENT)

    # ------------------------------------------------------------------
    # Sector strip (y=280..380) — taller colored blocks with times
    # ------------------------------------------------------------------

    def _draw_sector_strip(self, p: QPainter) -> None:
        sector_count = self._timing.get("sector_count", 0)
        strip_h = _SECTOR_Y1 - _SECTOR_Y0

        if sector_count <= 0:
            # No timing — show FLIR brake temps instead of empty strip
            self._draw_flir_strip(p)
            return

        lap_in_progress = self._timing.get("lap_in_progress", False)
        if not lap_in_progress:
            # No active lap — show black placeholders (no stale red fills)
            sector_w = _BAR_W / sector_count
            gap = 3
            for i in range(sector_count):
                sx = _BAR_X + i * sector_w
                rect = QRectF(sx + gap / 2, _SECTOR_Y0 + 3, sector_w - gap, strip_h - 6)
                p.fillRect(rect, QColor(BG_DARK))
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

            if i < len(sector_times) and sector_times[i] is not None and sector_times[i] > 0:
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

                # Sector insight + delta vs best — below the time
                if best_ms is not None:
                    diff_ms = sector_ms - best_ms

                    # Mini-insight text (between time and delta)
                    insight_text, insight_color = self._sector_insight(sector_ms, best_ms)
                    if insight_text:
                        p.setPen(insight_color)
                        p.setFont(QFont("Helvetica", 11))
                        insight_rect = QRectF(
                            rect.x(), rect.y() + rect.height() * 0.48,
                            rect.width(), 16)
                        p.drawText(insight_rect, Qt.AlignCenter, insight_text)

                    # Delta string
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

        # --- Brake quality dots above completed sectors ---
        if self._sector_brake_quality:
            dot_y = _SECTOR_Y0 - 8
            dot_r = 4
            color_map = {"green": QColor(GREEN), "yellow": QColor(YELLOW), "red": QColor(RED)}
            for i in range(min(len(self._sector_brake_quality), sector_count)):
                # Only show dots for completed sectors (with times)
                if i < len(sector_times) and sector_times[i] is not None and sector_times[i] > 0:
                    quality = self._sector_brake_quality[i]
                    dot_color = color_map.get(quality, QColor(DIM))
                    dot_x = _BAR_X + i * sector_w + sector_w / 2
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(dot_color)
                    p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

    # ------------------------------------------------------------------
    # FLIR brake temp strip (y=280..380) — shown when no sector data
    # ------------------------------------------------------------------

    def _draw_flir_strip(self, p: QPainter) -> None:
        """Road condition strip — fills sector area when no timing active.

        Uses surface classification colors (not just heat gradient) for each
        of the 3 FLIR zones. Immediate visual feedback on road conditions.
        """
        snap = self._snap
        road_ok = snap is not None and not snap.is_road_surface_stale()

        y0 = _SECTOR_Y0
        strip_h = _SECTOR_Y1 - _SECTOR_Y0

        if not road_ok:
            p.fillRect(QRectF(10, y0, _W - 20, strip_h), QColor(BG_PANEL))
            return

        # 3-zone bars using surface state classification colors
        states = zone_states_from_snap(snap)
        zone_w = _W / 3.0
        bar_y = y0 + 22
        bar_h = strip_h - 28

        for i, ss in enumerate(states):
            zx = i * zone_w
            col = QColor(ss.color)
            col.setAlpha(100)
            p.fillRect(QRectF(zx + 2, bar_y, zone_w - 4, bar_h), col)

        # Label
        p.setFont(QFont("Courier", FONT_BASE, QFont.Weight.Bold))
        p.setPen(QColor(GRAY))
        p.drawText(QRectF(10, y0, _W - 20, 20),
                   Qt.AlignmentFlag.AlignCenter, "ROAD CONDITION")

    # ------------------------------------------------------------------
    # Safety vitals (y=380..480) — 5 zones, DIM until warning
    # ------------------------------------------------------------------

    def _draw_safety_vitals(self, p: QPainter) -> None:
        """Dark cockpit safety vitals — invisible when normal, loud when not.

        Normal = DIM (barely visible). Warning = YELLOW. Critical = RED.
        Canyon-first: OIL | COOL | GRIP | BARO (hPa/hr).
        """
        snap = self._snap
        strip_y = _VITALS_Y0
        strip_h = _VITALS_Y1 - _VITALS_Y0

        p.fillRect(QRectF(0, strip_y, _W, strip_h), QColor(BG_DARK))

        oil_psi = snap.oil_psi if snap else 0.0
        coolant = snap.coolant_temp if snap else 0.0
        stale = snap.is_engine_stale() if snap else True

        # 4 safety zones: OIL | COOL | GRIP | BARO
        zone_w = _W / 4

        # --- OIL PSI (dark cockpit) ---
        oil_warn = oil_psi <= _OIL_WARN_LOW and not stale
        oil_crit = oil_psi <= _OIL_CRIT_LOW and not stale
        if oil_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif oil_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        self._draw_vital(p, 0, zone_w, "OIL", f"{oil_psi:.0f}", "PSI",
                         lc, vc if not stale else QColor(DIM), large=oil_crit)

        # --- COOLANT (dark cockpit) ---
        cool_warn = coolant >= _COOL_WARN and not stale
        cool_crit = coolant >= _COOL_CRIT and not stale
        if cool_crit:
            lc, vc = QColor(RED), QColor(RED)
        elif cool_warn:
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        else:
            lc, vc = QColor(DIM), QColor(DIM)
        self._draw_vital(p, zone_w, zone_w, "COOL", f"{coolant:.0f}", "\u00b0C",
                         lc, vc if not stale else QColor(DIM), large=cool_crit)

        # --- GRIP (moved to zone 3 — canyon priority) ---
        self._draw_grip_vital(p, zone_w * 2, zone_w)

        # --- BARO hPa/hr (canyon weather awareness) ---
        self._draw_baro_vital(p, zone_w * 3, zone_w)

    def _draw_baro_vital(self, p: QPainter, x: float, w: float) -> None:
        """BARO hPa/hr vital — canyon weather awareness in the vitals strip.

        Dark cockpit: DIM when CLEAR, escalates through CYAN/YELLOW/RED.
        Shows rate value so the driver learns to read pressure trends.
        Fog risk shown as label override when dew spread is closing.
        """
        snap = self._snap
        rate = snap.pressure_trend_hpa_hr if snap else 0.0
        threat = snap.weather_threat_level if snap else "CLEAR"
        dew_spread = snap.dew_point_spread_c if snap else 99.0
        humidity = snap.ambient_humidity_pct if snap else 0.0

        # Fog detection: dew spread <1.5C + humidity >93%
        fog_risk = dew_spread < 1.5 and humidity > 93.0

        # EC warning awareness
        has_ec = (snap.ec_available and snap.ec_warning_level in ("warning", "watch")
                  ) if snap else False

        # Dark cockpit coloring by threat level (EC can escalate)
        if threat == "STORM":
            lc, vc = QColor(RED), QColor(RED)
        elif threat == "RAIN_LIKELY":
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        elif fog_risk:
            lc, vc = QColor(CYAN), QColor(CYAN)
        elif threat == "CHANGING" or has_ec:
            lc, vc = QColor(CYAN), QColor(CYAN)
        else:
            lc, vc = QColor(DIM), QColor(DIM)

        # Label: FOG overrides BARO when fog conditions are met
        label = "FOG" if fog_risk else "BARO"

        # Value: show rate with sign (negative = falling = weather incoming)
        value = f"{rate:+.1f}"
        unit = "hPa/hr"

        self._draw_vital(p, x, w, label, value, unit, lc, vc)

    def _draw_weather_indicator(self, p: QPainter) -> None:
        """Full-width alert bar at bottom (y=462..480). Highest severity wins.

        Canyon-first: FOG gets its own alert (visibility is #1 canyon danger).
        """
        snap = self._snap
        if snap is None:
            return
        threat = snap.weather_threat_level
        has_ec = snap.ec_available and snap.ec_warning_level != "none"
        dew_spread = snap.dew_point_spread_c
        humidity = snap.ambient_humidity_pct
        fog_risk = dew_spread < 1.5 and humidity > 93.0

        text = ""
        bg = QColor(30, 80, 160)
        fg = QColor(255, 255, 255)

        rate = snap.pressure_trend_hpa_hr
        if threat == "STORM":
            text = f"STORM INCOMING — pressure falling {abs(rate):.1f} hPa/hr"
            bg = QColor(180, 20, 20)
        elif threat == "RAIN_LIKELY":
            text = f"RAIN LIKELY — pressure falling {abs(rate):.1f} hPa/hr"
            bg = QColor(200, 120, 0)
        elif fog_risk:
            text = "FOG — low visibility, reduce speed"
            bg = QColor(30, 80, 160)
        elif has_ec:
            lvl = snap.ec_warning_level
            if lvl == "warning":
                bg = QColor(180, 20, 20)
            elif lvl == "watch":
                bg = QColor(200, 120, 0)
            elif lvl == "advisory":
                bg, fg = QColor(250, 204, 21), QColor(0, 0, 0)
            desc = snap.ec_warning_description.split("\n")[0].strip()
            text = "EC: " + (desc[:75] + ("..." if len(desc) > 75 else "") if desc else snap.ec_warning_text)

        if not text:
            return

        # Full-width bar at very bottom of Sport Sharp
        bar_y, bar_h = 460, 20
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, bar_y, _W, bar_h))
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, bar_y, _W, bar_h),
                   Qt.AlignCenter, text)

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
        """Draw a single safety vital — label above, value + unit below.

        Uses full 100px strip height for legibility at arm's length.
        """
        # Label — 13pt min for readability
        p.setPen(label_color)
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        label_rect = QRectF(x, _VITALS_Y0 + 2, w, 16)
        p.drawText(label_rect, Qt.AlignCenter, label)

        # Value — large, bold, Helvetica to match rest of UI
        font_size = 32 if large else FONT_BIG  # 32pt warning, 26pt normal
        p.setPen(value_color)
        p.setFont(QFont("Helvetica", font_size, QFont.Bold))
        value_rect = QRectF(x, _VITALS_Y0 + 18, w, 36)
        p.drawText(value_rect, Qt.AlignCenter, value)

        # Unit — smaller, below value
        p.setPen(label_color)
        p.setFont(QFont("Helvetica", 11))
        unit_rect = QRectF(x, _VITALS_Y0 + 54, w, 16)
        p.drawText(unit_rect, Qt.AlignCenter, unit)

    def _draw_grip_vital(self, p: QPainter, x: float, w: float) -> None:
        """Draw GRIP mini-bar with F/R percentages — dark cockpit style.

        3-zone color bar: green (>90%), yellow (80-90%), red (<80%).
        DIM when grip is healthy, YELLOW/RED when degraded.
        """
        front = self._front_grip_pct
        rear = self._rear_grip_pct
        worst = min(front, rear)

        # Dark cockpit: determine severity
        if worst < 80:
            lc = QColor(RED)
            large = True
        elif worst < 90:
            lc = QColor(YELLOW)
            large = False
        else:
            lc = QColor(DIM)
            large = False

        # "GRIP" label
        p.setPen(lc)
        p.setFont(QFont("Helvetica", 12, QFont.Bold))
        p.drawText(QRectF(x, _VITALS_Y0 + 2, w, 16), Qt.AlignCenter, "GRIP")

        # Bar geometry — two bars side by side (F left, R right)
        bar_w = (w - 20) / 2  # each bar
        bar_h = 24
        bar_y = _VITALS_Y0 + 22
        f_x = x + 6
        r_x = x + 6 + bar_w + 8

        for pct, bx, label in [
            (front, f_x, "F"),
            (rear, r_x, "R"),
        ]:
            # Bar background
            p.fillRect(QRectF(bx, bar_y, bar_w, bar_h), QColor(BG_PANEL))

            # Filled portion — color based on grip level
            if pct >= 90:
                bar_color = QColor(GREEN)
            elif pct >= 80:
                bar_color = QColor(YELLOW)
            else:
                bar_color = QColor(RED)

            fill_w = max(0, min(1.0, pct / 100.0)) * bar_w
            # Dark cockpit: low alpha when healthy, bright when degraded
            if pct >= 90:
                bar_color.setAlpha(40)
            elif pct >= 80:
                bar_color.setAlpha(160)
            else:
                bar_color.setAlpha(220)
            p.fillRect(QRectF(bx, bar_y, fill_w, bar_h), bar_color)

            # Sub-label (F / R) above bar
            sub_color = lc if worst < 90 else QColor(DIM)
            p.setPen(sub_color)
            p.setFont(QFont("Helvetica", 10, QFont.Bold))
            p.drawText(QRectF(bx, bar_y - 14, bar_w, 14), Qt.AlignCenter, label)

            # Percentage inside bar
            pct_color = QColor(WHITE) if pct < 90 else QColor(DIM)
            font_size = 16 if large else 13
            p.setPen(pct_color)
            p.setFont(QFont("Helvetica", font_size, QFont.Bold))
            p.drawText(QRectF(bx, bar_y, bar_w, bar_h), Qt.AlignCenter, f"{pct:.0f}")

        # Unit label below bars
        p.setPen(lc)
        p.setFont(QFont("Helvetica", 11))
        p.drawText(QRectF(x, _VITALS_Y0 + 54, w, 16), Qt.AlignCenter, "%")

    # ------------------------------------------------------------------
    # Sector insight helper
    # ------------------------------------------------------------------

    @staticmethod
    def _sector_insight(sector_ms: int, best_ms: int | None) -> tuple[str, QColor]:
        """Generate mini-insight text for a completed sector.

        Returns (text, color) based on delta magnitude vs best.
        """
        if best_ms is None or best_ms <= 0:
            return ("", QColor(DIM))

        delta_ms = sector_ms - best_ms
        delta_pct = (delta_ms / best_ms) * 100

        if delta_ms <= -500:
            return ("big gain", QColor(GREEN))
        elif delta_ms <= -100:
            return ("faster", QColor(GREEN))
        elif delta_ms <= 0:
            return ("matched", QColor(WHITE))
        elif delta_pct < 2:
            return ("close", QColor(WHITE))
        elif delta_pct < 5:
            return ("a bit slow", QColor(YELLOW))
        else:
            return ("lost time", QColor(RED))

    # ------------------------------------------------------------------
    # Voice ticker (bottom of vitals strip, y=458..478)
    # ------------------------------------------------------------------

    def _paint_voice_ticker(self, p: QPainter) -> None:
        if not self._voice_ticker:
            return
        p.setFont(QFont("Helvetica", 11))
        alphas = [120, 70, 40]
        x, y0, w = 20, 458, 380
        for i, line in enumerate(self._voice_ticker):
            color = QColor(WHITE)
            color.setAlpha(alphas[min(i, 2)])
            p.setPen(color)
            elided = p.fontMetrics().elidedText(line, Qt.ElideRight, w)
            p.drawText(QRectF(x, y0 + i * 15, w, 15),
                       Qt.AlignLeft | Qt.AlignVCenter, elided)
