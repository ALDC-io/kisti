"""KiSTI - Radar Manager

Abstraction layer that selects between MockRadarGenerator and
future V1 BLE driver based on config. Re-emits radar_updated signal.
"""

from PySide6.QtCore import QObject, Signal

from config import RADAR_MOCK_ENABLED
from data.models import RadarState
from data.mock_radar_generator import MockRadarGenerator


class RadarManager(QObject):
    """Manages radar data source (mock or BLE).

    Signals:
        radar_updated(RadarState): Emitted at 2Hz with current radar state.
    """

    radar_updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        if RADAR_MOCK_ENABLED:
            self._source = MockRadarGenerator(self)
        else:
            # Future: V1BLEDriver(self)
            self._source = MockRadarGenerator(self)

        self._source.radar_updated.connect(self._on_source_updated)

    def _on_source_updated(self, radar_state):
        """Re-emit from whichever source is active."""
        self.radar_updated.emit(radar_state)

    def start(self):
        self._source.start()

    def stop(self):
        self._source.stop()
