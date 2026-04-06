"""Tests for DriveBC road weather integration."""

from sensors.drivebc_weather import (
    DriveBCData,
    DriveBCEvent,
    DriveBCPoller,
    haversine_km,
    extract_highway,
    _find_nearest_station,
    _filter_events,
    _parse_bbox,
    _normalize_severity,
    _station_coords,
    _road_condition,
)


# ---------------------------------------------------------------------------
# Mock DriveBC API responses
# ---------------------------------------------------------------------------

MOCK_RWIS_STATIONS = [
    {
        "geometry": {"type": "Point", "coordinates": [-122.80, 49.28]},
        "properties": {
            "station_name": "Port Mann Bridge",
            "road_condition": "WET",
            "road_temperature": 5.1,
            "air_temperature": 7.3,
            "precipitation": 1.2,
            "wind_speed": 22.0,
            "wind_direction": "SW",
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-121.50, 49.10]},
        "properties": {
            "station_name": "Coquihalla Summit",
            "road_condition": "SNOWY",
            "road_temperature": -6.0,
            "air_temperature": -8.2,
            "precipitation": 4.5,
            "wind_speed": 55.0,
            "wind_direction": "N",
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-123.10, 49.30]},
        "properties": {
            "station_name": "Lions Gate Bridge",
            "road_condition": "DRY",
            "road_temperature": 8.0,
            "air_temperature": 10.1,
            "precipitation": 0.0,
            "wind_speed": 12.0,
            "wind_direction": "W",
        },
    },
]

MOCK_RWIS_EMPTY = []

MOCK_EVENTS = [
    {
        "severity": "MAJOR",
        "event_type": "INCIDENT",
        "description": "Multi-vehicle accident blocking two lanes.",
        "route": "Highway 1",
        "display_category": "majorEvents",
        "latitude": 49.25,
        "longitude": -122.90,
    },
    {
        "severity": "CLOSURE",
        "event_type": "CONSTRUCTION",
        "description": "Full road closure for bridge maintenance.",
        "route": "Highway 99",
        "display_category": "closures",
        "latitude": 49.15,
        "longitude": -122.50,
    },
    {
        # Outside Metro Vancouver bbox — should be filtered out
        "severity": "MINOR",
        "event_type": "DELAY",
        "description": "Minor delay near Kamloops.",
        "route": "Highway 5",
        "display_category": "minorEvents",
        "latitude": 50.68,
        "longitude": -120.33,
    },
]

MOCK_EVENTS_EMPTY = []


