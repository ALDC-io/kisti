"""KiSTI - VIDEO Mode Widget

Quad-view camera feeds from the front sensor suite:
  Top-left:  RGB camera (main driving view)
  Top-right: FLIR Lepton 3.5 (live thermal — road surface)
  Bot-left:  LiDAR (point cloud)
  Bot-right: Weather camera + conditions overlay
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGridLayout

from ui.widgets.camera_feeds import (
    RGBCameraFeed, LiveThermalFeed, LiDARCameraFeed, WeatherOverlayFeed,
)


class VideoModeWidget(QWidget):
    """VIDEO mode: quad camera feed layout."""

    def __init__(self, flir_reader=None, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._rgb = RGBCameraFeed(self)
        self._ir = LiveThermalFeed(self)
        self._lidar = LiDARCameraFeed(self)
        self._weather = WeatherOverlayFeed(self)

        layout.addWidget(self._rgb, 0, 0)      # Top-left
        layout.addWidget(self._ir, 0, 1)        # Top-right (live thermal)
        layout.addWidget(self._lidar, 1, 0)     # Bottom-left
        layout.addWidget(self._weather, 1, 1)   # Bottom-right

        # Connect live thermal frames if reader provided
        if flir_reader is not None:
            flir_reader.frame_updated.connect(self._ir.on_frame)

        # Frame advance timer (15 fps for animated feeds)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(67)  # ~15fps
        self._anim_timer.timeout.connect(self._advance_frames)
        self._active = False

    def showEvent(self, event):
        """Start animation when tab becomes visible."""
        super().showEvent(event)
        self._active = True
        self._anim_timer.start()

    def hideEvent(self, event):
        """Stop animation when tab is hidden to save CPU."""
        super().hideEvent(event)
        self._active = False
        self._anim_timer.stop()

    def _advance_frames(self):
        # LiveThermalFeed.advance_frame() is a no-op — signal-driven
        self._rgb.advance_frame()
        self._lidar.advance_frame()
        self._weather.advance_frame()

    def update_data(self, vehicle_state):
        """Accept vehicle state for potential future use (e.g., overlaying speed)."""
        pass
