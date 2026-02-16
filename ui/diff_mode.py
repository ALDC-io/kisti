"""KiSTI - DIFF Mode Widget (Visual Redesign)

Center differential telemetry tab for MapDCCD-equipped 2014 STI.
Driver-intuitive visual layout: car silhouette with torque-glowing wheels,
arc gauge for lock %, split bar for F/R torque distribution, compact
sparklines, and event dots.

Layout (800 × ~380px content area):
┌──────────────────────────────────────────────────────────────────┐
│ ● DRY  ● CAN OK                         3   142 km/h           │ 24px
├─────────────────────────────────┬────────────────────────────────┤
│                                 │         LOCK                   │
│     ┌───┐         ┌───┐        │    ╭─────────────╮             │
│     │FL │         │FR │        │   ╱  GREEN→RED    ╲            │
│     └───┘         └───┘        │  │    arc gauge    │           │
│       ╔═══════════╗            │  │                 │    ~250px │
│       ║    STI    ║            │   ╲    62  %      ╱            │
│       ║ silhouette║            │    ╰─────────────╯             │
│       ╚═══════════╝            │       DIAL 45%                 │
│     ┌───┐         ┌───┐        │                                │
│     │RL │(glow)   │RR │(glow) │  [F ██41██░░59██R] split bar   │
│     └───┘         └───┘        │                                │
├─────────────────────────────────┴────────────────────────────────┤
│ LOCK▁▃▇  SLIP▁▅▃  THR▃▇▅    ●●●●   [MARK]                     │ ~80px
└──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from can.can_config import STALE_TIMEOUT_S, UI_REFRESH_MS
from model.vehicle_state import DiffState, DiffStateBridge, SurfaceState
from ui.theme import (
    BG_ACCENT,
    BG_DARK,
    BG_PANEL,
    CHERRY,
    CHROME_DARK,
    CHROME_MID,
    CYAN,
    DIM,
    GRAY,
    GREEN,
    HIGHLIGHT,
    RED,
    SILVER,
    WHITE,
    YELLOW,
)
from ui.widgets.diff_sparkline import DiffSparkline

# Log directory
LOG_DIR = Path.home() / "kisti" / "logs"


# ---------------------------------------------------------------------------
# _SlimStatusBar — 24px top bar
# ---------------------------------------------------------------------------

class _SlimStatusBar(QWidget):
    """Surface dot+word, CAN status dot+word, gear (big), speed + unit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self._surface = SurfaceState.DRY
        self._stale = True
        self._can_connected = False
        self._gear = 0
        self._speed = 0.0

    def set_state(
        self,
        surface: SurfaceState,
        stale: bool,
        can_connected: bool,
        gear: int,
        speed: float,
    ) -> None:
        self._surface = surface
        self._stale = stale
        self._can_connected = can_connected
        self._gear = gear
        self._speed = speed
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_PANEL))

        # Bottom border
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, h - 1, w, h - 1)

        cy = h // 2

        # -- Surface dot + label (left) --
        surface_color = QColor(self._surface.color)
        p.setPen(Qt.NoPen)
        p.setBrush(surface_color)
        p.drawEllipse(8, cy - 4, 8, 8)

        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.setPen(QPen(surface_color))
        p.drawText(QRectF(20, 0, 70, h), Qt.AlignVCenter | Qt.AlignLeft,
                   self._surface.label)

        # -- CAN status dot + label --
        if self._stale:
            dot_color = QColor(RED)
            status_text = "STALE"
        elif self._can_connected:
            dot_color = QColor(GREEN)
            status_text = "CAN OK"
        else:
            dot_color = QColor(YELLOW)
            status_text = "MOCK"

        can_x = 100
        p.setPen(Qt.NoPen)
        p.setBrush(dot_color)
        p.drawEllipse(can_x, cy - 4, 8, 8)

        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(SILVER)))
        p.drawText(QRectF(can_x + 12, 0, 60, h),
                   Qt.AlignVCenter | Qt.AlignLeft, status_text)

        # -- Gear (right side, large) --
        gear_text = str(self._gear) if self._gear > 0 else "N"
        p.setFont(QFont("Helvetica", 18, QFont.Bold))
        text_color = QColor(GRAY) if self._stale else QColor(WHITE)
        p.setPen(QPen(text_color))
        p.drawText(QRectF(w - 160, 0, 30, h),
                   Qt.AlignVCenter | Qt.AlignRight, gear_text)

        # -- Speed + unit --
        speed_text = f"{self._speed:.0f}" if not self._stale else "---"
        p.setFont(QFont("Helvetica", 13, QFont.Bold))
        p.setPen(QPen(text_color))
        p.drawText(QRectF(w - 120, 0, 60, h),
                   Qt.AlignVCenter | Qt.AlignRight, speed_text)

        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(w - 55, 0, 50, h),
                   Qt.AlignVCenter | Qt.AlignLeft, "km/h")

        p.end()


