"""KiSTI - Top Status Bar

Shows mode, clock, GPS, logging, network status, and corporate logos.
2014 STI gauge cluster style - black face, red accents, chrome trim.
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ui.theme import GREEN, RED, GRAY, BG_PANEL, CHROME_DARK, WHITE, HIGHLIGHT, FONT_HEADER
from ui.branding import kisti_logo, link_ecu_logo, nvidia_logo


class TopStatusBar(QWidget):
    """Fixed 40px status bar at top of screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"background-color: {BG_PANEL}; "
            f"border-bottom: 1px solid {CHROME_DARK};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        # All logos scaled to same height for consistent status bar
        _LOGO_H = 30

        # Link ECU logo (left)
        self._link_logo = QLabel()
        pm = link_ecu_logo(_LOGO_H)
        if not pm.isNull():
            self._link_logo.setPixmap(pm)
        self._link_logo.setFixedHeight(30)
        layout.addWidget(self._link_logo)

        # KiSTI logo (next to Link)
        self._kisti_logo = QLabel()
        kpm = kisti_logo(_LOGO_H)
        if not kpm.isNull():
            self._kisti_logo.setPixmap(kpm)
        self._kisti_logo.setFixedHeight(30)
        layout.addWidget(self._kisti_logo)

        self._mode_label = QLabel("STREET")
        self._mode_label.setStyleSheet(
            f"font-size: {FONT_HEADER}px; font-weight: 900; color: {HIGHLIGHT};"
        )
        layout.addWidget(self._mode_label)

        layout.addStretch()

        self._clock_label = QLabel("")
        self._clock_label.setStyleSheet(f"color: {WHITE}; font-weight: bold;")
        layout.addWidget(self._clock_label)

        self._gps_dot = QLabel("\u25cf GPS")
        self._gps_dot.setStyleSheet(f"color: {GREEN};")
        layout.addWidget(self._gps_dot)

        self._log_dot = QLabel("\u25cf LOG")
        self._log_dot.setStyleSheet(f"color: {GREEN};")
        layout.addWidget(self._log_dot)

        self._net_dot = QLabel("\u25cf NET")
        self._net_dot.setStyleSheet(f"color: {GREEN};")
        layout.addWidget(self._net_dot)

        self._v1_dot = QLabel("\u25cf V1")
        self._v1_dot.setStyleSheet(f"color: {GRAY};")
        layout.addWidget(self._v1_dot)

        # Nvidia logo (right) — same height as other logos
        self._nvidia_logo = QLabel()
        npm = nvidia_logo(_LOGO_H)
        if not npm.isNull():
            self._nvidia_logo.setPixmap(npm)
        self._nvidia_logo.setFixedHeight(30)
        layout.addWidget(self._nvidia_logo)

        # Clock tick
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

    def _update_clock(self):
        self._clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def update_state(self, system_state, mode_str):
        """Update all status indicators."""
        # Don't show "KiSTI" text — the logo already covers it
        self._mode_label.setText("" if mode_str == "KiSTI" else mode_str)
        self._gps_dot.setStyleSheet(
            f"color: {GREEN if system_state.gps_fix else RED};"
        )
        self._log_dot.setStyleSheet(
            f"color: {GREEN if system_state.logging else GRAY};"
        )
        self._net_dot.setStyleSheet(
            f"color: {GREEN if system_state.network else RED};"
        )
        self._v1_dot.setStyleSheet(
            f"color: {GREEN if system_state.v1_connected else GRAY};"
        )
