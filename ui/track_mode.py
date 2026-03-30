"""KiSTI - TRACK Mode Widget

Track map (left) + mini STI schematic (right) + session/brake/findings.
Mirrors STREET layout: prominent map left, at-a-glance schematic right.
"""

import random

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from ui.widgets.mini_sti_schematic import MiniStiSchematic
from ui.widgets.track_map_widget import TrackMapWidget
from ui.widgets.brake_strip import BrakeStripWidget
from ui.widgets.findings_list import FindingsListWidget
from ui.widgets.session_widget import SessionWidget
from ui.widgets.timing_display import TimingDisplayWidget


class TrackModeWidget(QWidget):
    """TRACK mode: track map left, mini STI schematic + telemetry right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._brake_counter = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Left: Track map (55%) + timing display + session timer
        left = QVBoxLayout()
        left.setSpacing(4)

        self._track_map = TrackMapWidget(self)
        left.addWidget(self._track_map, stretch=1)

        self._timing_display = TimingDisplayWidget(self)
        left.addWidget(self._timing_display)

        self._session_widget = SessionWidget(self)
        left.addWidget(self._session_widget)

        layout.addLayout(left, stretch=55)

        # Right panel (45%): mini schematic + brake strip + findings
        right = QVBoxLayout()
        right.setSpacing(4)

        self._schematic = MiniStiSchematic(self)
        right.addWidget(self._schematic, stretch=4)

        self._brake_strip = BrakeStripWidget(self)
        right.addWidget(self._brake_strip)

        self._findings_list = FindingsListWidget(self, show_header=False)
        right.addWidget(self._findings_list, stretch=2)

        layout.addLayout(right, stretch=45)

    def update_data(self, vehicle_state):
        """Update all child widgets from VehicleState."""
        self._track_map.update_position(vehicle_state.gps)
        self._session_widget.update_session(vehicle_state.session)
        self._schematic.update_data(vehicle_state)

        # Mock brake events (~every 10-15 ticks at 10Hz = every 1-1.5s)
        self._brake_counter += 1
        if self._brake_counter >= random.randint(10, 15):
            self._brake_counter = 0
            sev = random.choice(["warning", "warning", "critical"])
            self._brake_strip.add_event(sev)

        self._findings_list.update_findings(vehicle_state.findings)

    def update_timing(self, snap) -> None:
        """Update timing display from a DiffState snapshot."""
        self._timing_display.update_timing(
            lap_count=snap.lap_count,
            current_sector=snap.current_sector,
            sector_count=snap.sector_count,
            current_lap_time_ms=snap.current_lap_time_ms,
            delta_ms=snap.delta_ms,
            predicted_lap_ms=snap.predicted_lap_ms,
            theoretical_best_ms=snap.theoretical_best_ms,
            track_name=snap.track_name,
            timing_mode=snap.timing_mode,
        )

    def set_timing_mode(self, mode: int) -> None:
        """Set SI Drive mode for timing layout."""
        self._timing_display.set_mode(mode)
