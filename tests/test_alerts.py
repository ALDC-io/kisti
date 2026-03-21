"""Tests for the deterministic alert engine — threshold-based, no LLM."""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from model.vehicle_state import DiffStateBridge, SIDriveMode, WarmUpState
from alerts.alert_engine import (
    AlertEngine,
    Alert,
    AlertSeverity,
    OIL_PRESS_CRITICAL_PSI,
    OIL_PRESS_WARNING_PSI,
    OIL_TEMP_WARNING_C,
    COOLANT_TEMP_WARNING_C,
    COOLANT_TEMP_CRITICAL_C,
    FUEL_PRESS_CRITICAL_KPA,
    FUEL_PRESS_WARNING_KPA,
    BATTERY_LOW_V,
    ALERT_DEBOUNCE_S,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def bridge(qapp):
    return DiffStateBridge()


@pytest.fixture
def engine(bridge):
    eng = AlertEngine(bridge)
    return eng


def _set_engine_running(bridge):
    """Set engine telemetry so alert engine doesn't skip evaluation."""
    bridge.update_generic_dash_1(rpm=3000, map_kpa=100, tps=50, coolant_temp=85)
    bridge.update_generic_dash_2(iat_c=30, lambda_1=1.0, oil_pressure_kpa=350, oil_temp_c=90)
    bridge.update_generic_dash_3(ethanol_pct=0, fuel_pressure_kpa=380, battery_v=14.2, injector_duty=30)
    bridge.update_sensors(map_4bar_kpa=250, iat_ext_c=30, ethanol_ext_pct=0, oil_psi=55)


class TestAlertSeverity:
    def test_ordering(self):
        assert AlertSeverity.INFO < AlertSeverity.ADVISORY
        assert AlertSeverity.ADVISORY < AlertSeverity.WARNING
        assert AlertSeverity.WARNING < AlertSeverity.CRITICAL

    def test_labels(self):
        assert AlertSeverity.INFO.label == "info"
        assert AlertSeverity.CRITICAL.label == "critical"


class TestOilPressureAlerts:
    def test_normal_no_alert(self, engine, bridge):
        """Normal oil pressure (55 PSI) — no alert."""
        _set_engine_running(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()
        assert not any(a.alert_type.startswith("oil_pressure") for a in alerts)

    def test_warning_threshold(self, engine, bridge):
        """Oil pressure below warning threshold."""
        _set_engine_running(bridge)
        bridge.update_sensors(map_4bar_kpa=250, iat_ext_c=30, ethanol_ext_pct=0, oil_psi=20)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        oil_alerts = [a for a in alerts if a.alert_type == "oil_pressure_low"]
        assert len(oil_alerts) == 1
        assert oil_alerts[0].severity == AlertSeverity.WARNING

    def test_critical_threshold(self, engine, bridge):
        """Oil pressure below critical threshold."""
        _set_engine_running(bridge)
        bridge.update_sensors(map_4bar_kpa=250, iat_ext_c=30, ethanol_ext_pct=0, oil_psi=10)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        oil_alerts = [a for a in alerts if a.alert_type == "oil_pressure_critical"]
        assert len(oil_alerts) == 1
        assert oil_alerts[0].severity == AlertSeverity.CRITICAL


class TestOilTempAlerts:
    def test_overtemp(self, engine, bridge):
        _set_engine_running(bridge)
        bridge.update_generic_dash_2(iat_c=30, lambda_1=1.0, oil_pressure_kpa=350, oil_temp_c=135)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert any(a.alert_type == "oil_temp_high" for a in alerts)


class TestCoolantAlerts:
    def test_warning(self, engine, bridge):
        _set_engine_running(bridge)
        bridge.update_generic_dash_1(rpm=3000, map_kpa=100, tps=50, coolant_temp=108)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert any(a.alert_type == "coolant_high" for a in alerts)

    def test_critical(self, engine, bridge):
        _set_engine_running(bridge)
        bridge.update_generic_dash_1(rpm=3000, map_kpa=100, tps=50, coolant_temp=120)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert any(a.alert_type == "coolant_critical" for a in alerts)


class TestFuelPressureAlerts:
    def test_critical(self, engine, bridge):
        _set_engine_running(bridge)
        bridge.update_generic_dash_3(ethanol_pct=0, fuel_pressure_kpa=180, battery_v=14.2, injector_duty=30)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert any(a.alert_type == "fuel_pressure_critical" for a in alerts)


class TestBatteryAlerts:
    def test_low_voltage(self, engine, bridge):
        _set_engine_running(bridge)
        bridge.update_generic_dash_3(ethanol_pct=0, fuel_pressure_kpa=380, battery_v=11.8, injector_duty=30)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert any(a.alert_type == "battery_low" for a in alerts)


class TestDebouncing:
    def test_same_alert_debounced(self, engine, bridge):
        """Same alert type should not fire twice within debounce period."""
        _set_engine_running(bridge)
        bridge.update_sensors(map_4bar_kpa=250, iat_ext_c=30, ethanol_ext_pct=0, oil_psi=20)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        engine._evaluate()
        engine._evaluate()  # Second evaluation immediately after

        oil_alerts = [a for a in alerts if a.alert_type == "oil_pressure_low"]
        assert len(oil_alerts) == 1  # Only one, not two


class TestEngineNotRunning:
    def test_no_alerts_when_off(self, engine, bridge):
        """No alerts when RPM is 0 (engine off)."""
        bridge.update_generic_dash_1(rpm=0, map_kpa=0, tps=0, coolant_temp=20)
        bridge.update_sensors(map_4bar_kpa=100, iat_ext_c=20, ethanol_ext_pct=0, oil_psi=5)

        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))
        engine._evaluate()

        assert len(alerts) == 0
