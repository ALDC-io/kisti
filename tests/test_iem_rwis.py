"""Tests for IEM RWIS (Iowa Environmental Mesonet) road weather poller."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

from PySide6.QtWidgets import QApplication

if not QApplication.instance():
    _app = QApplication([])

from model.vehicle_state import DiffStateBridge
from sensors.iem_rwis import (
    IEMRWISPoller,
    IEMRWISData,
    IEMStationData,
    f_to_c,
    knots_to_kph,
    miles_to_km,
    inches_to_mm,
    normalize_road_condition,
    parse_station,
    parse_stations,
)


# ---------------------------------------------------------------------------
# Mock IEM API response
# ---------------------------------------------------------------------------

MOCK_IEM_RESPONSE = {
    "schema": ["station", "name", "county", "state", "network", "lat", "lon",
               "utc_valid", "tmpf", "dwpf", "relh", "vsby", "sknt", "drct",
               "gust", "feel", "subf", "tfs0", "tfs0_text", "tfs1", "tfs1_text",
               "tfs2", "tfs2_text", "tfs3", "tfs3_text", "pcpn"],
    "data": [
        {
            "station": "RAMI4",
            "name": "I-35 @ Ames",
            "county": "Story",
            "state": "IA",
            "network": "IA_RWIS",
            "lat": 42.034,
            "lon": -93.462,
            "utc_valid": "2026-04-06T12:00:00Z",
            "tmpf": 45.0,
            "dwpf": 35.0,
            "relh": 68.0,
            "vsby": 10.0,
            "sknt": 15.0,
            "drct": 270,
            "gust": 25.0,
            "feel": 40.0,
            "subf": 42.0,
            "tfs0": 38.0,
            "tfs0_text": "Wet",
            "tfs1": None,
            "tfs1_text": None,
            "tfs2": None,
            "tfs2_text": None,
            "tfs3": None,
            "tfs3_text": None,
            "pcpn": 0.05,
        },
        {
            "station": "RDMI4",
            "name": "I-35 @ Des Moines",
            "county": "Polk",
            "state": "IA",
            "network": "IA_RWIS",
            "lat": 41.600,
            "lon": -93.609,
            "utc_valid": "2026-04-06T12:00:00Z",
            "tmpf": 50.0,
            "dwpf": 40.0,
            "relh": 72.0,
            "vsby": 10.0,
            "sknt": 10.0,
            "drct": 180,
            "gust": 18.0,
            "feel": 47.0,
            "subf": 48.0,
            "tfs0": 52.0,
            "tfs0_text": "Dry",
            "tfs1": None,
            "tfs1_text": None,
            "tfs2": None,
            "tfs2_text": None,
            "tfs3": None,
            "tfs3_text": None,
            "pcpn": 0.0,
        },
        {
            "station": "RDUI4",
            "name": "US-20 @ Dubuque",
            "county": "Dubuque",
            "state": "IA",
            "network": "IA_RWIS",
            "lat": 42.500,
            "lon": -90.664,
            "utc_valid": "2026-04-06T12:00:00Z",
            "tmpf": 40.0,
            "dwpf": 32.0,
            "relh": 75.0,
            "vsby": 5.0,
            "sknt": 20.0,
            "drct": 310,
            "gust": 30.0,
            "feel": 33.0,
            "subf": 36.0,
            "tfs0": 30.0,
            "tfs0_text": "Ice",
            "tfs1": 31.0,
            "tfs1_text": "Ice Warning",
            "tfs2": None,
            "tfs2_text": None,
            "tfs3": None,
            "tfs3_text": None,
            "pcpn": 0.02,
        },
    ],
}

MOCK_IEM_EMPTY = {"schema": [], "data": []}

# Station with tfs0=None but tfs1 has data (sensor fallback test)
MOCK_STATION_SENSOR_FALLBACK = {
    "station": "RFAL",
    "name": "Fallback Sensor Station",
    "state": "IA",
    "lat": 42.0,
    "lon": -93.5,
    "utc_valid": "2026-04-06T12:00:00Z",
    "tmpf": 45.0,
    "tfs0": None,
    "tfs0_text": None,
    "tfs1": 35.0,
    "tfs1_text": "Frost",
    "tfs2": None,
    "tfs2_text": None,
    "tfs3": None,
    "tfs3_text": None,
    "pcpn": 0.0,
    "sknt": 5.0,
    "vsby": 10.0,
    "relh": 80.0,
}

# Station where all tfs sensors are None
MOCK_STATION_ALL_SENSORS_NULL = {
    "station": "RNUL",
    "name": "No Sensor Station",
    "state": "IA",
    "lat": 42.1,
    "lon": -93.6,
    "utc_valid": "2026-04-06T12:00:00Z",
    "tmpf": 50.0,
    "tfs0": None,
    "tfs0_text": None,
    "tfs1": None,
    "tfs1_text": None,
    "tfs2": None,
    "tfs2_text": None,
    "tfs3": None,
    "tfs3_text": None,
    "pcpn": 0.0,
    "sknt": 8.0,
    "vsby": 10.0,
    "relh": 55.0,
}


class _FakeClock:
    def __init__(self, start: float = 1000.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Unit conversion tests
# ---------------------------------------------------------------------------


class TestUnitConversions:
    """Fahrenheit to Celsius, knots to kph, miles to km, inches to mm."""

    def test_f_to_c_freezing(self):
        assert f_to_c(32.0) == 0.0

    def test_f_to_c_boiling(self):
        assert f_to_c(212.0) == 100.0

    def test_f_to_c_negative_40(self):
        """−40 is the same in both scales."""
        assert f_to_c(-40.0) == -40.0

    def test_f_to_c_none(self):
        assert f_to_c(None) is None

    def test_f_to_c_typical_road_temp(self):
        """38F ~= 3.3C."""
        result = f_to_c(38.0)
        assert result is not None
        assert abs(result - 3.333) < 0.01

    def test_knots_to_kph(self):
        """15 knots = 27.78 kph."""
        result = knots_to_kph(15.0)
        assert abs(result - 27.78) < 0.01

    def test_knots_to_kph_none(self):
        assert knots_to_kph(None) == 0.0

    def test_miles_to_km(self):
        """10 miles ~= 16.09 km."""
        result = miles_to_km(10.0)
        assert result is not None
        assert abs(result - 16.0934) < 0.01

    def test_miles_to_km_none(self):
        assert miles_to_km(None) is None

    def test_inches_to_mm(self):
        """1 inch = 25.4 mm."""
        assert abs(inches_to_mm(1.0) - 25.4) < 0.01

    def test_inches_to_mm_none(self):
        assert inches_to_mm(None) == 0.0


# ---------------------------------------------------------------------------
# Road condition mapping tests
# ---------------------------------------------------------------------------


class TestRoadConditionMapping:
    """IEM tfsN_text values to KiSTI standard condition strings."""

    def test_dry(self):
        assert normalize_road_condition("Dry") == "DRY"

    def test_wet(self):
        assert normalize_road_condition("Wet") == "WET"

    def test_ice(self):
        assert normalize_road_condition("Ice") == "ICY"

    def test_ice_warning(self):
        assert normalize_road_condition("Ice Warning") == "ICY"

    def test_frost(self):
        assert normalize_road_condition("Frost") == "FROSTY"

    def test_snow(self):
        assert normalize_road_condition("Snow") == "SNOWY"

    def test_slush(self):
        assert normalize_road_condition("Slush") == "SLUSHY"

    def test_black_ice(self):
        assert normalize_road_condition("Black Ice") == "ICY"

    def test_chemically_wet(self):
        assert normalize_road_condition("Chemically Wet") == "WET"

    def test_empty_string(self):
        assert normalize_road_condition("") == ""

    def test_unknown_maps_to_uppercase(self):
        """Unknown conditions fall back to uppercase."""
        assert normalize_road_condition("Standing Water") == "STANDING WATER"

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        assert normalize_road_condition("DRY") == "DRY"
        assert normalize_road_condition("dry") == "DRY"
        assert normalize_road_condition("Dry") == "DRY"


# ---------------------------------------------------------------------------
# Station parsing tests
# ---------------------------------------------------------------------------


class TestStationParsing:
    """Parse IEM JSON response into IEMStationData objects."""

    def test_parse_single_station(self):
        raw = MOCK_IEM_RESPONSE["data"][0]
        station = parse_station(raw)
        assert station.station == "RAMI4"
        assert station.name == "I-35 @ Ames"
        assert station.state == "IA"
        assert abs(station.lat - 42.034) < 0.001
        assert abs(station.lon - (-93.462)) < 0.001
        assert station.road_temp_f == 38.0
        assert station.road_condition_text == "Wet"
        assert station.air_temp_f == 45.0
        assert station.humidity_pct == 68.0
        assert station.wind_knots == 15.0
        assert station.visibility_miles == 10.0
        assert station.precipitation_in == 0.05

    def test_parse_full_response(self):
        stations = parse_stations(MOCK_IEM_RESPONSE)
        assert len(stations) == 3
        assert stations[0].station == "RAMI4"
        assert stations[1].station == "RDMI4"
        assert stations[2].station == "RDUI4"

    def test_parse_empty_response(self):
        stations = parse_stations(MOCK_IEM_EMPTY)
        assert stations == []

    def test_parse_plain_list(self):
        """Handle a plain list response (no schema/data wrapper)."""
        raw_list = MOCK_IEM_RESPONSE["data"]
        stations = parse_stations(raw_list)
        assert len(stations) == 3

    def test_sensor_fallback_tfs0_null(self):
        """When tfs0 is None, falls back to tfs1."""
        station = parse_station(MOCK_STATION_SENSOR_FALLBACK)
        assert station.road_temp_f == 35.0
        assert station.road_condition_text == "Frost"

    def test_all_sensors_null(self):
        """When all tfs sensors are None, road_temp_f is None."""
        station = parse_station(MOCK_STATION_ALL_SENSORS_NULL)
        assert station.road_temp_f is None
        assert station.road_condition_text == ""


# ---------------------------------------------------------------------------
# Nearest station by haversine tests
# ---------------------------------------------------------------------------


class TestNearestStation:
    """Find nearest IEM RWIS station from a list."""

    def test_nearest_to_des_moines(self):
        """Des Moines station is nearest when GPS is at Des Moines."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.nearest_station is not None
        assert data.nearest_station.station == "RDMI4"
        assert data.station_distance_km < 5.0

    def test_nearest_to_ames(self):
        """Ames station is nearest when GPS is near Ames."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=42.03, lon=-93.47, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.nearest_station is not None
        assert data.nearest_station.station == "RAMI4"

    def test_nearest_to_dubuque(self):
        """Dubuque station is nearest when GPS is in eastern Iowa."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=42.50, lon=-90.66, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.nearest_station is not None
        assert data.nearest_station.station == "RDUI4"


