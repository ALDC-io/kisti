"""KiSTI — Sport Screen (SI Drive Sport Mode)

Body dynamics + technique coaching display. Shows what AiM cannot:
friction ellipse, brake quality, balance trend, trail braking, grip.

Layout (800 × ~380px content area):
┌──────────────────────────────────────────────────────────────────┐
│ ● DRY  3  82 km/h                                               │ 20px status
├────────────────────────────────┬─────────────────────────────────┤
│                                │  BRAKE G   [████████▌···] 1.02  │
│    Friction Ellipse            │  BALANCE   [···▌██▌···] 0.98    │
│    (radius=130, 20 trail)      │  TRAIL     [███▌·····] 34%      │
│                                │                                 │
│                                │  DCCD      [████████▌···] 65%   │
│                                │  FRONT     [████████▌···] 95%   │
│                                │  REAR      [█████▌·····] 82%    │
└────────────────────────────────┴─────────────────────────────────┘

ADR-1: Paint functions, not QWidgets — no heap objects on Jetson's 344MB.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen,
)
from PySide6.QtWidgets import QWidget

from model.vehicle_state import DiffState, DiffStateBridge, SurfaceState
from ui.theme import (
    BG_DARK, BG_PANEL, CHERRY, CHROME_DARK, CYAN, DIM, GRAY,
    GREEN, HIGHLIGHT, RED, SILVER, WHITE, YELLOW,
)
from ui.g_force_ellipse import paint_g_ellipse


# Bar layout constants
_BAR_X = 420          # Left edge of bars panel
_BAR_W = 340          # Total bar area width
_BAR_H = 14           # Bar height
_BAR_LABEL_W = 60     # Label text width
_BAR_INNER_W = 220    # Actual bar fill width
_BAR_VALUE_W = 60     # Value text width
_BAR_SPACING = 8      # Vertical gap between bars


class SportScreen(QWidget):
    """Sport mode driving dynamics display.

    Fed by coaching timer at 1Hz:
      - update_balance(ratio) — from BalanceAnalyzer
      - update_grip(front_pct, rear_pct) — from GripAnalyzer
      - update_brake_analysis(summary) — from TechniqueAnalyzer
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge: Optional[DiffStateBridge] = None
        self._snap: Optional[DiffState] = None

        # G-trail for friction ellipse (list of (lat_g, lon_g) tuples)
        self._g_trail: list[tuple[float, float]] = []
        self._max_trail = 20

        # Coaching state (updated at 1Hz by main.py)
        self._balance_ratio: float = 1.0
        self._front_grip_pct: float = 100.0
        self._rear_grip_pct: float = 100.0
        self._brake_peak_g: float = 0.0
        self._brake_consistency: float = 1.0
        self._trail_brake_pct: float = 0.0

    def set_bridge(self, bridge: DiffStateBridge) -> None:
        self._bridge = bridge

    def update_data(self, snap: DiffState) -> None:
        """Called from UI refresh timer (~10-20Hz)."""
        self._snap = snap
        # Accumulate G trail
        lat_g = snap.lateral_g
        lon_g = snap.imu_accel_x
        self._g_trail.append((lat_g, lon_g))
        if len(self._g_trail) > self._max_trail:
            self._g_trail = self._g_trail[-self._max_trail:]
        self.update()

    # --- Coaching updates (1Hz from main.py) ---

    def update_balance(self, ratio: float) -> None:
        self._balance_ratio = ratio

    def update_grip(self, front_pct: float, rear_pct: float) -> None:
        self._front_grip_pct = front_pct
        self._rear_grip_pct = rear_pct

    def update_brake_analysis(self, summary: dict) -> None:
        self._brake_peak_g = summary.get("peak_g", 0.0)
        self._brake_consistency = summary.get("consistency", 1.0)
        self._trail_brake_pct = summary.get("trail_pct", 0.0)

    # --- Rendering ---

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        snap = self._snap

        # --- Top status line (20px) ---
        self._paint_status(p, w, snap)

        # --- Left: Friction ellipse ---
        ellipse_cx = 200
        ellipse_cy = h // 2 + 10
        ellipse_r = min(130, (h - 40) // 2 - 10)
        if snap:
            paint_g_ellipse(
                p, ellipse_cx, ellipse_cy, ellipse_r,
                snap, self._g_trail, self._balance_ratio,
                max_trail_dots=self._max_trail,
            )
        else:
            # Empty state — draw reference only
            p.setPen(QPen(QColor(DIM), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(ellipse_cx, ellipse_cy), ellipse_r, ellipse_r)

        # --- Right: Performance bars ---
        bar_y = 40
        bar_y = self._paint_bar(p, bar_y, "BRAKE G",
                                self._brake_peak_g / 1.5,  # Normalize to 1.5g max
                                f"{self._brake_peak_g:.2f}",
                                self._brake_g_color(self._brake_peak_g))
        bar_y = self._paint_balance_bar(p, bar_y)
        bar_y = self._paint_bar(p, bar_y, "TRAIL",
                                self._trail_brake_pct / 100.0,
                                f"{self._trail_brake_pct:.0f}%",
                                QColor(CYAN))

        # Separator
        bar_y += 6
        p.setPen(QPen(QColor(DIM), 1))
        p.drawLine(_BAR_X, bar_y, _BAR_X + _BAR_W, bar_y)
        bar_y += 10

        # Drivetrain cluster
        dccd_pct = snap.dccd_command_pct / 100.0 if snap else 0.0
        bar_y = self._paint_bar(p, bar_y, "DCCD",
                                dccd_pct,
                                f"{(dccd_pct * 100):.0f}%",
                                QColor(HIGHLIGHT))
        bar_y = self._paint_bar(p, bar_y, "FRONT",
                                self._front_grip_pct / 100.0,
                                f"{self._front_grip_pct:.0f}%",
                                self._grip_color(self._front_grip_pct))
        bar_y = self._paint_bar(p, bar_y, "REAR",
                                self._rear_grip_pct / 100.0,
                                f"{self._rear_grip_pct:.0f}%",
                                self._grip_color(self._rear_grip_pct))

        p.end()

    def _paint_status(self, p: QPainter, w: int, snap: Optional[DiffState]) -> None:
        """Top 20px status line: surface, gear, speed."""
        p.fillRect(0, 0, w, 20, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(0, 19, w, 19)

        if snap:
            # Surface dot
            surface_color = QColor(snap.surface_state.color)
            p.setPen(Qt.NoPen)
            p.setBrush(surface_color)
            p.drawEllipse(8, 6, 8, 8)
            p.setFont(QFont("Helvetica", 9, QFont.Bold))
            p.setPen(QPen(surface_color))
            p.drawText(QRectF(20, 0, 60, 20), Qt.AlignVCenter, snap.surface_state.label)

            # Gear + speed (right side)
            gear_text = str(snap.gear) if snap.gear > 0 else "N"
            p.setFont(QFont("Helvetica", 12, QFont.Bold))
            p.setPen(QPen(QColor(WHITE)))
            p.drawText(QRectF(w - 140, 0, 30, 20), Qt.AlignVCenter | Qt.AlignRight, gear_text)
            p.setFont(QFont("Helvetica", 10))
            p.drawText(QRectF(w - 100, 0, 50, 20), Qt.AlignVCenter | Qt.AlignRight,
                       f"{snap.speed_kph:.0f}")
            p.setFont(QFont("Helvetica", 8))
            p.setPen(QPen(QColor(GRAY)))
            p.drawText(QRectF(w - 45, 0, 40, 20), Qt.AlignVCenter, "km/h")

    def _paint_bar(self, p: QPainter, y: int, label: str,
                   fill_pct: float, value_text: str,
                   fill_color: QColor) -> int:
        """Paint a horizontal bar with label and value. Returns next Y."""
        fill_pct = max(0.0, min(1.0, fill_pct))

        # Label
        p.setFont(QFont("Helvetica", 8, QFont.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(_BAR_X, y, _BAR_LABEL_W, _BAR_H),
                   Qt.AlignVCenter | Qt.AlignRight, label)

        # Bar background
        bx = _BAR_X + _BAR_LABEL_W + 6
        p.fillRect(int(bx), y + 1, _BAR_INNER_W, _BAR_H - 2, QColor(DIM))

        # Bar fill
        fill_w = int(_BAR_INNER_W * fill_pct)
        if fill_w > 0:
            p.fillRect(int(bx), y + 1, fill_w, _BAR_H - 2, fill_color)

        # Value text
        p.setFont(QFont("Helvetica", 8))
        p.setPen(QPen(QColor(WHITE)))
        p.drawText(QRectF(bx + _BAR_INNER_W + 4, y, _BAR_VALUE_W, _BAR_H),
                   Qt.AlignVCenter | Qt.AlignLeft, value_text)

        return y + _BAR_H + _BAR_SPACING

    def _paint_balance_bar(self, p: QPainter, y: int) -> int:
        """Centered balance bar: understeer left, oversteer right, neutral center."""
        label = "BALANCE"
        p.setFont(QFont("Helvetica", 8, QFont.Bold))
        p.setPen(QPen(QColor(GRAY)))
        p.drawText(QRectF(_BAR_X, y, _BAR_LABEL_W, _BAR_H),
                   Qt.AlignVCenter | Qt.AlignRight, label)

        bx = _BAR_X + _BAR_LABEL_W + 6
        # Background
        p.fillRect(int(bx), y + 1, _BAR_INNER_W, _BAR_H - 2, QColor(DIM))

        # Center marker
        center_x = bx + _BAR_INNER_W / 2
        p.setPen(QPen(QColor(GRAY), 1))
        p.drawLine(int(center_x), y + 1, int(center_x), y + _BAR_H - 2)

        # Balance indicator: ratio 0.5-2.0 mapped to bar range
        # 1.0 = center, <1.0 = left (understeer), >1.0 = right (oversteer)
        ratio = self._balance_ratio
        normalized = (ratio - 0.5) / 1.5  # 0.5→0.0, 1.0→0.333, 2.0→1.0
        normalized = max(0.0, min(1.0, normalized))
        indicator_x = bx + _BAR_INNER_W * normalized

        # Color: blue=US, green=neutral, red=OS
        if ratio < 0.97:
            color = QColor(CYAN)  # Understeer = blue
        elif ratio > 1.03:
            color = QColor(RED)   # Oversteer = red
        else:
            color = QColor(GREEN)  # Neutral

        # Draw indicator block (3px wide)
        p.fillRect(int(indicator_x - 2), y + 1, 4, _BAR_H - 2, color)

        # Value text
        p.setFont(QFont("Helvetica", 8))
        p.setPen(QPen(QColor(WHITE)))
        p.drawText(QRectF(bx + _BAR_INNER_W + 4, y, _BAR_VALUE_W, _BAR_H),
                   Qt.AlignVCenter | Qt.AlignLeft, f"{ratio:.2f}")

        return y + _BAR_H + _BAR_SPACING

    @staticmethod
    def _brake_g_color(peak_g: float) -> QColor:
        if peak_g < 0.5:
            return QColor(GREEN)
        elif peak_g < 0.9:
            return QColor(YELLOW)
        return QColor(RED)

    @staticmethod
    def _grip_color(pct: float) -> QColor:
        if pct >= 90.0:
            return QColor(GREEN)
        elif pct >= 80.0:
            return QColor(YELLOW)
        return QColor(RED)
