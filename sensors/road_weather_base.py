"""KiSTI — Road Weather Provider Base Class

Lightweight base class for road weather providers (DriveBC, 511AB, IEM, 511ON).
Each provider runs a background daemon thread that polls an external API
and pushes data into DiffStateBridge via the existing update_drivebc() method.

Not an abstract base class — just shared boilerplate so providers only need
to implement poll_once() and _poll_loop().
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model.vehicle_state import DiffStateBridge

log = logging.getLogger("kisti.sensors.road_weather_base")

# Earth radius in km for haversine
_EARTH_RADIUS_KM = 6371.0


class RoadWeatherProvider:
    """Base class for road weather data providers.

    Each provider runs a background daemon thread that polls an external API
    and pushes data into DiffStateBridge via the existing update_drivebc() method.

    Pass ``clock`` and ``fetcher`` to override for testing.
    """

    def __init__(
        self,
        bridge: DiffStateBridge,
        lat: float,
        lon: float,
        bbox: str = "",
        clock=None,
        fetcher=None,
    ) -> None:
        self._bridge = bridge
        self._lat = lat
        self._lon = lon
        self._bbox = bbox
        self._clock = clock or time.monotonic
        self._fetcher = fetcher or self._default_fetch
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.source_name: str = ""  # "DriveBC", "511AB", "IEM-IA", "511ON"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start background polling thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name=f"road-weather-{self.source_name or 'unknown'}",
        )
        self._thread.start()
        log.info(
            "Road weather provider %s started (lat=%.2f, lon=%.2f)",
            self.source_name, self._lat, self._lon,
        )

    def stop(self) -> None:
        """Stop polling. Blocks up to 5 s for the thread to finish."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Position / heading updates (called from manager at 1 Hz)
    # ------------------------------------------------------------------

    def update_position(self, lat: float, lon: float) -> None:
        with self._lock:
            self._lat = lat
            self._lon = lon

    def update_heading(self, heading_deg: float) -> None:
        """Override in subclasses that support direction filtering."""

    # ------------------------------------------------------------------
    # Polling — subclass must implement
    # ------------------------------------------------------------------

    def poll_once(self):
        """Synchronous single poll — for testing or manual refresh."""
        raise NotImplementedError

    def _poll_loop(self) -> None:
        """Background polling loop — subclass must implement."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Bridge integration
    # ------------------------------------------------------------------

    def _push_to_bridge(self, **kwargs) -> None:
        """Map provider data into bridge.update_drivebc() and tag the source.

        ``kwargs`` are forwarded directly to
        ``DiffStateBridge.update_drivebc()``.
        """
        self._bridge.update_drivebc(**kwargs)
        # Tag which provider produced this data
        with self._bridge._lock:
            self._bridge._state.road_weather_source = self.source_name

    # ------------------------------------------------------------------
    # Default HTTP fetcher (overridden via constructor for tests)
    # ------------------------------------------------------------------

    @staticmethod
    def _default_fetch(url: str, timeout: int = 10):
        """Fetch JSON from *url* using stdlib urllib."""
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    # ------------------------------------------------------------------
    # Haversine (copied from sensors/drivebc_weather.py)
    # ------------------------------------------------------------------

    @staticmethod
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
