"""KiSTI — Iowa Environmental Mesonet (IEM) RWIS Poller

Polls IEM for US road weather data — a single integration covering
all 33 US states with RWIS networks (~2,198 stations total).

API: https://mesonet.agron.iastate.edu/api/1/rwis.json?network={STATE}_RWIS
  - Free, no auth, no registration
  - JSON response: {schema: [...], data: [...]}
  - Returns array of station objects per state network

Architecture follows the RoadWeatherProvider base class pattern
(sensors/road_weather_base.py): background daemon thread, thread-safe
data via lock, poll_once() for testing, injectable clock and fetcher.

On each poll:
  1. Detect US state from GPS lat/lon (sensors/us_state_lookup.py)
  2. If state changed, switch to new {STATE}_RWIS network
  3. Fetch all stations for the network
  4. Find nearest station by haversine distance
  5. Convert units (F->C, knots->kph, miles->km, inches->mm)
  6. Push to bridge via _push_to_bridge()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sensors.road_weather_base import RoadWeatherProvider
from sensors.us_state_lookup import lookup_state

if TYPE_CHECKING:
    from model.vehicle_state import DiffStateBridge

log = logging.getLogger("kisti.sensors.iem_rwis")

# Polling interval — IEM data updates every 5-10 minutes
POLL_INTERVAL_S = 300  # 5 minutes
REQUEST_TIMEOUT_S = 10

# IEM API base URL
IEM_API_URL = "https://mesonet.agron.iastate.edu/api/1/rwis.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IEMStationData:
    """Parsed data from a single IEM RWIS station."""
    station: str = ""
    name: str = ""
    state: str = ""
    lat: float = 0.0
    lon: float = 0.0
    road_temp_f: float | None = None       # tfs0 (or first non-null tfsN)
    road_condition_text: str = ""           # tfs0_text (or first non-null)
    air_temp_f: float | None = None        # tmpf
    humidity_pct: float | None = None      # relh
    wind_knots: float | None = None        # sknt
    visibility_miles: float | None = None  # vsby
    precipitation_in: float | None = None  # pcpn
    valid_utc: str = ""


@dataclass
class IEMRWISData:
    """Snapshot of latest IEM RWIS data for the current state network."""
    nearest_station: IEMStationData | None = None
    station_distance_km: float = 99.0
    network: str = ""           # e.g. "IA_RWIS"
    station_count: int = 0
    available: bool = False
    fetch_ts: float | None = None


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

def f_to_c(f: float | None) -> float | None:
    """Convert Fahrenheit to Celsius. Returns None if input is None."""
    if f is None:
        return None
    return (f - 32.0) * 5.0 / 9.0


def knots_to_kph(knots: float | None) -> float:
    """Convert knots to km/h. Returns 0.0 if input is None."""
    if knots is None:
        return 0.0
    return knots * 1.852


def miles_to_km(miles: float | None) -> float | None:
    """Convert statute miles to km. Returns None if input is None."""
    if miles is None:
        return None
    return miles * 1.60934


def inches_to_mm(inches: float | None) -> float:
    """Convert inches to mm. Returns 0.0 if input is None."""
    if inches is None:
        return 0.0
    return inches * 25.4


# ---------------------------------------------------------------------------
# Road condition text mapping
# ---------------------------------------------------------------------------

# IEM tfsN_text values mapped to KiSTI standard condition strings
_CONDITION_MAP: dict[str, str] = {
    "dry": "DRY",
    "wet": "WET",
    "ice": "ICY",
    "ice watch": "ICY",
    "ice warning": "ICY",
    "frost": "FROSTY",
    "snow": "SNOWY",
    "snow watch": "SNOWY",
    "snow warning": "SNOWY",
    "slush": "SLUSHY",
    "black ice": "ICY",
    "chemically wet": "WET",
    "trace moisture": "MOIST",
    "absorption": "MOIST",
    "dew": "MOIST",
}


def normalize_road_condition(text: str) -> str:
    """Map IEM tfsN_text to KiSTI standard condition.

    Falls back to uppercased text if no mapping exists.
    """
    if not text:
        return ""
    key = text.strip().lower()
    return _CONDITION_MAP.get(key, text.strip().upper())


# ---------------------------------------------------------------------------
# Station parsing
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    """Convert a value to float, returning None on failure or None input."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_station(raw: dict) -> IEMStationData:
    """Parse a single station dict from the IEM RWIS JSON response."""
    # Find first non-null surface sensor (tfs0 through tfs3)
    road_temp_f = None
    road_condition_text = ""
    for i in range(4):
        temp_key = f"tfs{i}"
        text_key = f"tfs{i}_text"
        temp_val = _safe_float(raw.get(temp_key))
        text_val = raw.get(text_key)
        if temp_val is not None or (text_val and str(text_val).strip()):
            road_temp_f = temp_val
            road_condition_text = str(text_val).strip() if text_val else ""
            break

    return IEMStationData(
        station=str(raw.get("station", "")),
        name=str(raw.get("name", "")),
        state=str(raw.get("state", "")),
        lat=_safe_float(raw.get("lat")) or 0.0,
        lon=_safe_float(raw.get("lon")) or 0.0,
        road_temp_f=road_temp_f,
        road_condition_text=road_condition_text,
        air_temp_f=_safe_float(raw.get("tmpf")),
        humidity_pct=_safe_float(raw.get("relh")),
        wind_knots=_safe_float(raw.get("sknt")),
        visibility_miles=_safe_float(raw.get("vsby")),
        precipitation_in=_safe_float(raw.get("pcpn")),
        valid_utc=str(raw.get("utc_valid", "")),
    )


