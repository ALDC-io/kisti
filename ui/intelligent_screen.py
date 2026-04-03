"""KiSTI - Intelligent Mode Screen (SI-Drive = 0)

Calm / street cruising display.  "What are the conditions?"
Big text, readable at arm's length on Kenwood Excelon 800x480.

Full QPainter rendering — no composite QWidget layouts.
Color accent: MODE_I_ACCENT (#00AAFF) blue.

Layout:
  y=0..114    Weather card — compact temp, humidity, pressure.
  y=118..310  FLIR road surface — live IR image (inferno colormap).
  y=316..480  Status strip — DCCD bar + surface badge + slip delta.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
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

        # Force periodic repaint even without data (1 Hz)
        from PySide6.QtCore import QTimer
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(1000)
        self._repaint_timer.timeout.connect(self.update)
        self._repaint_timer.start()

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

    def _on_frame_updated(self, frame) -> None:
        """Receive raw uint16 thermal frame — smooth, enhance contrast, colormap, cache."""
        self._frame_skip += 1
        if self._frame_skip % 3 != 0:
            return  # skip 2 of every 3 frames (~3 Hz effective)
        f32 = frame.astype(np.float32)

        # Temporal smoothing: 70% new + 30% previous → stable thermal zones
        if self._prev_frame is not None and self._prev_frame.shape == f32.shape:
            f32 = 0.7 * f32 + 0.3 * self._prev_frame
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

        # Subtle full-screen tint from road surface FLIR
        snap = self._snap
        if snap is not None and not snap.is_road_surface_stale():
            road_avg = (snap.road_temp_left + snap.road_temp_center + snap.road_temp_right) / 3.0
            tint = QColor(_brake_heat_color(road_avg))
            tint.setAlpha(15)
            p.fillRect(0, 0, _W, _H, tint)

        self._draw_weather(p)
        self._draw_flir_panel(p)
        self._draw_status_strip(p)
        self._paint_voice_ticker(p)
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

        # Section label
        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(20, 6, 200, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "WEATHER")

        # --- Temperature: left ---
        if available:
            temp_text = f"{snap.ambient_temp_c:.1f}"
            temp_color = QColor(WHITE)
        else:
            temp_text = "---"
            temp_color = QColor(GRAY)

        p.setFont(_font(44, bold=True))
        p.setPen(QPen(temp_color))
        p.drawText(QRectF(20, 22, 260, 66),
                   Qt.AlignLeft | Qt.AlignVCenter, temp_text)

        # Degree + C unit
        p.setFont(_font(44, bold=True))
        temp_width = p.fontMetrics().horizontalAdvance(temp_text)
        p.setFont(_font(22, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(20 + temp_width + 4, 22, 60, 66),
                   Qt.AlignLeft | Qt.AlignTop, "\u00b0C")

        # Small "TEMP" label
        p.setFont(_font(10))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(20, 90, 120, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "TEMPERATURE")

        # --- Humidity: right column, top ---
        hum_x = 440
        hum_y = 16

        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(hum_x, hum_y, 160, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "HUMIDITY")

        if available:
            hum_text = f"{snap.ambient_humidity_pct:.0f}%"
            hum_color = QColor(WHITE)
        else:
            hum_text = "---"
            hum_color = QColor(GRAY)

        p.setFont(_font(26, bold=True))
        p.setPen(QPen(hum_color))
        p.drawText(QRectF(hum_x, hum_y + 14, 200, 36),
                   Qt.AlignLeft | Qt.AlignVCenter, hum_text)

        # --- Pressure: right column, bottom ---
        prs_y = hum_y + 52

        p.setFont(_font(10, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(hum_x, prs_y, 160, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, "PRESSURE")

        if available:
            prs_text = f"{snap.ambient_pressure_hpa:.0f}"
            prs_color = QColor(WHITE)
            prs_unit = " hPa"
        else:
            prs_text = "---"
            prs_color = QColor(GRAY)
            prs_unit = ""

        p.setFont(_font(26, bold=True))
        p.setPen(QPen(prs_color))
        p.drawText(QRectF(hum_x, prs_y + 14, 200, 36),
                   Qt.AlignLeft | Qt.AlignVCenter, prs_text)

        # Unit label for pressure
        if prs_unit:
            prs_num_w = p.fontMetrics().horizontalAdvance(prs_text)
            p.setFont(_font(14))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(hum_x + prs_num_w + 4, prs_y + 14, 80, 36),
                       Qt.AlignLeft | Qt.AlignVCenter, prs_unit)

        # "NO SENSOR" overlay when unavailable
        if not available:
            p.setFont(_font(13))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, 40, _W, 30), Qt.AlignCenter, "NO WEATHER SENSOR")

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

        # Coaching text overlay at bottom of panel
        if self._coaching_text:
            sentiment_colors = {"green": GREEN, "amber": YELLOW, "dim": GRAY}
            coach_color = QColor(sentiment_colors.get(self._coaching_sentiment, GRAY))
            # Semi-transparent backing strip
            backing = QColor(0, 0, 0, 120)
            p.fillRect(QRectF(0, y0 + panel_h - 32, _W, 32), backing)
            p.setFont(_font(14, bold=True))
            p.setPen(QPen(coach_color))
            p.drawText(QRectF(20, y0 + panel_h - 30, _W - 40, 24),
                       Qt.AlignLeft | Qt.AlignVCenter, self._coaching_text)

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

        # Layout: Surface (left, primary) | SLIP (center) | DCCD (right, secondary)
        # Answers "What are the conditions?" — surface is #1 for Intelligent mode.

        # --- Surface badge (left, ~0..280) — PRIMARY ---
        surface_x = 20
        surface_y = y0 + 10

        p.setFont(_font(12, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(surface_x, surface_y, 120, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "SURFACE")

        if snap is not None:
            surface_label = snap.surface_state.label
            surface_color = QColor(snap.surface_state.color)
        else:
            surface_label = "---"
            surface_color = QColor(GRAY)

        # Large surface pill
        badge_y = surface_y + 24
        badge_h = 44

        p.setFont(_font(18, bold=True))
        badge_tw = p.fontMetrics().horizontalAdvance(surface_label) + 40
        badge_tw = max(badge_tw, 140)

        # Pill background
        pill_bg = QColor(surface_color)
        pill_bg.setAlphaF(0.25)
        p.setPen(Qt.NoPen)
        p.setBrush(pill_bg)
        p.drawRoundedRect(QRectF(surface_x, badge_y, badge_tw, badge_h), 22, 22)

        # Pill border
        p.setPen(QPen(surface_color, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(surface_x, badge_y, badge_tw, badge_h), 22, 22)

        # Surface text
        p.setFont(_font(20, bold=True))
        p.setPen(QPen(surface_color))
        p.drawText(QRectF(surface_x, badge_y, badge_tw, badge_h),
                   Qt.AlignCenter, surface_label)

        # --- Slip delta (center, ~300..560) ---
        slip_x = 320
        slip_label_y = y0 + 10

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
        dccd_label_y = y0 + 10
        dccd_bar_y = y0 + 34
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

    # ==================================================================
    # VOICE TICKER (y=448..478, left side)
    # ==================================================================

    def _paint_voice_ticker(self, p: QPainter) -> None:
        if not self._voice_ticker:
            return
        p.setFont(_font(11))
        alphas = [120, 70, 40]
        x, y0, w = 20, 448, 380
        for i, line in enumerate(self._voice_ticker):
            color = QColor(WHITE)
            color.setAlpha(alphas[min(i, 2)])
            p.setPen(QPen(color))
            elided = p.fontMetrics().elidedText(line, Qt.ElideRight, w)
            p.drawText(QRectF(x, y0 + i * 15, w, 15),
                       Qt.AlignLeft | Qt.AlignVCenter, elided)
