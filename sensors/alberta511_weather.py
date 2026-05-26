"""KiSTI — 511 Alberta Road Event Poller

Polls 511.alberta.ca for real-time road events (closures, incidents,
construction) and winter road conditions along the driving route.

Runs as a background daemon thread via RoadWeatherProvider base class.
Data is pushed into DiffStateBridge via update_drivebc() for display
on the QPainter UI.

API: 511.alberta.ca (Castle Rock platform, free, no auth)
  - /api/v2/get/event            — province-wide road events (year-round)
  - /api/v2/get/roadconditions   — road conditions (winter only, empty in spring/summer)

Response is a flat JSON array (not GeoJSON). Client-side bbox filtering required.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sensors.road_weather_base import RoadWeatherProvider

if TYPE_CHECKING:
    from model.vehicle_state import DiffStateBridge

log = logging.getLogger("kisti.sensors.alberta511_weather")

EVENTS_URL = "https://511.alberta.ca/api/v2/get/event"
CONDITIONS_URL = "https://511.alberta.ca/api/v2/get/roadconditions"

# Polling intervals
EVENTS_POLL_S = 120     # 2 minutes — events change frequently
CONDITIONS_POLL_S = 300  # 5 minutes — road conditions update slowly

# Default location — Calgary, AB
DEFAULT_LAT = float(os.environ.get("AB511_LAT", "51.05"))
DEFAULT_LON = float(os.environ.get("AB511_LON", "-114.07"))

# Default bbox — Alberta province
DEFAULT_BBOX = os.environ.get("AB511_BBOX", "-120.0,49.0,-110.0,60.0")

# Severity ordering for selecting the worst event
_SEVERITY_RANK = {"CLOSURE": 3, "MAJOR": 2, "MINOR": 1, "": 0}

# EventType → severity mapping
_EVENT_TYPE_SEVERITY = {
    "closures": "CLOSURE",
    "accidentsAndIncidents": "MAJOR",
    "roadwork": "MINOR",
    "generalInfo": "MINOR",
    "specialEvents": "MINOR",
    "restrictionClass": "MINOR",
}


@dataclass
class Alberta511Event:
    """A road event from 511 Alberta."""
    severity: str = ""           # CLOSURE / MAJOR / MINOR
    event_type: str = ""         # closures, roadwork, accidentsAndIncidents, etc.
    description: str = ""        # Full text (Description field)
    road_name: str = ""          # RoadwayName
    latitude: float = 0.0
    longitude: float = 0.0
    is_full_closure: bool = False


@dataclass
class Alberta511Data:
    """Snapshot of latest 511 Alberta road weather data."""
    nearby_events: list[Alberta511Event] = field(default_factory=list)
    road_condition: str = ""     # From roadconditions endpoint (winter only)
    available: bool = False
    fetch_ts: float | None = None


class Alberta511Poller(RoadWeatherProvider):
    """Background poller for 511 Alberta road events and conditions.

    Subclasses RoadWeatherProvider for lifecycle, bridge integration,
    and haversine. Polls two endpoints: events (2 min) and road
    conditions (5 min, winter only).

    Pass ``clock`` and ``fetcher`` to override for testing.
    """

    def __init__(
        self,
        bridge: DiffStateBridge | None = None,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        bbox: str = DEFAULT_BBOX,
        clock=None,
        fetcher=None,
    ) -> None:
        # Allow None bridge for standalone/test usage
        if bridge is not None:
            super().__init__(bridge=bridge, lat=lat, lon=lon, bbox=bbox,
                             clock=clock, fetcher=fetcher)
        else:
            # Lightweight init for testing without a bridge
            self._bridge = None  # type: ignore[assignment]
            self._lat = lat
            self._lon = lon
            self._bbox = bbox
            self._clock = clock or time.monotonic
            self._fetcher = fetcher or self._default_fetch
            self._stop = __import__("threading").Event()
            self._thread = None
            self._lock = __import__("threading").Lock()

        self.source_name = "511AB"
        self._bbox_parsed = _parse_bbox(bbox)
        self._heading: float | None = None
        self._data = Alberta511Data()

    @property
    def data(self) -> Alberta511Data:
        """Thread-safe read of latest 511AB data."""
        with self._lock:
            return self._data

    def update_heading(self, heading_deg: float) -> None:
        """Update GPS heading (0=N, 90=E) for future direction filtering."""
        self._heading = heading_deg

    def poll_once(self) -> Alberta511Data:
        """Synchronous single poll — for testing or manual refresh."""
        events = self._fetch_events()
        conditions = self._fetch_conditions()
        self._update(events, conditions)
        return self.data

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Main polling loop — runs in background thread."""
        last_events = 0.0
        last_conditions = 0.0

        while not self._stop.is_set():
            now = self._clock()

            events = None
            conditions = None

            if now - last_events >= EVENTS_POLL_S or last_events == 0.0:
                events = self._fetch_events()
                last_events = now

            if now - last_conditions >= CONDITIONS_POLL_S or last_conditions == 0.0:
                conditions = self._fetch_conditions()
                last_conditions = now

            if events is not None or conditions is not None:
                self._update(events, conditions)

            # Sleep in 5s chunks so stop() is responsive
            for _ in range(12):  # ~60s total
                if self._stop.is_set():
                    return
                self._stop.wait(5.0)

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    def _fetch_events(self) -> list[dict] | None:
        """Fetch all province-wide road events."""
        try:
            data = self._fetcher(EVENTS_URL)
            events = data if isinstance(data, list) else []
            log.info("511AB events: %d total", len(events))
            return events
        except Exception as exc:
            log.debug("511AB events fetch failed: %s", exc)
            return None

    def _fetch_conditions(self) -> list[dict] | None:
        """Fetch road conditions (winter only — empty in spring/summer)."""
        try:
            data = self._fetcher(CONDITIONS_URL)
            conditions = data if isinstance(data, list) else []
            log.info("511AB conditions: %d segments", len(conditions))
            return conditions
        except Exception as exc:
            log.debug("511AB conditions fetch failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Data update
    # ------------------------------------------------------------------

    def _update(
        self,
        events: list[dict] | None,
        conditions: list[dict] | None,
    ) -> None:
        """Merge new data into the shared snapshot and push to bridge."""
        with self._lock:
            now = self._clock()

            if events is not None:
                parsed = _filter_events(events, self._bbox_parsed)
                self._data.nearby_events = parsed

            if conditions is not None:
                self._data.road_condition = _extract_nearest_condition(
                    conditions, self._lat, self._lon, self._bbox_parsed,
                )

            if events is not None or conditions is not None:
                self._data.fetch_ts = now
                self._data.available = True

            # Push to bridge if available
            if self._bridge is not None and self._data.available:
                nearby = self._data.nearby_events
                # Find nearest event
                nearest = _find_nearest_event(nearby, self._lat, self._lon)
                if nearest:
                    evt_text = nearest.description[:200]
                    evt_sev = nearest.severity
                    station_name = f"511AB: {nearest.road_name}" if nearest.road_name else "511AB"
                    dist = self.haversine_km(
                        self._lat, self._lon,
                        nearest.latitude, nearest.longitude,
                    )
                else:
                    evt_text = ""
                    evt_sev = ""
                    station_name = ""
                    dist = 99.0

                age = (now - self._data.fetch_ts) if self._data.fetch_ts else 0.0

                self._push_to_bridge(
                    road_condition=self._data.road_condition,
                    road_temp_c=None,
                    station_name=station_name,
                    station_distance_km=round(dist, 1),
                    precipitation_mm=0.0,
                    wind_kph=0.0,
                    event_count=len(nearby),
                    event_text=evt_text,
                    event_severity=evt_sev,
                    data_age_s=age,
                    air_temp_c=None,
                )


# ---------------------------------------------------------------------------
# Bbox parsing
# ---------------------------------------------------------------------------

def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """Parse 'lon_min,lat_min,lon_max,lat_max' into tuple."""
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Expected 4 values, got {len(parts)}")
        return (parts[0], parts[1], parts[2], parts[3])
    except (ValueError, TypeError):
        log.warning("Invalid bbox %r, using Alberta default", bbox)
        return (-120.0, 49.0, -110.0, 60.0)


# ---------------------------------------------------------------------------
# Event parsing and filtering
# ---------------------------------------------------------------------------

def _event_in_bbox(
    event: dict,
    bbox: tuple[float, float, float, float],
) -> bool:
    """Check if an event's Latitude/Longitude falls within the bbox."""
    lon_min, lat_min, lon_max, lat_max = bbox

    lat = event.get("Latitude")
    lon = event.get("Longitude")
    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            return lon_min <= lon_f <= lon_max and lat_min <= lat_f <= lat_max
        except (TypeError, ValueError):
            pass

    return False


def _map_severity(event: dict) -> str:
    """Map 511AB EventType to CLOSURE/MAJOR/MINOR.

    IsFullClosure: true always overrides to CLOSURE.
    """
    if event.get("IsFullClosure"):
        return "CLOSURE"

    event_type = event.get("EventType", "")
    return _EVENT_TYPE_SEVERITY.get(event_type, "MINOR")


def _parse_event(event: dict) -> Alberta511Event:
    """Parse a raw 511AB event dict into Alberta511Event."""
    return Alberta511Event(
        severity=_map_severity(event),
        event_type=event.get("EventType", ""),
        description=str(event.get("Description", ""))[:300],
        road_name=str(event.get("RoadwayName", "")),
        latitude=_safe_float(event.get("Latitude"), 0.0),
        longitude=_safe_float(event.get("Longitude"), 0.0),
        is_full_closure=bool(event.get("IsFullClosure", False)),
    )


def _filter_events(
    events: list[dict],
    bbox: tuple[float, float, float, float],
) -> list[Alberta511Event]:
    """Filter events to bbox and parse into Alberta511Event."""
    result: list[Alberta511Event] = []
    for e in events:
        if not _event_in_bbox(e, bbox):
            continue
        result.append(_parse_event(e))
    return result


def _find_nearest_event(
    events: list[Alberta511Event],
    lat: float,
    lon: float,
) -> Alberta511Event | None:
    """Find the nearest event by haversine distance.

    Among events at similar distance (within 5 km), prefer higher severity.
    """
    if not events:
        return None

    scored: list[tuple[float, int, Alberta511Event]] = []
    for evt in events:
        if evt.latitude == 0.0 and evt.longitude == 0.0:
            continue
        dist = RoadWeatherProvider.haversine_km(lat, lon, evt.latitude, evt.longitude)
        sev_rank = _SEVERITY_RANK.get(evt.severity, 0)
        scored.append((dist, -sev_rank, evt))

    if not scored:
        return events[0] if events else None

    # Sort by distance first, then by severity (higher = better, hence negative)
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][2]


