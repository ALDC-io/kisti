"""KiSTI - Top Status Bar

Shows SI-Drive mode badge, warm-up state, CAN status, clock,
GPS/logging/network status dots, and corporate logos.
2014 STI gauge cluster style - black face, mode-colored accents, chrome trim.
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from model.vehicle_state import SIDriveMode, WarmUpState
from ui.theme import (
    GREEN, RED, YELLOW, GRAY, BG_PANEL, CHROME_DARK, WHITE, HIGHLIGHT,
    FONT_HEADER, MODE_I_ACCENT, MODE_S_ACCENT, MODE_SS_ACCENT,
)
from ui.branding import kisti_logo, link_ecu_logo, nvidia_logo

_MODE_COLORS = {
    SIDriveMode.INTELLIGENT: MODE_I_ACCENT,
    SIDriveMode.SPORT: MODE_S_ACCENT,
    SIDriveMode.SPORT_SHARP: MODE_SS_ACCENT,
}

_WARMUP_COLORS = {
    WarmUpState.COLD: "#4488FF",    # Cool blue
    WarmUpState.WARMING: "#FF8800",  # Amber
    WarmUpState.READY: GREEN,        # Green
}


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

        # SI-Drive mode badge (colored pill)
        self._mode_badge = QLabel("INTELLIGENT")
        self._update_mode_badge(SIDriveMode.INTELLIGENT)
        layout.addWidget(self._mode_badge)

        # Warm-up state indicator
        self._warmup_label = QLabel("\u25cf COLD")
        self._warmup_label.setStyleSheet(f"color: {_WARMUP_COLORS[WarmUpState.COLD]};")
        layout.addWidget(self._warmup_label)

        # CAN status dot
        self._can_dot = QLabel("\u25cf CAN")
        self._can_dot.setStyleSheet(f"color: {GRAY};")
        layout.addWidget(self._can_dot)

        layout.addStretch()

        self._clock_label = QLabel("")
        self._clock_label.setStyleSheet(f"color: {WHITE}; font-weight: bold;")
        layout.addWidget(self._clock_label)

        # Status dots — all start dark, only light when hardware confirmed
        self._gps_dot = QLabel("\u25cf GPS")
        self._gps_dot.setStyleSheet(f"color: {GRAY};")
        layout.addWidget(self._gps_dot)

        self._log_dot = QLabel("\u25cf LOG")
        self._log_dot.setStyleSheet(f"color: {GRAY};")
        layout.addWidget(self._log_dot)

        self._net_dot = QLabel("\u25cf NET")
        self._net_dot.setStyleSheet(f"color: {GRAY};")
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

        # Clock tick + real hardware status check
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

        # Real hardware status check every 10 seconds
        self._hw_timer = QTimer(self)
        self._hw_timer.setInterval(10000)
        self._hw_timer.timeout.connect(self._check_real_hardware)
        self._hw_timer.start()
        # Initial check after 2 seconds (let system settle)
        QTimer.singleShot(2000, self._check_real_hardware)

    def _update_mode_badge(self, mode: SIDriveMode) -> None:
        """Update SI-Drive badge appearance."""
        color = _MODE_COLORS.get(mode, MODE_I_ACCENT)
        text = mode.label.upper()
        font_size = 10 if len(text) > 8 else 13
        self._mode_badge.setText(text)
        self._mode_badge.setStyleSheet(
            f"background-color: {color}; color: {WHITE}; "
            f"font-size: {font_size}px; font-weight: 900; "
            f"padding: 2px 10px; border-radius: 10px;"
        )

    def set_si_drive_mode(self, mode_int: int) -> None:
        """Update badge when SI-Drive mode changes."""
        try:
            mode = SIDriveMode(mode_int)
        except ValueError:
            return
        self._update_mode_badge(mode)

    def set_warmup_state(self, warmup_int: int) -> None:
        """Update warm-up indicator."""
        try:
            warmup = WarmUpState(warmup_int)
        except ValueError:
            return
        color = _WARMUP_COLORS.get(warmup, GRAY)
        self._warmup_label.setText(f"\u25cf {warmup.label.upper()}")
        self._warmup_label.setStyleSheet(f"color: {color};")

    def set_can_status(self, connected: bool) -> None:
        """Update CAN bus status dot."""
        self._can_dot.setStyleSheet(f"color: {GREEN if connected else RED};")

    def _update_clock(self):
        self._clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _check_real_hardware(self):
        """Check real hardware status and update dots."""
        import subprocess
        import os

        # NET — real network connectivity
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True, timeout=4,
            )
            net_ok = result.returncode == 0
        except Exception:
            net_ok = False
        self._net_dot.setStyleSheet(f"color: {GREEN if net_ok else GRAY};")

        # GPS — check for GPS device (gpsd or /dev/ttyUSB* or /dev/ttyACM*)
        gps_ok = False
        for dev in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1"]:
            if os.path.exists(dev):
                gps_ok = True
                break
        self._gps_dot.setStyleSheet(f"color: {GREEN if gps_ok else GRAY};")

        # LOG — check if a DuckDB session is actively recording
        log_ok = os.path.exists("/tmp/kisti_session_active")
        self._log_dot.setStyleSheet(f"color: {GREEN if log_ok else GRAY};")

        # V1 — Valentine One BLE (check if bluetoothctl sees a V1 device)
        v1_ok = False
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True, text=True, timeout=3,
            )
            if "V1" in result.stdout or "Valentine" in result.stdout:
                v1_ok = True
        except Exception:
            pass
        self._v1_dot.setStyleSheet(f"color: {GREEN if v1_ok else GRAY};")

    def update_state(self, system_state, mode_str):
        """Legacy compat: update from vehicle state (if mock data active)."""
        # SI-Drive badge now driven by set_si_drive_mode() signal
        pass
