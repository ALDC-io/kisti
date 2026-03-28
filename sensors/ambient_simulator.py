"""KiSTI - Ambient Weather Simulator

Simulates changing weather conditions through the same signal interface
as YoctopuceReader. Runs a scripted scenario over ~90 seconds:

  Phase 1 (0-15s):  Stable — mild and dry baseline
  Phase 2 (15-35s): Pressure drops — storm front approaching
  Phase 3 (35-50s): Temperature drops — cold front arrives
  Phase 4 (50-65s): Humidity rises — rain approaching
  Phase 5 (65-80s): Conditions stabilise — pressure recovers
  Phase 6 (80-90s): Stable — new baseline

Voice announces simulation start, condition changes (via existing
condition_changed pipeline), and simulation end.

Usage:
    From main.py with --sim-ambient flag, or directly:
        sim = AmbientSimulator()
        sim.reading_updated.connect(...)
        sim.condition_changed.connect(...)
        sim.start()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from sensors.yoctopuce_reader import (
    AmbientChange,
    AmbientReading,
    HUMIDITY_DELTA_PCT,
    PRESSURE_DELTA_HPA,
    TEMP_DELTA_C,
    _density_altitude,
    _dew_point,
)

log = logging.getLogger("kisti.sensors.ambient_sim")

SIM_TICK_MS = 1000  # 1 Hz — matches real sensor rate


@dataclass
class _Phase:
    """A simulation phase with target values and duration."""
    duration_s: int
    temp_c: float
    humidity_pct: float
    pressure_hpa: float


# Scripted weather scenario — each phase ramps linearly to target
_PHASES: list[_Phase] = [
    _Phase(duration_s=15, temp_c=20.0, humidity_pct=50.0, pressure_hpa=1013.0),  # stable baseline
    _Phase(duration_s=20, temp_c=19.0, humidity_pct=55.0, pressure_hpa=1005.0),  # pressure drops (storm)
    _Phase(duration_s=15, temp_c=14.0, humidity_pct=58.0, pressure_hpa=1004.0),  # temp drops (cold front)
    _Phase(duration_s=15, temp_c=13.5, humidity_pct=78.0, pressure_hpa=1003.0),  # humidity rises (rain)
    _Phase(duration_s=15, temp_c=15.0, humidity_pct=65.0, pressure_hpa=1010.0),  # recovery (clearing)
    _Phase(duration_s=10, temp_c=16.0, humidity_pct=55.0, pressure_hpa=1012.0),  # stable new baseline
]


class AmbientSimulator(QObject):
    """Simulates changing ambient weather through YoctopuceReader-compatible signals."""

    reading_updated = Signal(object)    # emits AmbientReading
    condition_changed = Signal(object)  # emits AmbientChange
    simulation_started = Signal()       # emits when sim begins
    simulation_ended = Signal()         # emits when sim completes

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(SIM_TICK_MS)
        self._timer.timeout.connect(self._tick)

        self._tick_count: int = 0
        self._phase_idx: int = 0
        self._phase_tick: int = 0

        # Current interpolated values
        self._temp: float = _PHASES[0].temp_c
        self._humidity: float = _PHASES[0].humidity_pct
        self._pressure: float = _PHASES[0].pressure_hpa

        # Baseline for delta detection (same logic as YoctopuceReader)
        self._baseline: Optional[AmbientReading] = None
        self._last_reading = AmbientReading()

    def start(self) -> bool:
        """Start the simulation. Returns True always (no hardware required)."""
        self._tick_count = 0
        self._phase_idx = 0
        self._phase_tick = 0
        self._temp = _PHASES[0].temp_c
        self._humidity = _PHASES[0].humidity_pct
        self._pressure = _PHASES[0].pressure_hpa
        self._baseline = None

        log.info("Ambient simulation starting (%d phases, %ds total)",
                 len(_PHASES), sum(p.duration_s for p in _PHASES))
        self.simulation_started.emit()
        self._timer.start()

        # Emit initial reading immediately
        self._emit_reading()
        return True

    def stop(self) -> None:
        """Stop the simulation."""
        self._timer.stop()
        log.info("Ambient simulation stopped at tick %d", self._tick_count)

    def last_reading(self) -> AmbientReading:
        return self._last_reading

    @property
    def available(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        """Advance simulation by one second."""
        self._tick_count += 1
        self._phase_tick += 1

        phase = _PHASES[self._phase_idx]

        # Check if current phase is complete
        if self._phase_tick >= phase.duration_s:
            self._phase_idx += 1
            self._phase_tick = 0

            # Simulation complete?
            if self._phase_idx >= len(_PHASES):
                self._timer.stop()
                log.info("Ambient simulation complete (%d ticks)", self._tick_count)
                self.simulation_ended.emit()
                return

            phase = _PHASES[self._phase_idx]

        # Interpolate toward current phase target
        target = _PHASES[self._phase_idx]
        remaining = max(target.duration_s - self._phase_tick, 1)
        rate = 1.0 / remaining  # fraction to move per tick

        self._temp += (target.temp_c - self._temp) * rate
        self._humidity += (target.humidity_pct - self._humidity) * rate
        self._pressure += (target.pressure_hpa - self._pressure) * rate

        self._emit_reading()

    def _emit_reading(self) -> None:
        """Build and emit current reading, check for condition changes."""
        reading = AmbientReading(
            temperature_c=round(self._temp, 1),
            humidity_pct=round(self._humidity, 1),
            pressure_hpa=round(self._pressure, 1),
            dew_point_c=round(_dew_point(self._temp, self._humidity), 1),
            density_altitude_ft=round(_density_altitude(self._pressure, self._temp), 0),
            available=True,
        )
        self._last_reading = reading
        self.reading_updated.emit(reading)
        self._check_deltas(reading)

    def _check_deltas(self, reading: AmbientReading) -> None:
        """Detect significant changes — same logic as YoctopuceReader._check_deltas."""
        if self._baseline is None:
            self._baseline = reading
            return

        b = self._baseline

        p_delta = reading.pressure_hpa - b.pressure_hpa
        if abs(p_delta) >= PRESSURE_DELTA_HPA:
            if p_delta < 0:
                msg = "Pressure falling. Weather system moving in."
            else:
                msg = "Pressure rising. Conditions stabilising."
            self.condition_changed.emit(AmbientChange(
                event=f"pressure_{'falling' if p_delta < 0 else 'rising'}",
                message=msg,
                old_value=b.pressure_hpa,
                new_value=reading.pressure_hpa,
                delta=round(p_delta, 1),
            ))
            self._baseline = reading
            return

        t_delta = reading.temperature_c - b.temperature_c
        if abs(t_delta) >= TEMP_DELTA_C:
            if t_delta < 0:
                msg = "Temperature dropping. Track conditions may worsen."
            else:
                msg = "Temperature rising. Grip should improve."
            self.condition_changed.emit(AmbientChange(
                event="temp_dropping" if t_delta < 0 else "temp_rising",
                message=msg,
                old_value=b.temperature_c,
                new_value=reading.temperature_c,
                delta=round(t_delta, 1),
            ))
            self._baseline = reading
            return

        h_delta = reading.humidity_pct - b.humidity_pct
        if abs(h_delta) >= HUMIDITY_DELTA_PCT:
            if h_delta > 0:
                msg = "Humidity rising. Increased condensation risk."
            else:
                msg = "Humidity dropping. Drier conditions ahead."
            self.condition_changed.emit(AmbientChange(
                event="humidity_rising" if h_delta > 0 else "humidity_dropping",
                message=msg,
                old_value=b.humidity_pct,
                new_value=reading.humidity_pct,
                delta=round(h_delta, 1),
            ))
            self._baseline = reading
