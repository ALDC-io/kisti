"""KiSTI - Corner Grid Widget

2x2 grid of CornerCell widgets (FL/FR/RL/RR).
"""

from PySide6.QtWidgets import QWidget, QGridLayout

from ui.widgets.corner_widget import CornerCell


class CornerGrid(QWidget):
    """2x2 grid layout of corner cells representing four wheels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._cells = {}
        positions = {"FL": (0, 0), "FR": (0, 1), "RL": (1, 0), "RR": (1, 1)}
        for name, (row, col) in positions.items():
            cell = CornerCell(name, self)
            layout.addWidget(cell, row, col)
            self._cells[name] = cell

    def update_vehicle(self, vehicle_state):
        """Update all corners from VehicleState."""
        for name, cell in self._cells.items():
            if name in vehicle_state.corners:
                cell.update_data(vehicle_state.corners[name])

    def highlight_corners(self, corner_names):
        """Highlight specific corners, clear others."""
        for name, cell in self._cells.items():
            cell.set_highlighted(name in corner_names)

    def cell(self, name):
        return self._cells.get(name)
