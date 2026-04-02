"""KiSTI - Intelligent Mode Screen (SI-Drive = 0)

Calm / street cruising display.  "What are the conditions?"
Big text, readable at arm's length on Kenwood Excelon 800x480.

Full QPainter rendering — no composite QWidget layouts.
Color accent: MODE_I_ACCENT (#00AAFF) blue.

Layout:
  y=0..160    Weather card — BIG temp, humidity, pressure. 3 values only.
  y=160..340  FLIR brake temps — 2x2 grid filling 800px wide + warm-up badge.
  y=340..480  Status strip — DCCD bar + surface badge + slip delta.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap: DiffState | None = None

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
        self.update()  # schedule repaint

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, _W, _H, QColor(BG_DARK))

        # Subtle full-screen tint from road surface FLIR
        snap = self._snap
        if snap is not None and snap.flir_available and not snap.is_flir_stale():
            tint = QColor(_brake_heat_color(snap.brake_temp_fl))
            tint.setAlpha(15)
            p.fillRect(0, 0, _W, _H, tint)

        self._draw_weather(p)
        self._draw_flir_panel(p)
        self._draw_status_strip(p)
        p.end()

    # ==================================================================
    # WEATHER CARD (y=0..160)
    # BIG temperature, humidity, pressure.  Full width.
    # ==================================================================

    def _draw_weather(self, p: QPainter) -> None:
        snap = self._snap
        available = snap is not None and snap.ambient_available

        # Card background (no border — clean edge)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_ACCENT))
        p.drawRoundedRect(QRectF(6, 6, _W - 12, 148), 6, 6)

        # Section label
        p.setFont(_font(12, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(20, 10, 200, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "WEATHER")

        # --- Temperature: BIG center-left ---
        if available:
            temp_text = f"{snap.ambient_temp_c:.1f}"
            temp_color = QColor(WHITE)
        else:
            temp_text = "---"
            temp_color = QColor(GRAY)

        # Large temperature number
        p.setFont(_font(56, bold=True))
        p.setPen(QPen(temp_color))
        p.drawText(QRectF(20, 28, 300, 90),
                   Qt.AlignLeft | Qt.AlignVCenter, temp_text)

        # Degree + C unit to the right of the number
        p.setFont(_font(28, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        # Measure how wide the temp text is at 56pt to position the unit
        metrics = p.fontMetrics()
        p.setFont(_font(56, bold=True))
        temp_width = p.fontMetrics().horizontalAdvance(temp_text)
        p.setFont(_font(28, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(20 + temp_width + 4, 28, 80, 90),
                   Qt.AlignLeft | Qt.AlignTop, "\u00b0C")

        # Small "TEMP" label under the number
        p.setFont(_font(11))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(20, 120, 120, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "TEMPERATURE")

        # --- Humidity: right column, top ---
        hum_x = 440
        hum_y = 32

        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(hum_x, hum_y, 160, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, "HUMIDITY")

        if available:
            hum_text = f"{snap.ambient_humidity_pct:.0f}%"
            hum_color = QColor(WHITE)
        else:
            hum_text = "---"
            hum_color = QColor(GRAY)

        p.setFont(_font(36, bold=True))
        p.setPen(QPen(hum_color))
        p.drawText(QRectF(hum_x, hum_y + 18, 200, 50),
                   Qt.AlignLeft | Qt.AlignVCenter, hum_text)

        # --- Pressure: right column, bottom ---
        prs_y = hum_y + 72

        p.setFont(_font(11, bold=True))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(hum_x, prs_y, 160, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, "PRESSURE")

        if available:
            prs_text = f"{snap.ambient_pressure_hpa:.0f}"
            prs_color = QColor(WHITE)
            prs_unit = " hPa"
        else:
            prs_text = "---"
            prs_color = QColor(GRAY)
            prs_unit = ""

        p.setFont(_font(36, bold=True))
        p.setPen(QPen(prs_color))
        p.drawText(QRectF(hum_x, prs_y + 18, 200, 50),
                   Qt.AlignLeft | Qt.AlignVCenter, prs_text)

        # Unit label for pressure
        if prs_unit:
            prs_num_w = p.fontMetrics().horizontalAdvance(prs_text)
            p.setFont(_font(16))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(hum_x + prs_num_w + 4, prs_y + 18, 80, 50),
                       Qt.AlignLeft | Qt.AlignVCenter, prs_unit)

        # "NO SENSOR" overlay when unavailable
        if not available:
            p.setFont(_font(14))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, 60, _W, 30), Qt.AlignCenter, "NO WEATHER SENSOR")

    # ==================================================================
    # ROAD SURFACE (y=160..340)
    # Forward-facing FLIR (grill-mounted) — road surface temp + warm-up.
    # ==================================================================

    def _draw_flir_panel(self, p: QPainter) -> None:
        snap = self._snap
        stale = snap is None or snap.is_flir_stale()
        flir_ok = snap is not None and snap.flir_available and not stale

        y0 = 160
        panel_h = 180  # y=160..340

        # Section label
        p.setFont(_font(12, bold=True))
        p.setPen(QPen(QColor(MODE_I_ACCENT)))
        p.drawText(QRectF(20, y0 + 4, 200, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "ROAD SURFACE")

        # Warm-up badge (top-right, always shown)
        self._draw_warmup_badge(p, y0)

        if not flir_ok:
            p.setFont(_font(16))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(0, y0 + 60, _W, 40), Qt.AlignCenter,
                       "FLIR NOT CONNECTED")
            return

        # Road surface temp — single large reading from forward FLIR
        # Uses brake_temp_fl as road surface proxy (single camera)
        road_temp = snap.brake_temp_fl
        heat_col = _brake_heat_color(road_temp)

        # Large temperature card — centered
        card_x = 20
        card_y = y0 + 30
        card_w = _W - 40
        card_h = 130

        # Heat-colored background
        bg = QColor(heat_col)
        bg.setAlpha(40)
        p.fillRect(QRectF(card_x, card_y, card_w, card_h), bg)

        # Big temperature — left-aligned to match weather text above
        p.setFont(_font(56, bold=True))
        p.setPen(QPen(heat_col))
        p.drawText(QRectF(20, card_y + 10, 300, 80),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{road_temp:.0f}\u00b0C")

        # "ROAD TEMP" sublabel
        p.setFont(_font(14))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(20, card_y + 90, 200, 24),
                   Qt.AlignLeft | Qt.AlignVCenter, "ROAD TEMPERATURE")

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
    # STATUS STRIP (y=340..480)
    # DCCD bar + Surface badge + Slip delta — one horizontal row.
    # ==================================================================

    def _draw_status_strip(self, p: QPainter) -> None:
        snap = self._snap
        stale_diff = snap is None or snap.is_diff_stale()
        stale_wheel = snap is None or snap.is_wheel_stale()

        y0 = 340
        strip_h = 140  # y=340..480

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
