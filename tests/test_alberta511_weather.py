"""Tests for 511 Alberta road event poller."""

from sensors.alberta511_weather import (
    Alberta511Data,
    Alberta511Event,
    Alberta511Poller,
    _event_in_bbox,
    _extract_nearest_condition,
    _filter_events,
    _find_nearest_event,
    _map_severity,
    _parse_bbox,
    _parse_event,
    EVENTS_POLL_S,
    CONDITIONS_POLL_S,
)
from sensors.road_weather_base import RoadWeatherProvider


# ---------------------------------------------------------------------------
# Mock 511AB API responses
# ---------------------------------------------------------------------------

MOCK_EVENTS = [
    {
        "ID": "AB-1001",
        "RoadwayName": "Highway 2",
        "DirectionOfTravel": "Northbound",
        "Description": "Multi-vehicle collision blocking two lanes near Airdrie.",
        "Latitude": 51.29,
        "Longitude": -114.02,
        "EventType": "accidentsAndIncidents",
        "EventSubType": "collision",
        "IsFullClosure": False,
        "Severity": "Major",
        "Reported": 1712400000000,
        "LastUpdated": 1712403600000,
    },
    {
        "ID": "AB-1002",
        "RoadwayName": "Highway 1",
        "DirectionOfTravel": "Westbound",
        "Description": "Full closure for bridge repair near Canmore.",
        "Latitude": 51.07,
        "Longitude": -115.35,
        "EventType": "closures",
        "EventSubType": "bridgeClosure",
        "IsFullClosure": True,
        "Severity": "Major",
        "Reported": 1712390000000,
        "LastUpdated": 1712403600000,
    },
    {
        "ID": "AB-1003",
        "RoadwayName": "Highway 2",
        "DirectionOfTravel": "Southbound",
        "Description": "Lane closure for road work near Red Deer.",
        "Latitude": 52.27,
        "Longitude": -113.81,
        "EventType": "roadwork",
        "EventSubType": "laneWork",
        "IsFullClosure": False,
        "Severity": "Minor",
        "Reported": 1712380000000,
        "LastUpdated": 1712403600000,
    },
    {
        # Outside Alberta bbox — Saskatchewan border
        "ID": "AB-1004",
        "RoadwayName": "Highway 1",
        "DirectionOfTravel": "Eastbound",
        "Description": "Minor delay near Saskatchewan border.",
        "Latitude": 50.00,
        "Longitude": -109.50,
        "EventType": "generalInfo",
        "EventSubType": "delay",
        "IsFullClosure": False,
        "Severity": "Minor",
        "Reported": 1712380000000,
        "LastUpdated": 1712403600000,
    },
]

MOCK_CONDITIONS_WINTER = [
    {
        "Latitude": 51.10,
        "Longitude": -114.10,
        "RoadCondition": "Icy",
        "RoadwayName": "Highway 2",
    },
    {
        "Latitude": 52.00,
        "Longitude": -113.80,
        "RoadCondition": "Snow Covered",
        "RoadwayName": "Highway 2",
    },
]

MOCK_EVENTS_EMPTY = []
MOCK_CONDITIONS_EMPTY = []


