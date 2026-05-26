"""Tests for Ontario 511 road event poller."""

from sensors.ontario511_weather import (
    Ontario511Data,
    Ontario511Event,
    Ontario511Poller,
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
# Mock Ontario 511 API responses
# ---------------------------------------------------------------------------

MOCK_EVENTS = [
    {
        "ID": "ON-1001",
        "RoadwayName": "QEW",
        "DirectionOfTravel": "Westbound",
        "Description": "Multi-vehicle collision blocking two lanes near Niagara Falls.",
        "Latitude": 43.09,
        "Longitude": -79.06,
        "EventType": "accidentsAndIncidents",
        "EventSubType": "collision",
        "IsFullClosure": False,
        "Severity": "Major",
        "Reported": 1712400000000,
        "LastUpdated": 1712403600000,
    },
    {
        "ID": "ON-1002",
        "RoadwayName": "Highway 401",
        "DirectionOfTravel": "Eastbound",
        "Description": "Full closure for bridge repair near Toronto.",
        "Latitude": 43.71,
        "Longitude": -79.50,
        "EventType": "closures",
        "EventSubType": "bridgeClosure",
        "IsFullClosure": True,
        "Severity": "Major",
        "Reported": 1712390000000,
        "LastUpdated": 1712403600000,
    },
    {
        "ID": "ON-1003",
        "RoadwayName": "Highway 7",
        "DirectionOfTravel": "Westbound",
        "Description": "Lane closure for road work near Peterborough.",
        "Latitude": 44.30,
        "Longitude": -78.31,
        "EventType": "roadwork",
        "EventSubType": "laneWork",
        "IsFullClosure": False,
        "Severity": "Minor",
        "Reported": 1712380000000,
        "LastUpdated": 1712403600000,
    },
    {
        # Outside Ontario bbox — South of border (USA)
        "ID": "ON-1004",
        "RoadwayName": "Highway 2",
        "DirectionOfTravel": "Southbound",
        "Description": "Minor delay near USA border.",
        "Latitude": 41.00,
        "Longitude": -79.00,
        "EventType": "generalInfo",
        "EventSubType": "delay",
        "IsFullClosure": False,
        "Severity": "Minor",
        "Reported": 1712380000000,
        "LastUpdated": 1712403600000,
    },
]

# Ontario 511 uses array of condition strings
MOCK_CONDITIONS_YEAR_ROUND = [
    {
        "Latitude": 43.10,
        "Longitude": -79.10,
        "Condition": ["Bare and dry road", "Good visibility"],
        "RoadwayName": "QEW",
    },
    {
        "Latitude": 43.70,
        "Longitude": -79.50,
        "Condition": ["Partly covered road", "Reduced visibility"],
        "RoadwayName": "Highway 401",
    },
    {
        "Latitude": 44.30,
        "Longitude": -78.30,
        "Condition": ["Ice on road"],
        "RoadwayName": "Highway 7",
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
        assert evt.road_name == "QEW"
        assert evt.description.startswith("Multi-vehicle collision")
        assert evt.latitude == 43.09
        assert evt.longitude == -79.06
        assert evt.event_type == "accidentsAndIncidents"
        assert evt.is_full_closure is False

    def test_description_truncated(self):
        """Long descriptions are truncated to 300 chars."""
        raw = {
            "Description": "X" * 500,
            "RoadwayName": "Test",
            "Latitude": 43.0,
            "Longitude": -79.0,
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
        """Events within Ontario bbox are included."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        events = _filter_events(MOCK_EVENTS, bbox)
        # 3 inside bbox (ON-1001/2/3), 1 outside (ON-1004 at lon=-80.5)
        assert len(events) == 3

    def test_event_outside_bbox_excluded(self):
        """Event south of Ontario border is outside Ontario bbox."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        events = _filter_events(MOCK_EVENTS, bbox)
        descriptions = [e.description for e in events]
        # ON-1004 should be excluded (lat=41.00 < 41.7 bbox boundary)
        assert not any("USA" in d for d in descriptions)

    def test_narrow_bbox(self):
        """Narrow bbox around Toronto only includes nearby events."""
        bbox = _parse_bbox("-80.0,43.5,-79.0,43.8")
        events = _filter_events(MOCK_EVENTS, bbox)
        # Only ON-1002 (43.71, -79.50) in range
        assert len(events) == 1

    def test_empty_events(self):
        """Empty event list returns empty."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        events = _filter_events([], bbox)
        assert events == []


# ---------------------------------------------------------------------------
# Nearest event selection
# ---------------------------------------------------------------------------


class TestNearestEvent:
    def test_finds_nearest(self):
        """Nearest event is selected by haversine distance."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        filtered = _filter_events(MOCK_EVENTS, bbox)
        nearest = _find_nearest_event(filtered, lat=43.65, lon=-79.38)
        assert nearest is not None
        assert nearest.road_name == "Highway 401"

    def test_prefers_severity_at_equal_distance(self):
        """Among events at same distance, prefer higher severity."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        filtered = _filter_events(MOCK_EVENTS, bbox)
        nearest = _find_nearest_event(filtered, lat=43.70, lon=-79.50)
        # Should pick the CLOSURE (ON-1002) over others
        assert nearest.severity == "CLOSURE"

    def test_empty_event_list(self):
        """Empty event list returns None."""
        nearest = _find_nearest_event([], lat=43.65, lon=-79.38)
        assert nearest is None

    def test_ignores_zero_coordinates(self):
        """Events with (0, 0) coordinates are skipped."""
        events = [
            Ontario511Event(road_name="A", latitude=0.0, longitude=0.0),
            Ontario511Event(road_name="B", latitude=43.65, longitude=-79.38),
        ]
        nearest = _find_nearest_event(events, lat=43.65, lon=-79.38)
        assert nearest.road_name == "B"


# ---------------------------------------------------------------------------
# Road conditions (Ontario-specific: array of condition strings)
# ---------------------------------------------------------------------------


class TestRoadConditions:
    def test_bare_and_dry_road(self):
        """'Bare and dry road' maps to DRY."""
        cond = _extract_nearest_condition(
            [{"Latitude": 43.10, "Longitude": -79.10, "Condition": ["Bare and dry road"]}],
            lat=43.10, lon=-79.10,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == "DRY"

    def test_partly_covered_road(self):
        """'Partly covered road' maps to WET."""
        cond = _extract_nearest_condition(
            [{"Latitude": 43.70, "Longitude": -79.50, "Condition": ["Partly covered road"]}],
            lat=43.70, lon=-79.50,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == "WET"

    def test_ice_on_road(self):
        """'Ice on road' maps to ICY."""
        cond = _extract_nearest_condition(
            [{"Latitude": 44.30, "Longitude": -78.30, "Condition": ["Ice on road"]}],
            lat=44.30, lon=-78.30,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == "ICY"

    def test_multiple_conditions_array(self):
        """Condition is an array — picks first mapped condition."""
        cond = _extract_nearest_condition(
            [{"Latitude": 43.10, "Longitude": -79.10, "Condition": ["Good visibility", "Bare and dry road"]}],
            lat=43.10, lon=-79.10,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == "DRY"

    def test_no_matching_conditions(self):
        """Unknown condition text returns empty."""
        cond = _extract_nearest_condition(
            [{"Latitude": 43.10, "Longitude": -79.10, "Condition": ["Unknown condition"]}],
            lat=43.10, lon=-79.10,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == ""

    def test_empty_conditions_list(self):
        """Empty conditions list returns empty."""
        cond = _extract_nearest_condition(
            [],
            lat=43.65, lon=-79.38,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == ""

    def test_nearest_by_distance(self):
        """Nearest condition by distance is selected."""
        cond = _extract_nearest_condition(
            MOCK_CONDITIONS_YEAR_ROUND,
            lat=43.10, lon=-79.10,
            bbox=_parse_bbox("-95.2,41.7,-74.3,56.9")
        )
        assert cond == "DRY"


# ---------------------------------------------------------------------------
# Malformed responses
# ---------------------------------------------------------------------------


class TestMalformedResponses:
    def test_malformed_events_list(self):
        """Non-list event response is treated as empty."""
        # Poller handles this gracefully
        poller = Ontario511Poller(clock=_FakeClock(), fetcher=lambda u: {"not": "list"})
        assert isinstance(poller._data, Ontario511Data)

    def test_malformed_conditions_list(self):
        """Non-list conditions response is treated as empty."""
        poller = Ontario511Poller(clock=_FakeClock(), fetcher=lambda u: {"not": "list"})
        assert isinstance(poller._data, Ontario511Data)

    def test_missing_latitude(self):
        """Event with missing Latitude is filtered out."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        raw = {"Longitude": -79.0, "RoadwayName": "Test", "EventType": "roadwork"}
        # _event_in_bbox returns False if lat/lon missing
        assert _event_in_bbox(raw, bbox) is False

    def test_missing_longitude(self):
        """Event with missing Longitude is filtered out."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        raw = {"Latitude": 43.0, "RoadwayName": "Test", "EventType": "roadwork"}
        assert _event_in_bbox(raw, bbox) is False

    def test_non_numeric_coordinates(self):
        """Non-numeric coordinates are ignored."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        raw = {"Latitude": "not a number", "Longitude": "also not", "EventType": "roadwork"}
        assert _event_in_bbox(raw, bbox) is False


# ---------------------------------------------------------------------------
# Bbox parsing
# ---------------------------------------------------------------------------


class TestBboxParsing:
    def test_valid_bbox(self):
        """Valid bbox string is parsed correctly."""
        bbox = _parse_bbox("-95.2,41.7,-74.3,56.9")
        assert bbox == (-95.2, 41.7, -74.3, 56.9)

    def test_bbox_with_spaces(self):
        """Bbox with spaces around commas is parsed."""
        bbox = _parse_bbox("-95.2 , 41.7 , -74.3 , 56.9")
        assert bbox == (-95.2, 41.7, -74.3, 56.9)

    def test_invalid_bbox_too_few_values(self):
        """Invalid bbox with too few values falls back to default."""
        bbox = _parse_bbox("-95.2,41.7,-74.3")
        assert bbox == (-95.2, 41.7, -74.3, 56.9)  # Ontario default

    def test_invalid_bbox_non_numeric(self):
        """Non-numeric bbox falls back to default."""
        bbox = _parse_bbox("not,a,valid,bbox")
        assert bbox == (-95.2, 41.7, -74.3, 56.9)  # Ontario default

    def test_invalid_bbox_empty_string(self):
        """Empty bbox falls back to default."""
        bbox = _parse_bbox("")
        assert bbox == (-95.2, 41.7, -74.3, 56.9)  # Ontario default


# ---------------------------------------------------------------------------
# Poller integration
# ---------------------------------------------------------------------------


class TestPollerIntegration:
    def test_poller_initializes(self):
        """Ontario511Poller initializes without crash."""
        poller = Ontario511Poller(clock=_FakeClock())
        assert poller.source_name == "511ON"
        assert isinstance(poller._data, Ontario511Data)
        assert poller._data.available is False

    def test_poll_once_returns_data(self):
        """poll_once() fetches and returns Ontario511Data."""
        def mock_fetch(url):
            if "event" in url:
                return MOCK_EVENTS
            else:
                return MOCK_CONDITIONS_YEAR_ROUND

        poller = Ontario511Poller(clock=_FakeClock(), fetcher=mock_fetch)
        data = poller.poll_once()
        assert isinstance(data, Ontario511Data)
        assert data.available is True
        assert len(data.nearby_events) == 3

    def test_poll_once_empty_response(self):
        """poll_once() handles empty responses gracefully."""
        def mock_fetch(url):
            return []

        poller = Ontario511Poller(clock=_FakeClock(), fetcher=mock_fetch)
        data = poller.poll_once()
        assert data.nearby_events == []
        assert data.road_condition == ""


# ---------------------------------------------------------------------------
# Polling intervals
# ---------------------------------------------------------------------------


class TestPollIntervals:
    def test_events_poll_interval(self):
        """Events are polled every EVENTS_POLL_S seconds."""
        assert EVENTS_POLL_S == 120

    def test_conditions_poll_interval(self):
        """Conditions are polled every CONDITIONS_POLL_S seconds."""
        assert CONDITIONS_POLL_S == 300

    def test_conditions_less_frequent_than_events(self):
        """Conditions poll less frequently than events."""
        assert CONDITIONS_POLL_S > EVENTS_POLL_S