def parse_stations(response: dict) -> list[IEMStationData]:
    """Parse the IEM RWIS JSON response into a list of station data.

    IEM returns ``{"schema": [...], "data": [...]}``.
    Also handles a plain list (for robustness).
    """
    if isinstance(response, list):
        return [parse_station(r) for r in response]

    data = response.get("data", [])
    if isinstance(data, list):
        return [parse_station(r) for r in data if isinstance(r, dict)]

    return []


# ---------------------------------------------------------------------------
# IEM RWIS Poller
# ---------------------------------------------------------------------------

class IEMRWISPoller(RoadWeatherProvider):
    """Background poller for IEM RWIS road weather data.

    Auto-detects US state from GPS position and fetches the
    corresponding {STATE}_RWIS network.
    """

    def __init__(
        self,
        bridge: DiffStateBridge,
        lat: float = 41.6,
        lon: float = -93.6,
        clock=None,
        fetcher=None,
    ) -> None:
        super().__init__(
            bridge=bridge, lat=lat, lon=lon, clock=clock, fetcher=fetcher,
        )
        self._current_state: str | None = None
        self._current_network: str = ""
        self._stations: list[IEMStationData] = []
        self._data = IEMRWISData()
        self.source_name = "IEM"

    @property
    def data(self) -> IEMRWISData:
        """Thread-safe read of latest IEM RWIS data."""
        with self._lock:
            return self._data

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Background polling loop."""
        last_poll = 0.0

        while not self._stop.is_set():
            now = self._clock()

            if now - last_poll >= POLL_INTERVAL_S or last_poll == 0.0:
                self._do_poll()
                last_poll = self._clock()

            # Sleep in 5s chunks so stop() is responsive
            for _ in range(12):  # ~60s total
                if self._stop.is_set():
                    return
                self._stop.wait(5.0)

    def _do_poll(self) -> None:
        """Single poll cycle: detect state, fetch, find nearest, push."""
        with self._lock:
            lat, lon = self._lat, self._lon

        # Detect US state from GPS position
        state = lookup_state(lat, lon)
        if state is None:
            log.debug("GPS position (%.4f, %.4f) not in a US RWIS state", lat, lon)
            with self._lock:
                self._data.available = False
            return

        # Switch network if state changed
        network = f"{state}_RWIS"
        if state != self._current_state:
            log.info("IEM RWIS: switching to %s network", network)
            self._current_state = state
            self._current_network = network
            self.source_name = f"IEM-{state}"

        # Fetch stations for the current network
        url = f"{IEM_API_URL}?network={network}"
        try:
            raw = self._fetcher(url)
            stations = parse_stations(raw)
            log.info("IEM RWIS %s: %d stations fetched", network, len(stations))
        except Exception as exc:
            log.debug("IEM RWIS fetch failed (%s): %s", network, exc)
            return

        self._stations = stations

        # Find nearest station
        nearest = None
        nearest_dist = float("inf")
        for s in stations:
            if s.lat == 0.0 and s.lon == 0.0:
                continue
            dist = self.haversine_km(lat, lon, s.lat, s.lon)
            if dist < nearest_dist:
                nearest = s
                nearest_dist = dist

        now = self._clock()

        with self._lock:
            self._data.network = network
            self._data.station_count = len(stations)
            self._data.fetch_ts = now

            if nearest is not None:
                self._data.nearest_station = nearest
                self._data.station_distance_km = round(nearest_dist, 1)
                self._data.available = True
            else:
                self._data.nearest_station = None
                self._data.station_distance_km = 99.0
                self._data.available = len(stations) > 0

        # Push to bridge
        if nearest is not None:
            condition = normalize_road_condition(nearest.road_condition_text)
            road_temp_c = f_to_c(nearest.road_temp_f)
            air_temp_c = f_to_c(nearest.air_temp_f)
            wind_kph = knots_to_kph(nearest.wind_knots)
            pcpn_mm = inches_to_mm(nearest.precipitation_in)

            # Compute data age from valid_utc (if parseable)
            age = self._compute_age(nearest.valid_utc)

            station_label = f"IEM: {nearest.name}" if nearest.name else nearest.station

            self._push_to_bridge(
                road_condition=condition,
                road_temp_c=road_temp_c,
                station_name=station_label,
                station_distance_km=round(nearest_dist, 1),
                precipitation_mm=pcpn_mm,
                wind_kph=round(wind_kph, 1),
                event_count=0,          # IEM doesn't provide events
                event_text="",
                event_severity="",
                data_age_s=age,
                air_temp_c=air_temp_c,
            )

    def _compute_age(self, utc_valid_str: str) -> float:
        """Compute age in seconds from a UTC datetime string.

        Returns 0.0 if the string can't be parsed (wall-clock not available
        on Jetson in offline mode anyway).
        """
        if not utc_valid_str:
            return 0.0
        try:
            import datetime
            # IEM format: "2026-04-06T12:00:00Z" or "2026-04-06 12:00"
            clean = utc_valid_str.replace("Z", "+00:00").replace(" ", "T")
            if "+" not in clean and len(clean) == 16:
                clean += ":00+00:00"
            elif "+" not in clean:
                clean += "+00:00"
            dt = datetime.datetime.fromisoformat(clean)
            now = datetime.datetime.now(datetime.timezone.utc)
            return max(0.0, (now - dt).total_seconds())
        except Exception:
            return 0.0

    def poll_once(self) -> IEMRWISData:
        """Synchronous single poll -- for testing or manual refresh."""
        self._do_poll()
        return self.data
