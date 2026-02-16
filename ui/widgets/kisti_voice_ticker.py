"""KiSTI - Compact Voice Ticker Widget

Embeddable typewriter ticker for KiSTI persona speech.
Mini KITT-style waveform indicator + newest lines at top.
"""

import random

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PySide6.QtWidgets import QWidget

from ui.theme import BG_PANEL, GRAY, WHITE, CHROME_DARK

KISTI_RED = "#C80A33"
_CHAR_MS = 30


class KistiVoiceTicker(QWidget):
    """Compact KiSTI voice ticker — mini waveform + typewriter lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(45)
        self._speaking = False
        self._char_queue = []
        self._current_line = ""
        self._line_queue = []
        self._recent_lines = []  # Last 2 completed lines
        self._pause_ticks = 0

        # Mini waveform state (3 columns, levels 0-4)
        self._wf_levels = [0, 0, 0]
        self._wf_tick = 0

        self._type_timer = QTimer(self)
        self._type_timer.setInterval(_CHAR_MS)
        self._type_timer.timeout.connect(self._type_tick)
        self._type_timer.start()

    def queue_line(self, text):
        """Add a line to the speech queue."""
        if text.strip():
            self._line_queue.append(text)
            if not self._type_timer.isActive():
                self._type_timer.start()

    def _start_speaking(self, text):
        self._speaking = True
        self._char_queue = list(text)
        self._current_line = ""

    def _stop_speaking(self):
        self._speaking = False
        self._wf_levels = [0, 0, 0]
        if self._current_line.strip():
            self._recent_lines.append(self._current_line)
            if len(self._recent_lines) > 2:
                self._recent_lines.pop(0)
        self._current_line = ""
        self.update()

    def _type_tick(self):
        # Animate mini waveform when speaking
        if self._speaking:
            self._wf_tick += 1
            if self._wf_tick % 3 == 0:
                center = random.randint(1, 4)
                left = max(0, int(center * random.uniform(0.3, 0.9)))
                right = max(0, int(center * random.uniform(0.3, 0.9)))
                self._wf_levels = [left, center, right]

        if self._pause_ticks > 0:
            self._pause_ticks -= 1
            return

        if self._speaking and self._char_queue:
            self._current_line += self._char_queue.pop(0)
            self.update()
        elif self._speaking and not self._char_queue:
            self._stop_speaking()
            self._pause_ticks = int(500 / _CHAR_MS)
        elif not self._speaking and self._line_queue:
            next_line = self._line_queue.pop(0)
            if next_line.strip():
                self._start_speaking(next_line)
            else:
                self._pause_ticks = int(500 / _CHAR_MS)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # === Mini KiSTI waveform (3 mirrored bars) ===
        wf_x = 4
        wf_cy = h // 2
        bar_w = 3
        gap = 1
        base_color = QColor(KISTI_RED)

        p.setPen(Qt.NoPen)
        for i, level in enumerate(self._wf_levels):
            bx = wf_x + i * (bar_w + gap)
            bar_h = max(1, level * 2)  # 0-8px per half
            if self._speaking and level > 0:
                color = QColor(base_color)
                color.setAlphaF(max(0.4, 1.0 - abs(i - 1) * 0.2))
            else:
                color = QColor(base_color)
                color.setAlphaF(0.1)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(bx, wf_cy - bar_h, bar_w, bar_h * 2), 1, 1)

        # === Text area — newest at top ===
        text_x = wf_x + 3 * (bar_w + gap) + 6
        font = QFont("JetBrains Mono", 9)
        font.setStyleHint(QFont.Monospace)
        p.setFont(font)
        fm = p.fontMetrics()
        line_h = fm.height() + 2
        y = 4

        # Current line first (newest, at top) — KiSTI red with cursor
        if self._current_line:
            p.setPen(QColor(KISTI_RED))
            display = self._current_line + "\u2588"
            truncated = fm.elidedText(display, Qt.ElideRight, w - text_x - 8)
            p.drawText(text_x, y + fm.ascent(), truncated)
            y += line_h

        # Recent completed lines below (newest first)
        p.setPen(QColor(GRAY))
        for line in reversed(self._recent_lines):
            if y + fm.ascent() > h - 4:
                break
            truncated = fm.elidedText(line, Qt.ElideRight, w - text_x - 8)
            p.drawText(text_x, y + fm.ascent(), truncated)
            y += line_h

        p.end()
