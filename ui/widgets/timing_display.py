"""KiSTI - Timing Display Widget

Live delta/splits overlay for the 800x480 display.
Three SI Drive mode layouts:
  - Intelligent: full (lap, delta, predicted, theoretical, sectors, track)
  - Sport: compact (lap, delta, current sector)
  - Sport Sharp: minimal (delta bar only)

Designed to be overlaid on any mode or embedded in TRACK mode.
Uses QPainter custom painting for maximum performance on Jetson.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_PANEL, GREEN, RED, YELLOW, CYAN, WHITE, GRAY, DIM,
    CHERRY, HIGHLIGHT,
)


class TimingDisplayWidget(QWidget):
    """Live timing overlay widget.

    Call :meth:`update_timing` with DiffState timing fields.
    Call :meth:`set_mode` with SIDriveMode to switch layouts.
    """

    # Mode constants matching SIDriveMode values
    MODE_INTELLIGENT = 0
    MODE_SPORT = 1
    MODE_SPORT_SHARP = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)

        # Timing state
        self._lap_count: int = 0
        self._current_sector: int = 0
        self._sector_count: int = 0
        self._current_lap_time_ms: int = 0
        self._delta_ms: int = 0
        self._predicted_lap_ms: int = 0
        self._theoretical_best_ms: int = 0
        self._track_name: str = ""
        self._timing_mode: str = ""
        self._mode: int = self.MODE_INTELLIGENT

        # Delta flash animation
        self._flash_visible: bool = True
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._toggle_flash)
        self._prev_delta_sign: int = 0  # Track sign changes for flash

    def set_mode(self, mode: int) -> None:
        """Switch SI Drive display layout."""
        self._mode = mode
        self.update()

    def update_timing(
        self,
        lap_count: int = 0,
        current_sector: int = 0,
        sector_count: int = 0,
        current_lap_time_ms: int = 0,
        delta_ms: int = 0,
        predicted_lap_ms: int = 0,
        theoretical_best_ms: int = 0,
        track_name: str = "",
        timing_mode: str = "",
    ) -> None:
        """Update all timing fields from DiffState."""
        # Detect delta sign change for flash
        new_sign = 1 if delta_ms > 0 else (-1 if delta_ms < 0 else 0)
        if new_sign != self._prev_delta_sign and self._prev_delta_sign != 0:
            self._flash_visible = True
            self._flash_timer.start()
            QTimer.singleShot(2000, self._flash_timer.stop)
        self._prev_delta_sign = new_sign

        self._lap_count = lap_count
        self._current_sector = current_sector
        self._sector_count = sector_count
        self._current_lap_time_ms = current_lap_time_ms
        self._delta_ms = delta_ms
        self._predicted_lap_ms = predicted_lap_ms
        self._theoretical_best_ms = theoretical_best_ms
        self._track_name = track_name
        self._timing_mode = timing_mode
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))

        if not self._track_name:
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Helvetica", 12))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No track detected")
            p.end()
            return

        if self._mode == self.MODE_SPORT_SHARP:
            self._paint_sharp(p, w, h)
        elif self._mode == self.MODE_SPORT:
            self._paint_sport(p, w, h)
        else:
            self._paint_intelligent(p, w, h)

        p.end()

    def _paint_intelligent(self, p: QPainter, w: int, h: int) -> None:
        """Full layout: all timing data."""
        # Row 1: Track name + lap count
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 10))
        mode_label = "P2P" if self._timing_mode == "point_to_point" else "CIR"
        p.drawText(QRectF(4, 2, w - 8, 14), Qt.AlignLeft,
                   f"{self._track_name}  [{mode_label}]")
        p.drawText(QRectF(4, 2, w - 8, 14), Qt.AlignRight,
                   f"LAP {self._lap_count}")

        # Row 2: Current lap time (big)
        y_time = 18
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 22, QFont.Bold))
        p.drawText(QRectF(4, y_time, w * 0.5, 28), Qt.AlignLeft | Qt.AlignVCenter,
                   self._fmt_time(self._current_lap_time_ms))

        # Row 2 right: Delta (colored)
        if self._delta_ms != 0 or self._lap_count >= 2:
            delta_color = GREEN if self._delta_ms <= 0 else RED
            if self._flash_timer.isActive() and not self._flash_visible:
                delta_color = DIM
            p.setPen(QColor(delta_color))
            p.setFont(QFont("Helvetica", 22, QFont.Bold))
            sign = "+" if self._delta_ms > 0 else ("-" if self._delta_ms < 0 else "")
            delta_text = f"{sign}{abs(self._delta_ms) / 1000:.1f}"
            p.drawText(QRectF(w * 0.5, y_time, w * 0.5 - 4, 28),
                       Qt.AlignRight | Qt.AlignVCenter, delta_text)

        # Row 3: Predicted + Theoretical
        y_row3 = 48
        if self._predicted_lap_ms > 0:
            p.setPen(QColor(CYAN))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(QRectF(4, y_row3, w * 0.5, 14), Qt.AlignLeft,
                       f"PRED {self._fmt_time(self._predicted_lap_ms)}")

        if self._theoretical_best_ms > 0:
            p.setPen(QColor(YELLOW))
            p.setFont(QFont("Helvetica", 10))
            p.drawText(QRectF(w * 0.5, y_row3, w * 0.5 - 4, 14), Qt.AlignRight,
                       f"THEO {self._fmt_time(self._theoretical_best_ms)}")

        # Row 4: Sector indicator
        if self._sector_count > 0:
            y_sec = h - 14
            self._paint_sector_dots(p, 4, y_sec, w - 8, 10)

    def _paint_sport(self, p: QPainter, w: int, h: int) -> None:
        """Compact layout: lap + delta + sector."""
        # Lap time left
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 18, QFont.Bold))
        p.drawText(QRectF(4, 4, w * 0.5, h - 8), Qt.AlignLeft | Qt.AlignVCenter,
                   self._fmt_time(self._current_lap_time_ms))

        # Delta right
        if self._delta_ms != 0 or self._lap_count >= 2:
            color = GREEN if self._delta_ms <= 0 else RED
            p.setPen(QColor(color))
            p.setFont(QFont("Helvetica", 18, QFont.Bold))
            sign = "+" if self._delta_ms > 0 else ("-" if self._delta_ms < 0 else "")
            p.drawText(QRectF(w * 0.5, 4, w * 0.5 - 4, h - 8),
                       Qt.AlignRight | Qt.AlignVCenter,
                       f"{sign}{abs(self._delta_ms) / 1000:.1f}")

        # Sector dots at bottom
        if self._sector_count > 0:
            self._paint_sector_dots(p, 4, h - 12, w - 8, 8)

    def _paint_sharp(self, p: QPainter, w: int, h: int) -> None:
        """Minimal layout: delta bar only."""
        # Delta bar — green left (ahead), red right (behind)
        bar_h = max(h - 4, 8)
        bar_y = 2

        # Background bar
        p.fillRect(QRectF(2, bar_y, w - 4, bar_h), QColor(DIM))

        # Delta indicator
        center_x = w / 2
        max_delta_ms = 5000  # 5 seconds full scale
        frac = min(abs(self._delta_ms) / max_delta_ms, 1.0)
        bar_w = frac * (w / 2 - 4)

        if self._delta_ms < 0:
            # Ahead — green bar extending left from center
            p.fillRect(QRectF(center_x - bar_w, bar_y, bar_w, bar_h), QColor(GREEN))
        elif self._delta_ms > 0:
            # Behind — red bar extending right from center
            p.fillRect(QRectF(center_x, bar_y, bar_w, bar_h), QColor(RED))

        # Center tick
        p.setPen(QPen(QColor(WHITE), 2))
        p.drawLine(int(center_x), bar_y, int(center_x), bar_y + bar_h)

        # Delta text overlay
        if self._delta_ms != 0:
            p.setPen(QColor(WHITE))
            p.setFont(QFont("Helvetica", 10, QFont.Bold))
            sign = "+" if self._delta_ms > 0 else "-"
            p.drawText(QRectF(0, bar_y, w, bar_h), Qt.AlignCenter,
                       f"{sign}{abs(self._delta_ms) / 1000:.1f}")

    def _paint_sector_dots(self, p: QPainter, x: int, y: int, w: int, h: int) -> None:
        """Paint sector progress dots."""
        if self._sector_count <= 0:
            return
        dot_w = min(w / self._sector_count - 2, 20)
        spacing = (w - dot_w * self._sector_count) / max(self._sector_count - 1, 1)

        for i in range(self._sector_count):
            dx = x + i * (dot_w + spacing)
            if i < self._current_sector:
                color = GREEN  # completed
            elif i == self._current_sector:
                color = HIGHLIGHT  # current
            else:
                color = DIM  # upcoming
            p.fillRect(QRectF(dx, y, dot_w, h), QColor(color))

    @staticmethod
    def _fmt_time(ms: int) -> str:
        """Format milliseconds as M:SS.s or SS.s."""
        if ms <= 0:
            return "--:--.--"
        secs = ms / 1000.0
        if secs >= 60:
            m, sec = divmod(secs, 60)
            return f"{int(m)}:{sec:04.1f}"
        return f"{secs:.1f}"

    def _toggle_flash(self) -> None:
        self._flash_visible = not self._flash_visible
        self.update()