# ---------------------------------------------------------------------------
# Network switching tests
# ---------------------------------------------------------------------------


class TestNetworkSwitching:
    """State detection and network switching on GPS movement."""

    def test_iowa_network(self):
        """GPS in Iowa selects IA_RWIS network."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.network == "IA_RWIS"

    def test_state_change_updates_network(self):
        """Moving from Iowa to Minnesota switches to MN_RWIS."""
        bridge = DiffStateBridge()
        clock = _FakeClock()

        networks_requested = []

        def tracking_fetcher(url):
            networks_requested.append(url)
            return MOCK_IEM_RESPONSE

        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=tracking_fetcher,
        )
        # First poll in Iowa
        poller.poll_once()
        assert "IA_RWIS" in networks_requested[-1]

        # Move to Minnesota
        poller.update_position(44.98, -93.27)
        clock.advance(301)  # past poll interval
        poller.poll_once()
        assert "MN_RWIS" in networks_requested[-1]

    def test_source_name_updates_with_state(self):
        """source_name includes state code."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        assert poller.source_name == "IEM-IA"

    def test_outside_us_not_available(self):
        """GPS in Canada (no US state) sets available=False."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=51.05, lon=-114.07, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert not data.available


# ---------------------------------------------------------------------------
# Empty / error response handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Graceful handling of empty/error responses."""

    def test_empty_response(self):
        """Empty station list from IEM."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_EMPTY,
        )
        data = poller.poll_once()
        assert data.nearest_station is None
        assert data.station_count == 0

    def test_network_failure(self):
        """HTTP error doesn't crash -- data stays at default."""
        bridge = DiffStateBridge()
        clock = _FakeClock()

        def failing_fetcher(url):
            raise ConnectionError("No WiFi on Jetson")

        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=failing_fetcher,
        )
        data = poller.poll_once()
        assert not data.available


