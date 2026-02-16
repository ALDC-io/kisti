"""KiSTI - STREET Mode Widget

Radar-first layout: V1 banner top, map with speed/GPS overlay left,
mini STI schematic right with color-changing sensor nodes.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from ui.theme import YELLOW, RED, GRAY
from ui.widgets.map_widget import MapWidget
from ui.widgets.radar_alert_widget import RadarAlertWidget
from ui.widgets.mini_sti_schematic import MiniStiSchematic


class StreetModeWidget(QWidget):
    """STREET mode: radar banner + map with overlays + mini STI schematic."""

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # Top: Radar alert — full width, 70px
        self._radar_widget = RadarAlertWidget(self, height=70)
        outer.addWidget(self._radar_widget)

        # Body: Map (55%) + Mini STI schematic (45%)
        body = QHBoxLayout()
        body.setSpacing(4)

        self._map = MapWidget(self)
        body.addWidget(self._map, stretch=55)

        self._schematic = MiniStiSchematic(self)
        body.addWidget(self._schematic, stretch=45)

        outer.addLayout(body, stretch=1)

        # Bottom: single alert line
        self._alert_label = QLabel("")
        self._alert_label.setFixedHeight(18)
        self._alert_label.setStyleSheet(f"font-size: 11px; color: {GRAY}; padding: 0 4px;")
        outer.addWidget(self._alert_label)

    def update_data(self, vehicle_state):
        """Update all child widgets from VehicleState."""
        self._map.update_position(vehicle_state.gps)
        self._map.update_radar(vehicle_state.radar)
        self._radar_widget.update_radar(vehicle_state.radar)
        self._schematic.update_data(vehicle_state)

        # Single alert line
        severity_colors = {"info": GRAY, "warning": YELLOW, "critical": RED}
        if vehicle_state.findings:
            f = vehicle_state.findings[0]
            color = severity_colors.get(f.severity, GRAY)
            self._alert_label.setText(f"\u25cf {f.title}")
            self._alert_label.setStyleSheet(f"font-size: 11px; color: {color}; padding: 0 4px;")
        else:
            self._alert_label.setText("")