class _FakeClock:
    def __init__(self, start: float = 1000.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Event parsing tests
# ---------------------------------------------------------------------------


class TestEventParsing:
    def test_fields_extracted(self):
        """Core fields parsed from raw event dict."""
        evt = _parse_event(MOCK_EVENTS[0])
        assert evt.road_name == "Highway 2"
        assert evt.description.startswith("Multi-vehicle collision")
        assert evt.latitude == 51.29
        assert evt.longitude == -114.02
        assert evt.event_type == "accidentsAndIncidents"
        assert evt.is_full_closure is False

    def test_description_truncated(self):
        """Long descriptions are truncated to 300 chars."""
        raw = {
            "Description": "X" * 500,
            "RoadwayName": "Test",
            "Latitude": 51.0,
            "Longitude": -114.0,
            "EventType": "generalInfo",
            "IsFullClosure": False,
        }
        evt = _parse_event(raw)
        assert len(evt.description) == 300

    def test_missing_fields_default(self):
        """Missing fields default to empty/zero."""
        evt = _parse_event({})
        assert evt.road_name == ""
        assert evt.description == ""
        assert evt.latitude == 0.0
        assert evt.longitude == 0.0
        assert evt.event_type == ""
        assert evt.is_full_closure is False


# ---------------------------------------------------------------------------
# Severity mapping tests
# ---------------------------------------------------------------------------


class TestSeverityMapping:
    def test_closures_maps_to_closure(self):
        assert _map_severity({"EventType": "closures"}) == "CLOSURE"

    def test_accidents_maps_to_major(self):
        assert _map_severity({"EventType": "accidentsAndIncidents"}) == "MAJOR"

    def test_roadwork_maps_to_minor(self):
        assert _map_severity({"EventType": "roadwork"}) == "MINOR"

    def test_general_info_maps_to_minor(self):
        assert _map_severity({"EventType": "generalInfo"}) == "MINOR"

    def test_special_events_maps_to_minor(self):
        assert _map_severity({"EventType": "specialEvents"}) == "MINOR"

    def test_restriction_maps_to_minor(self):
        assert _map_severity({"EventType": "restrictionClass"}) == "MINOR"

    def test_unknown_type_maps_to_minor(self):
        assert _map_severity({"EventType": "somethingNew"}) == "MINOR"

    def test_empty_type_maps_to_minor(self):
        assert _map_severity({}) == "MINOR"


class TestIsFullClosureOverride:
    def test_full_closure_overrides_roadwork(self):
        """IsFullClosure: true overrides any EventType to CLOSURE."""
        assert _map_severity({
            "EventType": "roadwork",
            "IsFullClosure": True,
        }) == "CLOSURE"

    def test_full_closure_overrides_general_info(self):
        assert _map_severity({
            "EventType": "generalInfo",
            "IsFullClosure": True,
        }) == "CLOSURE"

    def test_full_closure_overrides_accidents(self):
        assert _map_severity({
            "EventType": "accidentsAndIncidents",
            "IsFullClosure": True,
        }) == "CLOSURE"

    def test_false_closure_does_not_override(self):
        """IsFullClosure: false does not affect EventType mapping."""
        assert _map_severity({
            "EventType": "roadwork",
            "IsFullClosure": False,
        }) == "MINOR"


# ---------------------------------------------------------------------------
# Bbox filtering tests
# ---------------------------------------------------------------------------


class TestBboxFiltering:
    def test_events_within_bbox_included(self):
        """Events within Alberta bbox are included."""
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        events = _filter_events(MOCK_EVENTS, bbox)
        # 3 inside bbox (AB-1001/2/3), 1 outside (AB-1004 at lon=-109.5)
        assert len(events) == 3

    def test_event_outside_bbox_excluded(self):
        """Event near Saskatchewan border is outside Alberta bbox."""
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        events = _filter_events(MOCK_EVENTS, bbox)
        road_names = [e.road_name for e in events]
        # AB-1004 should be excluded (lon=-109.5 < -110.0 bbox boundary)
        descriptions = [e.description for e in events]
        assert not any("Saskatchewan" in d for d in descriptions)

    def test_narrow_bbox(self):
        """Narrow bbox around Calgary only includes nearby events."""
        bbox = _parse_bbox("-115.5,50.5,-113.5,51.5")
        events = _filter_events(MOCK_EVENTS, bbox)
        # Only AB-1001 (51.29, -114.02) and AB-1002 (51.07, -115.35) in range
        assert len(events) == 2

    def test_empty_events(self):
        """Empty event list returns empty."""
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        events = _filter_events([], bbox)
        assert events == []


# ---------------------------------------------------------------------------
# Nearest event tests
# ---------------------------------------------------------------------------


class TestNearestEvent:
    def test_finds_nearest_to_calgary(self):
        """Nearest event to Calgary is the accident on Hwy 2 (Airdrie)."""
        events = [_parse_event(e) for e in MOCK_EVENTS[:3]]
        nearest = _find_nearest_event(events, 51.05, -114.07)
        assert nearest is not None
        assert nearest.road_name == "Highway 2"
        assert nearest.event_type == "accidentsAndIncidents"

    def test_finds_nearest_to_canmore(self):
        """Nearest event to Canmore is the closure on Hwy 1."""
        events = [_parse_event(e) for e in MOCK_EVENTS[:3]]
        nearest = _find_nearest_event(events, 51.08, -115.34)
        assert nearest is not None
        assert nearest.road_name == "Highway 1"
        assert nearest.event_type == "closures"

    def test_empty_events_returns_none(self):
        """No events -> None."""
        assert _find_nearest_event([], 51.05, -114.07) is None

    def test_events_without_coords(self):
        """Events with zero coords still return something if they exist."""
        events = [Alberta511Event(
            severity="MINOR",
            description="No location",
            latitude=0.0,
            longitude=0.0,
        )]
        result = _find_nearest_event(events, 51.05, -114.07)
        # Falls back to first event since no coords to score
        assert result is not None
        assert result.description == "No location"


# ---------------------------------------------------------------------------
# Road condition parsing tests
# ---------------------------------------------------------------------------


class TestRoadConditions:
    def test_nearest_condition_winter(self):
        """Finds nearest road condition from winter data."""
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        cond = _extract_nearest_condition(
            MOCK_CONDITIONS_WINTER, 51.05, -114.07, bbox,
        )
        assert cond == "ICY"  # nearest to Calgary

    def test_empty_conditions_returns_empty(self):
        """Empty conditions (spring/summer) returns empty string."""
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        cond = _extract_nearest_condition([], 51.05, -114.07, bbox)
        assert cond == ""


# ---------------------------------------------------------------------------
# Empty / malformed response handling
# ---------------------------------------------------------------------------


class TestMalformedResponses:
    def test_malformed_event_missing_coords(self):
        """Event missing Latitude/Longitude excluded by bbox filter."""
        events = [{"EventType": "closures", "Description": "No coords"}]
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        result = _filter_events(events, bbox)
        assert result == []

    def test_malformed_event_bad_lat(self):
        """Event with non-numeric latitude excluded."""
        events = [{
            "EventType": "closures",
            "Description": "Bad lat",
            "Latitude": "not-a-number",
            "Longitude": -114.0,
        }]
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        result = _filter_events(events, bbox)
        assert result == []

    def test_non_list_response_handled(self):
        """Fetcher returning non-list is handled gracefully."""
        clock = _FakeClock()

        def fetcher(url):
            return {"error": "something unexpected"}

        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()
        # available because _update was called even with empty parsed lists
        assert data.available
        assert data.nearby_events == []
        assert data.road_condition == ""


# ---------------------------------------------------------------------------
# Bbox parsing tests
# ---------------------------------------------------------------------------


class TestBboxParsing:
    def test_valid_bbox(self):
        bbox = _parse_bbox("-120.0,49.0,-110.0,60.0")
        assert bbox == (-120.0, 49.0, -110.0, 60.0)

    def test_bbox_with_spaces(self):
        bbox = _parse_bbox("-120.0, 49.0, -110.0, 60.0")
        assert bbox == (-120.0, 49.0, -110.0, 60.0)

    def test_invalid_bbox_uses_default(self):
        bbox = _parse_bbox("bad,data")
        assert bbox == (-120.0, 49.0, -110.0, 60.0)


# ---------------------------------------------------------------------------
# Poller integration tests (mock HTTP)
# ---------------------------------------------------------------------------


class TestPollerIntegration:
    @staticmethod
    def _make_fetcher(events_response, conditions_response):
        """Create a mock fetcher returning canned data."""
        def mock_fetch(url):
            if "event" in url:
                return events_response
            if "roadconditions" in url:
                return conditions_response
            raise ValueError(f"Unexpected URL: {url}")
        return mock_fetch

    def test_full_poll(self):
        """Full poll returns filtered events and conditions."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_EVENTS, MOCK_CONDITIONS_WINTER)
        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert len(data.nearby_events) == 3  # 3 inside Alberta bbox
        assert data.road_condition == "ICY"
        assert data.fetch_ts == clock()

    def test_empty_events_no_crash(self):
        """Empty events doesn't crash."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_EVENTS_EMPTY, MOCK_CONDITIONS_WINTER)
        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.nearby_events == []
        assert data.road_condition == "ICY"

    def test_empty_conditions_summer(self):
        """Empty conditions (summer) returns empty string."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_EVENTS, MOCK_CONDITIONS_EMPTY)
        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )
        data = poller.poll_once()

        assert data.available
        assert data.road_condition == ""
        assert len(data.nearby_events) == 3

    def test_network_failure_stays_unavailable(self):
        """Complete network failure keeps data.available = False."""
        clock = _FakeClock()

        def failing_fetch(url):
            raise ConnectionError("No WiFi on Jetson")

        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=failing_fetch,
        )
        data = poller.poll_once()
        assert not data.available

    def test_partial_failure_events_only(self):
        """If events succeed but conditions fail, events still available."""
        clock = _FakeClock()

        def partial_fetch(url):
            if "event" in url:
                return MOCK_EVENTS
            raise ConnectionError("Conditions API down")

        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=partial_fetch,
        )
        data = poller.poll_once()

        assert data.available
        assert len(data.nearby_events) == 3
        assert data.road_condition == ""  # default

    def test_partial_failure_conditions_only(self):
        """If conditions succeed but events fail, conditions still available."""
        clock = _FakeClock()

        def partial_fetch(url):
            if "roadconditions" in url:
                return MOCK_CONDITIONS_WINTER
            raise ConnectionError("Events API down")

        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=partial_fetch,
        )
        data = poller.poll_once()

        assert data.available
        assert data.road_condition == "ICY"
        assert data.nearby_events == []

    def test_update_position(self):
        """Updating GPS position changes which condition is nearest."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_EVENTS_EMPTY, MOCK_CONDITIONS_WINTER)
        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )

        # First poll near Calgary — ICY is nearest
        data1 = poller.poll_once()
        assert data1.road_condition == "ICY"

        # Move near Red Deer — Snow Covered is nearest
        poller.update_position(52.00, -113.80)
        data2 = poller.poll_once()
        assert data2.road_condition == "SNOW COVERED"

    def test_thread_safety_data_property(self):
        """Data property returns under lock."""
        clock = _FakeClock()
        fetcher = self._make_fetcher(MOCK_EVENTS, MOCK_CONDITIONS_EMPTY)
        poller = Alberta511Poller(
            bridge=None, lat=51.05, lon=-114.07,
            clock=clock, fetcher=fetcher,
        )
        poller.poll_once()
        snap1 = poller.data
        snap2 = poller.data
        assert snap1.available == snap2.available
        assert len(snap1.nearby_events) == len(snap2.nearby_events)

    def test_default_constructor(self):
        """Default constructor uses Calgary defaults."""
        poller = Alberta511Poller(bridge=None)
        assert poller._lat == 51.05
        assert poller._lon == -114.07

    def test_source_name(self):
        """Source name is 511AB."""
        poller = Alberta511Poller(bridge=None)
        assert poller.source_name == "511AB"


# ---------------------------------------------------------------------------
# Poll interval tests
# ---------------------------------------------------------------------------


class TestPollIntervals:
    def test_events_poll_interval(self):
        """Events poll every 2 minutes."""
        assert EVENTS_POLL_S == 120

    def test_conditions_poll_interval(self):
        """Conditions poll every 5 minutes."""
        assert CONDITIONS_POLL_S == 300