# ---------------------------------------------------------------------------
# Road conditions (winter only)
# ---------------------------------------------------------------------------

def _condition_in_bbox(
    cond: dict,
    bbox: tuple[float, float, float, float],
) -> bool:
    """Check if a road condition segment has coordinates in bbox."""
    lon_min, lat_min, lon_max, lat_max = bbox

    # Road conditions may have Latitude/Longitude or LocationDescription
    lat = cond.get("Latitude")
    lon = cond.get("Longitude")
    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            return lon_min <= lon_f <= lon_max and lat_min <= lat_f <= lat_max
        except (TypeError, ValueError):
            pass

    return False


def _extract_nearest_condition(
    conditions: list[dict],
    lat: float,
    lon: float,
    bbox: tuple[float, float, float, float],
) -> str:
    """Extract road condition from nearest segment within bbox.

    Returns "" if no conditions available (normal in spring/summer).
    """
    if not conditions:
        return ""

    best_condition = ""
    best_dist = float("inf")

    for cond in conditions:
        if not _condition_in_bbox(cond, bbox):
            continue

        c_lat = cond.get("Latitude")
        c_lon = cond.get("Longitude")
        if c_lat is None or c_lon is None:
            continue

        try:
            c_lat_f, c_lon_f = float(c_lat), float(c_lon)
        except (TypeError, ValueError):
            continue

        dist = RoadWeatherProvider.haversine_km(lat, lon, c_lat_f, c_lon_f)
        if dist < best_dist:
            best_dist = dist
            # Condition field varies: "Condition", "RoadCondition", "SurfaceCondition"
            condition_text = (
                cond.get("Condition")
                or cond.get("RoadCondition")
                or cond.get("SurfaceCondition")
                or ""
            )
            best_condition = str(condition_text).upper()

    return best_condition


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _safe_float(value, default: float = 0.0) -> float:
    """Convert value to float or return default."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
