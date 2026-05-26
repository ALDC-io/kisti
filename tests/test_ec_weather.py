"""Tests for Environment Canada weather integration."""

import json
import time
from unittest.mock import patch

from sensors.ec_weather import (
    ECWarning,
    ECWeatherData,
    ECWeatherPoller,
    _nested_float,
    _safe_float,
)


# ---------------------------------------------------------------------------
# Mock EC API responses
# ---------------------------------------------------------------------------

MOCK_ALERTS_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "alert_type": "warning",
                "alert_name_en": "Snowfall Warning",
                "alert_text_en": "Heavy snowfall expected. 20-30 cm.",
                "feature_name_en": "Central Okanagan",
            },
        },
        {
            "type": "Feature",
            "properties": {
                "alert_type": "statement",
                "alert_name_en": "special weather statement",
                "alert_text_en": "Unsettled weather continues.",
                "feature_name_en": "Central Okanagan",
            },
        },
    ],
}

MOCK_ALERTS_EMPTY = {"type": "FeatureCollection", "features": []}

MOCK_CITYPAGE_RESPONSE = {
    "properties": {
        "currentConditions": {
            "temperature": {"value": {"en": 5.2}},
            "relativeHumidity": {"value": {"en": 78}},
            "pressure": {"value": {"en": 101.5}},
            "condition": {"en": "Cloudy"},
            "wind": {"speed": {"value": {"en": 15}}},
        },
        "hourlyForecastGroup": {
            "hourlyForecasts": [
                {
                    "condition": {"en": "Snow"},
                    "temperature": {"value": {"en": -2}},
                },
                {
                    "condition": {"en": "Snow"},
                    "temperature": {"value": {"en": -3}},
                },
            ],
        },
    },
}