# ---------------------------------------------------------------------------
# _TorqueSilhouette — STI body with glowing wheels
# ---------------------------------------------------------------------------

class _TorqueSilhouette(QWidget):
    """Top-down STI body outline with CYAN-glowing wheels based on torque."""

    # Wheel center positions (normalized to car bbox)
    _WHEEL_CENTERS = {
        "FL": (0.11, 0.16),
        "FR": (0.89, 0.16),
        "RL": (0.11, 0.74),
        "RR": (0.89, 0.74),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lock_pct = 0.0       # 0-100
        self._throttle_pct = 0.0   # 0-100
        self._slip_delta: Optional[float] = None
        self._stale = True
        self._tick = 0  # for pulse animation

    def set_state(
        self,
        lock_pct: float,
        throttle_pct: float,
        slip_delta: Optional[float],
        stale: bool,
    ) -> None:
        self._lock_pct = lock_pct
        self._throttle_pct = throttle_pct
        self._slip_delta = slip_delta
        self._stale = stale
        self._tick += 1
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Calculate car dimensions — centered, padded
        pad = 8
        avail_w = w - 2 * pad
        avail_h = h - 2 * pad
        car_aspect = 2.3  # height/width ratio for hatchback

        if avail_h / max(avail_w, 1) > car_aspect:
            car_w = avail_w
            car_h = car_w * car_aspect
        else:
            car_h = avail_h
            car_w = car_h / car_aspect

        cx = (w - car_w) / 2
        cy = (h - car_h) / 2

        # Draw car body outline
        self._draw_body(p, cx, cy, car_w, car_h)

        # Draw wheels with torque glow
        self._draw_wheels(p, cx, cy, car_w, car_h)

        p.end()

    def _draw_body(self, p: QPainter, cx: float, cy: float, cw: float, ch: float) -> None:
        """Draw 2014 STI hatchback top-down silhouette (from sti_heatmap_widget)."""
        body = QPainterPath()

        # Front bumper
        body.moveTo(cx + cw * 0.25, cy + ch * 0.02)
        body.quadTo(cx + cw * 0.5, cy - cw * 0.03,
                    cx + cw * 0.75, cy + ch * 0.02)

        # Right side — front fender flare
        body.lineTo(cx + cw * 0.82, cy + ch * 0.05)
        body.quadTo(cx + cw * 0.90, cy + ch * 0.10,
                    cx + cw * 0.87, cy + ch * 0.20)

        # Right side — door/B-pillar pinch
        body.quadTo(cx + cw * 0.83, cy + ch * 0.30,
                    cx + cw * 0.81, cy + ch * 0.42)

        # Right side — rear quarter panel flare
        body.quadTo(cx + cw * 0.83, cy + ch * 0.55,
                    cx + cw * 0.90, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.92, cy + ch * 0.72,
                    cx + cw * 0.88, cy + ch * 0.80)

        # Rear — hatchback squared-off tail
        body.lineTo(cx + cw * 0.84, cy + ch * 0.90)
        body.quadTo(cx + cw * 0.78, cy + ch * 0.95,
                    cx + cw * 0.5, cy + ch * 0.96)
        body.quadTo(cx + cw * 0.22, cy + ch * 0.95,
                    cx + cw * 0.16, cy + ch * 0.90)

        # Left side — rear fender flare
        body.lineTo(cx + cw * 0.12, cy + ch * 0.80)
        body.quadTo(cx + cw * 0.08, cy + ch * 0.72,
                    cx + cw * 0.10, cy + ch * 0.65)
        body.quadTo(cx + cw * 0.17, cy + ch * 0.55,
                    cx + cw * 0.19, cy + ch * 0.42)

        # Left side — door/B-pillar pinch
        body.quadTo(cx + cw * 0.17, cy + ch * 0.30,
                    cx + cw * 0.13, cy + ch * 0.20)

        # Left side — front fender flare
        body.quadTo(cx + cw * 0.10, cy + ch * 0.10,
                    cx + cw * 0.18, cy + ch * 0.05)

        body.closeSubpath()

        # Fill body dark
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(15, 15, 15, 160))
        p.drawPath(body)

        # Body outline — chrome
        p.setPen(QPen(QColor(CHROME_MID), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(body)

        # Interior details — windshield
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(int(cx + cw * 0.24), int(cy + ch * 0.20),
                   int(cx + cw * 0.30), int(cy + ch * 0.30))
        p.drawLine(int(cx + cw * 0.76), int(cy + ch * 0.20),
                   int(cx + cw * 0.70), int(cy + ch * 0.30))
        p.drawLine(int(cx + cw * 0.30), int(cy + ch * 0.30),
                   int(cx + cw * 0.70), int(cy + ch * 0.30))

        # Rear hatch window
        p.drawLine(int(cx + cw * 0.30), int(cy + ch * 0.68),
                   int(cx + cw * 0.32), int(cy + ch * 0.80))
        p.drawLine(int(cx + cw * 0.70), int(cy + ch * 0.68),
                   int(cx + cw * 0.68), int(cy + ch * 0.80))
        p.drawLine(int(cx + cw * 0.32), int(cy + ch * 0.80),
                   int(cx + cw * 0.68), int(cy + ch * 0.80))

        # Hood scoop
        scoop = QPainterPath()
        scoop.moveTo(cx + cw * 0.42, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.58, cy + ch * 0.06)
        scoop.lineTo(cx + cw * 0.56, cy + ch * 0.17)
        scoop.lineTo(cx + cw * 0.44, cy + ch * 0.17)
        scoop.closeSubpath()
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(QColor(20, 20, 20))
        p.drawPath(scoop)

        # Center line
        p.setPen(QPen(QColor(DIM), 0.5, Qt.DotLine))
        p.drawLine(int(cx + cw * 0.5), int(cy + ch * 0.02),
                   int(cx + cw * 0.5), int(cy + ch * 0.96))

    def _draw_wheels(self, p: QPainter, cx: float, cy: float, cw: float, ch: float) -> None:
        """Draw wheels with torque-glow based on DCCD state."""
        wheel_w = cw * 0.14
        wheel_h = cw * 0.26

        lock_frac = self._lock_pct / 100.0  # 0..1
        throttle_frac = self._throttle_pct / 100.0  # 0..1

        # Front fraction: 41% open → 50% locked
        front_frac = 0.41 + lock_frac * 0.09
        rear_frac = 1.0 - front_frac

        # Scale glow intensity by throttle
        front_intensity = front_frac * throttle_frac
        rear_intensity = rear_frac * throttle_frac

        abs_slip = abs(self._slip_delta) if self._slip_delta is not None else 0.0

        for name, (wcx_n, wcy_n) in self._WHEEL_CENTERS.items():
            wx = cx + wcx_n * cw - wheel_w / 2
            wy = cy + wcy_n * ch - wheel_h / 2
            center = QPointF(cx + wcx_n * cw, cy + wcy_n * ch)

            is_front = name.startswith("F")
            intensity = front_intensity if is_front else rear_intensity

            # Determine wheel color based on slip
            if self._stale:
                glow_color = QColor(DIM)
                outline_color = QColor(DIM)
            elif abs_slip > 5.0:
                # Hard slip: RED + 4Hz pulse
                pulse = 0.5 + 0.5 * math.sin(self._tick * 0.63)  # ~4Hz at 20Hz refresh
                glow_color = QColor(RED)
                glow_color.setAlphaF(0.4 + 0.6 * pulse)
                outline_color = QColor(RED)
            elif abs_slip > 2.0:
                # Mild slip: YELLOW
                glow_color = QColor(YELLOW)
                glow_color.setAlphaF(0.6)
                outline_color = QColor(YELLOW)
            else:
                # Normal: CYAN torque glow
                glow_color = QColor(CYAN)
                glow_color.setAlphaF(max(0.15, min(0.9, intensity)))
                outline_color = QColor(CYAN)

            # Radial glow behind wheel
            if not self._stale and intensity > 0.05:
                glow_radius = max(wheel_w, wheel_h) * 0.9
                grad = QRadialGradient(center, glow_radius)
                gc = QColor(glow_color)
                gc.setAlphaF(min(0.7, glow_color.alphaF()))
                grad.setColorAt(0.0, gc)
                mid = QColor(glow_color)
                mid.setAlphaF(gc.alphaF() * 0.4)
                grad.setColorAt(0.5, mid)
                fade = QColor(glow_color)
                fade.setAlphaF(0.0)
                grad.setColorAt(1.0, fade)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(grad))
                p.drawEllipse(center, glow_radius, glow_radius)

            # Wheel rectangle
            rect = QRectF(wx, wy, wheel_w, wheel_h)
            p.setPen(QPen(outline_color, 1.5))
            p.setBrush(QColor(0, 0, 0, 80))
            p.drawRoundedRect(rect, 3, 3)

            # Wheel label
            p.setFont(QFont("Helvetica", 7, QFont.Bold))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(rect, Qt.AlignCenter, name)


# ---------------------------------------------------------------------------
# _LockArcGauge — semicircular arc gauge for lock %
# ---------------------------------------------------------------------------

class _LockArcGauge(QWidget):
    """Semi-circular arc gauge (210°→330°) with GREEN→YELLOW→RED fill."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lock_pct = 0.0
        self._dial_pct: Optional[float] = None
        self._stale = True

    def set_state(self, lock_pct: float, dial_pct: Optional[float], stale: bool) -> None:
        self._lock_pct = lock_pct
        self._dial_pct = dial_pct
        self._stale = stale
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # "LOCK" label at top
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(0, 2, w, 16), Qt.AlignHCenter | Qt.AlignTop, "LOCK")

        # Arc geometry — centered in widget
        arc_top = 20
        arc_size = min(w - 16, h - 56)  # leave room for labels
        arc_rect = QRectF((w - arc_size) / 2, arc_top, arc_size, arc_size)

        # Arc spans from 210° to 330° (sweeping 120° total through bottom)
        # Qt angles: 0=3 o'clock, positive=CCW
        # We want a gauge from ~7 o'clock to ~5 o'clock (bottom arc, 240° sweep)
        start_angle = 210 * 16  # Qt uses 1/16th degree units
        span_angle = 120 * 16

        # Background arc (dim track)
        pen_width = 10
        p.setPen(QPen(QColor(DIM), pen_width, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(arc_rect, start_angle, span_angle)

        if not self._stale:
            # Filled arc — proportion of lock
            frac = min(1.0, max(0.0, self._lock_pct / 100.0))
            fill_span = int(span_angle * frac)

            if fill_span > 0:
                # Color based on lock %
                if self._lock_pct < 40:
                    arc_color = QColor(GREEN)
                elif self._lock_pct < 70:
                    # Interpolate GREEN→YELLOW
                    t = (self._lock_pct - 40) / 30.0
                    arc_color = QColor(
                        int(0x00 + t * (0xFF - 0x00)),
                        int(0xCC + t * (0xAA - 0xCC)),
                        int(0x66 + t * (0x00 - 0x66)),
                    )
                else:
                    # Interpolate YELLOW→RED
                    t = min(1.0, (self._lock_pct - 70) / 30.0)
                    arc_color = QColor(
                        int(0xFF),
                        int(0xAA * (1 - t) + 0x1A * t),
                        int(0x00),
                    )

                p.setPen(QPen(arc_color, pen_width, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(arc_rect, start_angle, fill_span)

                # Needle dot at tip of filled arc
                angle_deg = 210 + 120 * frac
                angle_rad = math.radians(angle_deg)
                dot_r = arc_size / 2
                dot_cx = arc_rect.center().x() + dot_r * math.cos(angle_rad)
                dot_cy = arc_rect.center().y() - dot_r * math.sin(angle_rad)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(WHITE))
                p.drawEllipse(QPointF(dot_cx, dot_cy), 4, 4)

            # Center value text
            p.setFont(QFont("Helvetica", 28, QFont.Bold))
            p.setPen(QPen(QColor(WHITE)))
            val_text = f"{self._lock_pct:.0f}"
            fm = p.fontMetrics()
            text_h = fm.height()
            center_y = arc_rect.center().y() - text_h / 2
            p.drawText(QRectF(0, center_y, w, text_h),
                       Qt.AlignHCenter | Qt.AlignVCenter, val_text)

            # "%" unit — positioned just right of the number
            num_w = fm.horizontalAdvance(val_text)
            pct_x = w / 2 + num_w / 2 + 2
            p.setFont(QFont("Helvetica", 14))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(pct_x, center_y + 4, 30, text_h),
                       Qt.AlignLeft | Qt.AlignVCenter, "%")
        else:
            # Stale — show dash
            p.setFont(QFont("Helvetica", 28, QFont.Bold))
            p.setPen(QPen(QColor(GRAY)))
            text_h = p.fontMetrics().height()
            center_y = arc_rect.center().y() - text_h / 2
            p.drawText(QRectF(0, center_y, w, text_h),
                       Qt.AlignHCenter | Qt.AlignVCenter, "\u2014")

        # DIAL value below arc
        dial_y = arc_rect.bottom() + 4
        p.setFont(QFont("Helvetica", 9))
        p.setPen(QPen(QColor(GRAY)))
        if self._dial_pct is not None and not self._stale:
            dial_text = f"DIAL {self._dial_pct:.0f}%"
        else:
            dial_text = "DIAL \u2014"
        p.drawText(QRectF(0, dial_y, w, 18), Qt.AlignHCenter | Qt.AlignTop, dial_text)

        p.end()


# ---------------------------------------------------------------------------
# _SplitBar — horizontal front/rear torque split bar
# ---------------------------------------------------------------------------

class _SplitBar(QWidget):
    """Horizontal bar showing F/R torque distribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(30)
        self._front_pct = 41.0  # default open diff split
        self._lock_pct = 0.0    # 0=open, 100=locked
        self._stale = True

    def set_state(self, front_pct: float, lock_pct: float, stale: bool) -> None:
        self._front_pct = front_pct
        self._lock_pct = lock_pct
        self._stale = stale
        self.update()

    def _bar_color(self) -> QColor:
        """GREEN (open) → teal → BLUE (locked) based on lock %."""
        t = min(1.0, max(0.0, self._lock_pct / 100.0))
        # GREEN #00CC66 → CYAN #00CCFF → BLUE #0077DD
        if t < 0.5:
            s = t * 2.0
            r = 0
            g = 0xCC
            b = int(0x66 + s * (0xFF - 0x66))
        else:
            s = (t - 0.5) * 2.0
            r = 0
            g = int(0xCC - s * (0xCC - 0x77))
            b = int(0xFF - s * (0xFF - 0xDD))
        return QColor(r, g, b)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        label_h = 14
        margin_y = 4
        bar_x = 4
        bar_w = w - 8
        bar_y = margin_y + label_h + 2
        bar_h = h - 2 * margin_y - 2 * label_h - 4

        # "F" label top
        p.setFont(QFont("Helvetica", 8, QFont.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(0, margin_y, w, label_h),
                   Qt.AlignHCenter | Qt.AlignCenter, "F")

        # "R" label bottom
        p.drawText(QRectF(0, h - margin_y - label_h, w, label_h),
                   Qt.AlignHCenter | Qt.AlignCenter, "R")

        # Bar background
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.setBrush(QColor(BG_PANEL))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        if not self._stale:
            frac = min(1.0, max(0.0, self._front_pct / 100.0))
            front_h = bar_h * frac
            bar_color = self._bar_color()

            # Front fill (top part) — dimmer (less torque)
            if front_h > 1:
                p.setPen(Qt.NoPen)
                fill_color = QColor(bar_color)
                fill_color.setAlphaF(0.25)
                p.setBrush(fill_color)
                p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, front_h), 3, 3)

            # Rear fill (bottom part) — brighter (more torque)
            rear_h = bar_h - front_h
            if rear_h > 1:
                p.setPen(Qt.NoPen)
                rear_color = QColor(bar_color)
                rear_color.setAlphaF(0.65)
                p.setBrush(rear_color)
                p.drawRoundedRect(QRectF(bar_x, bar_y + front_h, bar_w, rear_h), 3, 3)

            # 50% center marker
            center_y = bar_y + bar_h * 0.5
            p.setPen(QPen(QColor(WHITE), 1, Qt.DashLine))
            p.drawLine(QPointF(bar_x + 1, center_y),
                       QPointF(bar_x + bar_w - 1, center_y))

            # Split text — front % above center, rear % below
            p.setFont(QFont("Helvetica", 7, QFont.Bold))
            p.setPen(QPen(QColor(WHITE)))
            rear_pct = 100.0 - self._front_pct
            p.drawText(QRectF(0, center_y - 14, w, 12),
                       Qt.AlignHCenter | Qt.AlignBottom, f"{self._front_pct:.0f}")
            p.drawText(QRectF(0, center_y + 2, w, 12),
                       Qt.AlignHCenter | Qt.AlignTop, f"{rear_pct:.0f}")

        p.end()


