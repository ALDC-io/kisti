"""KiSTI — Sport Sharp Screen (SI Drive Sport Sharp / Race Engineer)

Dark cockpit philosophy: normal = invisible. Only deviations from optimal
are shown. Minimal HUD with friction ellipse, grip mini-bar, sector brake
quality dots, and safety vitals that dim when normal.

Layout (800 × ~380px content area):
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    Friction Ellipse                               │
│                    (radius=80, 10 trail, MODE_SS_ACCENT)         │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ GRIP [F ████ R ████]  ●●●●●●  OIL 72°  CLT 88°  BAT 14.1      │
│              grip bar    sector brake quality    dark cockpit     │
└──────────────────────────────────────────────────────────────────┘

ADR-1: Paint functions, not QWidgets.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen,
)
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState, DiffStateBridge
from ui.theme import (
    BG_DARK, BG_PANEL, CHROME_DARK, CYAN, DIM, GRAY,
    GREEN, HIGHLIGHT, RED, SILVER, WHITE, YELLOW,
)
from ui.g_force_ellipse import paint_g_ellipse

# Sport Sharp accent (red — maximum attack)
MODE_SS_ACCENT = "#FF0000"


class SharpScreen(QWidget):
    """Sport Sharp mode HUD — dark cockpit, deviations only.

    Fed by coaching timer at 1Hz:
      - update_balance(ratio)
      - update_grip(front_pct, rear_pct)
      - update_sector_brake_quality(dots)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge: Optional[DiffStateBridge] = None
        self._snap: Optional[DiffState] = None

        # G-trail (smaller for sharp screen)
        self._g_trail: list[tuple[float, float]] = []
        self._max_trail = 10

        # Coaching state
        self._balance_ratio: float = 1.0
        self._front_grip_pct: float = 100.0
        self._rear_grip_pct: float = 100.0

        # Sector brake quality dots (green/yellow/red per sector)
        self._sector_dots: list[str] = []  # List of color hex strings

    def set_bridge(self, bridge: DiffStateBridge) -> None:
        self._bridge = bridge

    def update_data(self, snap: DiffState) -> None:
        self._snap = snap
        lat_g = snap.lateral_g
        lon_g = snap.imu_accel_x
        self._g_trail.append((lat_g, lon_g))
        if len(self._g_trail) > self._max_trail:
            self._g_trail = self._g_trail[-self._max_trail:]
        self.update()

    def update_balance(self, ratio: float) -> None:
        self._balance_ratio = ratio

    def update_grip(self, front_pct: float, rear_pct: float) -> None:
        self._front_grip_pct = front_pct
        self._rear_grip_pct = rear_pct

    def update_sector_brake_quality(self, dots: list[str]) -> None:
        """Update sector brake quality dots (list of color hex strings)."""
        self._sector_dots = dots

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        snap = self._snap

        # --- Center: Friction ellipse (dominant visual) ---
        ellipse_cx = w // 2
        ellipse_cy = (h - 60) // 2  # Leave 60px for bottom bar
        ellipse_r = min(80, (h - 80) // 2 - 10)
        if snap:
            paint_g_ellipse(
                p, ellipse_cx, ellipse_cy, ellipse_r,
                snap, self._g_trail, self._balance_ratio,
                max_trail_dots=self._max_trail,
                accent_color=MODE_SS_ACCENT,
            )
        else:
            p.setPen(QPen(QColor(DIM), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(ellipse_cx, ellipse_cy), ellipse_r, ellipse_r)

        # --- Bottom bar (60px) ---
        bar_y = h - 55
        p.fillRect(0, bar_y - 2, w, 57, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, bar_y - 2, w, bar_y - 2)

        # GRIP mini-bar: 3-zone color bar (front + rear)
        self._paint_grip_bar(p, 10, bar_y, snap)

        # Sector brake quality dots
        self._paint_sector_dots(p, 280, bar_y + 4)

        # Dark cockpit safety vitals (dim when normal)
        if snap:
            self._paint_dark_vitals(p, w, bar_y, snap)

        p.end()

    def _paint_grip_bar(self, p: QPainter, x: int, y: int,
                        snap: Optional[DiffState]) -> None:
        """Compact front/rear grip bar."""
        p.setFont(QFont("Helvetica", 8, QFont.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(x, y + 12, "GRIP")

        bar_x = x + 36
        bar_w = 80
        bar_h = 8

        # Front
        p.setFont(QFont("Helvetica", 7))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(bar_x, y + 10, "F")
        p.fillRect(bar_x + 10, y + 3, bar_w, bar_h, QColor(DIM))
        fill_w = int(bar_w * self._front_grip_pct / 100.0)
        if fill_w > 0:
            p.fillRect(bar_x + 10, y + 3, fill_w, bar_h,
                       self._grip_color(self._front_grip_pct))

        # Rear
        rear_x = bar_x + bar_w + 20
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(rear_x, y + 10, "R")
        p.fillRect(rear_x + 10, y + 3, bar_w, bar_h, QColor(DIM))
        fill_w = int(bar_w * self._rear_grip_pct / 100.0)
        if fill_w > 0:
            p.fillRect(rear_x + 10, y + 3, fill_w, bar_h,
                       self._grip_color(self._rear_grip_pct))

        # Second row: percentage values
        p.setFont(QFont("Helvetica", 7))
        p.setPen(QPen(self._grip_color(self._front_grip_pct)))
        p.drawText(bar_x + 10, y + 24, f"{self._front_grip_pct:.0f}%")
        p.setPen(QPen(self._grip_color(self._rear_grip_pct)))
        p.drawText(rear_x + 10, y + 24, f"{self._rear_grip_pct:.0f}%")

    def _paint_sector_dots(self, p: QPainter, x: int, y: int) -> None:
        """Sector brake quality dots — one per completed sector."""
        if not self._sector_dots:
            # Placeholder: show empty circles
            p.setFont(QFont("Helvetica", 7))
            p.setPen(QPen(QColor(DIM)))
            p.drawText(x, y + 8, "BRAKE")
            for i in range(6):
                p.setPen(QPen(QColor(DIM), 1))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(x + 40 + i * 14, y + 2, 8, 8)
            return

        p.setFont(QFont("Helvetica", 7))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(x, y + 8, "BRAKE")
        for i, color_hex in enumerate(self._sector_dots[-8:]):  # Show last 8
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color_hex))
            p.drawEllipse(x + 40 + i * 14, y + 2, 8, 8)

    def _paint_dark_vitals(self, p: QPainter, w: int, y: int,
                           snap: DiffState) -> None:
        """Safety vitals — dim gray when normal, bright when abnormal."""
        vitals = []

        # Oil temp (normal: 70-110°C)
        oil_t = snap.oil_temp_c
        if oil_t > 0:
            oil_color = QColor(RED) if oil_t > 120 else (
                QColor(YELLOW) if oil_t > 110 else QColor(DIM))
            vitals.append(("OIL", f"{oil_t:.0f}°", oil_color))

        # Coolant temp (normal: 80-100°C)
        clt = snap.coolant_temp
        if clt > 0:
            clt_color = QColor(RED) if clt > 105 else (
                QColor(YELLOW) if clt > 100 else QColor(DIM))
            vitals.append(("CLT", f"{clt:.0f}°", clt_color))

        # Battery (normal: 13.5-14.5V)
        bat = snap.battery_v
        if bat > 0:
            bat_color = QColor(RED) if bat < 12.0 else (
                QColor(YELLOW) if bat < 13.0 else QColor(DIM))
            vitals.append(("BAT", f"{bat:.1f}", bat_color))

        # Oil pressure (warn below 15 PSI at speed)
        oil_p = snap.oil_psi
        if oil_p > 0:
            op_color = QColor(RED) if oil_p < 15 and snap.speed_kph > 30 else QColor(DIM)
            vitals.append(("PSI", f"{oil_p:.0f}", op_color))

        # Paint right-aligned
        vx = w - 20
        p.setFont(QFont("Helvetica", 8))
        for label, val, color in reversed(vitals):
            val_w = len(val) * 7 + 4
            label_w = len(label) * 6 + 4

            p.setPen(QPen(color))
            p.drawText(int(vx - val_w), y + 12, val)
            vx -= val_w

            # Label is always dim
            p.setPen(QPen(QColor(DIM)))
            p.drawText(int(vx - label_w), y + 12, label)
            vx -= label_w + 10

    @staticmethod
    def _grip_color(pct: float) -> QColor:
        if pct >= 90.0:
            return QColor(GREEN)
        elif pct >= 80.0:
            return QColor(YELLOW)
        return QColor(RED)