class _FakeClock:
    def __init__(self, start: float = 1000.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestECWarningParsing:
    def test_parse_warnings(self):
        """Warnings are parsed from EC response."""
        clock = _FakeClock()
        responses = {
            "alerts": MOCK_ALERTS_RESPONSE,
            "citypage": MOCK_CITYPAGE_RESPONSE,
        }

        def mock_fetch(url):
            if "weather-alerts" in url:
                return responses["alerts"]
            return responses["citypage"]

        poller = ECWeatherPoller(clock=clock, fetcher=mock_fetch)
        data = poller.poll_once()

        assert data.available
        assert len(data.warnings) == 2
        assert data.warnings[0].alert_type == "warning"
        assert data.warnings[0].alert_name == "Snowfall Warning"
        assert data.highest_warning == "warning"
        assert data.warning_text == "Snowfall Warning"

    def test_empty_warnings(self):
        """No warnings returns empty list with 'none' level."""
        clock = _FakeClock()

        def mock_fetch(url):
            if "weather-alerts" in url:
                return MOCK_ALERTS_EMPTY
            return MOCK_CITYPAGE_RESPONSE

        poller = ECWeatherPoller(clock=clock, fetcher=mock_fetch)
        data = poller.poll_once()

        assert data.available
        assert len(data.warnings) == 0
        assert data.highest_warning == "none"
        assert data.warning_text == ""

    def test_highest_warning_rank(self):
        """Warning ranks higher than statement."""
        clock = _FakeClock()

        def mock_fetch(url):
            if "weather-alerts" in url:
                return MOCK_ALERTS_RESPONSE
            return MOCK_CITYPAGE_RESPONSE

        poller = ECWeatherPoller(clock=clock, fetcher=mock_fetch)
        data = poller.poll_once()

        # "warning" > "statement"
        assert data.highest_warning == "warning"


class TestECForecastParsing:
    def test_parse_current_conditions(self):
        """Current conditions are extracted from citypage."""
        clock = _FakeClock()

        def mock_fetch(url):
            if "weather-alerts" in url:
                return MOCK_ALERTS_EMPTY
            return MOCK_CITYPAGE_RESPONSE

        poller = ECWeatherPoller(clock=clock, fetcher=mock_fetch)
        data = poller.poll_once()

        assert data.ec_temp_c == 5.2
        assert data.ec_humidity_pct == 78
        assert data.ec_pressure_kpa == 101.5
        assert data.ec_condition == "Cloudy"
        assert data.ec_wind_kph == 15

    def test_parse_hourly_forecast(self):
        """Next-hour forecast is extracted."""
        clock = _FakeClock()

        def mock_fetch(url):
            if "weather-alerts" in url:
                return MOCK_ALERTS_EMPTY
            return MOCK_CITYPAGE_RESPONSE

        poller = ECWeatherPoller(clock=clock, fetcher=mock_fetch)
        data = poller.poll_once()

        assert data.forecast_condition == "Snow"
        assert data.forecast_temp_c == -2


class TestECOfflineGraceful:
    def test_fetch_failure_returns_unavailable(self):
        """Network failure keeps data unavailable."""
        clock = _FakeClock()

        def failing_fetch(url):
            raise ConnectionError("No WiFi")

        poller = ECWeatherPoller(clock=clock, fetcher=failing_fetch)
        data = poller.poll_once()

        # poll_once calls _update with None, None — should not set available
        assert not data.available

    def test_partial_failure_uses_available_data(self):
        """If warnings succeed but forecast fails, warnings still update."""
        clock = _FakeClock()
        call_count = [0]

        def partial_fetch(url):
            call_count[0] += 1
            if "weather-alerts" in url:
                return MOCK_ALERTS_RESPONSE
            raise ConnectionError("Forecast unavailable")

        poller = ECWeatherPoller(clock=clock, fetcher=partial_fetch)
        data = poller.poll_once()

        assert data.available
        assert len(data.warnings) == 2
        assert data.forecast_condition == ""  # not updated


class TestECWeatherFusion:
    def test_ec_warning_upgrades_threat(self):
        """EC warning upgrades sensor CLEAR to RAIN_LIKELY."""
        from sensors.weather_engine import WeatherEngine, ThreatLevel

        clock = _FakeClock()
        engine = WeatherEngine(clock=clock)

        # Feed stable sensor data (CLEAR conditions)
        for i in range(60):
            clock.advance(1.0)
            result = engine.feed(
                1013.0, 50.0, 20.0, 7.0,
                ec_warning_level="warning",
                ec_data_age_s=300.0,
            )

        assert result.threat_level >= ThreatLevel.RAIN_LIKELY

    def test_ec_watch_upgrades_to_changing(self):
        """EC watch upgrades CLEAR to CHANGING."""
        from sensors.weather_engine import WeatherEngine, ThreatLevel

        clock = _FakeClock()
        engine = WeatherEngine(clock=clock)

        for i in range(60):
            clock.advance(1.0)
            result = engine.feed(
                1013.0, 50.0, 20.0, 7.0,
                ec_warning_level="watch",
                ec_data_age_s=300.0,
            )

        assert result.threat_level >= ThreatLevel.CHANGING

    def test_stale_ec_data_ignored(self):
        """EC data older than 1 hour is not used for fusion."""
        from sensors.weather_engine import WeatherEngine, ThreatLevel

        clock = _FakeClock()
        engine = WeatherEngine(clock=clock)

        for i in range(60):
            clock.advance(1.0)
            result = engine.feed(
                1013.0, 50.0, 20.0, 7.0,
                ec_warning_level="warning",
                ec_data_age_s=7200.0,  # 2 hours old
            )

        assert result.threat_level == ThreatLevel.CLEAR

    def test_ec_never_downgrades(self):
        """EC 'none' doesn't downgrade sensor-detected STORM."""
        from sensors.weather_engine import WeatherEngine, ThreatLevel

        clock = _FakeClock()
        engine = WeatherEngine(clock=clock)

        # Feed rapidly falling pressure (STORM from sensors)
        for i in range(60):
            clock.advance(1.0)
            pressure = 1013.0 - (i * 0.07)  # ~4.2 hPa/hr drop
            result = engine.feed(
                pressure, 50.0, 20.0, 7.0,
                ec_warning_level="none",
                ec_data_age_s=300.0,
            )

        assert result.threat_level == ThreatLevel.STORM


class TestECAlertEngine:
    def test_ec_warning_fires_alert(self):
        """EC warning level triggers alert through alert engine."""
        from alerts.alert_engine import AlertEngine
        from model.vehicle_state import DiffStateBridge

        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        bridge.update_ec_weather("warning", "Snowfall Warning", "Snow", "Snow", 60.0)
        engine._evaluate()

        ec_alerts = [a for a in alerts if a.alert_type == "ec_weather_warning"]
        assert len(ec_alerts) == 1
        assert "Snowfall Warning" in ec_alerts[0].message

    def test_ec_statement_no_alert(self):
        """EC statement level does not fire alert."""
        from alerts.alert_engine import AlertEngine
        from model.vehicle_state import DiffStateBridge

        bridge = DiffStateBridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        bridge.update_ec_weather("statement", "special weather statement", "Cloudy", "Cloudy", 60.0)
        engine._evaluate()

        ec_alerts = [a for a in alerts if a.alert_type == "ec_weather_warning"]
        assert len(ec_alerts) == 0


class TestHelpers:
    def test_safe_float(self):
        assert _safe_float(3.14) == 3.14
        assert _safe_float("5.0") == 5.0
        assert _safe_float(None) is None
        assert _safe_float("N/A") is None

    def test_nested_float(self):
        d = {"temperature": {"value": {"en": 19.1}}}
        assert _nested_float(d, "temperature") == 19.1

    def test_nested_float_wind(self):
        d = {"wind": {"speed": {"value": {"en": 15}}}}
        assert _nested_float(d, "wind", "speed") == 15
