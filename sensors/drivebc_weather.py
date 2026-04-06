"""KiSTI — DriveBC Road Weather Integration

Polls DriveBC RWIS (Road Weather Information System) stations and road
events for real-time road surface conditions along the driving route.

Runs in a background thread, provides data to WeatherEngine for fusion
with hyperlocal Yoctopuce sensor readings and EC regional forecasts.

Architecture:
  Hyperlocal (Yoctopuce) = ground truth at the car (1Hz, exact)
  Regional (EC API)      = prediction window extension (10-15 min)
  Road-surface (DriveBC) = actual road condition reports from RWIS sensors

API: drivebc.ca (free, no auth, no rate limits)
  - /api/weather/current/   — 258 RWIS stations with road condition,
    road temp, air temp, precipitation, wind, GeoJSON location
  - /api/events/            — closures, incidents, chain-ups with
    severity, location, description
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("kisti.sensors.drivebc_weather")

RWIS_URL = "https://www.drivebc.ca/api/weather/current/?format=json"
EVENTS_URL = "https://www.drivebc.ca/api/events/?format=json"

# Polling intervals
RWIS_POLL_S = 300       # 5 minutes — RWIS stations update slowly
EVENTS_POLL_S = 120     # 2 minutes — events can change faster
REQUEST_TIMEOUT_S = 10

# Default location — Coquitlam, BC
DEFAULT_LAT = float(os.environ.get("DRIVEBC_LAT", "49.28"))
DEFAULT_LON = float(os.environ.get("DRIVEBC_LON", "-122.79"))

# Default bbox — Metro Vancouver
DEFAULT_BBOX = os.environ.get("DRIVEBC_BBOX", "-123.2,49.1,-122.0,49.5")

# Current highway — filter stations/events to this road only.
# Set via env var or update_highway(). Empty = show all (nearest-neighbor).
DEFAULT_HIGHWAY = os.environ.get("DRIVEBC_HIGHWAY", "")

# Earth radius in km for haversine
_EARTH_RADIUS_KM = 6371.0


@dataclass
class DriveBCEvent:
    """A road event (closure, incident, chain-up requirement)."""
    severity: str = ""           # CLOSURE / MAJOR / MINOR
    event_type: str = ""         # e.g. "INCIDENT", "CONSTRUCTION", "CHAIN_UP"
    description: str = ""        # Full text (truncated)
    road_name: str = ""          # e.g. "Highway 1"
    display_category: str = ""   # e.g. "closures", "majorEvents"


@dataclass
class DriveBCData:
    """Snapshot of latest DriveBC road weather data."""
    # Nearest RWIS station
    nearest_station_name: str = ""
    road_condition: str = ""            # DRY/WET/ICY/SNOWY/FROSTY/MOIST/SLUSHY
    road_temperature_c: Optional[float] = None
    air_temperature_c: Optional[float] = None
    precipitation_mm: float = 0.0
    wind_speed_kph: float = 0.0
    wind_direction: str = ""
    station_distance_km: float = 0.0    # haversine distance to nearest station

    # Nearby road events
    nearby_events: list[DriveBCEvent] = field(default_factory=list)

    # Metadata
    available: bool = False
    fetch_ts: Optional[float] = None    # monotonic timestamp of last fetch


class DriveBCPoller:
    """Background poller for DriveBC RWIS and road event data.

    Runs in a daemon thread. Call start() to begin polling.
    Read latest via the `data` property (thread-safe).

    Pass `clock` and `fetcher` to override for testing.
    """

    def __init__(
        self,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        bbox: str = DEFAULT_BBOX,
        highway: str = DEFAULT_HIGHWAY,
        clock=None,
        fetcher=None,
    ) -> None:
        self._lat = lat
        self._lon = lon
        self._bbox = bbox
        self._bbox_parsed = _parse_bbox(bbox)
        self._highway = highway  # e.g. "1", "7", "99" — empty = all
        self._heading: Optional[float] = None  # GPS heading in degrees (0=N, 90=E)
        self._clock = clock or time.monotonic
        self._fetcher = fetcher or _http_fetch
        self._data = DriveBCData()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def data(self) -> DriveBCData:
        """Thread-safe read of latest DriveBC data."""
        with self._lock:
            return self._data

    def update_position(self, lat: float, lon: float) -> None:
        """Update GPS position for nearest-station lookup."""
        self._lat = lat
        self._lon = lon

    def update_heading(self, heading_deg: float) -> None:
        """Update GPS heading (0=N, 90=E) for ahead-only filtering."""
        self._heading = heading_deg

    def update_highway(self, highway: str) -> None:
        """Set current highway (e.g. "1", "7", "99"). Empty = all."""
        self._highway = highway

    def start(self) -> None:
        """Start background polling thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="drivebc-weather",
        )
        self._thread.start()
        log.info("DriveBC poller started (lat=%.2f, lon=%.2f)", self._lat, self._lon)

    def stop(self) -> None:
        """Stop polling."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _poll_loop(self) -> None:
        """Main polling loop — runs in background thread."""
        last_rwis = 0.0
        last_events = 0.0

        while not self._stop.is_set():
            now = self._clock()

            stations = None
            events = None

            if now - last_rwis >= RWIS_POLL_S or last_rwis == 0.0:
                stations = self._fetch_rwis()
                last_rwis = now

            if now - last_events >= EVENTS_POLL_S or last_events == 0.0:
                events = self._fetch_events()
                last_events = now

            if stations is not None or events is not None:
                self._update(stations, events)

            # Sleep in 5s chunks so stop() is responsive
            for _ in range(12):  # ~60s total
                if self._stop.is_set():
                    return
                self._stop.wait(5.0)

    def _fetch_rwis(self) -> Optional[list[dict]]:
        """Fetch all RWIS station data."""
        try:
            data = self._fetcher(RWIS_URL)
            stations = data if isinstance(data, list) else data.get("features", [])
            log.info("DriveBC RWIS: %d stations fetched", len(stations))
            return stations
        except Exception as exc:
            log.debug("DriveBC RWIS fetch failed: %s", exc)
            return None

    def _fetch_events(self) -> Optional[list[dict]]:
        """Fetch road events."""
        try:
            data = self._fetcher(EVENTS_URL)
            events = data if isinstance(data, list) else data.get("events", [])
            log.info("DriveBC events: %d total", len(events))
            return events
        except Exception as exc:
            log.debug("DriveBC events fetch failed: %s", exc)
            return None

    def _update(
        self,
        stations: Optional[list[dict]],
        events: Optional[list[dict]],
    ) -> None:
        """Merge new data into the shared snapshot.

        Filters by highway (if set) and direction (ahead-only if heading known).
        """
        with self._lock:
            now = self._clock()

            if stations is not None:
                # Filter to current highway if set
                filtered = stations
                if self._highway:
                    filtered = [s for s in stations if _station_on_highway(s, self._highway)]

                # Filter to ahead-only if heading is known
                if self._heading is not None:
                    filtered = [
                        s for s in filtered
                        if _is_ahead(self._lat, self._lon, self._heading, s)
                    ]

                # Fall back to all stations on highway if none ahead
                if not filtered and self._highway:
                    filtered = [s for s in stations if _station_on_highway(s, self._highway)]

                nearest = _find_nearest_station(
                    filtered if filtered else stations, self._lat, self._lon,
                )
                if nearest is not None:
                    station, distance_km = nearest
                    self._data.nearest_station_name = _station_name(station)
                    self._data.road_condition = _road_condition(station)
                    self._data.road_temperature_c = _station_float(station, "road_temperature", "roadTemperature", "road_surface_temperature")
                    self._data.air_temperature_c = _station_float(station, "air_temperature", "airTemperature", "temperature")
                    self._data.precipitation_mm = _station_float(station, "precipitation", "precipitationAmount") or 0.0
                    self._data.wind_speed_kph = _station_float(station, "wind_speed", "windSpeed", "average_wind") or 0.0
                    self._data.wind_direction = _station_str(station, "wind_direction", "windDirection", "windCardinalDir")
                    self._data.station_distance_km = round(distance_km, 1)

            if events is not None:
                all_events = _filter_events(events, self._bbox_parsed)
                # Filter events to current highway if set
                if self._highway:
                    hwy_events = [e for e in all_events if _event_on_highway(e, self._highway)]
                    self._data.nearby_events = hwy_events if hwy_events else all_events
                else:
                    self._data.nearby_events = all_events

            if stations is not None or events is not None:
                self._data.fetch_ts = now
                self._data.available = True

    def poll_once(self) -> DriveBCData:
        """Synchronous single poll — for testing or manual refresh."""
        stations = self._fetch_rwis()
        events = self._fetch_events()
        self._update(stations, events)
        return self.data


# ---------------------------------------------------------------------------
# Haversine distance (pure math, no numpy)
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


# ---------------------------------------------------------------------------
# Station helpers — defensive against varying API response shapes
# ---------------------------------------------------------------------------

def _station_coords(station: dict) -> Optional[tuple[float, float]]:
    """Extract (lat, lon) from a station dict. Handles GeoJSON and flat."""
    # GeoJSON geometry — API uses "location" or "geometry"
    geom = station.get("location") or station.get("geometry")
    if isinstance(geom, dict):
        coords = geom.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                # GeoJSON is [lon, lat]
                return float(coords[1]), float(coords[0])
            except (TypeError, ValueError):
                pass

    # Flat properties
    props = station.get("properties", station)
    lat = props.get("latitude") or props.get("lat")
    lon = props.get("longitude") or props.get("lon") or props.get("lng")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    return None


def _station_name(station: dict) -> str:
    """Extract station name from various API shapes."""
    props = station.get("properties", station)
    for key in ("weather_station_name", "station_name", "stationName", "name", "location_description", "locationDescription"):
        val = props.get(key)
        if val:
            return str(val)
    return "Unknown Station"


def _road_condition(station: dict) -> str:
    """Extract road condition string, normalized to uppercase."""
    props = station.get("properties", station)
    for key in ("road_condition", "roadCondition", "road_surface_condition", "roadSurfaceCondition"):
        val = props.get(key)
        if val:
            return str(val).upper()
    return ""


def _station_float(station: dict, *keys: str) -> Optional[float]:
    """Try multiple possible keys for a float value.

    Handles strings like "6 km/h" or "0 mm" by stripping non-numeric suffix.
    """
    props = station.get("properties", station)
    for key in keys:
        val = props.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                # Try stripping unit suffix (e.g. "6 km/h" → "6")
                if isinstance(val, str):
                    numeric = val.split()[0] if val.strip() else ""
                    try:
                        return float(numeric)
                    except (TypeError, ValueError):
                        pass
                continue
    return None


def _station_str(station: dict, *keys: str) -> str:
    """Try multiple possible keys for a string value."""
    props = station.get("properties", station)
    for key in keys:
        val = props.get(key)
        if val is not None:
            return str(val)
    return ""


# ---------------------------------------------------------------------------
# Highway extraction + directional filtering
# ---------------------------------------------------------------------------

_HWY_PATTERN = re.compile(r"(?:Hwy|Highway|highway)\s*#?\s*(\d+\w?)", re.IGNORECASE)


def extract_highway(text: str) -> str:
    """Extract highway number from description text (e.g. 'Hwy 1' → '1')."""
    if not text:
        return ""
    m = _HWY_PATTERN.search(text)
    return m.group(1) if m else ""


def _station_on_highway(station: dict, highway: str) -> bool:
    """Check if a station's location_description references the given highway."""
    desc = station.get("location_description") or ""
    name = station.get("weather_station_name") or ""
    hwy = extract_highway(desc) or extract_highway(name)
    return hwy == highway


