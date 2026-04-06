"""KiSTI - Sport Mode Screen (SI-Drive = 1)

Performance / fast-road screen. Medium density.
MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport shows ONLY what the MXG cannot:
  - DCCD + surface + slip (AWD dynamics)
  - FLIR road surface conditions
  - Friction ellipse with trail (IMU)
  - Technique panel: brake G, balance, trail %, DCCD, front/rear grip
  - Coaching text from TechniqueAnalyzer

800x440 content area, 100% QPainter — no composite QWidget layouts.

Layout:
  y=0..100   DCCD bar + surface + slip (left) | Road zones (right)
  y=100..440 Technique panel (left 350px) | Friction ellipse (right)
"""

from __future__ import annotations

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
from ui.g_force_ellipse import paint_g_ellipse
from ui.road_condition import (
    paint_zone_tint,
    paint_edge_glow,
    paint_zone_bar,
    zone_states_from_snap,
    any_zone_low_grip,
)
from ui.theme import (
    BG_DARK,
    BG_PANEL,
    BG_ACCENT,
    WHITE,
    GRAY,
    DIM,
    GREEN,
    YELLOW,
    RED,
    CYAN,
    CHROME_DARK,
    MODE_S_ACCENT,
)


# ---------------------------------------------------------------------------
# DriveBC event banner formatter
# ---------------------------------------------------------------------------

def _drivebc_event_banner(text: str) -> str:
    """Format DriveBC event for at-a-glance banner."""
    if not text:
        return "DriveBC: Road event ahead"
    parts = text.split(". ")
    lead = parts[0].rstrip(".")
    details = [p.rstrip(".") for p in parts[1:] if not p.startswith(("Until ", "From ", "Starting ", "Last updated ", "Next update "))]
    banner = f"DriveBC: {lead} ahead"
    if details:
        banner += f" — {details[0]}"
    return banner[:80]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Friction ellipse center — right panel (350..800, 100..440)
_G_CENTER_X = 575
_G_CENTER_Y = 250

# Wheel speed delta thresholds (km/h)
_WS_MODERATE = 2.0
_WS_SEVERE = 5.0

