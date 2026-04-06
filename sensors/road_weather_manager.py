"""KiSTI — GPS-Based Road Weather Provider Manager

Activates / deactivates road weather providers based on GPS position.
Called at 1 Hz from the coaching timer with lat/lon.  When the position
enters a new geographic region the appropriate provider is started and
the previous one is stopped.

Provider classes are imported lazily so that a missing module (e.g. the
Alberta 511 connector isn't written yet) never crashes startup.
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model.vehicle_state import DiffStateBridge
    from sensors.road_weather_base import RoadWeatherProvider

log = logging.getLogger("kisti.sensors.road_weather_manager")


class RoadWeatherManager:
    """Activates/deactivates road weather providers based on GPS position.

    Called at 1 Hz from coaching timer with GPS lat/lon.
    When position enters a new region, starts the appropriate provider
    and stops the previous one.
    """

    # (name, source_name, provider_class_path, lat_min, lat_max, lon_min, lon_max)
    REGIONS: list[tuple[str, str, str, float, float, float, float]] = [
        ("BC", "DriveBC", "sensors.drivebc_weather.DriveBCProvider", 48.3, 60.0, -139.1, -114.0),
        ("AB", "511AB", "sensors.alberta511_weather.Alberta511Poller", 49.0, 60.0, -120.0, -110.0),
        ("ON", "511ON", "sensors.ontario511_weather.Ontario511Poller", 41.7, 56.9, -95.2, -74.3),
        ("US", "IEM", "sensors.iem_rwis.IEMRWISPoller", 24.5, 49.0, -125.0, -66.9),
    ]

    def __init__(self, bridge: DiffStateBridge) -> None:
        self._bridge = bridge
        self._active_provider: RoadWeatherProvider | None = None
        self._active_region: str | None = None
        self._lat: float = 0.0
        self._lon: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start with a region override from env, or wait for first GPS fix.

        Set ``KISTI_REGION`` to one of BC / AB / ON / US to force a region
        without waiting for GPS.
        """
        override = os.environ.get("KISTI_REGION", "").strip().upper()
        if override:
            valid_names = [r[0] for r in self.REGIONS]
            if override in valid_names:
                log.info("Road weather: KISTI_REGION override → %s", override)
                self._switch_provider(override)
            else:
                log.warning(
                    "Road weather: KISTI_REGION=%r not in %s — ignoring",
                    override, valid_names,
                )

    def stop(self) -> None:
        """Stop the active provider (if any)."""
        if self._active_provider:
            self._active_provider.stop()
            log.info("Road weather: stopped %s", self._active_region)
            self._active_provider = None
            self._active_region = None

    # ------------------------------------------------------------------
    # Position / heading updates (called at 1 Hz)
    # ------------------------------------------------------------------

    def update_position(self, lat: float, lon: float) -> None:
        """Called at 1 Hz from coaching timer.  Switches provider if region changed."""
        self._lat = lat
        self._lon = lon

        new_region = self._detect_region(lat, lon)
        if new_region and new_region != self._active_region:
            self._switch_provider(new_region)

        if self._active_provider:
            self._active_provider.update_position(lat, lon)

    def update_heading(self, heading_deg: float) -> None:
        """Forward heading to the active provider."""
        if self._active_provider:
            self._active_provider.update_heading(heading_deg)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_providers(self) -> list:
        """List of currently active providers (0 or 1)."""
        return [self._active_provider] if self._active_provider else []

    @property
    def active_region(self) -> str | None:
        """Currently active region name, or None."""
        return self._active_region

    # ------------------------------------------------------------------
    # Region detection
    # ------------------------------------------------------------------

    def _detect_region(self, lat: float, lon: float) -> str | None:
        """Return the first region whose bounding box contains (lat, lon)."""
        for name, _source, _cls_path, lat_min, lat_max, lon_min, lon_max in self.REGIONS:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return name
        return None

    # ------------------------------------------------------------------
    # Provider switching
    # ------------------------------------------------------------------

    def _switch_provider(self, region_name: str) -> None:
        """Stop the current provider and start the one for *region_name*."""
        # Stop old provider
        if self._active_provider:
            self._active_provider.stop()
            log.info("Road weather: stopped %s", self._active_region)

        # Find region config
        for name, source, cls_path, *_bounds in self.REGIONS:
            if name == region_name:
                provider = self._import_provider(cls_path, source)
                if provider is None:
                    log.warning(
                        "Road weather: could not load provider for %s (%s) — skipping",
                        region_name, cls_path,
                    )
                    self._active_provider = None
                    self._active_region = None
                    return

                self._active_provider = provider
                self._active_region = region_name
                self._active_provider.start()
                log.info("Road weather: activated %s (%s)", region_name, source)
                return

        log.warning("Road weather: unknown region %r", region_name)

    def _import_provider(self, cls_path: str, source_name: str) -> RoadWeatherProvider | None:
        """Dynamically import and instantiate a provider class.

        Returns None if the module or class cannot be found (the provider
        hasn't been written yet).  This keeps startup safe.
        """
        module_path, class_name = cls_path.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
        except (ImportError, AttributeError) as exc:
            log.debug("Road weather: import %s failed: %s", cls_path, exc)
            return None

        try:
            provider = cls(self._bridge, self._lat, self._lon)
            provider.source_name = source_name
            return provider
        except Exception as exc:  # noqa: BLE001
            log.debug("Road weather: instantiation of %s failed: %s", cls_path, exc)
            return None
