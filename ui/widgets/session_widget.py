"""KiSTI - Session Widget

Displays session time, lap count, last lap, best lap.
STI gauge style: white bold numbers, gray labels, red best lap.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel

from ui.theme import WHITE, SILVER, GRAY, GREEN, HIGHLIGHT, FONT_BIG, FONT_BASE


def _fmt_time(seconds):
    if seconds <= 0:
        return "--:--"
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:04.1f}"


class SessionWidget(QWidget):
    """Session timing display - STI instrument style."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        layout.addWidget(self._tag("SESSION"), 0, 0)
        self._time_label = self._value("--:--")
        layout.addWidget(self._time_label, 0, 1)

        layout.addWidget(self._tag("LAP"), 1, 0)
        self._lap_label = self._value("0")
        layout.addWidget(self._lap_label, 1, 1)

        layout.addWidget(self._tag("LAST"), 2, 0)
        self._last_label = self._value("--:--")
        layout.addWidget(self._last_label, 2, 1)

        layout.addWidget(self._tag("BEST"), 3, 0)
        self._best_label = self._value("--:--", color=GREEN)
        layout.addWidget(self._best_label, 3, 1)

    def _tag(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {GRAY}; font-size: 10px; font-weight: bold;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lbl

    def _value(self, text, color=WHITE):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-size: {FONT_BASE}px; font-weight: 900;")
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return lbl

    def update_session(self, session_data):
        self._time_label.setText(_fmt_time(session_data.session_time_s))
        self._lap_label.setText(str(session_data.lap_count))

        if session_data.lap_times:
            self._last_label.setText(_fmt_time(session_data.lap_times[-1]))
        else:
            self._last_label.setText("--:--")

        if session_data.best_lap > 0:
            self._best_label.setText(_fmt_time(session_data.best_lap))
        else:
            self._best_label.setText("--:--")