# FLIR thresholds
# Road surface temp thresholds (forward-facing grill FLIR)
_FLIR_COLD = 5.0      # Ice risk
_FLIR_GREEN = 15.0    # Cool but safe
_FLIR_YELLOW = 40.0   # Warm/optimal
_FLIR_RED = 55.0      # Very hot pavement


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

        # Voice ticker (fed from main.py at 1Hz)
        self._voice_ticker: list[str] = []

        # Coaching text (fed from TechniqueAnalyzer at 1Hz)
        self._coaching_text: str = ""
        self._coaching_sentiment: str = "dim"

        # Paint counter for edge glow pulse
        self._paint_count: int = 0

        # Balance / grip / brake analysis (fed from coaching layer at 1Hz)
        self._balance_ratio: float = 1.0
        self._balance_text: str = ""
        self._balance_sentiment: str = "dim"
        self._front_grip_pct: float = 100.0
        self._rear_grip_pct: float = 100.0
        self._brake_peak_g: float = 0.0
        self._trail_brake_pct: float = 0.0

        self.setMinimumSize(800, 440)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Called at 20 Hz from main timer with a DiffState snapshot."""
        self._snap = snap
        self._g_trail.append((snap.imu_accel_y, snap.imu_accel_x))
        self.update()

    def update_voice_ticker(self, lines: list[str]) -> None:
        """Cache voice ticker lines (called at 1Hz from main.py)."""
        self._voice_ticker = lines

    def update_coaching(self, text: str, sentiment: str = "dim") -> None:
        """Cache coaching text from TechniqueAnalyzer (1Hz)."""
        self._coaching_text = text
        self._coaching_sentiment = sentiment

    def update_balance(self, ratio: float, text: str, sentiment: str) -> None:
        """Cache balance analysis from BalanceAnalyzer (1Hz)."""
        self._balance_ratio = ratio
        self._balance_text = text
        self._balance_sentiment = sentiment

    def update_grip(self, front_pct: float, rear_pct: float) -> None:
        """Cache per-axle grip from GripAnalyzer (1Hz)."""
        self._front_grip_pct = front_pct
        self._rear_grip_pct = rear_pct

    def update_brake_analysis(self, peak_g: float, trail_pct: float) -> None:
        """Cache brake quality from TechniqueAnalyzer (1Hz)."""
        self._brake_peak_g = peak_g
        self._trail_brake_pct = trail_pct

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

        # Per-zone road condition background tint
        zones = zone_states_from_snap(self._snap)
        if not snap.is_road_surface_stale():
            paint_zone_tint(p, w, h, zones, alpha=18)
        diff_stale = True if self._snap is None else snap.is_diff_stale()
        dynamics_stale = True if self._snap is None else snap.is_dynamics_stale()

        # --- Top band (y=0..100) ---
        self._paint_dccd_strip(p, snap, diff_stale)
        self._paint_flir_summary(p, snap)

        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, 100, w, 100)

        # Weather threat pill (dim-until-warning, dark cockpit)
        self._paint_weather_threat(p, snap)

        # --- Middle + bottom band (y=100..440) ---
        self._paint_technique_panel(p, snap, diff_stale, dynamics_stale)
        self._paint_g_ellipse(p, snap)
        self._paint_coaching(p)
        self._paint_voice_ticker(p)

        # Edge glow for LOW_GRIP
        if not snap.is_road_surface_stale():
            self._paint_count += 1
            paint_edge_glow(p, w, h, any_zone_low_grip(zones), self._paint_count)

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

        # Per-zone road condition indicators (3 thin bars)
        zones = zone_states_from_snap(self._snap if not stale else None)
        badge_x = 8
        badge_y = 40
        badge_tw = 60
        row2_h = 22
        paint_zone_bar(p, badge_x, badge_y, badge_tw, 18, zones,
                       paint_count=self._paint_count)

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
    # Top band: Road surface temp (right, 510..790) — forward FLIR
    # ------------------------------------------------------------------

    def _paint_flir_summary(self, p: QPainter, snap: DiffState) -> None:
        # Full-width road condition zone bar in the reserved FLIR panel
        p.fillRect(QRectF(510, 6, 280, 86), QColor(BG_PANEL))
        zones = zone_states_from_snap(self._snap)
        if not snap.is_road_surface_stale():
            paint_zone_bar(p, 516, 12, 268, 72, zones,
                           paint_count=self._paint_count, show_labels=True)

    # ------------------------------------------------------------------
    # Weather threat pill (dark cockpit — invisible when CLEAR)
    # ------------------------------------------------------------------

    def _paint_weather_threat(self, p: QPainter, snap: DiffState) -> None:
        """Full-width alert bar at bottom (y=424..440). Highest severity wins."""
        # Build candidates: (severity, text, bg, fg)
        candidates: list[tuple[int, str, QColor, QColor]] = []
        white = QColor(255, 255, 255)
        black = QColor(0, 0, 0)

        threat = snap.weather_threat_level
        rate = snap.pressure_trend_hpa_hr
        if threat == "STORM":
            candidates.append((50, f"STORM INCOMING — pressure falling {abs(rate):.1f} hPa/hr",
                               QColor(180, 20, 20), white))
        elif threat == "RAIN_LIKELY":
            candidates.append((25, f"RAIN LIKELY — pressure falling {abs(rate):.1f} hPa/hr",
                               QColor(200, 120, 0), white))

        if snap.ec_available and snap.ec_warning_level != "none":
            lvl = snap.ec_warning_level
            ec_bg = {"warning": QColor(180, 20, 20), "watch": QColor(200, 120, 0),
                     "advisory": QColor(250, 204, 21)}.get(lvl, QColor(30, 80, 160))
            ec_fg = black if lvl == "advisory" else white
            ec_sev = {"warning": 45, "watch": 30, "advisory": 20, "statement": 10}.get(lvl, 10)
            desc = snap.ec_warning_description.split("\n")[0].strip()
            ec_text = "EC: " + (desc[:75] + ("..." if len(desc) > 75 else "") if desc else snap.ec_warning_text)
            candidates.append((ec_sev, ec_text, ec_bg, ec_fg))

        if snap.drivebc_available and snap.drivebc_road_condition:
            cond = snap.drivebc_road_condition.upper()
            if cond in ("ICY", "SNOWY", "FROSTY"):
                dbc_text = f"DriveBC: {cond} road — {snap.drivebc_station_name}"
                candidates.append((42, dbc_text, QColor(180, 20, 20), white))
            elif cond in ("WET", "SLUSHY", "MOIST"):
                dbc_text = f"DriveBC: {cond} road — {snap.drivebc_station_name}"
                candidates.append((15, dbc_text, QColor(30, 80, 160), white))

        if snap.drivebc_available and snap.drivebc_event_count > 0:
            sev = snap.drivebc_event_severity
            evt_sev = 48 if sev == "CLOSURE" else 22
            evt_bg = QColor(180, 20, 20) if sev == "CLOSURE" else QColor(200, 120, 0)
            candidates.append((evt_sev, _drivebc_event_banner(snap.drivebc_event_text), evt_bg, white))

        if not candidates:
            return

        # Pick highest severity
        candidates.sort(key=lambda c: c[0], reverse=True)
        _, text, bg, fg = candidates[0]

        # Full-width bar at bottom of Sport screen
        bar_y, bar_h = 424, 16
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, bar_y, 800, bar_h))
        p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, bar_y, 800, bar_h),
                   Qt.AlignmentFlag.AlignCenter, text)

    # ------------------------------------------------------------------
    # Middle band: Technique panel (left, 0..350)
    # ------------------------------------------------------------------

    def _paint_technique_panel(
        self, p: QPainter, snap: DiffState,
        diff_stale: bool, dynamics_stale: bool,
    ) -> None:
        bar_x = 8
        bar_w = 220
        bar_h = 28
        label_w = 60
        val_w = 80
        y_start = 120
        spacing = 48

        # --- 1. BRAKE G — standard bar, max 1.5g, RED, peak hold ---
        y = y_start
        peak_g = self._brake_peak_g
        frac = min(1.0, peak_g / 1.5) if peak_g > 0 else 0.0
        val_str = f"{peak_g:.2f}g" if peak_g > 0.01 else "---"
        self._paint_standard_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "BRAKE G", frac, RED, val_str)
        # Peak hold marker (thin white line at peak position)
        if peak_g > 0.05:
            bx = bar_x + label_w
            peak_px = int(bx + bar_w * min(1.0, peak_g / 1.5))
            p.setPen(QPen(QColor(WHITE), 2))
            p.drawLine(peak_px, int(y + 2), peak_px, int(y + bar_h - 2))

        # --- 2. BALANCE — centered bar, green/yellow/red ---
        y = y_start + spacing
        ratio = self._balance_ratio
        # Normalize: 1.0 = center, <0.95 = understeer (left), >1.05 = oversteer (right)
        # Map deviation from 1.0 into -1..+1 range (0.7 → -1.0, 1.3 → +1.0)
        deviation = ratio - 1.0
        norm = max(-1.0, min(1.0, deviation / 0.3))
        abs_dev = abs(deviation)
        if abs_dev < 0.05:
            balance_color = GREEN
        elif abs_dev < 0.15:
            balance_color = YELLOW
        else:
            balance_color = RED
        bal_val = self._balance_text if self._balance_text else f"{ratio:.2f}"
        self._paint_centered_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "BALANCE", norm, balance_color, bal_val)

        # --- 3. TRAIL % — standard bar, max 100%, CYAN ---
        y = y_start + 2 * spacing
        trail_pct = self._trail_brake_pct
        frac = min(1.0, trail_pct / 100.0)
        val_str = f"{trail_pct:.0f}%" if trail_pct > 0.1 else "---"
        self._paint_standard_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "TRAIL %", frac, CYAN, val_str)

        # --- 4. DCCD — standard bar, max 100%, green/yellow/red ---
        y = y_start + 3 * spacing
        dccd = snap.dccd_command_pct if not diff_stale else 0.0
        frac = min(1.0, dccd / 100.0)
        if dccd > 70:
            dccd_color = RED
        elif dccd > 40:
            dccd_color = YELLOW
        else:
            dccd_color = GREEN
        val_str = f"{dccd:.0f}%" if not diff_stale else "---"
        self._paint_standard_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "DCCD", frac, dccd_color, val_str)

        # --- 5. F GRIP — standard bar, max 100%, green/yellow/red ---
        y = y_start + 4 * spacing
        fg = self._front_grip_pct
        frac = min(1.0, fg / 100.0)
        if fg > 90:
            fg_color = GREEN
        elif fg > 80:
            fg_color = YELLOW
        else:
            fg_color = RED
        val_str = f"{fg:.0f}%"
        self._paint_standard_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "F GRIP", frac, fg_color, val_str)

        # --- 6. R GRIP — standard bar, max 100%, green/yellow/red ---
        y = y_start + 5 * spacing
        rg = self._rear_grip_pct
        frac = min(1.0, rg / 100.0)
        if rg > 90:
            rg_color = GREEN
        elif rg > 80:
            rg_color = YELLOW
        else:
            rg_color = RED
        val_str = f"{rg:.0f}%"
        self._paint_standard_bar(p, bar_x, y, label_w, bar_w, bar_h, val_w,
                                 "R GRIP", frac, rg_color, val_str)

    def _paint_standard_bar(
        self, p: QPainter,
        bar_x: int, y: float, label_w: int, bar_w: int, bar_h: int,
        val_w: int, label: str, frac: float, fill_color: str, val_str: str,
    ) -> None:
        """Paint a single standard (left-to-right) bar with label and value."""
        # Label
        p.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(bar_x, y, label_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        bx = bar_x + label_w
        # Background
        p.fillRect(int(bx), int(y + 2), int(bar_w), int(bar_h - 4), QColor(BG_ACCENT))
        # Fill
        if frac > 0:
            fw = int(bar_w * min(1.0, frac))
            p.fillRect(int(bx), int(y + 2), fw, int(bar_h - 4), QColor(fill_color))

        # Value text
        p.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        p.setPen(QPen(QColor(fill_color) if val_str != "---" else QColor(GRAY)))
        p.drawText(QRectF(bx + bar_w + 4, y, val_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, val_str)

    def _paint_centered_bar(
        self, p: QPainter,
        bar_x: int, y: float, label_w: int, bar_w: int, bar_h: int,
        val_w: int, label: str, norm: float, fill_color: str, val_str: str,
    ) -> None:
        """Paint a centered bar (deviation from center) with label and value."""
        # Label
        p.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(bar_x, y, label_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        bx = bar_x + label_w
        # Background
        p.fillRect(int(bx), int(y + 2), int(bar_w), int(bar_h - 4), QColor(BG_ACCENT))
        # Center line
        center = bx + bar_w / 2
        p.setPen(QPen(QColor(GRAY), 1))
        p.drawLine(int(center), int(y + 2), int(center), int(y + bar_h - 2))

        # Fill from center
        if abs(norm) > 0.01:
            fill_px = int(abs(norm) * (bar_w / 2))
            if norm >= 0:
                p.fillRect(int(center), int(y + 2), fill_px, int(bar_h - 4), QColor(fill_color))
            else:
                p.fillRect(int(center - fill_px), int(y + 2), fill_px, int(bar_h - 4), QColor(fill_color))

        # Value text
        p.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        p.setPen(QPen(QColor(fill_color) if val_str != "---" else QColor(GRAY)))
        p.drawText(QRectF(bx + bar_w + 4, y, val_w, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, val_str)

    # ------------------------------------------------------------------
    # Middle band: Friction ellipse (right, 350..800)
    # ------------------------------------------------------------------

    def _paint_g_ellipse(self, p: QPainter, snap: DiffState) -> None:
        p.fillRect(350, 100, 450, 340, QColor(BG_DARK))
        paint_g_ellipse(p, _G_CENTER_X, _G_CENTER_Y, 130, snap, self._g_trail,
                        balance_ratio=self._balance_ratio, max_trail_dots=20,
                        accent_color=CYAN)

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Voice ticker (top-right panel, x=515..785, y=10..86)
    # ------------------------------------------------------------------

    def _paint_voice_ticker(self, p: QPainter) -> None:
        if not self._voice_ticker:
            return
        p.setFont(QFont("Helvetica", 11))
        alphas = [120, 70, 40]
        x, y0, w = 515, 12, 270
        for i, line in enumerate(self._voice_ticker[:5]):
            color = QColor(WHITE)
            color.setAlpha(alphas[min(i, 2)])
            p.setPen(color)
            elided = p.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, w)
            p.drawText(QRectF(x, y0 + i * 15, w, 15),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

    # ------------------------------------------------------------------
    # Coaching text (below G magnitude, y=418..438)
    # ------------------------------------------------------------------

    def _paint_coaching(self, p: QPainter) -> None:
        if not self._coaching_text:
            return
        sentiment_colors = {"green": GREEN, "amber": YELLOW, "dim": DIM}
        color = QColor(sentiment_colors.get(self._coaching_sentiment, DIM))
        p.setPen(color)
        p.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        p.drawText(
            QRectF(0, 418, 800, 20),
            Qt.AlignmentFlag.AlignCenter, self._coaching_text,
        )

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
