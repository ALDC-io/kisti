"""KiSTI - Main Window

Assembles status bar, content area (QStackedWidget), and softkey bar.
Includes splash screen on startup and full corporate branding.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel,
)

from config import WINDOW_WIDTH, WINDOW_HEIGHT
from data.mock_generator import MockDataGenerator
from data.radar_manager import RadarManager
from data.models import RadarState
from ui.theme import STYLESHEET, BG_DARK, GRAY
from ui.status_bar import TopStatusBar
from ui.softkey_bar import BottomSoftkeyBar
from ui.kisti_mode import KistiModeWidget
from ui.street_mode import StreetModeWidget
from ui.track_mode import TrackModeWidget
from ui.diff_mode import DiffModeWidget
from ui.video_mode import VideoModeWidget
from ui.settings_mode import SettingsModeWidget
from ui.splash_screen import SplashScreen
from model.vehicle_state import DiffStateBridge
from can.kisti_can import create_can_source


class MainWindow(QMainWindow):
    """800x480 fixed-size main window with mode switching."""

    def __init__(self, fullscreen=False):
        super().__init__()
        self.setWindowTitle("KiSTI")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLESHEET)
        self._fullscreen = fullscreen

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Status bar (40px)
        self._status_bar = TopStatusBar(self)
        main_layout.addWidget(self._status_bar)

        # Content area (380px)
        self._stack = QStackedWidget(self)
        main_layout.addWidget(self._stack, stretch=1)

        # Mode widgets — order matches softkey bar: KiSTI, STREET, TRACK, DIFF, VIDEO, LOG, SETTINGS
        self._kisti_mode = KistiModeWidget(self)
        self._street_mode = StreetModeWidget(self)
        self._track_mode = TrackModeWidget(self)
        self._diff_mode = DiffModeWidget(self)
        self._video_mode = VideoModeWidget(self)
        self._settings_mode = SettingsModeWidget(self)
        self._stack.addWidget(self._kisti_mode)     # index 0
        self._stack.addWidget(self._street_mode)    # index 1
        self._stack.addWidget(self._track_mode)     # index 2
        self._stack.addWidget(self._diff_mode)      # index 3
        self._stack.addWidget(self._video_mode)     # index 4

        # Placeholder page for LOG
        placeholder = QLabel("LOG\n(Coming Soon)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {GRAY}; font-size: 24px;")
        self._stack.addWidget(placeholder)          # index 5

        self._stack.addWidget(self._settings_mode)  # index 6

        # Softkey bar (60px)
        self._softkey_bar = BottomSoftkeyBar(self)
        self._softkey_bar.mode_changed.connect(self._on_mode_changed)
        main_layout.addWidget(self._softkey_bar)

        # Current mode tracking — start on KiSTI
        self._current_mode = "KiSTI"
        self._stack.setCurrentIndex(0)
        self._mode_indices = {
            "KiSTI": 0, "STREET": 1, "TRACK": 2, "DIFF": 3,
            "VIDEO": 4, "LOG": 5, "SETTINGS": 6,
        }

        # F11 fullscreen toggle
        shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
        shortcut.activated.connect(self._toggle_fullscreen)

        # Mock data generator
        self._generator = MockDataGenerator(self)
        self._generator.data_updated.connect(self._on_data_updated)

        # Radar manager (separate data pipeline at 2Hz)
        self._radar_manager = RadarManager(self)
        self._radar_manager.radar_updated.connect(self._on_radar_updated)
        self._latest_radar = RadarState()

        # CAN / DIFF data pipeline (separate from mock telemetry)
        self._diff_bridge = DiffStateBridge(self)
        self._diff_mode.set_bridge(self._diff_bridge)
        self._can_listener, self._mock_can = create_can_source(self._diff_bridge, self)

        # Show splash first, then start
        self._splash = SplashScreen(self._on_splash_done)
        self._splash.show()

    def _on_splash_done(self):
        """Called when splash screen closes."""
        self._generator.start()
        self._radar_manager.start()
        # Start CAN listener or mock CAN generator
        if self._can_listener is not None:
            self._can_listener.start()
        if self._mock_can is not None:
            self._mock_can.start()
        if self._fullscreen:
            self.showFullScreen()

    def _on_radar_updated(self, radar_state):
        """Store latest radar state for merging into vehicle data pipeline."""
        self._latest_radar = radar_state

    def _on_mode_changed(self, mode):
        if mode in self._mode_indices:
            self._stack.setCurrentIndex(self._mode_indices[mode])
            self._current_mode = mode

    def _on_data_updated(self, vehicle_state):
        """Route data to active mode widget and status bar."""
        # Merge radar state into vehicle telemetry
        vehicle_state.radar = self._latest_radar
        vehicle_state.system.v1_connected = self._latest_radar.connected

        self._status_bar.update_state(vehicle_state.system, self._current_mode)

        # Update the mode that the user is currently viewing
        if self._current_mode == "KiSTI":
            self._kisti_mode.update_data(vehicle_state)
        elif self._current_mode == "STREET":
            self._street_mode.update_data(vehicle_state)
        elif self._current_mode == "TRACK":
            self._track_mode.update_data(vehicle_state)
        elif self._current_mode == "VIDEO":
            self._video_mode.update_data(vehicle_state)
        elif self._current_mode == "DIFF":
            self._diff_mode.update_data(vehicle_state)
        elif self._current_mode == "SETTINGS":
            self._settings_mode.update_data(vehicle_state)
        # Also set the session mode to match UI mode
        vehicle_state.session.mode = self._current_mode

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def closeEvent(self, event):
        self._generator.stop()
        self._radar_manager.stop()
        if self._can_listener is not None:
            self._can_listener.stop()
        if self._mock_can is not None:
            self._mock_can.stop()
        super().closeEvent(event)