class _FakeClock:
    def __init__(self, start: float = 1000.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Haversine distance tests
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_zero_distance(self):
        """Same point should be ~0 km."""
        assert haversine_km(49.28, -122.79, 49.28, -122.79) < 0.001

    def test_known_distance(self):
        """Vancouver to Coquihalla Summit is ~150 km."""
        dist = haversine_km(49.28, -123.12, 49.38, -121.06)
        assert 140 < dist < 200

    def test_short_distance(self):
        """Coquitlam to Port Mann Bridge is ~2 km."""
        dist = haversine_km(49.28, -122.79, 49.28, -122.80)
        assert 0.1 < dist < 5.0

    def test_symmetry(self):
        """Distance A->B == distance B->A."""
        d1 = haversine_km(49.28, -122.79, 50.00, -121.00)
        d2 = haversine_km(50.00, -121.00, 49.28, -122.79)
        assert abs(d1 - d2) < 0.01

    def test_antipodal(self):
        """Opposite sides of Earth should be ~20,000 km."""
        dist = haversine_km(0.0, 0.0, 0.0, 180.0)
        assert 19000 < dist < 21000


# ---------------------------------------------------------------------------
# Nearest station selection tests
# ---------------------------------------------------------------------------


class TestNearestStation:
    def test_finds_nearest(self):
        """Nearest station to Coquitlam is Port Mann Bridge."""
        result = _find_nearest_station(MOCK_RWIS_STATIONS, 49.28, -122.79)
        assert result is not None
        station, dist_km = result
        assert station["properties"]["station_name"] == "Port Mann Bridge"
        assert dist_km < 5.0

    def test_finds_nearest_different_position(self):
        """Nearest station to downtown Vancouver is Lions Gate Bridge."""
        result = _find_nearest_station(MOCK_RWIS_STATIONS, 49.30, -123.12)
        assert result is not None
        station, dist_km = result
        assert station["properties"]["station_name"] == "Lions Gate Bridge"

    def test_empty_stations_returns_none(self):
        """No stations -> None."""
        result = _find_nearest_station([], 49.28, -122.79)
        assert result is None

    def test_stations_without_coords_skipped(self):
        """Stations missing geometry are skipped gracefully."""
        broken_stations = [
            {"properties": {"station_name": "No coords"}},
            MOCK_RWIS_STATIONS[0],
        ]
        result = _find_nearest_station(broken_stations, 49.28, -122.79)
        assert result is not None
        station, _ = result
        assert station["properties"]["station_name"] == "Port Mann Bridge"

    def test_all_stations_broken_returns_none(self):
        """All stations missing coords -> None."""
        broken = [
            {"properties": {"station_name": "Broken A"}},
            {"properties": {"station_name": "Broken B"}},
        ]
        result = _find_nearest_station(broken, 49.28, -122.79)
        assert result is None


# ---------------------------------------------------------------------------
# Station coordinate extraction tests
# ---------------------------------------------------------------------------


class TestStationCoords:
    def test_geojson_format(self):
        """GeoJSON [lon, lat] is parsed correctly."""
        station = {"geometry": {"coordinates": [-122.80, 49.28]}}
        coords = _station_coords(station)
        assert coords is not None
        lat, lon = coords
        assert abs(lat - 49.28) < 0.01
        assert abs(lon - (-122.80)) < 0.01

    def test_flat_properties(self):
        """Flat lat/lon in properties."""
        station = {"properties": {"latitude": 49.28, "longitude": -122.80}}
        coords = _station_coords(station)
        assert coords is not None
        lat, lon = coords
        assert abs(lat - 49.28) < 0.01

    def test_flat_top_level(self):
        """Flat lat/lon at top level (no properties wrapper)."""
        station = {"latitude": 49.28, "longitude": -122.80}
        coords = _station_coords(station)
        assert coords is not None

    def test_missing_coords_returns_none(self):
        """Station with no geometry or lat/lon returns None."""
        station = {"properties": {"name": "No location"}}
        assert _station_coords(station) is None


# ---------------------------------------------------------------------------
# Event filtering tests
# ---------------------------------------------------------------------------


class TestEventFiltering:
    def test_filters_within_bbox(self):
        """Events within Metro Vancouver bbox are included."""
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        events = _filter_events(MOCK_EVENTS, bbox)
        # 2 inside bbox, 1 outside (Kamloops)
        assert len(events) == 2

    def test_event_outside_bbox_excluded(self):
        """Kamloops event is outside Metro Vancouver bbox."""
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        events = _filter_events(MOCK_EVENTS, bbox)
        names = [e.road_name for e in events]
        assert "Highway 5" not in names

    def test_empty_events(self):
        """Empty event list returns empty."""
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        events = _filter_events([], bbox)
        assert events == []

    def test_event_properties_mapped(self):
        """Event fields are mapped correctly to DriveBCEvent."""
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        events = _filter_events(MOCK_EVENTS, bbox)
        # Find the INCIDENT event
        incident = [e for e in events if e.event_type == "INCIDENT"]
        assert len(incident) == 1
        assert incident[0].severity == "MAJOR"
        assert incident[0].road_name == "Highway 1"
        assert "Multi-vehicle" in incident[0].description

    def test_event_with_head_tail_points(self):
        """Events with head/tail point format are detected."""
        events = [
            {
                "severity": "MINOR",
                "event_type": "DELAY",
                "description": "Slow traffic.",
                "route": "Highway 7",
                "display_category": "minorEvents",
                "head": {"latitude": 49.25, "longitude": -122.50},
                "tail": {"latitude": 49.20, "longitude": -122.60},
            },
        ]
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        result = _filter_events(events, bbox)
        assert len(result) == 1

    def test_description_truncated(self):
        """Long descriptions are truncated to 300 chars."""
        events = [
            {
                "severity": "MINOR",
                "event_type": "INFO",
                "description": "X" * 500,
                "route": "Highway 1",
                "display_category": "info",
                "latitude": 49.25,
                "longitude": -122.50,
            },
        ]
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        result = _filter_events(events, bbox)
        assert len(result[0].description) == 300


# ---------------------------------------------------------------------------
# Severity normalization tests
# ---------------------------------------------------------------------------


class TestSeverityNormalization:
    def test_closure(self):
        assert _normalize_severity({"severity": "CLOSURE"}) == "CLOSURE"

    def test_closed_maps_to_closure(self):
        assert _normalize_severity({"severity": "CLOSED"}) == "CLOSURE"

    def test_major(self):
        assert _normalize_severity({"severity": "MAJOR"}) == "MAJOR"

    def test_high_maps_to_major(self):
        assert _normalize_severity({"severity": "HIGH"}) == "MAJOR"

    def test_unknown_maps_to_minor(self):
        assert _normalize_severity({"severity": "LOW"}) == "MINOR"

    def test_empty_maps_to_minor(self):
        assert _normalize_severity({}) == "MINOR"

    def test_event_type_closure_override(self):
        """If event_type contains CLOSURE, severity is CLOSURE."""
        assert _normalize_severity(
            {"severity": "MINOR", "event_type": "ROAD_CLOSURE"}
        ) == "CLOSURE"


# ---------------------------------------------------------------------------
# Road condition extraction tests
# ---------------------------------------------------------------------------


class TestRoadCondition:
    def test_extracts_from_properties(self):
        station = {"properties": {"road_condition": "icy"}}
        assert _road_condition(station) == "ICY"

    def test_uppercase_normalization(self):
        station = {"properties": {"road_condition": "Wet"}}
        assert _road_condition(station) == "WET"

    def test_camelcase_key(self):
        station = {"properties": {"roadCondition": "SNOWY"}}
        assert _road_condition(station) == "SNOWY"

    def test_missing_returns_empty(self):
        station = {"properties": {}}
        assert _road_condition(station) == ""


# ---------------------------------------------------------------------------
# Bbox parsing tests
# ---------------------------------------------------------------------------


class TestBboxParsing:
    def test_valid_bbox(self):
        bbox = _parse_bbox("-123.2,49.1,-122.0,49.5")
        assert bbox == (-123.2, 49.1, -122.0, 49.5)

    def test_bbox_with_spaces(self):
        bbox = _parse_bbox("-123.2, 49.1, -122.0, 49.5")
        assert bbox == (-123.2, 49.1, -122.0, 49.5)

    def test_invalid_bbox_uses_default(self):
        bbox = _parse_bbox("bad,data")
        # Falls back to Metro Vancouver default
        assert bbox == (-123.2, 49.1, -122.0, 49.5)


# ---------------------------------------------------------------------------
# Poller integration tests (mock HTTP)
# ---------------------------------------------------------------------------


class TestPollerIntegration:
    def _make_fetcher(self, rwis_response, events_response):
        """Create a mock fetcher returning canned data."""
        def mock_fetch(url):
            if "weather/current" in url:
                return rwis_response
            if "events" in url:
                return events_response
            raise ValueError(f"Unexpected URL: {url}")
        return mock_fetch

    def test_full_poll(self):
        """Full poll returns nearest station and filtered events."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_STATIONS, MOCK_EVENTS)
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == "Port Mann Bridge"
        assert data.road_condition == "WET"
        assert data.road_temperature_c == 5.1
        assert data.air_temperature_c == 7.3
        assert data.precipitation_mm == 1.2
        assert data.wind_speed_kph == 22.0
        assert data.wind_direction == "SW"
        assert data.station_distance_km < 5.0
        assert len(data.nearby_events) == 2
        assert data.fetch_ts == clock()

    def test_empty_rwis_no_crash(self):
        """Empty RWIS response doesn't crash — station fields stay default."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_EMPTY, MOCK_EVENTS)
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == ""
        assert data.road_condition == ""
        assert len(data.nearby_events) == 2

    def test_empty_events(self):
        """Empty events list returns no nearby events."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_STATIONS, MOCK_EVENTS_EMPTY)
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == "Port Mann Bridge"
        assert data.nearby_events == []

    def test_network_failure_stays_unavailable(self):
        """Complete network failure keeps data.available = False."""
        clock = _FakeClock()

        def failing_fetch(url):
            raise ConnectionError("No WiFi on Jetson")

        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=failing_fetch,
        )
        data = poller.poll_once()

        assert not data.available

    def test_partial_failure_rwis_only(self):
        """If RWIS succeeds but events fail, RWIS data still available."""
        clock = _FakeClock()

        def partial_fetch(url):
            if "weather/current" in url:
                return MOCK_RWIS_STATIONS
            raise ConnectionError("Events API down")

        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=partial_fetch,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == "Port Mann Bridge"
        assert data.nearby_events == []  # default empty

    def test_partial_failure_events_only(self):
        """If events succeed but RWIS fails, events still available."""
        clock = _FakeClock()

        def partial_fetch(url):
            if "events" in url:
                return MOCK_EVENTS
            raise ConnectionError("RWIS API down")

        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=partial_fetch,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == ""  # not updated
        assert len(data.nearby_events) == 2

    def test_thread_safety_data_property(self):
        """Data property returns a snapshot, not a reference that mutates."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_STATIONS, MOCK_EVENTS)
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        poller.poll_once()
        snap1 = poller.data
        assert snap1.road_condition == "WET"

        # The data property reads under lock — verify it doesn't throw
        snap2 = poller.data
        assert snap2.road_condition == snap1.road_condition

    def test_update_position(self):
        """Updating GPS position changes nearest station selection."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_STATIONS, MOCK_EVENTS_EMPTY)
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )

        # First poll near Coquitlam
        data1 = poller.poll_once()
        assert data1.nearest_station_name == "Port Mann Bridge"

        # Move to downtown Vancouver
        poller.update_position(49.30, -123.12)
        data2 = poller.poll_once()
        assert data2.nearest_station_name == "Lions Gate Bridge"

    def test_geojson_wrapper_response(self):
        """API returning {features: [...]} wrapper is handled."""
        clock = _FakeClock()
        wrapped = {"features": MOCK_RWIS_STATIONS}
        fetcher = self._make_fetcher(wrapped, {"events": MOCK_EVENTS})
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearest_station_name == "Port Mann Bridge"
        assert len(data.nearby_events) == 2

    def test_default_constructor(self):
        """Default constructor uses Coquitlam defaults."""
        poller = DriveBCPoller()
        assert poller._lat == 49.28
        assert poller._lon == -122.79


# ---------------------------------------------------------------------------
# Highway auto-detect tests
# ---------------------------------------------------------------------------

# Stations with location_description containing highway info
MOCK_HWY_STATIONS = [
    {
        "geometry": {"type": "Point", "coordinates": [-122.75, 49.27]},
        "weather_station_name": "Port Mann Bridge Mid Span",
        "location_description": "Hwy 1, at Port Mann Bridge",
        "properties": {
            "road_condition": "WET",
            "road_temperature": 6.0,
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-122.70, 49.26]},
        "weather_station_name": "Langley Bypass",
        "location_description": "Hwy 1, near 200th St",
        "properties": {
            "road_condition": "DRY",
            "road_temperature": 8.0,
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-122.80, 49.29]},
        "weather_station_name": "Lougheed Hwy at Westwood",
        "location_description": "Hwy 7, at Westwood St",
        "properties": {
            "road_condition": "DRY",
            "road_temperature": 9.0,
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-122.85, 49.22]},
        "weather_station_name": "Alex Fraser Bridge",
        "location_description": "Hwy 91, at Alex Fraser Bridge",
        "properties": {
            "road_condition": "WET",
            "road_temperature": 5.5,
        },
    },
    {
        "geometry": {"type": "Point", "coordinates": [-122.60, 49.25]},
        "weather_station_name": "Langley Freeway",
        "location_description": "Hwy 1, near 232nd St",
        "properties": {
            "road_condition": "DRY",
            "road_temperature": 7.5,
        },
    },
]


class TestHighwayAutoDetect:
    @staticmethod
    def _make_fetcher(stations, events):
        def fetcher(url):
            if "weather" in url:
                return stations
            return events
        return fetcher

    def test_auto_detect_hwy1_from_nearest(self):
        """Near Port Mann, 3 of 5 nearest stations are on Hwy 1."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_HWY_STATIONS, [])
        poller = DriveBCPoller(
            lat=49.27, lon=-122.75, clock=clock, fetcher=fetcher,
        )
        poller.poll_once()  # loads stations
        hwy = poller.auto_detect_highway()
        assert hwy == "1"

    def test_auto_detect_hwy7_when_closer(self):
        """Near Lougheed Hwy, station on Hwy 7 is closest."""
        clock = _FakeClock()
        # Only Hwy 7 and Hwy 91 stations nearby
        stations = [MOCK_HWY_STATIONS[2], MOCK_HWY_STATIONS[3]]
        fetcher = self._make_fetcher(stations, [])
        poller = DriveBCPoller(
            lat=49.29, lon=-122.80, clock=clock, fetcher=fetcher,
        )
        poller.poll_once()
        hwy = poller.auto_detect_highway()
        assert hwy == "7"

    def test_auto_detect_empty_without_poll(self):
        """Without polling, no stations cached — returns empty."""
        clock = _FakeClock()
        fetcher = self._make_fetcher([], [])
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        hwy = poller.auto_detect_highway()
        assert hwy == ""

    def test_auto_detect_no_highway_in_description(self):
        """Stations without highway info return empty."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_RWIS_STATIONS, [])
        poller = DriveBCPoller(
            lat=49.28, lon=-122.79, clock=clock, fetcher=fetcher,
        )
        poller.poll_once()
        hwy = poller.auto_detect_highway()
        assert hwy == ""

    def test_detected_highway_property(self):
        """detected_highway returns current highway setting."""
        poller = DriveBCPoller(highway="99")
        assert poller.detected_highway == "99"
        poller.update_highway("1")
        assert poller.detected_highway == "1"

    def test_extract_highway_patterns(self):
        """extract_highway handles various highway name formats."""
        assert extract_highway("Hwy 1, at Port Mann") == "1"
        assert extract_highway("Highway 99 near tunnel") == "99"
        assert extract_highway("Hwy #7 at Westwood") == "7"
        assert extract_highway("No highway here") == ""
        assert extract_highway("") == ""