def _event_on_highway(event: "DriveBCEvent", highway: str) -> bool:
    """Check if a parsed DriveBCEvent references the given highway."""
    # Check road_name field
    hwy = extract_highway(event.road_name) or extract_highway(event.description)
    return hwy == highway


def _is_ahead(
    car_lat: float, car_lon: float, heading_deg: float, station: dict,
) -> bool:
    """Check if a station is ahead of the car (within ±90° of heading).

    Uses dot product of heading vector and car→station vector.
    Returns True if no coordinates available (don't filter out unknowns).
    """
    coords = _station_coords(station)
    if coords is None:
        return True  # Don't filter out stations without coords

    s_lat, s_lon = coords
    # Approximate: dlat ~ north, dlon ~ east (corrected by cos(lat))
    dlat = s_lat - car_lat
    dlon = (s_lon - car_lon) * math.cos(math.radians(car_lat))

    # Heading vector (heading 0=N, 90=E)
    h_rad = math.radians(heading_deg)
    hx = math.sin(h_rad)  # east component
    hy = math.cos(h_rad)  # north component

    # Dot product > 0 means station is in front
    dot = dlat * hy + dlon * hx
    return dot > 0


# ---------------------------------------------------------------------------
# Nearest station finder
# ---------------------------------------------------------------------------

