"""KiSTI - DriveBC + EC Event Simulator

Simulates road events and weather alerts through DiffStateBridge for
demo/trade show mode.  Runs a scripted scenario over ~120 seconds:

  Phase 1 (0-15s):   Clear — dry road, no alerts
  Phase 2 (15-30s):  DriveBC WET road, temp dropping
  Phase 3 (30-50s):  EC watch → DriveBC construction event ahead
  Phase 4 (50-70s):  EC warning (snowfall), ICY road, road temp <0
  Phase 5 (70-90s):  CLOSURE event — road closed ahead
  Phase 6 (90-110s): Conditions clearing — road WET, EC advisory
  Phase 7 (110-120s): All clear — back to baseline

Usage:
    From main.py with --demo flag:
        sim = EventSimulator(bridge)
        sim.start()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger("kisti.sensors.event_sim")


@dataclass
class _EventPhase:
    """A simulation phase with target DriveBC + EC state."""
    duration_s: int
    # DriveBC
    road_condition: str           # DRY/WET/ICY/SNOWY/FROSTY/MOIST
    road_temp_c: float | None
    air_temp_c: float | None
    station_name: str
    station_distance_km: float
    precipitation_mm: float
    wind_kph: float
    event_count: int
    event_text: str
    event_severity: str           # ""/MINOR/MAJOR/CLOSURE
    # EC
    ec_warning_level: str         # none/statement/advisory/watch/warning
    ec_warning_text: str
    ec_warning_description: str
    ec_condition: str
    ec_forecast_condition: str


_PHASES: list[_EventPhase] = [
    # Phase 1: Clear baseline
    _EventPhase(
        duration_s=15,
        road_condition="DRY", road_temp_c=14.0, air_temp_c=16.0,
        station_name="Port Mann Bridge", station_distance_km=7.1,
        precipitation_mm=0.0, wind_kph=8.0,
        event_count=0, event_text="", event_severity="",
        ec_warning_level="none", ec_warning_text="", ec_warning_description="",
        ec_condition="Partly Cloudy", ec_forecast_condition="Cloudy",
    ),
    # Phase 2: Road getting wet, temp dropping
    _EventPhase(
        duration_s=15,
        road_condition="WET", road_temp_c=8.0, air_temp_c=10.0,
        station_name="Port Mann Bridge", station_distance_km=7.1,
        precipitation_mm=2.4, wind_kph=22.0,
        event_count=0, event_text="", event_severity="",
        ec_warning_level="statement", ec_warning_text="Special Weather Statement",
        ec_warning_description="A Pacific frontal system will bring rain to the Lower Mainland tonight",
        ec_condition="Rain", ec_forecast_condition="Rain",
    ),
    # Phase 3: EC watch + construction ahead
    _EventPhase(
        duration_s=20,
        road_condition="WET", road_temp_c=5.0, air_temp_c=6.0,
        station_name="Coquihalla Summit", station_distance_km=12.3,
        precipitation_mm=5.1, wind_kph=35.0,
        event_count=1,
        event_text="Road Construction on Hwy 1 westbound. Single lane alternating traffic. Expect delays up to 20 minutes.",
        event_severity="MAJOR",
        ec_warning_level="watch", ec_warning_text="Winter Storm Watch",
        ec_warning_description="Snowfall warning in effect for Coquihalla Highway. 15-25 cm expected above 800m",
        ec_condition="Rain", ec_forecast_condition="Snow",
    ),
    # Phase 4: EC warning, ICY road
    _EventPhase(
        duration_s=20,
        road_condition="ICY", road_temp_c=-2.0, air_temp_c=0.0,
        station_name="Coquihalla Summit", station_distance_km=12.3,
        precipitation_mm=8.0, wind_kph=45.0,
        event_count=1,
        event_text="Compact snow on Hwy 5 northbound between Hope and Merritt. Winter tires or chains required.",
        event_severity="MAJOR",
        ec_warning_level="warning", ec_warning_text="Snowfall Warning",
        ec_warning_description="Heavy snow 20-30 cm by morning. Visibility reduced to near zero in blowing snow. Travel not recommended",
        ec_condition="Snow", ec_forecast_condition="Snow",
    ),
    # Phase 5: CLOSURE
    _EventPhase(
        duration_s=20,
        road_condition="SNOWY", road_temp_c=-4.0, air_temp_c=-2.0,
        station_name="Coquihalla Summit", station_distance_km=12.3,
        precipitation_mm=12.0, wind_kph=55.0,
        event_count=1,
        event_text="Road closed. Multi-vehicle incident on Hwy 5 at Zopkios. Avalanche control in progress.",
        event_severity="CLOSURE",
        ec_warning_level="warning", ec_warning_text="Snowfall Warning",
        ec_warning_description="Heavy snow continuing. 30+ cm accumulated. Extreme caution on mountain passes",
        ec_condition="Heavy Snow", ec_forecast_condition="Snow",
    ),
    # Phase 6: Clearing
    _EventPhase(
        duration_s=20,
        road_condition="WET", road_temp_c=3.0, air_temp_c=5.0,
        station_name="Port Mann Bridge", station_distance_km=7.1,
        precipitation_mm=1.0, wind_kph=18.0,
        event_count=0, event_text="", event_severity="",
        ec_warning_level="advisory", ec_warning_text="Freezing Rain Advisory",
        ec_warning_description="Risk of freezing rain overnight as temperatures hover near zero",
        ec_condition="Cloudy", ec_forecast_condition="Clearing",
    ),
    # Phase 7: All clear
    _EventPhase(
        duration_s=10,
        road_condition="DRY", road_temp_c=12.0, air_temp_c=14.0,
        station_name="Port Mann Bridge", station_distance_km=7.1,
        precipitation_mm=0.0, wind_kph=10.0,
        event_count=0, event_text="", event_severity="",
        ec_warning_level="none", ec_warning_text="", ec_warning_description="",
        ec_condition="Clearing", ec_forecast_condition="Sunny",
    ),
]


class EventSimulator(QObject):
    """Simulates DriveBC + EC events through DiffStateBridge."""

    def __init__(self, bridge, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._timer = QTimer(self)
        self._timer.setInterval(1000)  # 1 Hz
        self._timer.timeout.connect(self._tick)

        self._tick_count: int = 0
        self._phase_idx: int = 0
        self._phase_tick: int = 0

        # Interpolated road temp for smooth transitions
        self._road_temp: float = _PHASES[0].road_temp_c or 14.0
        self._air_temp: float = _PHASES[0].air_temp_c or 16.0

        # Alert dedup window: prevent simultaneous alerts within 3s window
        self._last_alert_time: dict[str, float] = {}
        self._alert_dedup_window_s: float = 3.0

    def start(self) -> None:
        """Start the event simulation."""
        self._tick_count = 0
        self._phase_idx = 0
        self._phase_tick = 0
        self._road_temp = _PHASES[0].road_temp_c or 14.0
        self._air_temp = _PHASES[0].air_temp_c or 16.0
        self._last_alert_time.clear()

        total = sum(p.duration_s for p in _PHASES)
        log.info("Event simulation starting (%d phases, %ds total, dedup=%fs)", len(_PHASES), total, self._alert_dedup_window_s)
        self._timer.start()
        self._push()

    def stop(self) -> None:
        self._timer.stop()
        log.info("Event simulation stopped at tick %d", self._tick_count)

    def _should_push_alert(self, alert_type: str) -> bool:
        """Check if alert type should fire — prevents simultaneous alerts within dedup window."""
        import time
        now = time.monotonic()
        last = self._last_alert_time.get(alert_type, 0.0)
        if now - last < self._alert_dedup_window_s:
            return False
        self._last_alert_time[alert_type] = now
        return True

    def _tick(self) -> None:
        self._tick_count += 1
        self._phase_tick += 1

        phase = _PHASES[self._phase_idx]

        if self._phase_tick >= phase.duration_s:
            self._phase_idx += 1
            self._phase_tick = 0

            if self._phase_idx >= len(_PHASES):
                # Loop back to start for continuous demo
                self._phase_idx = 0
                log.info("Event simulation looping (%d ticks)", self._tick_count)

            phase = _PHASES[self._phase_idx]

        # Smooth temperature transitions
        target_road = phase.road_temp_c if phase.road_temp_c is not None else self._road_temp
        target_air = phase.air_temp_c if phase.air_temp_c is not None else self._air_temp
        remaining = max(phase.duration_s - self._phase_tick, 1)
        rate = 1.0 / remaining
        self._road_temp += (target_road - self._road_temp) * rate
        self._air_temp += (target_air - self._air_temp) * rate

        self._push()

    def _push(self) -> None:
        """Push current state into DiffStateBridge with dedup spacing."""
        phase = _PHASES[self._phase_idx]

        # Push road condition if dedup window allows
        if self._should_push_alert("road_condition"):
            self._bridge.update_drivebc(
                road_condition=phase.road_condition,
                road_temp_c=round(self._road_temp, 1),
                station_name=phase.station_name,
                station_distance_km=phase.station_distance_km,
                precipitation_mm=phase.precipitation_mm,
                wind_kph=phase.wind_kph,
                event_count=phase.event_count,
                event_text=phase.event_text,
                event_severity=phase.event_severity,
                data_age_s=0.0,
                air_temp_c=round(self._air_temp, 1),
            )

        # Push EC weather if dedup window allows
        if self._should_push_alert("ec_weather"):
            self._bridge.update_ec_weather(
                warning_level=phase.ec_warning_level,
                warning_text=phase.ec_warning_text,
                condition=phase.ec_condition,
                forecast_condition=phase.ec_forecast_condition,
                data_age_s=0.0,
                warning_description=phase.ec_warning_description,
            )
