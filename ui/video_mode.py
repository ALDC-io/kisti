"""KiSTI - VIDEO Mode Widget

Quad-view camera feeds from the front sensor suite:
  Top-left:  RGB camera (main driving view)
  Top-right: Teledyne IR (thermal)
  Bot-left:  LiDAR (point cloud)
  Bot-right: Weather camera + conditions overlay

Scene: Fall day canyon drive on Duffey Lake Road, BC (Hwy 99).
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGridLayout

from ui.widgets.camera_feeds import (
    RGBCameraFeed, IRCameraFeed, LiDARCameraFeed, WeatherOverlayFeed,
)


class VideoModeWidget(QWidget):
    """VIDEO mode: quad camera feed layout."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._rgb = RGBCameraFeed(self)
        self._ir = IRCameraFeed(self)
        self._lidar = LiDARCameraFeed(self)
        self._weather = WeatherOverlayFeed(self)

        layout.addWidget(self._rgb, 0, 0)      # Top-left
        layout.addWidget(self._ir, 0, 1)        # Top-right
        layout.addWidget(self._lidar, 1, 0)     # Bottom-left
        layout.addWidget(self._weather, 1, 1)   # Bottom-right

        # Frame advance timer (15 fps for smooth animation)
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
        self._rgb.advance_frame()
        self._ir.advance_frame()
        self._lidar.advance_frame()
        self._weather.advance_frame()

    def update_data(self, vehicle_state):
        """Accept vehicle state for potential future use (e.g., overlaying speed)."""
        pass
