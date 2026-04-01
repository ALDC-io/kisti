"""KiSTI - Main Window

SI-Drive-controlled display with 3 screens (Intelligent / Sport / Sport#).
No softkey bar — SI-Drive physical knob is the only mode selector.
Content area: 800x440 (full height minus 40px status bar).
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel,
)

from config import WINDOW_WIDTH, WINDOW_HEIGHT
from data.mock_generator import MockDataGenerator
from data.radar_manager import RadarManager
from data.models import RadarState
from model.vehicle_state import DiffStateBridge, SIDriveMode
from ui.theme import STYLESHEET, BG_DARK, GRAY
from ui.status_bar import TopStatusBar
from ui.intelligent_screen import IntelligentScreenWidget
from ui.sport_screen import SportScreenWidget
from ui.sharp_screen import SportSharpScreenWidget
from ui.kisti_mode import KistiModeWidget
from ui.street_mode import StreetModeWidget
from ui.track_mode import TrackModeWidget
from ui.diff_mode import DiffModeWidget
from ui.video_mode import VideoModeWidget
from ui.settings_mode import SettingsModeWidget
from ui.splash_screen import SplashScreen
from ui.widgets.critical_flash_overlay import CriticalFlashOverlay
from can.kisti_can import create_can_source

log = logging.getLogger("kisti.ui.main")


def _placeholder(text: str) -> QLabel:
    """Create a placeholder label for screens not yet built."""
    lbl = QLabel(f"{text}\n(Coming Soon)")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"color: {GRAY}; font-size: 24px;")
    return lbl


class MainWindow(QMainWindow):
    """800x480 fixed-size main window. SI-Drive selects between 3 screens."""

    def __init__(self, fullscreen=False, bridge=None, mode_manager=None):
        super().__init__()
        self.setWindowTitle("KiSTI")
        if fullscreen:
            self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        else:
            self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLESHEET)
        self._fullscreen = fullscreen
        self._external_bridge = bridge is not None
        self._mode_manager = mode_manager

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Status bar (40px)
        self._status_bar = TopStatusBar(self)
        main_layout.addWidget(self._status_bar)

        # Content area (440px — no softkey bar, SI-Drive handles mode selection)
        self._stack = QStackedWidget(self)
        main_layout.addWidget(self._stack, stretch=1)

        # CAN / DIFF data pipeline
        self._diff_bridge = bridge if bridge is not None else DiffStateBridge(self)

        # Legacy mode widgets (kept for voice pipeline + data compat)
        self._kisti_mode = KistiModeWidget(self)
        self._kisti_mode.set_bridge(self._diff_bridge)
        self._diff_mode = DiffModeWidget(self)
        self._diff_mode.set_bridge(self._diff_bridge)
        self._track_mode = TrackModeWidget(self)

        # === 3 SI-Drive screens ===
        self._intelligent_screen = IntelligentScreenWidget(self)
        self._sport_screen = SportScreenWidget(self)
        self._sharp_screen = SportSharpScreenWidget(self)

        self._stack.addWidget(self._intelligent_screen)  # index 0: Intelligent
        self._stack.addWidget(self._sport_screen)        # index 1: Sport
        self._stack.addWidget(self._sharp_screen)        # index 2: Sport Sharp

        self._current_si_drive: int = 0
        self._stack.setCurrentIndex(0)

        # Critical flash overlay (WARNING/CRITICAL visual feedback in S# mode)
        self._flash_overlay = CriticalFlashOverlay(central)
        self._flash_overlay.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self._flash_overlay.raise_()

        # Wire mode manager signals if provided
        if self._mode_manager is not None:
            self._mode_manager.si_drive_changed.connect(self._on_si_drive_changed)
            self._mode_manager.warmup_changed.connect(self._status_bar.set_warmup_state)

        # F11 fullscreen toggle
        shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
        shortcut.activated.connect(self._toggle_fullscreen)

        # Mock data generator — disabled, only real hardware
        self._generator = None
        self._radar_manager = None
        self._latest_radar = RadarState()

        # Only create CAN source if we own the bridge (avoid double listeners)
        if self._external_bridge:
            self._can_listener, self._mock_can = None, None
        else:
            self._can_listener, self._mock_can = create_can_source(self._diff_bridge, self)

        # Show splash first, then start
        self._splash = SplashScreen(self._on_splash_done)
        self._splash.show()

    def _on_splash_done(self):
        """Called when splash screen closes."""
        if self._radar_manager is not None:
            self._radar_manager.start()
        if not self._external_bridge and self._can_listener is not None:
            self._can_listener.start()
        if self._fullscreen:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.showFullScreen()

    def _on_si_drive_changed(self, mode_int: int) -> None:
        """Switch display to the screen for the new SI-Drive mode."""
        if 0 <= mode_int < self._stack.count():
            self._current_si_drive = mode_int
            self._stack.setCurrentIndex(mode_int)
            self._status_bar.set_si_drive_mode(mode_int)
            log.info("Display: SI-Drive %d (%s)",
                     mode_int, SIDriveMode(mode_int).label)

    def _on_radar_updated(self, radar_state):
        """Store latest radar state for merging into vehicle data pipeline."""
        self._latest_radar = radar_state

    def flash_alert(self, alert) -> None:
        """Flash overlay for WARNING/CRITICAL alerts in Sport Sharp mode."""
        if self._current_si_drive == SIDriveMode.SPORT_SHARP:
            self._flash_overlay.flash(alert.severity, alert.short_message)

    def update_from_bridge(self, snap) -> None:
        """Feed DiffState snapshot to the active screen (called at 20Hz)."""
        widget = self._stack.currentWidget()
        if hasattr(widget, 'update_state'):
            widget.update_state(snap)

    def _on_data_updated(self, vehicle_state):
        """Route legacy VehicleState data to active screen."""
        vehicle_state.radar = self._latest_radar
        vehicle_state.system.v1_connected = self._latest_radar.connected

        widget = self._stack.currentWidget()
        if hasattr(widget, 'update_data'):
            widget.update_data(vehicle_state)

    def queue_speech(self, text: str, urgency: str = "normal") -> None:
        """Queue text to be spoken through the KiSTI mode AudioPlayer."""
        self._kisti_mode._queue_lines([text], urgency=urgency)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def closeEvent(self, event):
        if self._generator:
            self._generator.stop()
        if self._radar_manager:
            self._radar_manager.stop()
        if self._can_listener is not None:
            self._can_listener.stop()
        if self._mock_can is not None:
            self._mock_can.stop()
        super().closeEvent(event)
