"""KiSTI - SETTINGS Mode Widget

System info, corporate branding, and configuration.
Shows Nvidia + Link ECU logos prominently with system diagnostics.
"""

import platform
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
)

from ui.theme import (
    BG_PANEL, BG_ACCENT, HIGHLIGHT, GREEN, RED, YELLOW,
    WHITE, SILVER, GRAY, CHROME_DARK, CHROME_MID,
    FONT_HEADER, FONT_BIG,
)
from ui.branding import nvidia_logo, link_ecu_logo, kisti_logo


class SettingsModeWidget(QWidget):
    """SETTINGS page: system info + corporate branding."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Left: Branding column
        brand_col = QVBoxLayout()
        brand_col.setSpacing(12)

        # KiSTI logo
        logo_h = 36
        kisti_label = QLabel()
        kisti_label.setAlignment(Qt.AlignCenter)
        pm = kisti_logo(logo_h)
        if not pm.isNull():
            kisti_label.setPixmap(pm)
        brand_col.addWidget(kisti_label)

        subtitle = QLabel("Knowledge-Integrated Smart\nTelemetry Interface")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 11px; color: {SILVER};")
        brand_col.addWidget(subtitle)

        brand_col.addSpacing(8)

        # Link ECU logo
        link_label = QLabel()
        link_label.setAlignment(Qt.AlignCenter)
        pm = link_ecu_logo(logo_h)
        if not pm.isNull():
            link_label.setPixmap(pm)
        brand_col.addWidget(link_label)

        link_text = QLabel("Link Engine Management")
        link_text.setAlignment(Qt.AlignCenter)
        link_text.setStyleSheet(f"font-size: 10px; color: {GRAY};")
        brand_col.addWidget(link_text)

        brand_col.addSpacing(8)

        # Nvidia logo
        nvidia_label = QLabel()
        nvidia_label.setAlignment(Qt.AlignCenter)
        pm = nvidia_logo(logo_h)
        if not pm.isNull():
            nvidia_label.setPixmap(pm)
        brand_col.addWidget(nvidia_label)

        powered_by = QLabel("Powered by NVIDIA Jetson Orin")
        powered_by.setAlignment(Qt.AlignCenter)
        powered_by.setStyleSheet(f"font-size: 10px; color: {GRAY};")
        brand_col.addWidget(powered_by)

        brand_col.addStretch()

        # Version
        ver = QLabel("v0.2.0-alpha")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet(f"font-size: 9px; color: {GRAY};")
        brand_col.addWidget(ver)

        layout.addLayout(brand_col, stretch=40)

        # Right: System info
        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        sys_header = QLabel("SYSTEM")
        sys_header.setStyleSheet(
            f"font-size: {FONT_HEADER}px; font-weight: bold; color: {HIGHLIGHT};"
        )
        info_col.addWidget(sys_header)

        # System info grid
        grid = QGridLayout()
        grid.setSpacing(4)

        self._info_items = {}
        rows = [
            ("Platform", f"{platform.machine()}"),
            ("OS", f"L4T / JetPack"),
            ("Python", platform.python_version()),
            ("Display", "800x480 HDMI"),
            ("Target", "Kenwood Excelon"),
        ]

        for i, (key, val) in enumerate(rows):
            k = QLabel(key)
            k.setStyleSheet(f"font-size: 11px; color: {GRAY};")
            v = QLabel(val)
            v.setStyleSheet(f"font-size: 11px; color: {WHITE};")
            grid.addWidget(k, i, 0)
            grid.addWidget(v, i, 1)
            self._info_items[key] = v

        info_col.addLayout(grid)

        info_col.addSpacing(8)

        # Sensor status header
        sensor_header = QLabel("SENSORS")
        sensor_header.setStyleSheet(
            f"font-size: {FONT_HEADER}px; font-weight: bold; color: {HIGHLIGHT};"
        )
        info_col.addWidget(sensor_header)

        sensor_grid = QGridLayout()
        sensor_grid.setSpacing(4)

        self._sensor_labels = {}
        sensors = [
            "Link ECU (CAN)",
            "Teledyne IR",
            "LiDAR",
            "RGB Camera",
            "Weather Camera",
            "GPS",
            "Valentine V1 (BLE)",
        ]
        for i, name in enumerate(sensors):
            n = QLabel(name)
            n.setStyleSheet(f"font-size: 11px; color: {SILVER};")
            dot = QLabel("\u25cf")
            dot.setStyleSheet(f"font-size: 11px; color: {GREEN};")
            sensor_grid.addWidget(dot, i, 0)
            sensor_grid.addWidget(n, i, 1)
            self._sensor_labels[name] = dot

        info_col.addLayout(sensor_grid)
        info_col.addStretch()

        layout.addLayout(info_col, stretch=60)

    def update_data(self, vehicle_state):
        """Update sensor connection status indicators."""
        for cam in vehicle_state.sensors.all_cameras():
            key = cam.name
            # Map camera names to our label keys
            label_map = {
                "Teledyne IR": "Teledyne IR",
                "LiDAR": "LiDAR",
                "RGB": "RGB Camera",
                "Weather": "Weather Camera",
            }
            label_key = label_map.get(key)
            if label_key and label_key in self._sensor_labels:
                color = GREEN if cam.connected else RED
                self._sensor_labels[label_key].setStyleSheet(
                    f"font-size: 11px; color: {color};"
                )

        gps_color = GREEN if vehicle_state.system.gps_fix else RED
        if "GPS" in self._sensor_labels:
            self._sensor_labels["GPS"].setStyleSheet(
                f"font-size: 11px; color: {gps_color};"
            )

        v1_color = GREEN if vehicle_state.system.v1_connected else RED
        if "Valentine V1 (BLE)" in self._sensor_labels:
            self._sensor_labels["Valentine V1 (BLE)"].setStyleSheet(
                f"font-size: 11px; color: {v1_color};"
            )
