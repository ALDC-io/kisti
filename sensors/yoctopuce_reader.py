"""KiSTI - Yoctopuce Yocto-Meteo-V2 Ambient Weather Sensor

Reads temperature, humidity, and barometric pressure from the
Yoctopuce Yocto-Meteo-V2-C via USB. Designed for exterior mounting
to provide ambient conditions for density altitude, grip estimation,
and weather change detection.

Polls at 1 Hz via QTimer on the main thread. Falls back gracefully
if the sensor is unplugged or the yoctopuce library is unavailable.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.sensors.yoctopuce")

POLL_INTERVAL_MS = 1000  # 1 Hz — ambient conditions change slowly

# Delta thresholds for "significant change" detection.
# These fire voice alerts so the driver knows conditions shifted.
PRESSURE_DELTA_HPA = 5.0    # weather system movement
TEMP_DELTA_C = 3.0           # warm/cold front arrival
HUMIDITY_DELTA_PCT = 15.0    # condensation / hydroplaning risk


@dataclass
class AmbientReading:
    """Single ambient weather reading."""
    temperature_c: float = 0.0
    humidity_pct: float = 0.0
    pressure_hpa: float = 0.0
    density_altitude_ft: float = 0.0
    dew_point_c: float = 0.0
    available: bool = False


@dataclass
class AmbientChange:
    """Describes a significant ambient condition change."""
    event: str              # e.g., "pressure_falling", "temp_dropping"
    message: str            # driver-friendly description
    old_value: float
    new_value: float
    delta: float


def _dew_point(temp_c: float, rh_pct: float) -> float:
    """Magnus formula dew point approximation."""
    if rh_pct <= 0:
        return temp_c
    a, b = 17.27, 237.7
    alpha = (a * temp_c) / (b + temp_c) + math.log(rh_pct / 100.0)
    return (b * alpha) / (a - alpha)


def _density_altitude(pressure_hpa: float, temp_c: float) -> float:
    """Density altitude in feet from pressure and temperature.

    Uses ICAO standard atmosphere model. Higher density altitude = less
    engine power and aerodynamic grip.
    """
    if pressure_hpa <= 0:
        return 0.0
    # Pressure altitude (feet)
    pressure_alt_ft = (1 - (pressure_hpa / 1013.25) ** 0.190284) * 145366.45
    # ISA temperature at this pressure altitude
    isa_temp_c = 15.0 - 1.98 * (pressure_alt_ft / 1000.0)
    # Density altitude correction: ~120 ft per degree C above ISA
    density_alt_ft = pressure_alt_ft + 120.0 * (temp_c - isa_temp_c)
    return density_alt_ft


class YoctopuceReader(QObject):
    """Polls Yoctopuce Yocto-Meteo-V2 for ambient weather data."""

    reading_updated = Signal(object)    # emits AmbientReading (every poll)
    condition_changed = Signal(object)  # emits AmbientChange (on significant delta)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._available = False
        self._temp_sensor = None
        self._hum_sensor = None
        self._pres_sensor = None
        self._serial: str = ""
        self._last_reading = AmbientReading()
        self._baseline: Optional[AmbientReading] = None  # set on first valid read

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> bool:
        """Initialize Yoctopuce API and start polling.

        Returns True if sensor found, False otherwise.
        """
        try:
            from yoctopuce.yocto_api import YAPI, YRefParam
            from yoctopuce.yocto_temperature import YTemperature
            from yoctopuce.yocto_humidity import YHumidity
            from yoctopuce.yocto_pressure import YPressure
        except ImportError:
            log.warning("yoctopuce library not installed — ambient sensor disabled")
            return False

        errmsg = YRefParam()
        res = YAPI.RegisterHub("usb", errmsg)
        if res != 0:
            log.warning("Yoctopuce USB access failed: %s", errmsg.value)
            return False

        self._temp_sensor = YTemperature.FirstTemperature()
        self._hum_sensor = YHumidity.FirstHumidity()
        self._pres_sensor = YPressure.FirstPressure()

        if self._temp_sensor and self._temp_sensor.isOnline():
            self._serial = self._temp_sensor.get_module().get_serialNumber()
            self._available = True
            self._timer.start()
            log.info("Yoctopuce Yocto-Meteo-V2 online (serial: %s)", self._serial)
            # Immediate first read
            self._poll()
            return True

        log.info("No Yoctopuce sensor found")
        return False

    def stop(self) -> None:
        self._timer.stop()
        if self._available:
            try:
                from yoctopuce.yocto_api import YAPI
                YAPI.FreeAPI()
            except Exception:
                pass
            self._available = False
            log.info("Yoctopuce reader stopped")

    def last_reading(self) -> AmbientReading:
        return self._last_reading

    @property
    def available(self) -> bool:
        return self._available

    def _poll(self) -> None:
        """Read all three sensors and emit reading."""
        if not self._available:
            return

        try:
            temp_c = self._temp_sensor.get_currentValue()
            hum_pct = self._hum_sensor.get_currentValue()
            pres_hpa = self._pres_sensor.get_currentValue()

            reading = AmbientReading(
                temperature_c=temp_c,
                humidity_pct=hum_pct,
                pressure_hpa=pres_hpa,
                dew_point_c=_dew_point(temp_c, hum_pct),
                density_altitude_ft=_density_altitude(pres_hpa, temp_c),
                available=True,
            )
            self._last_reading = reading
            self.reading_updated.emit(reading)

            # Check for significant condition changes
            self._check_deltas(reading)

        except Exception as exc:
            log.debug("Yoctopuce poll error: %s", exc)
            self._last_reading = AmbientReading(available=False)

    def _check_deltas(self, reading: AmbientReading) -> None:
        """Compare current reading against baseline; emit condition_changed on significant delta."""
        if self._baseline is None:
            self._baseline = reading
            return

        b = self._baseline

        # Pressure change — weather system movement
        p_delta = reading.pressure_hpa - b.pressure_hpa
        if abs(p_delta) >= PRESSURE_DELTA_HPA:
            direction = "falling" if p_delta < 0 else "rising"
            if p_delta < 0:
                msg = "Pressure falling. Weather system moving in."
            else:
                msg = "Pressure rising. Conditions stabilising."
            self.condition_changed.emit(AmbientChange(
                event=f"pressure_{direction}",
                message=msg,
                old_value=b.pressure_hpa,
                new_value=reading.pressure_hpa,
                delta=p_delta,
            ))
            self._baseline = reading
            return  # one change per poll cycle to avoid voice spam

        # Temperature change — grip / engine performance shift
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
                delta=t_delta,
            ))
            self._baseline = reading
            return

        # Humidity change — condensation / hydroplaning risk
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
                delta=h_delta,
            ))
            self._baseline = reading
