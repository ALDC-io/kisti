"""Tests for alert routing — voice vs display vs silent."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from alerts.alert_engine import AlertEngine, Alert, AlertSeverity

# Ensure QApplication exists
if not QApplication.instance():
    _app = QApplication([])


class TestAlertRouting:
    def test_voice_alert_types_are_safety_critical(self):
        """Voice alerts should only be safety-critical types."""
        expected = {
            "oil_pressure_low",
            "oil_pressure_critical",
            "coolant_critical",
            "fuel_pressure_critical",
        }
        assert AlertEngine.VOICE_ALERT_TYPES == expected

    def test_display_alert_types(self):
        """Display-only alerts should include grip and g-force."""
        assert "grip_wet" in AlertEngine.DISPLAY_ALERT_TYPES
        assert "high_g_advisory" in AlertEngine.DISPLAY_ALERT_TYPES
        assert "high_g_warning" in AlertEngine.DISPLAY_ALERT_TYPES

    def test_oil_critical_emits_voice(self):
        """Oil pressure critical should emit voice_alert signal."""
        from model.vehicle_state import DiffStateBridge
        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)

        voice_alerts = []
        display_alerts = []
        all_alerts = []

        engine.voice_alert.connect(lambda a: voice_alerts.append(a))
        engine.display_alert.connect(lambda a: display_alerts.append(a))
        engine.alert_fired.connect(lambda a: all_alerts.append(a))

        # Fire an oil pressure critical alert
        alert = Alert(
            alert_type="oil_pressure_critical",
            severity=AlertSeverity.CRITICAL,
            message="Oil pressure critical",
            short_message="Oil!",
            value=10.0,
        )
        engine._fire(alert)

        assert len(all_alerts) == 1
        assert len(voice_alerts) == 1
        assert len(display_alerts) == 0

    def test_grip_wet_emits_display_only(self):
        """Grip wet should emit display_alert, NOT voice_alert."""
        from model.vehicle_state import DiffStateBridge
        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)

        voice_alerts = []
        display_alerts = []

        engine.voice_alert.connect(lambda a: voice_alerts.append(a))
        engine.display_alert.connect(lambda a: display_alerts.append(a))

        alert = Alert(
            alert_type="grip_wet",
            severity=AlertSeverity.ADVISORY,
            message="Wet surface",
            short_message="Wet",
        )
        engine._fire(alert)

        assert len(voice_alerts) == 0
        assert len(display_alerts) == 1

    def test_ambient_alerts_are_silent(self):
        """Ambient alerts (pressure, temp, humidity) should be silent — no voice or display."""
        from model.vehicle_state import DiffStateBridge
        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)

        voice_alerts = []
        display_alerts = []
        all_alerts = []

        engine.voice_alert.connect(lambda a: voice_alerts.append(a))
        engine.display_alert.connect(lambda a: display_alerts.append(a))
        engine.alert_fired.connect(lambda a: all_alerts.append(a))

        alert = Alert(
            alert_type="pressure_falling",
            severity=AlertSeverity.ADVISORY,
            message="Pressure falling",
            short_message="Pressure",
        )
        engine._fire(alert)

        assert len(all_alerts) == 1      # logged to DuckDB
        assert len(voice_alerts) == 0    # no voice
        assert len(display_alerts) == 0  # no display emphasis

    def test_coolant_critical_emits_voice(self):
        """Coolant critical is safety-critical → voice."""
        from model.vehicle_state import DiffStateBridge
        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)

        voice_alerts = []
        engine.voice_alert.connect(lambda a: voice_alerts.append(a))

        alert = Alert(
            alert_type="coolant_critical",
            severity=AlertSeverity.CRITICAL,
            message="Overtemp",
            short_message="Overtemp!",
        )
        engine._fire(alert)
        assert len(voice_alerts) == 1