# ---------------------------------------------------------------------------
# _EventDots — 4 colored circles for BRK/HB/ABS/VDC
# ---------------------------------------------------------------------------

class _EventDots(QWidget):
    """Four colored circles indicating event flags."""

    _DOTS = [
        ("BRK", "brake"),
        ("HB", "handbrake"),
        ("ABS", "abs_active"),
        ("VDC", "vdc_tc"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._flags: dict[str, bool] = {k: False for _, k in self._DOTS}

    def set_flags(self, brake: bool, handbrake: bool, abs_active: bool, vdc_tc: bool) -> None:
        self._flags["brake"] = brake
        self._flags["handbrake"] = handbrake
        self._flags["abs_active"] = abs_active
        self._flags["vdc_tc"] = vdc_tc
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        dot_r = 7
        gap = 6
        total_w = len(self._DOTS) * (dot_r * 2 + gap) - gap
        x = (w - total_w) / 2
        cy = h / 2

        for label, key in self._DOTS:
            active = self._flags[key]
            center = QPointF(x + dot_r, cy)

            if active:
                # Glow behind
                glow = QRadialGradient(center, dot_r * 2)
                glow_c = QColor(RED)
                glow_c.setAlphaF(0.4)
                glow.setColorAt(0.0, glow_c)
                fade = QColor(RED)
                fade.setAlphaF(0.0)
                glow.setColorAt(1.0, fade)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(center, dot_r * 2, dot_r * 2)

                # Solid dot
                p.setBrush(QColor(RED))
                p.setPen(Qt.NoPen)
            else:
                p.setBrush(QColor(DIM))
                p.setPen(Qt.NoPen)

            p.drawEllipse(center, dot_r, dot_r)

            # Tiny label below
            p.setFont(QFont("Helvetica", 6))
            p.setPen(QPen(QColor(GRAY) if not active else QColor(WHITE)))
            p.drawText(QRectF(x - 2, cy + dot_r + 1, dot_r * 2 + 4, 10),
                       Qt.AlignHCenter | Qt.AlignTop, label)

            x += dot_r * 2 + gap

        p.end()


# ---------------------------------------------------------------------------
# _BottomStrip — sparklines + event dots + MARK button
# ---------------------------------------------------------------------------

class _BottomStrip(QWidget):
    """Composite: 3 compact sparklines side-by-side + event dots + MARK button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # Sparklines container (vertical stack, compact)
        spark_col = QVBoxLayout()
        spark_col.setContentsMargins(0, 0, 0, 0)
        spark_col.setSpacing(1)

        self.spark_lock = DiffSparkline(
            label="LOCK", color=HIGHLIGHT, min_val=0.0, max_val=100.0,
            compact=True, parent=self,
        )
        self.spark_slip = DiffSparkline(
            label="SLIP", color=CYAN, min_val=-10.0, max_val=10.0,
            show_zero_line=True, compact=True, parent=self,
        )
        self.spark_throttle = DiffSparkline(
            label="THR", color=GREEN, min_val=0.0, max_val=100.0,
            compact=True, parent=self,
        )

        spark_col.addWidget(self.spark_lock)
        spark_col.addWidget(self.spark_slip)
        spark_col.addWidget(self.spark_throttle)

        layout.addLayout(spark_col, stretch=55)

        # Event dots
        self.event_dots = _EventDots(self)
        self.event_dots.setFixedWidth(100)
        layout.addWidget(self.event_dots, stretch=0)

        # MARK button
        self.mark_btn = QPushButton("MARK", self)
        self.mark_btn.setFixedHeight(60)
        self.mark_btn.setMinimumWidth(80)
        self.mark_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_ACCENT};
                color: {SILVER};
                border: 2px solid {CHROME_DARK};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                margin: 2px 4px 2px 4px;
            }}
            QPushButton:pressed {{
                background-color: {CHERRY};
                color: {WHITE};
                border-color: {HIGHLIGHT};
            }}
        """)
        layout.addWidget(self.mark_btn, stretch=0)


# ---------------------------------------------------------------------------
# DiffModeWidget — main tab (public API unchanged)
# ---------------------------------------------------------------------------

class DiffModeWidget(QWidget):
    """Full DIFF tab: center diff telemetry for MapDCCD 2014 STI.

    Requires a DiffStateBridge to be set via set_bridge() before updates
    will display.  Internally runs a 20 Hz QTimer to poll the bridge
    and refresh all sub-widgets.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge: Optional[DiffStateBridge] = None
        self._last_state = DiffState()
        self._mark_flash_until = 0.0

        self._build_ui()
        self._ensure_log_dir()

        # 20 Hz refresh timer (started when bridge is set)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(UI_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh)

    def set_bridge(self, bridge: DiffStateBridge) -> None:
        """Connect to a DiffStateBridge for live data."""
        self._bridge = bridge
        self._refresh_timer.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Slim status bar (24px) --
        self._status_bar = _SlimStatusBar(self)
        root.addWidget(self._status_bar)

        # -- Middle section: silhouette (left) + arc gauge + split bar (right) --
        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(2)

        self._silhouette = _TorqueSilhouette(self)
        mid.addWidget(self._silhouette, stretch=50)

        # Thin vertical separator
        sep = QWidget(self)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {CHROME_DARK};")
        mid.addWidget(sep)

        # Right column: arc gauge + vertical split bar side by side
        right_col = QHBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(2)

        self._arc_gauge = _LockArcGauge(self)
        right_col.addWidget(self._arc_gauge, stretch=1)

        self._split_bar = _SplitBar(self)
        right_col.addWidget(self._split_bar, stretch=0)

        mid.addLayout(right_col, stretch=50)

        root.addLayout(mid, stretch=70)

        # -- Bottom strip (~80px): sparklines + dots + MARK --
        self._bottom = _BottomStrip(self)
        root.addWidget(self._bottom, stretch=30)

        # Wire MARK button
        self._bottom.mark_btn.clicked.connect(self._on_mark)

    def _ensure_log_dir(self) -> None:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # degrade gracefully

    def _refresh(self) -> None:
        """20 Hz timer callback: read bridge snapshot, push to sub-widgets."""
        if self._bridge is None:
            return

        state = self._bridge.snapshot()
        self._last_state = state
        now = time.monotonic()
        stale = state.is_any_stale(now, STALE_TIMEOUT_S)
        diff_stale = state.is_diff_stale(now, STALE_TIMEOUT_S)
        ctx_stale = state.is_context_stale(now, STALE_TIMEOUT_S)

        # Status bar
        self._status_bar.set_state(
            state.surface_state, stale, state.can_connected,
            state.gear, state.speed_kph,
        )

        # Torque silhouette
        self._silhouette.set_state(
            state.dccd_command_pct, state.throttle_pct,
            state.slip_delta, diff_stale,
        )

        # Arc gauge
        self._arc_gauge.set_state(state.dccd_command_pct, state.dccd_dial_pct, diff_stale)

        # Split bar — front % = 41 + lock*0.09
        lock_frac = state.dccd_command_pct / 100.0
        front_pct = (0.41 + lock_frac * 0.09) * 100.0
        self._split_bar.set_state(front_pct, state.dccd_command_pct, diff_stale)

        # Event dots
        self._bottom.event_dots.set_flags(
            state.brake, state.handbrake, state.abs_active, state.vdc_tc,
        )

        # Sparklines — push new sample each tick
        self._bottom.spark_lock.push(state.dccd_command_pct)
        self._bottom.spark_slip.push(
            state.slip_delta if state.slip_delta is not None else 0.0,
        )
        self._bottom.spark_throttle.push(state.throttle_pct)

        # Trigger repaint on sparklines
        self._bottom.spark_lock.update()
        self._bottom.spark_slip.update()
        self._bottom.spark_throttle.update()

        # MARK button flash feedback
        mark_btn = self._bottom.mark_btn
        if now < self._mark_flash_until:
            mark_btn.setText("MARKED")
            mark_btn.setStyleSheet(mark_btn.styleSheet().replace(
                f"background-color: {BG_ACCENT}", f"background-color: {GREEN}"))
        elif mark_btn.text() != "MARK":
            mark_btn.setText("MARK")
            mark_btn.setStyleSheet(mark_btn.styleSheet().replace(
                f"background-color: {GREEN}", f"background-color: {BG_ACCENT}"))

    def _on_mark(self) -> None:
        """Write a JSONL segment marker record and flash the button."""
        state = self._last_state
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "MARK",
            "dccd_command_pct": round(state.dccd_command_pct, 1),
            "dccd_dial_pct": round(state.dccd_dial_pct, 1) if state.dccd_dial_pct is not None else None,
            "surface": state.surface_state.label,
            "gear": state.gear,
            "speed_kph": round(state.speed_kph, 1),
            "throttle_pct": round(state.throttle_pct, 1),
            "slip_delta": round(state.slip_delta, 2) if state.slip_delta is not None else None,
            "brake": state.brake,
            "handbrake": state.handbrake,
            "abs": state.abs_active,
            "vdc_tc": state.vdc_tc,
        }

        try:
            log_file = LOG_DIR / f"marks_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass  # degrade gracefully — don't crash the UI

        # Flash button for 0.6 seconds
        self._mark_flash_until = time.monotonic() + 0.6

    def update_data(self, vehicle_state) -> None:
        """Compatibility shim: called by MainWindow data routing.

        The DIFF tab gets its data from DiffStateBridge, not from
        VehicleState.  This method exists so MainWindow can call it
        uniformly without special-casing.
        """
        pass  # Data comes from the CAN bridge, not mock generator