def _find_nearest_station(
    stations: list[dict],
    lat: float,
    lon: float,
) -> Optional[tuple[dict, float]]:
    """Find the RWIS station nearest to (lat, lon).

    Returns (station_dict, distance_km) or None if no stations have coords.
    """
    best = None
    best_dist = float("inf")

    for s in stations:
        coords = _station_coords(s)
        if coords is None:
            continue
        dist = haversine_km(lat, lon, coords[0], coords[1])
        if dist < best_dist:
            best = s
            best_dist = dist

    if best is not None:
        return best, best_dist
    return None


# ---------------------------------------------------------------------------
# Event filtering
# ---------------------------------------------------------------------------

def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """Parse 'lon_min,lat_min,lon_max,lat_max' into tuple."""
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Expected 4 values, got {len(parts)}")
        return (parts[0], parts[1], parts[2], parts[3])
    except (ValueError, TypeError):
        log.warning("Invalid bbox %r, using Metro Vancouver default", bbox)
        return (-123.2, 49.1, -122.0, 49.5)


def _event_in_bbox(
    event: dict,
    bbox: tuple[float, float, float, float],
) -> bool:
    """Check if an event's location falls within the bbox."""
    lon_min, lat_min, lon_max, lat_max = bbox

    # Try GeoJSON geometry — API uses "location" or "geometry"
    geom = event.get("location") or event.get("geometry")
    if isinstance(geom, dict):
        coords = geom.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                lon, lat = float(coords[0]), float(coords[1])
                return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max
            except (TypeError, ValueError, IndexError):
                pass

    # Try flat lat/lon
    lat = event.get("latitude") or event.get("lat")
    lon = event.get("longitude") or event.get("lon") or event.get("lng")
    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            return lon_min <= lon_f <= lon_max and lat_min <= lat_f <= lat_max
        except (TypeError, ValueError):
            pass

    # Try head/tail points (DriveBC uses these for road segments)
    for point_key in ("head", "tail", "start_point", "end_point"):
        point = event.get(point_key)
        if isinstance(point, dict):
            plat = point.get("latitude") or point.get("lat")
            plon = point.get("longitude") or point.get("lon") or point.get("lng")
            if plat is not None and plon is not None:
                try:
                    lat_f, lon_f = float(plat), float(plon)
                    if lon_min <= lon_f <= lon_max and lat_min <= lat_f <= lat_max:
                        return True
                except (TypeError, ValueError):
                    continue

    return False