# ---------------------------------------------------------------------------
# Bridge integration tests
# ---------------------------------------------------------------------------


class TestBridgeIntegration:
    """Verify data is pushed to DiffStateBridge correctly."""

    def test_bridge_receives_road_condition(self):
        """Bridge is updated with road condition from nearest station."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        assert snap.drivebc_road_condition == "DRY"  # Des Moines station
        assert snap.drivebc_available is True

    def test_bridge_receives_temperatures(self):
        """Bridge gets road temp and air temp in Celsius."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        # Des Moines: tfs0=52F -> ~11.1C, tmpf=50F -> 10C
        assert snap.drivebc_road_temp_c is not None
        assert abs(snap.drivebc_road_temp_c - 11.111) < 0.1
        assert snap.drivebc_air_temp_c is not None
        assert abs(snap.drivebc_air_temp_c - 10.0) < 0.1

    def test_bridge_receives_station_name(self):
        """Bridge gets IEM-prefixed station name."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        assert snap.drivebc_station_name == "IEM: I-35 @ Des Moines"

    def test_bridge_weather_source_tagged(self):
        """road_weather_source is set to IEM-{STATE}."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        assert snap.road_weather_source == "IEM-IA"

    def test_bridge_wind_kph_converted(self):
        """Wind speed is converted from knots to kph."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        # Des Moines: 10 knots -> 18.52 kph
        assert abs(snap.drivebc_wind_kph - 18.5) < 0.1

    def test_bridge_precipitation_converted(self):
        """Precipitation is converted from inches to mm."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        # Use Ames station (has pcpn=0.05)
        poller = IEMRWISPoller(
            bridge=bridge, lat=42.03, lon=-93.47, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        poller.poll_once()
        snap = bridge.snapshot()
        # 0.05 inches = 1.27 mm
        assert abs(snap.drivebc_precipitation_mm - 1.27) < 0.01


# ---------------------------------------------------------------------------
# Poll interval / timing tests
# ---------------------------------------------------------------------------


class TestPollTiming:
    """Verify poll interval behavior."""

    def test_immediate_first_poll(self):
        """First call always polls (last_poll == 0)."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        call_count = [0]

        def counting_fetcher(url):
            call_count[0] += 1
            return MOCK_IEM_RESPONSE

        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=counting_fetcher,
        )
        poller.poll_once()
        assert call_count[0] == 1

    def test_data_snapshot_has_fetch_ts(self):
        """Data snapshot includes fetch timestamp."""
        bridge = DiffStateBridge()
        clock = _FakeClock(start=5000.0)
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.fetch_ts is not None
        assert data.fetch_ts >= 5000.0

    def test_station_count_in_data(self):
        """Data snapshot includes station count for the network."""
        bridge = DiffStateBridge()
        clock = _FakeClock()
        poller = IEMRWISPoller(
            bridge=bridge, lat=41.60, lon=-93.61, clock=clock,
            fetcher=lambda url: MOCK_IEM_RESPONSE,
        )
        data = poller.poll_once()
        assert data.station_count == 3
