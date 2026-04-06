"""KiSTI — Environment Canada Weather Integration

Polls EC GeoMet API for regional weather warnings and forecasts.
Runs in a background thread, provides data to WeatherEngine for
fusion with hyperlocal Yoctopuce sensor readings.

Architecture:
  Hyperlocal (Yoctopuce) = ground truth at the car (1Hz, exact)
  Regional (EC API) = prediction window extension (10-15 min, area-wide)

API: api.weather.gc.ca (free, no auth, no rate limits)
  - weather-alerts: active warnings by GPS bbox
  - citypageweather-realtime: conditions + forecast by city_id
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("kisti.sensors.ec_weather")

EC_BASE = "https://api.weather.gc.ca"
ALERTS_PATH = "/collections/weather-alerts/items"
CITYPAGE_PATH = "/collections/citypageweather-realtime/items"

# Polling intervals
ALERT_POLL_S = 600     # 10 minutes
FORECAST_POLL_S = 900  # 15 minutes
REQUEST_TIMEOUT_S = 10

# Default location — override via EC_CITY_ID / EC_BBOX env vars,
# or dynamically from GPS09 Pro once installed.
# Coquitlam, BC — "Metro Vancouver northeast including Coquitlam and Maple Ridge"
DEFAULT_BBOX = os.environ.get("EC_BBOX", "-122.90,49.20,-122.65,49.35")
DEFAULT_CITY_ID = os.environ.get("EC_CITY_ID", "bc-35")

# Warning severity ranking
_WARNING_RANK = {
    "none": 0,
    "statement": 1,
    "advisory": 2,
    "watch": 3,
    "warning": 4,
}


@dataclass
class ECWarning:
    """An active Environment Canada weather warning."""
    alert_type: str = ""       # "warning", "watch", "advisory", "statement"
    alert_name: str = ""       # e.g. "Snowfall Warning"
    description: str = ""      # Full text (truncated)
    feature_name: str = ""     # e.g. "Central Okanagan"


@dataclass
class ECWeatherData:
    """Snapshot of latest Environment Canada data."""
    # Warnings
    warnings: list[ECWarning] = field(default_factory=list)
    highest_warning: str = "none"  # "none" / "statement" / "advisory" / "watch" / "warning"
    warning_text: str = ""         # Short name of highest warning
    warning_description: str = ""  # Actual alert content (first ~120 chars)

    # Current conditions (EC station)
    ec_temp_c: Optional[float] = None
    ec_humidity_pct: Optional[float] = None
    ec_pressure_kpa: Optional[float] = None
    ec_condition: str = ""         # "Sunny", "Cloudy", "Rain", "Snow", etc.
    ec_wind_kph: Optional[float] = None

    # Hourly forecast (next hour)
    forecast_condition: str = ""   # "Rain", "Snow", "Partly cloudy", etc.
    forecast_temp_c: Optional[float] = None

    # Metadata
    fetch_ts: float = 0.0         # monotonic timestamp of last successful fetch
    available: bool = False


class ECWeatherPoller:
    """Background poller for Environment Canada weather data.

    Runs in a daemon thread. Call start() to begin polling.
    Read latest via the `data` property (thread-safe).

    Pass `clock` and `fetcher` to override for testing.
    """

    def __init__(
        self,
        city_id: str = DEFAULT_CITY_ID,
        bbox: str = DEFAULT_BBOX,
        clock=None,
        fetcher=None,
    ) -> None:
        self._city_id = city_id
        self._bbox = bbox
        self._clock = clock or time.monotonic
        self._fetcher = fetcher or _http_fetch
        self._data = ECWeatherData()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def data(self) -> ECWeatherData:
        """Thread-safe read of latest EC data."""
        with self._lock:
            return self._data

    def start(self) -> None:
        """Start background polling thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="ec-weather",
        )
        self._thread.start()
        log.info("EC weather poller started (city=%s)", self._city_id)

    def stop(self) -> None:
        """Stop polling."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _poll_loop(self) -> None:
        """Main polling loop — runs in background thread."""
        last_alert = 0.0
        last_forecast = 0.0

        while not self._stop.is_set():
            now = self._clock()

            warnings = None
            forecast = None

            if now - last_alert >= ALERT_POLL_S or last_alert == 0.0:
                warnings = self._fetch_warnings()
                last_alert = now

            if now - last_forecast >= FORECAST_POLL_S or last_forecast == 0.0:
                forecast = self._fetch_citypage()
                last_forecast = now

            if warnings is not None or forecast is not None:
                self._update(warnings, forecast)

            # Sleep in 5s chunks so stop() is responsive
            for _ in range(12):  # ~60s total
                if self._stop.is_set():
                    return
                self._stop.wait(5.0)

    def _fetch_warnings(self) -> Optional[list[ECWarning]]:
        """Fetch active weather warnings for our bbox."""
        url = f"{EC_BASE}{ALERTS_PATH}?f=json&lang=en&bbox={self._bbox}"
        try:
            data = self._fetcher(url)
            warnings = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                warnings.append(ECWarning(
                    alert_type=props.get("alert_type", "").lower(),
                    alert_name=props.get("alert_name_en", ""),
                    description=props.get("alert_text_en", "")[:300],
                    feature_name=props.get("feature_name_en", ""),
                ))
            log.info("EC warnings: %d active for bbox %s", len(warnings), self._bbox)
            return warnings
        except Exception as exc:
            log.debug("EC warnings fetch failed: %s", exc)
            return None

    def _fetch_citypage(self) -> Optional[dict]:
        """Fetch city page with current conditions + hourly forecast."""
        url = f"{EC_BASE}{CITYPAGE_PATH}/{self._city_id}?f=json&lang=en"
        try:
            data = self._fetcher(url)
            return data.get("properties", {})
        except Exception as exc:
            log.debug("EC citypage fetch failed: %s", exc)
            return None

    def _update(
        self,
        warnings: Optional[list[ECWarning]],
        citypage: Optional[dict],
    ) -> None:
        """Merge new data into the shared snapshot."""
        with self._lock:
            now = self._clock()

            if warnings is not None:
                self._data.warnings = warnings
                highest = "none"
                highest_text = ""
                highest_desc = ""
                for w in warnings:
                    rank = _WARNING_RANK.get(w.alert_type, 0)
                    if rank > _WARNING_RANK.get(highest, 0):
                        highest = w.alert_type
                        highest_text = w.alert_name
                        highest_desc = w.description
                self._data.highest_warning = highest
                self._data.warning_text = highest_text
                self._data.warning_description = highest_desc

            if citypage is not None:
                cc = citypage.get("currentConditions", {})
                self._data.ec_temp_c = _nested_float(cc, "temperature")
                self._data.ec_humidity_pct = _nested_float(cc, "relativeHumidity")
                self._data.ec_pressure_kpa = _nested_float(cc, "pressure")
                self._data.ec_wind_kph = _nested_float(cc, "wind", "speed")
                cond = cc.get("condition")
                if isinstance(cond, dict):
                    self._data.ec_condition = cond.get("en", "")
                elif isinstance(cond, str):
                    self._data.ec_condition = cond

                # Hourly forecast — first entry = next hour
                hourly = citypage.get("hourlyForecastGroup", {})
                forecasts = hourly.get("hourlyForecasts", [])
                if forecasts:
                    h = forecasts[0]
                    fc_cond = h.get("condition", "")
                    self._data.forecast_condition = (
                        fc_cond.get("en", "") if isinstance(fc_cond, dict) else str(fc_cond)
                    )
                    fc_temp = h.get("temperature", "")
                    if isinstance(fc_temp, dict):
                        self._data.forecast_temp_c = _safe_float(
                            fc_temp.get("value", {}).get("en") if isinstance(fc_temp.get("value"), dict)
                            else fc_temp.get("value")
                        )
                    else:
                        self._data.forecast_temp_c = _safe_float(fc_temp)

            if warnings is not None or citypage is not None:
                self._data.fetch_ts = now
                self._data.available = True

    def poll_once(self) -> ECWeatherData:
        """Synchronous single poll — for testing or manual refresh."""
        warnings = self._fetch_warnings()
        citypage = self._fetch_citypage()
        self._update(warnings, citypage)
        return self.data


def _http_fetch(url: str) -> dict:
    """Default HTTP fetcher using stdlib."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _nested_float(d: dict, *keys) -> Optional[float]:
    """Extract a float from EC's nested {value: {en: N}} structure."""
    node = d
    for k in keys:
        node = node.get(k, {})
        if not isinstance(node, dict):
            return _safe_float(node)
    val = node.get("value", {})
    if isinstance(val, dict):
        return _safe_float(val.get("en"))
    return _safe_float(val)


def _safe_float(val, default=None) -> Optional[float]:
    """Safely convert to float, returning None on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
