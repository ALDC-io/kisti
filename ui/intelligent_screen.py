"""KiSTI - Intelligent Mode Screen (SI-Drive = 0)

Calm / street cruising display.  "What are the conditions?"
Big text, readable at arm's length on Kenwood Excelon 800x480.

Full QPainter rendering — no composite QWidget layouts.
Color accent: MODE_I_ACCENT (#00AAFF) blue.

Layout:
  y=0..114    Weather card — compact temp, humidity, pressure.
  y=118..310  FLIR road surface — live IR image (inferno colormap).
  y=316..455  Status strip — surface/slip/DCCD row + ABS/spread/VDC row.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState
from ui.road_condition import (
    paint_zone_tint,
    paint_edge_glow,
    paint_zone_bar,
    zone_states_from_snap,
    any_zone_low_grip,
    worst_state_label,
)
from ui.g_force_ellipse import paint_g_ellipse
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
    MODE_I_ACCENT,
)

# ---------------------------------------------------------------------------
# FLIR brake temp thresholds (deg C)
# ---------------------------------------------------------------------------
# Road surface temp thresholds (forward-facing grill FLIR)
_FLIR_COLD: float = 5.0      # Ice risk
_FLIR_GREEN: float = 15.0    # Cool but safe
_FLIR_YELLOW: float = 40.0   # Warm/optimal
_FLIR_RED: float = 55.0      # Very hot pavement

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


def _draw_trend_arrow_large(p: QPainter, x: float, y: float, h: float,
                            rate: float, threshold: float = 0.5) -> None:
    """Draw a trend arrow matching the adjacent 38pt value height.

    x, y = top-left of arrow area. h = height of the value text cell.
    Arrow is vertically centered in h, ~24px tall, 16px wide head.
    """
    abs_rate = abs(rate)
    if abs_rate < threshold * 0.3:
        # Stable — no arrow (reading is already white = fine)
        return

    # Color by rate magnitude
    if abs_rate < threshold:
        color = QColor(GREEN)
    elif abs_rate < threshold * 3:
        color = QColor(YELLOW)
    else:
        color = QColor(RED)

    p.save()
    p.setPen(QPen(color, 4.0))
    p.setRenderHint(QPainter.Antialiasing, True)

    # Arrow geometry — vertically centered in the cell
    arrow_h = 24.0
    cy = y + h / 2.0  # vertical center
    cx = x + 10.0     # horizontal center
    top = cy - arrow_h / 2.0
    bot = cy + arrow_h / 2.0
    head_w = 8.0      # half-width of arrowhead

    if rate > 0:
        # Up arrow
        p.drawLine(QPointF(cx, bot), QPointF(cx, top))
        p.drawLine(QPointF(cx, top), QPointF(cx - head_w, top + 8))
        p.drawLine(QPointF(cx, top), QPointF(cx + head_w, top + 8))
    else:
        # Down arrow
        p.drawLine(QPointF(cx, top), QPointF(cx, bot))
        p.drawLine(QPointF(cx, bot), QPointF(cx - head_w, bot - 8))
        p.drawLine(QPointF(cx, bot), QPointF(cx + head_w, bot - 8))

    p.restore()


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

    Three-section layout optimised for arm's-length readability:
      - Weather card (big temp, humidity, pressure)
      - FLIR brake temps (full-width 2x2 grid + warm-up badge)
      - Status strip (DCCD bar + surface badge + slip delta)
    """

    def __init__(self, flir_reader=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap: DiffState | None = None
        self._cached_ir_image: QImage | None = None
        self._prev_frame: np.ndarray | None = None  # temporal smoothing
        self._frame_skip: int = 0  # process every 3rd frame (~3 Hz)

        # Tell Qt we paint our entire rect every frame (compositorless X11)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

        # Voice ticker (fed from main.py at 1Hz)
        self._voice_ticker: list[str] = []

        # Coaching text (fed from ConditionRuleEngine at 1Hz)
        self._coaching_text: str = ""
        self._coaching_sentiment: str = "dim"
        self._coaching_level: int = 2  # CoachingLevel.FULL

        # Paint counter for edge glow pulse animation
        self._paint_count: int = 0

        # Alert banner rotation index (cycles every 20s when multiple alerts)
        self._alert_index: int = 0

        # Force periodic repaint even without data (1 Hz)
        from PySide6.QtCore import QTimer
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(1000)
        self._repaint_timer.timeout.connect(self.update)
        self._repaint_timer.start()

        # Alert rotation timer — advance banner every 20s
        self._alert_rotate_timer = QTimer(self)
        self._alert_rotate_timer.setInterval(20_000)
        self._alert_rotate_timer.timeout.connect(self._rotate_alert)
        self._alert_rotate_timer.start()

        if flir_reader is not None:
            flir_reader.frame_updated.connect(self._on_frame_updated)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, snap: DiffState) -> None:
        """Called at 20 Hz from MainWindow with the latest DiffState snapshot."""
        self._snap = snap
        self.update()  # schedule repaint

    def update_voice_ticker(self, lines: list[str]) -> None:
        """Cache voice ticker lines (called at 1Hz from main.py)."""
        self._voice_ticker = lines

    def update_coaching(self, text: str, sentiment: str = "dim") -> None:
        """Cache coaching text from ConditionRuleEngine (1Hz)."""
        self._coaching_text = text
        self._coaching_sentiment = sentiment

    def set_coaching_level(self, level: int) -> None:
        """Update coaching level from ModeManager (K5 button)."""
        self._coaching_level = level

    def _rotate_alert(self) -> None:
        """Advance alert banner index every 20s."""
        self._alert_index += 1
        self.update()

    def _on_frame_updated(self, frame) -> None:
        """Receive raw uint16 thermal frame — enhance contrast, colormap, cache.

        No frame skipping — process every frame at native 9Hz for responsive
        road condition detection. Light temporal smoothing (90/10) for noise
        reduction without perceptible lag.
        """
        f32 = frame.astype(np.float32)

        # Light temporal smoothing: 90% new + 10% previous — noise only, no lag
        if self._prev_frame is not None and self._prev_frame.shape == f32.shape:
            f32 = 0.9 * f32 + 0.1 * self._prev_frame
        self._prev_frame = f32

        # Normalize to uint8
        mn, mx = float(f32.min()), float(f32.max())
        if mx == mn:
            norm = np.zeros(f32.shape, dtype=np.uint8)
        else:
            norm = ((f32 - mn) / (mx - mn) * 255.0).astype(np.uint8)

        # CLAHE — adaptive histogram equalization for thermal contrast
        # Reuse cached CLAHE object (cv2.createCLAHE is cheap but no need to recreate)
        try:
            if not hasattr(self, '_clahe'):
                import cv2
                self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
            norm = self._clahe.apply(norm)
        except (ImportError, AttributeError):
            pass

        rgb = self._INFERNO_LUT[norm]  # single LUT index — fast
        h, w = rgb.shape[:2]
        self._cached_ir_image = QImage(
            rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888
        )
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))

        # Per-zone road condition background tint
        snap = self._snap
        zones = zone_states_from_snap(snap)
        if snap is not None and not snap.is_road_surface_stale():
            paint_zone_tint(p, _W, _H, zones, alpha=28)

        self._draw_weather(p)
        self._draw_flir_panel(p)
        self._draw_ec_banner(p)
        self._draw_status_strip(p)
        self._draw_coaching_bar(p)
        self._paint_voice_ticker(p)
        self._draw_info_line(p)

        # Edge glow for LOW_GRIP — drawn last so it's on top
        if snap is not None and not snap.is_road_surface_stale():
            self._paint_count += 1
            paint_edge_glow(p, _W, _H, any_zone_low_grip(zones), self._paint_count)

        p.end()

    # ==================================================================
    # WEATHER CARD (y=0..160)
    # BIG temperature, humidity, pressure.  Full width.
    # ==================================================================

    def _draw_weather(self, p: QPainter) -> None:
        snap = self._snap
        available = snap is not None and snap.ambient_available

        # Card background (compact)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_ACCENT))
        p.drawRoundedRect(QRectF(6, 4, _W - 12, 108), 6, 6)

        # 4-column layout: WEATHER | ROAD | HUMIDITY | PRESSURE
        col_w = (_W - 40) / 4.0  # ~190px each
        cols = [20, 20 + col_w, 20 + col_w * 2, 20 + col_w * 3]

        # --- Col 1: WEATHER (ambient temp) ---
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(cols[0], 6, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "WEATHER")

        if available:
            temp_text = f"{snap.ambient_temp_c:.1f}\u00b0"
            temp_color = QColor(WHITE)
        else:
            temp_text = "---"
            temp_color = QColor(GRAY)

        p.setFont(_font(38, bold=True))
        p.setPen(QPen(temp_color))
        p.drawText(QRectF(cols[0], 24, col_w, 56),
                   Qt.AlignLeft | Qt.AlignVCenter, temp_text)

        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[0], 82, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "AIR TEMP")

        # --- Col 2: ROAD (FLIR surface temp) ---
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(cols[1], 6, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "ROAD")

        if snap is not None and not snap.is_road_surface_stale():
            road_avg = (snap.road_temp_left + snap.road_temp_center + snap.road_temp_right) / 3.0
            road_text = f"{road_avg:.1f}\u00b0"
            road_color = _brake_heat_color(road_avg)
        else:
            road_text = "---"
            road_color = QColor(GRAY)

        p.setFont(_font(38, bold=True))
        p.setPen(QPen(road_color))
        p.drawText(QRectF(cols[1], 24, col_w, 56),
                   Qt.AlignLeft | Qt.AlignVCenter, road_text)

        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[1], 82, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "ROAD SURFACE")

        # --- Col 3: HUMIDITY ---
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[2], 6, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "HUMIDITY")

        if available:
            hum_text = f"{snap.ambient_humidity_pct:.0f}%"
            hum_color = QColor(WHITE)
        else:
            hum_text = "---"
            hum_color = QColor(GRAY)

        p.setFont(_font(38, bold=True))
        p.setPen(QPen(hum_color))
        p.drawText(QRectF(cols[2], 24, col_w, 56),
                   Qt.AlignLeft | Qt.AlignVCenter, hum_text)

        # Humidity trend arrow — after value
        if available:
            hum_fm = p.fontMetrics()
            hum_tw = hum_fm.horizontalAdvance(hum_text)
            _draw_trend_arrow_large(p, cols[2] + hum_tw + 6, 24, 56,
                                    snap.humidity_trend_pct_hr, threshold=2.0)

        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[2], 82, col_w, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "RELATIVE")

        # --- Col 4: PRESSURE (right-aligned) ---
        prs_right = _W - 20  # right edge with margin
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[3], 6, prs_right - cols[3], 16),
                   Qt.AlignRight | Qt.AlignVCenter, "BARO")

        if available:
            prs_text = f"{snap.ambient_pressure_hpa:.0f}"
            prs_color = QColor(WHITE)
            # Color baro value by threat level
            threat = snap.weather_threat_level
            if threat == "STORM":
                prs_color = QColor(RED)
            elif threat == "RAIN_LIKELY":
                prs_color = QColor(YELLOW)
            elif threat == "CHANGING":
                prs_color = QColor(MODE_I_ACCENT)
        else:
            prs_text = "---"
            prs_color = QColor(GRAY)

        p.setFont(_font(38, bold=True))
        p.setPen(QPen(prs_color))
        # Shift text left to leave room for arrow on the right
        prs_fm = p.fontMetrics()
        prs_tw = prs_fm.horizontalAdvance(prs_text)
        prs_text_x = prs_right - prs_tw - 26
        p.drawText(QRectF(prs_text_x, 24, prs_tw, 56),
                   Qt.AlignLeft | Qt.AlignVCenter, prs_text)

        # Baro trend arrow — after value
        if available:
            _draw_trend_arrow_large(p, prs_text_x + prs_tw + 6, 24, 56,
                                    snap.pressure_trend_hpa_hr, threshold=0.5)

        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(cols[3], 82, prs_right - cols[3], 16),
                   Qt.AlignRight | Qt.AlignVCenter, "hPa")

        # Weather threat text removed — consolidated into rotating FLIR banner.

        # EC regional alert banner — drawn after FLIR so it overlays the thermal image.
        # Rendered in _draw_ec_banner() which is called after _draw_flir_panel().

        # EC forecast condition (top-left, subtle)
        if snap is not None and snap.ec_available and snap.ec_forecast_condition:
            p.setFont(_font(9))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(cols[0], 98, 200, 14),
                       Qt.AlignLeft | Qt.AlignVCenter,
                       f"EC: {snap.ec_forecast_condition}")

        # "NO SENSOR" overlay when unavailable
        if not available and (snap is None or snap.is_road_surface_stale()):
            p.setFont(_font(13))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, 40, _W, 30), Qt.AlignCenter, "NO SENSORS")

    # ==================================================================
    # ROAD SURFACE (y=160..340)
    # Forward-facing FLIR (grill-mounted) — road surface temp + warm-up.
    # ==================================================================

    # ---------------------------------------------------------------------------
    # Inferno colormap — precomputed 256-entry LUT (no per-frame np.interp)
    # 0 → black, 64 → deep purple, 128 → orange, 192 → yellow, 255 → white
    # ---------------------------------------------------------------------------
    _INFERNO_LUT = np.zeros((256, 3), dtype=np.uint8)
    _stops = np.array([[0,0,0],[59,7,100],[249,115,22],[253,224,71],[255,255,255]], dtype=np.float32)
    _keys = np.array([0, 64, 128, 192, 255], dtype=np.float32)
    for _ch in range(3):
        _INFERNO_LUT[:, _ch] = np.interp(np.arange(256), _keys, _stops[:, _ch]).astype(np.uint8)
    del _stops, _keys, _ch

    def _draw_flir_panel(self, p: QPainter) -> None:
        y0 = 118
        panel_h = 192  # y=118..310

        # Warm-up badge (top-right, always shown)
        self._draw_warmup_badge(p, y0)

        if self._cached_ir_image is not None:
            # Blit cached QImage (colormap applied in _on_frame_updated)
            p.drawImage(QRectF(0, y0, _W, panel_h), self._cached_ir_image)

            pass  # clean thermal image — no label overlay
        else:
            # Section label
            p.setFont(_font(12, bold=True))
            p.setPen(QPen(QColor(MODE_I_ACCENT)))
            p.drawText(QRectF(20, y0 + 4, 200, 20),
                       Qt.AlignLeft | Qt.AlignVCenter, "ROAD SURFACE")

            p.setFont(_font(16))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, y0 + 60, _W, 40), Qt.AlignCenter,
                       "FLIR NOT CONNECTED")
            return

        # Coaching text moved to _draw_coaching_bar (below status strip)

    def _draw_ec_banner(self, p: QPainter) -> None:
        """Alert banner overlaid on FLIR panel — rotates every 20s when multiple.

        Builds list of active alerts (weather engine + EC), sorted by severity.
        Cycles through them so the driver sees all active warnings.
        """
        snap = self._snap
        if snap is None:
            return

        # Build list of (severity, text, bg_color) tuples
        alerts: list[tuple[int, str, QColor]] = []

        # Weather engine alerts (white text on red/orange for readability)
        threat = snap.weather_threat_level
        rate = snap.pressure_trend_hpa_hr
        if threat == "STORM":
            alerts.append((50, f"STORM INCOMING — pressure falling {abs(rate):.1f} hPa/hr",
                           QColor(180, 20, 20)))
        elif threat == "RAIN_LIKELY":
            alerts.append((25, f"RAIN LIKELY — pressure falling {abs(rate):.1f} hPa/hr",
                           QColor(200, 120, 0)))
        # CHANGING is too subtle for a banner — BARO color already shows it

        # EC alerts — show actual description, not just "Special Weather Statement"
        if snap.ec_available and snap.ec_warning_level != "none":
            lvl = snap.ec_warning_level
            ec_colors = {
                "warning": QColor(180, 20, 20),
                "watch": QColor(200, 120, 0),
                "advisory": QColor(250, 204, 21),
            }
            bg = ec_colors.get(lvl, QColor(30, 80, 160))
            sev = {"warning": 45, "watch": 30, "advisory": 20, "statement": 10}.get(lvl, 10)
            # Use first line of description, fall back to alert name
            desc = snap.ec_warning_description.split("\n")[0].strip()
            if desc:
                # Truncate to fit 800px banner (~75 chars at font 10, with EC: prefix)
                ec_display = "EC: " + desc[:75] + ("..." if len(desc) > 75 else "")
            else:
                ec_display = "EC: " + snap.ec_warning_text
            alerts.append((sev, ec_display, bg))

        # DriveBC RWIS road conditions — actual road surface state from highway sensors
        if snap.drivebc_available and snap.drivebc_road_condition:
            cond = snap.drivebc_road_condition.upper()
            if cond in ("ICY", "SNOWY", "FROSTY"):
                dbc_text = f"DriveBC: {cond} road — {snap.drivebc_station_name}"
                if snap.drivebc_road_temp_c is not None:
                    dbc_text += f" ({snap.drivebc_road_temp_c:.0f}°C)"
                alerts.append((42, dbc_text, QColor(180, 20, 20)))
            elif cond in ("WET", "SLUSHY", "MOIST"):
                dbc_text = f"DriveBC: {cond} road — {snap.drivebc_station_name}"
                alerts.append((15, dbc_text, QColor(30, 80, 160)))

        # DriveBC road events — closures and major incidents
        if snap.drivebc_available and snap.drivebc_event_count > 0:
            sev = snap.drivebc_event_severity
            evt_bg = QColor(180, 20, 20) if sev == "CLOSURE" else QColor(200, 120, 0)
            evt_sev = 48 if sev == "CLOSURE" else 22
            evt_text = snap.drivebc_event_text[:70]
            alerts.append((evt_sev, f"DriveBC: {evt_text}", evt_bg))

        if not alerts:
            return

        # Sort by severity descending, rotate through the list
        alerts.sort(key=lambda a: a[0], reverse=True)
        idx = self._alert_index % len(alerts)
        _, text, bg_color = alerts[idx]

        # Full-width banner at top of FLIR panel
        # White text on dark backgrounds (red/orange), black on light (yellow/grey)
        severity = alerts[idx][0]
        text_color = QColor(255, 255, 255) if severity >= 10 else QColor(0, 0, 0)

        banner_y = 118
        banner_h = 22
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawRect(QRectF(0, banner_y, _W, banner_h))
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(text_color))
        p.drawText(QRectF(0, banner_y, _W, banner_h),
                   Qt.AlignCenter, text)

    def _draw_warmup_badge(self, p: QPainter, y0: int) -> None:
        """Draw warm-up state badge (COLD / WARMING / READY) overlaid on FLIR panel."""
        snap = self._snap
        if snap is None:
            warmup_label = "---"
            warmup_color = QColor(GRAY)
        else:
            warmup_label = snap.warmup_state.label
            warmup_color = QColor(snap.warmup_state.color)

        # Badge position: top-right of FLIR section
        badge_x = _W - 180
        badge_y = y0 + 4
        badge_w = 160
        badge_h = 24

        # Pill background
        pill_bg = QColor(warmup_color)
        pill_bg.setAlphaF(0.25)
        p.setPen(Qt.NoPen)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 12, 12)

        # Border
        p.setPen(QPen(warmup_color, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 12, 12)

        # Text
        p.setFont(_font(13, bold=True))
        p.setPen(QPen(warmup_color))
        p.drawText(QRectF(badge_x, badge_y, badge_w, badge_h),
                   Qt.AlignCenter, warmup_label)

    # ==================================================================
    # STATUS STRIP (y=316..480)
    # DCCD bar + Surface badge + Slip delta — one horizontal row.
    # ==================================================================

    def _draw_status_strip(self, p: QPainter) -> None:
        snap = self._snap
        stale_diff = snap is None or snap.is_diff_stale()
        stale_wheel = snap is None or snap.is_wheel_stale()

        y0 = 316
        strip_h = 164  # y=316..480

        # Layout: Full-width road condition zone bar (top) → slip + DCCD below
        # Road condition is THE HERO — spans entire screen width.

        # --- Full-width road condition zone bar (y0..y0+60) ---
        zones = zone_states_from_snap(snap)
        bar_y = y0 + 4
        bar_h = 50
        paint_zone_bar(p, 10, bar_y, _W - 20, bar_h, zones,
                       paint_count=self._paint_count, show_labels=True)

        # Worst-condition label — right-aligned beside the bar
        worst_label, worst_color = worst_state_label(zones)
        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(worst_color)))
        p.drawText(QRectF(10, bar_y + bar_h + 2, _W - 20, 16),
                   Qt.AlignCenter, worst_label)

        # --- Row 2: Slip (left) | DCCD (right) — below zone bar ---
        row2_base = y0 + 72
        slip_x = 20
        slip_label_y = row2_base

        p.setFont(_font(12, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(slip_x, slip_label_y, 100, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "SLIP \u0394")

        slip_val_y = slip_label_y + 22

        if snap is not None and snap.slip_delta is not None and not stale_wheel:
            slip_val = snap.slip_delta
            slip_color = QColor(_wheel_delta_color(abs(slip_val)))
            p.setFont(_font(40, bold=True))
            p.setPen(QPen(slip_color))
            p.drawText(QRectF(slip_x, slip_val_y, 180, 56),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{slip_val:+.1f}")

            # Unit
            slip_num_w = p.fontMetrics().horizontalAdvance(f"{slip_val:+.1f}")
            p.setFont(_font(14))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(slip_x + slip_num_w + 4, slip_val_y + 10, 60, 30),
                       Qt.AlignLeft | Qt.AlignVCenter, "km/h")
        else:
            p.setFont(_font(40, bold=True))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(slip_x, slip_val_y, 180, 56),
                       Qt.AlignLeft | Qt.AlignVCenter, "---")

        # --- DCCD bar (right, ~580..780) — compact, secondary ---
        dccd_x = 590
        dccd_label_y = row2_base
        dccd_bar_y = row2_base + 24
        dccd_bar_h = 20
        dccd_bar_w = 160

        # Label
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(dccd_x, dccd_label_y, 80, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, "DCCD")

        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(dccd_x, dccd_bar_y, dccd_bar_w, dccd_bar_h), 4, 4)

        if not stale_diff and snap is not None:
            lock_frac = min(snap.dccd_command_pct / 100.0, 1.0)
            if lock_frac > 0.01:
                lock_color = QColor(MODE_I_ACCENT)
                if snap.dccd_command_pct > 80:
                    lock_color = QColor(YELLOW)
                p.setBrush(lock_color)
                p.drawRoundedRect(
                    QRectF(dccd_x, dccd_bar_y,
                           dccd_bar_w * lock_frac, dccd_bar_h), 4, 4)
            pct_text = f"{snap.dccd_command_pct:.0f}%"
            pct_color = QColor(WHITE)
        else:
            pct_text = "---%"
            pct_color = QColor(GRAY)

        # Bar border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(dccd_x, dccd_bar_y, dccd_bar_w, dccd_bar_h), 4, 4)

        # Percentage text — below bar, compact
        p.setFont(_font(14, bold=True))
        p.setPen(QPen(pct_color))
        p.drawText(QRectF(dccd_x, dccd_bar_y + dccd_bar_h + 4, dccd_bar_w, 22),
                   Qt.AlignLeft | Qt.AlignVCenter, pct_text)

        # --- Row 3: ABS | VDC ---
        row2_y = row2_base + 68

        # ABS indicator (left)
        abs_x = 24
        abs_dot_y = row2_y + 14
        if not stale_diff and snap is not None and snap.abs_active:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(RED))
            p.drawEllipse(QPointF(abs_x, abs_dot_y), 6, 6)
            p.setFont(_font(14, bold=True))
            p.setPen(QPen(QColor(RED)))
            p.drawText(abs_x + 12, int(abs_dot_y) + 5, "ABS")
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(DIM))
            p.drawEllipse(QPointF(abs_x, abs_dot_y), 4, 4)
            p.setFont(_font(11))
            p.setPen(QPen(QColor(DIM)))
            p.drawText(abs_x + 10, int(abs_dot_y) + 4, "ABS")

        # VDC/TC indicator (right of ABS)
        vdc_x = 100
        vdc_dot_y = row2_y + 14
        if not stale_diff and snap is not None and snap.vdc_tc:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(YELLOW))
            p.drawEllipse(QPointF(vdc_x, vdc_dot_y), 6, 6)
            p.setFont(_font(14, bold=True))
            p.setPen(QPen(QColor(YELLOW)))
            p.drawText(vdc_x + 12, int(vdc_dot_y) + 5, "VDC")
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(DIM))
            p.drawEllipse(QPointF(vdc_x, vdc_dot_y), 4, 4)
            p.setFont(_font(11))
            p.setPen(QPen(QColor(DIM)))
            p.drawText(vdc_x + 10, int(vdc_dot_y) + 4, "VDC")

        # --- GPS altitude + satellite count (lower-right) ---
        gps_stale = snap is None or snap.is_gps_stale()
        gps_x = 580
        gps_y = row2_y + 4

        # Elevation
        p.setFont(_font(11, bold=True))
        if gps_stale:
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(gps_x, gps_y, 170, 18),
                       Qt.AlignRight | Qt.AlignVCenter, "ELEV ---")
        else:
            p.setPen(QPen(QColor(WHITE)))
            p.drawText(QRectF(gps_x, gps_y, 170, 18),
                       Qt.AlignRight | Qt.AlignVCenter,
                       f"ELEV {snap.gps_altitude_m:.0f} m")

        # Satellite count with status dot
        sat_y = gps_y + 20
        if gps_stale:
            sat_text = "--- SAT"
            dot_color = QColor(GRAY)
        else:
            sat_text = f"{snap.gps_satellites} SAT"
            dot_color = QColor(GREEN) if snap.gps_satellites >= 6 else QColor(GRAY)

        # Dot
        p.setPen(Qt.NoPen)
        p.setBrush(dot_color)
        p.drawEllipse(QPointF(gps_x + 126, sat_y + 9), 5, 5)

        # Text
        p.setFont(_font(11))
        p.setPen(QPen(QColor(WHITE) if not gps_stale else QColor(GRAY)))
        p.drawText(QRectF(gps_x, sat_y, 120, 18),
                   Qt.AlignRight | Qt.AlignVCenter, sat_text)

        # --- Mini G-dot (no trail) ---
        g_cx = 720.0
        g_cy = row2_y + 2
        paint_g_ellipse(p, g_cx, g_cy, 40, snap, deque(), max_trail_dots=0)

    # ==================================================================
    # VOICE TICKER (y=448..478, left side)
    # ==================================================================

    def _draw_coaching_bar(self, p: QPainter) -> None:
        """Coaching/warning text above info line (y=448..466)."""
        if not self._coaching_text:
            return
        sentiment_colors = {"green": GREEN, "amber": YELLOW, "dim": GRAY}
        coach_color = QColor(sentiment_colors.get(self._coaching_sentiment, GRAY))
        p.fillRect(QRectF(0, 448, _W, 18), QColor(BG_PANEL))
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(coach_color))
        p.drawText(QRectF(20, 448, _W - 40, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, self._coaching_text)

    def _draw_info_line(self, p: QPainter) -> None:
        """INFO LINE at bottom — matches MXG Strada placement (y=466..480).

        Alerts are shown in the FLIR banner above. This line shows
        supplementary status only (pressure rate, or dim placeholder).
        """
        snap = self._snap
        text = ""
        if snap is not None and snap.weather_threat_level == "CLEAR":
            rate = snap.pressure_trend_hpa_hr
            if abs(rate) > 0.3:
                text = f"Pressure {rate:+.1f} hPa/hr"

        p.fillRect(QRectF(0, 466, _W, 14), QColor(BG_PANEL))
        if text:
            p.setFont(_font(8))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, 466, _W, 14),
                       Qt.AlignCenter, text)
        else:
            p.setFont(_font(8))
            p.setPen(QPen(QColor(DIM)))
            p.drawText(QRectF(0, 466, _W, 14),
                       Qt.AlignCenter, "INFO LINE")

    def _paint_voice_ticker(self, p: QPainter) -> None:
        """Voice ticker — sits above coaching bar (y=412..455)."""
        if not self._voice_ticker:
            return
        p.setFont(_font(10))
        alphas = [120, 70, 40]
        x, y0, w = 20, 415, 380
        for i, line in enumerate(self._voice_ticker[:3]):
            color = QColor(WHITE)
            color.setAlpha(alphas[min(i, 2)])
            p.setPen(QPen(color))
            elided = p.fontMetrics().elidedText(line, Qt.ElideRight, w)
            p.drawText(QRectF(x, y0 + i * 14, w, 14),
                       Qt.AlignLeft | Qt.AlignVCenter, elided)
