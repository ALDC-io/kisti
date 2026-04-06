"""KiSTI - Sport Sharp Screen (SI-Drive=2) — CANYON MODE

Dark cockpit canyon driving display.  "Am I safe?  What's changing?"
G-force ellipse dominates the screen.  Everything else is peripheral,
invisible when nominal, escalating visibility when abnormal.

MXG Strada handles: gear, speed, RPM, boost, lambda, oil, coolant.
KiSTI Sport Sharp shows ONLY what the MXG cannot:
  - G-force circle (cornering commitment, braking quality)
  - Road surface conditions (FLIR + DriveBC)
  - Grip estimation (front/rear axle)
  - Weather intelligence (BARO, EC, DriveBC, fog)
  - DCCD center-diff lock
  - Balance (understeer/oversteer)

800x480 QPainter, dark cockpit principle throughout.
Track variant preserved in sharp_screen_track.py.

Layout (800x480):
  y=0..30    Header: balance(L) | DCCD arc(C) | weather pill(R)
  y=30..400  HERO: G-force ellipse (r=170, center 400,215)
             Left edge: grip bars (F/R)
             Right edge: road zone bars (L/C/R)
  y=400..460 Bottom strip: BARO | road bar | road temp | voice ticker
  y=460..480 Alert bar (severity-driven, full width)
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
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
    WHITE,
    GRAY,
    DIM,
    GREEN,
    YELLOW,
    RED,
    CYAN,
    MODE_SS_ACCENT,
    FONT_BASE,
    FONT_BIG,
    FONT_XLARGE,
    FONT_MEGA,
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
# Layout constants
# ---------------------------------------------------------------------------

_W = 800
_H = 480

# Zone boundaries
_HEADER_Y1 = 30
_HERO_Y0 = 30
_HERO_Y1 = 400
_STRIP_Y0 = 400
_STRIP_Y1 = 460
_ALERT_Y0 = 460
_ALERT_Y1 = 480

# G-force hero ellipse
_G_CENTER_X = 400
_G_CENTER_Y = 215
_G_RADIUS = 170

# Grip bars (left edge, vertical)
_GRIP_X = 8
_GRIP_BAR_W = 16
_GRIP_GAP = 8
_GRIP_Y0 = 120
_GRIP_Y1 = 340

# Road zone bar (right edge, vertical)
_ROAD_X = 760
_ROAD_BAR_W = 32
_ROAD_Y0 = 120
_ROAD_Y1 = 340

# Safety thresholds (dark cockpit escalation)
_OIL_WARN_LOW = 15.0
_OIL_CRIT_LOW = 10.0
_COOL_WARN = 100.0
_COOL_CRIT = 105.0


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _font(size: int, bold: bool = False) -> QFont:
    f = QFont("Helvetica", size)
    if bold:
        f.setWeight(QFont.Bold)
    return f


# ---------------------------------------------------------------------------
# Surface state colors (matching road_condition.py)
# ---------------------------------------------------------------------------

from model.vehicle_state import SurfaceState

_ZONE_COLORS = {
    SurfaceState.DRY: QColor(0, 204, 102, 100),        # green, low alpha
    SurfaceState.WET: QColor(0, 100, 255, 170),         # blue
    SurfaceState.COLD: QColor(0, 200, 255, 200),        # cyan
    SurfaceState.LOW_GRIP: QColor(255, 26, 26, 240),    # red
}

_ZONE_ALPHA = {
    SurfaceState.DRY: 100,
    SurfaceState.WET: 170,
    SurfaceState.COLD: 200,
    SurfaceState.LOW_GRIP: 240,
}


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SportSharpScreenWidget(QWidget):
    """Sport Sharp (S#) canyon-focused QPainter widget — 800x480.

    "Am I safe?  What's changing?"
    Dark cockpit: nearly black when nominal, lights up when conditions
    demand attention.  G-force ellipse dominates the screen.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_W, _H)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        self._snap: Optional[DiffState] = None
        self._timing: dict = {}

        # G-force dot trail (canyon intensity feedback)
        self._g_trail: deque[tuple[float, float]] = deque(maxlen=40)

        # Paint counter for edge glow pulse
        self._paint_count: int = 0

        # Voice ticker (fed from main.py at 1Hz)
        self._voice_ticker: list[str] = []

        # Balance / grip (fed from coaching analyzers)
        self._balance_ratio: float = 1.0
        self._front_grip_pct: float = 100.0
        self._rear_grip_pct: float = 100.0
        self._sector_brake_quality: list[str] = []

    # ------------------------------------------------------------------
    # Public API (unchanged from track version)
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
        """Accept timing data — cached but not displayed in canyon mode."""
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
        """Accept brake quality — cached but not displayed in canyon mode."""
        self._sector_brake_quality = sector_qualities

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))

        snap = self._snap
        zones = zone_states_from_snap(snap)

        # 1. Full-screen road condition tint (dark cockpit: DRY = no tint)
        if snap is not None and not snap.is_road_surface_stale():
            paint_zone_tint(p, _W, _H, zones, alpha=10)

        # 2. Hero: G-force ellipse (dominates screen)
        self._paint_hero_ellipse(p)

        # 3. Header bar (balance, DCCD, weather) — ghost-dim
        self._paint_header(p)

        # 4. Left edge: grip bars
        self._paint_grip_bars(p)

        # 5. Right edge: road zone bars (vertical)
        self._paint_road_zones(p, zones)

        # 6. Bottom strip: BARO, road bar, DriveBC temp, voice ticker
        self._paint_bottom_strip(p, zones)

        # 7. Alert bar (y=460..480)
        self._paint_alert_bar(p)

        # 8. Edge glow for LOW_GRIP (drawn last — on top of everything)
        if snap is not None and not snap.is_road_surface_stale():
            self._paint_count += 1
            paint_edge_glow(p, _W, _H, any_zone_low_grip(zones), self._paint_count)

        p.end()

    # ------------------------------------------------------------------
    # Hero: G-force ellipse (y=30..400, full width)
    # ------------------------------------------------------------------

    def _paint_hero_ellipse(self, p: QPainter) -> None:
        """G-force friction ellipse — the reason this screen exists."""
        paint_g_ellipse(
            p,
            _G_CENTER_X,
            _G_CENTER_Y,
            _G_RADIUS,
            self._snap,
            self._g_trail,
            balance_ratio=self._balance_ratio,
            max_trail_dots=30,
            accent_color=MODE_SS_ACCENT,
        )

    # ------------------------------------------------------------------
    # Header bar (y=0..30) — ghost-dim peripheral awareness
    # ------------------------------------------------------------------

    def _paint_header(self, p: QPainter) -> None:
        snap = self._snap

        # --- Balance indicator (left) ---
        ratio = self._balance_ratio
        if ratio < 0.95:
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(QColor(0, 150, 255, 180)))  # blue
            p.drawText(QRectF(10, 4, 90, 22), Qt.AlignLeft | Qt.AlignVCenter, "UNDER")
        elif ratio > 1.05:
            p.setFont(_font(11, bold=True))
            p.setPen(QPen(QColor(255, 50, 50, 180)))  # red
            p.drawText(QRectF(10, 4, 90, 22), Qt.AlignLeft | Qt.AlignVCenter, "OVER")

        # --- DCCD arc gauge (center) ---
        dccd_pct = snap.dccd_pct if snap else 0.0
        stale = snap is None or snap.is_diff_stale()
        cx, cy, arc_r = 400, 16, 12

        # DIM outline always (driver expects to see it)
        p.setPen(QPen(QColor(DIM), 2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2),
                  0 * 16, 180 * 16)  # top semicircle

        if not stale and dccd_pct > 5:
            # Fill proportional to lock percentage
            if dccd_pct > 70:
                fill_color = QColor(RED)
            elif dccd_pct > 40:
                fill_color = QColor(YELLOW)
            else:
                fill_color = QColor(GREEN)

            sweep = int(180 * (dccd_pct / 100.0))
            p.setPen(Qt.NoPen)
            p.setBrush(fill_color)
            # Draw filled arc (pie slice)
            path = QPainterPath()
            path.moveTo(cx, cy)
            path.arcTo(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2),
                       0, sweep)
            path.closeSubpath()
            p.drawPath(path)

        # DCCD label
        p.setFont(_font(8))
        p.setPen(QPen(QColor(DIM) if (stale or dccd_pct <= 5) else QColor(GRAY)))
        p.drawText(QRectF(cx - 20, cy - arc_r - 10, 40, 10),
                   Qt.AlignCenter, "DCCD")

        # DCCD percentage (only when >5%)
        if not stale and dccd_pct > 5:
            p.setFont(_font(9, bold=True))
            p.setPen(QPen(fill_color))
            p.drawText(QRectF(cx - 20, cy + arc_r + 1, 40, 12),
                       Qt.AlignCenter, f"{dccd_pct:.0f}%")

        # --- Weather threat pill (right) ---
        if snap is not None:
            threat = snap.weather_threat_level
            has_ec = snap.ec_available and snap.ec_warning_level not in ("none", "")

            pill_text = ""
            pill_color = None

            if threat == "STORM":
                pill_text, pill_color = "STORM", QColor(RED)
            elif threat == "RAIN_LIKELY":
                pill_text, pill_color = "RAIN", QColor(YELLOW)
            elif has_ec:
                lvl = snap.ec_warning_level
                if lvl in ("warning", "watch"):
                    pill_text = "EC"
                    pill_color = QColor(YELLOW) if lvl == "warning" else QColor(CYAN)

            if pill_text and pill_color:
                p.setFont(_font(10, bold=True))
                fm = p.fontMetrics()
                pw = fm.horizontalAdvance(pill_text) + 16
                px = _W - 10 - pw
                py = 5
                ph = 20

                p.setPen(Qt.NoPen)
                p.setBrush(pill_color)
                p.setOpacity(0.3)
                p.drawRoundedRect(QRectF(px, py, pw, ph), 4, 4)
                p.setOpacity(1.0)
                p.setPen(QPen(pill_color))
                p.drawText(QRectF(px, py, pw, ph), Qt.AlignCenter, pill_text)

    # ------------------------------------------------------------------
    # Left edge: grip bars (x=8..48, y=120..340)
    # ------------------------------------------------------------------

    def _paint_grip_bars(self, p: QPainter) -> None:
        """Front/rear grip bars — dark cockpit: invisible when healthy."""
        front = self._front_grip_pct
        rear = self._rear_grip_pct

        bars = [
            ("F", front, _GRIP_X),
            ("R", rear, _GRIP_X + _GRIP_BAR_W + _GRIP_GAP),
        ]

        bar_h = _GRIP_Y1 - _GRIP_Y0

        for label, pct, x in bars:
            # Determine color and alpha
            if pct < 80:
                color = QColor(RED)
                alpha = 220
            elif pct < 90:
                color = QColor(YELLOW)
                alpha = 160
            else:
                color = QColor(GREEN)
                alpha = 30  # Dark cockpit: barely visible when healthy

            # Background slot
            slot_color = QColor(BG_PANEL)
            p.setPen(Qt.NoPen)
            p.setBrush(slot_color)
            p.drawRoundedRect(QRectF(x, _GRIP_Y0, _GRIP_BAR_W, bar_h), 3, 3)

            # Fill from bottom up
            fill_h = max(0, min(1.0, pct / 100.0)) * bar_h
            fill_y = _GRIP_Y1 - fill_h
            fill_color = QColor(color)
            fill_color.setAlpha(alpha)
            p.setBrush(fill_color)
            p.drawRoundedRect(QRectF(x, fill_y, _GRIP_BAR_W, fill_h), 3, 3)

            # Label at top
            p.setFont(_font(9))
            label_color = QColor(DIM) if pct >= 90 else color
            p.setPen(QPen(label_color))
            p.drawText(QRectF(x, _GRIP_Y0 - 14, _GRIP_BAR_W, 12),
                       Qt.AlignCenter, label)

            # Percentage text — only when degraded
            if pct < 90:
                p.setFont(_font(12, bold=True))
                p.setPen(QPen(color))
                mid_y = _GRIP_Y0 + bar_h / 2 - 8
                p.drawText(QRectF(x - 4, mid_y, _GRIP_BAR_W + 8, 16),
                           Qt.AlignCenter, f"{pct:.0f}")

    # ------------------------------------------------------------------
    # Right edge: road zone bars (x=760..792, y=120..340)
    # ------------------------------------------------------------------

    def _paint_road_zones(self, p: QPainter, zones: list) -> None:
        """Vertical road condition bars — L/C/R zones, dark cockpit."""
        zone_h = (_ROAD_Y1 - _ROAD_Y0 - 8) // 3  # 3 zones with gaps
        labels = ["L", "C", "R"]

        for i, (state, label) in enumerate(zip(zones, labels)):
            y = _ROAD_Y0 + i * (zone_h + 4)
            color = _ZONE_COLORS.get(state, QColor(GREEN))
            alpha = _ZONE_ALPHA.get(state, 100)

            # LOW_GRIP pulse
            if state == SurfaceState.LOW_GRIP:
                pulse = int(30 * math.sin(self._paint_count * 0.06))
                alpha = min(255, alpha + pulse)

            fill = QColor(color)
            fill.setAlpha(alpha)

            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(QRectF(_ROAD_X, y, _ROAD_BAR_W, zone_h), 3, 3)

            # Zone label
            label_color = QColor(DIM) if state == SurfaceState.DRY else QColor(WHITE)
            p.setFont(_font(9))
            p.setPen(QPen(label_color))
            p.drawText(QRectF(_ROAD_X, y, _ROAD_BAR_W, zone_h),
                       Qt.AlignCenter, label)

    # ------------------------------------------------------------------
    # Bottom strip (y=400..460): BARO | road bar | road temp | ticker
    # ------------------------------------------------------------------

    def _paint_bottom_strip(self, p: QPainter, zones: list) -> None:
        snap = self._snap

        # Dark background for strip
        p.fillRect(QRectF(0, _STRIP_Y0, _W, _STRIP_Y1 - _STRIP_Y0), QColor(BG_PANEL))

        # --- BARO trend (x=10..160) ---
        rate = snap.pressure_trend_hpa_hr if snap else 0.0
        threat = snap.weather_threat_level if snap else "CLEAR"
        dew_spread = snap.dew_point_spread_c if snap else 99.0
        humidity = snap.ambient_humidity_pct if snap else 0.0
        fog_risk = dew_spread < 1.5 and humidity > 93.0

        if threat == "STORM":
            lc, vc = QColor(RED), QColor(RED)
        elif threat == "RAIN_LIKELY":
            lc, vc = QColor(YELLOW), QColor(YELLOW)
        elif fog_risk:
            lc, vc = QColor(CYAN), QColor(CYAN)
        elif threat == "CHANGING":
            lc, vc = QColor(CYAN), QColor(CYAN)
        else:
            lc, vc = QColor(DIM), QColor(DIM)

        label = "FOG" if fog_risk else "BARO"
        value = f"{rate:+.1f}"
        unit = "hPa/hr"

        p.setFont(_font(9))
        p.setPen(QPen(lc))
        p.drawText(QRectF(10, _STRIP_Y0 + 2, 150, 14), Qt.AlignLeft, label)
        p.setFont(_font(18, bold=True))
        p.setPen(QPen(vc))
        p.drawText(QRectF(10, _STRIP_Y0 + 16, 150, 26), Qt.AlignLeft, value)
        p.setFont(_font(8))
        p.setPen(QPen(lc))
        p.drawText(QRectF(10, _STRIP_Y0 + 42, 150, 12), Qt.AlignLeft, unit)

        # --- Road condition zone bar (x=170..380) ---
        if snap is not None and not snap.is_road_surface_stale():
            paint_zone_bar(p, 170, _STRIP_Y0 + 12, 200, 32, zones,
                           paint_count=self._paint_count, show_labels=True)

        # --- DriveBC road temp (x=390..500) ---
        if snap is not None and snap.drivebc_available:
            road_temp = snap.drivebc_road_temp_c
            if road_temp is not None:
                if road_temp < 0:
                    tc = QColor(RED)
                elif road_temp < 5:
                    tc = QColor(YELLOW)
                elif road_temp < 10:
                    tc = QColor(CYAN)
                else:
                    tc = QColor(DIM)

                p.setFont(_font(9))
                p.setPen(QPen(tc))
                p.drawText(QRectF(390, _STRIP_Y0 + 2, 110, 14), Qt.AlignLeft, "ROAD")
                p.setFont(_font(18, bold=True))
                p.drawText(QRectF(390, _STRIP_Y0 + 16, 110, 26), Qt.AlignLeft, f"{road_temp:.0f}°")
                p.setFont(_font(8))
                p.drawText(QRectF(390, _STRIP_Y0 + 42, 110, 12), Qt.AlignLeft,
                           snap.drivebc_station_name[:20] if snap.drivebc_station_name else "")

        # --- Voice ticker (x=510..790) ---
        if self._voice_ticker:
            lines = self._voice_ticker[:2]
            alphas = [120, 60]
            for i, line in enumerate(lines):
                p.setFont(_font(10))
                text_color = QColor(WHITE)
                text_color.setAlpha(alphas[i] if i < len(alphas) else 40)
                p.setPen(QPen(text_color))
                y = _STRIP_Y0 + 6 + i * 24
                p.drawText(QRectF(510, y, 280, 20),
                           Qt.AlignRight | Qt.AlignVCenter, line)

    # ------------------------------------------------------------------
    # Alert bar (y=460..480) — severity-driven, full width
    # ------------------------------------------------------------------

    def _paint_alert_bar(self, p: QPainter) -> None:
        """Full-width alert bar. Highest severity wins.

        Canyon-first: FOG gets its own alert.
        """
        snap = self._snap
        if snap is None:
            return

        # Build candidates: (severity, text, bg, fg)
        candidates: list[tuple[int, str, QColor, QColor]] = []
        white = QColor(255, 255, 255)
        black = QColor(0, 0, 0)

        threat = snap.weather_threat_level
        rate = snap.pressure_trend_hpa_hr
        dew_spread = snap.dew_point_spread_c
        humidity = snap.ambient_humidity_pct
        fog_risk = dew_spread < 1.5 and humidity > 93.0

        if threat == "STORM":
            candidates.append((50, f"STORM INCOMING — pressure falling {abs(rate):.1f} hPa/hr",
                               QColor(180, 20, 20), white))
        elif threat == "RAIN_LIKELY":
            candidates.append((25, f"RAIN LIKELY — pressure falling {abs(rate):.1f} hPa/hr",
                               QColor(200, 120, 0), white))

        if fog_risk:
            candidates.append((35, "FOG — low visibility, reduce speed",
                               QColor(30, 80, 160), white))

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

        candidates.sort(key=lambda c: c[0], reverse=True)
        _, text, bg, fg = candidates[0]

        # Full-width bar
        bar_y, bar_h = _ALERT_Y0, _ALERT_Y1 - _ALERT_Y0
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, bar_y, _W, bar_h))
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(fg))
        p.drawText(QRectF(0, bar_y, _W, bar_h),
                   Qt.AlignCenter, text)