def _normalize_severity(event: dict) -> str:
    """Map DriveBC severity to CLOSURE/MAJOR/MINOR."""
    sev = str(event.get("severity", "")).upper()
    if sev in ("CLOSURE", "CLOSED"):
        return "CLOSURE"
    if sev in ("MAJOR", "HIGH"):
        return "MAJOR"

    # Also check event type for closures
    etype = str(event.get("event_type", event.get("eventType", ""))).upper()
    if "CLOSURE" in etype or "CLOSED" in etype:
        return "CLOSURE"

    return "MINOR"


def _filter_events(
    events: list[dict],
    bbox: tuple[float, float, float, float],
) -> list[DriveBCEvent]:
    """Filter events to those within bbox and map to DriveBCEvent."""
    result: list[DriveBCEvent] = []
    for e in events:
        if not _event_in_bbox(e, bbox):
            continue
        # optimized_description is the at-a-glance version (no highway/direction boilerplate)
        opt_desc = e.get("optimized_description", "") or ""
        raw_desc = e.get("description", "") or ""
        desc = str(opt_desc).strip() if opt_desc else str(raw_desc)[:300]
        result.append(DriveBCEvent(
            severity=_normalize_severity(e),
            event_type=str(e.get("event_type", e.get("eventType", ""))),
            description=desc,
            road_name=str(e.get("route_display", e.get("route", e.get("road_name", e.get("highway_name", ""))))),
            display_category=str(e.get("display_category", e.get("displayCategory", ""))),
        ))
    return result


# ---------------------------------------------------------------------------
# HTTP fetcher (default — overridden in tests)
# ---------------------------------------------------------------------------

def _http_fetch(url: str) -> dict | list:
    """Default HTTP fetcher using stdlib."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        return json.loads(resp.read())
