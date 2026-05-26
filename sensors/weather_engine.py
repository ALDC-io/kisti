"""KiSTI — Weather Nowcasting Engine

Transforms raw barometric + ambient sensor readings into actionable
weather intelligence for the driver. Runs at 1Hz alongside
YoctopuceReader, feeding trend fields into DiffState.

Threat levels:
  CLEAR      — stable, no action
  CHANGING   — weather shifting, advisory
  RAIN_LIKELY — rain probable within 1-2 hours
  STORM      — severe system, pit window

Implementation:
  - Rolling 10-minute window for rate-of-change (linear regression slope)
  - 3-hour window for Zambretti-style trend classification
  - Multi-sensor rules: baro + humidity + dew spread for rain/fog detection
  - All pure Python — no numpy (Jetson RAM constraint)
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

log = logging.getLogger("kisti.sensors.weather_engine")


# ---------------------------------------------------------------------------
# Threat levels (ordered by severity)
# ---------------------------------------------------------------------------

class ThreatLevel(IntEnum):
    CLEAR = 0
    CHANGING = 1
    RAIN_LIKELY = 2
    STORM = 3


THREAT_LABELS = {
    ThreatLevel.CLEAR: "CLEAR",
    ThreatLevel.CHANGING: "CHANGING",
    ThreatLevel.RAIN_LIKELY: "RAIN_LIKELY",
    ThreatLevel.STORM: "STORM",
}


# ---------------------------------------------------------------------------
# Thresholds (from meteorological research)
# ---------------------------------------------------------------------------

# Pressure rate of change (hPa/hr) — absolute value of falling rate
RATE_CHANGING = 0.5       # minor shift
RATE_RAIN_LIKELY = 1.5    # front approaching
RATE_STORM = 3.5          # severe system

# Multi-sensor rain-imminent thresholds
RAIN_BARO_RATE = 1.5      # hPa/hr falling
RAIN_DEW_SPREAD = 2.5     # °C (temp - dew_point)
RAIN_HUMIDITY = 85.0       # %RH

# Fog risk thresholds
FOG_DEW_SPREAD = 1.5      # °C
FOG_HUMIDITY = 93.0        # %RH

# Snow risk thresholds
SNOW_TEMP_C = 2.0             # °C — snow possible at or below
SNOW_HUMIDITY = 80.0          # %RH
SNOW_BARO_RATE = 0.5          # hPa/hr falling (approaching system)

# Cold front detection
COLD_FRONT_RISE_RATE = 2.0  # hPa/hr rising after a low

# Rolling window sizes
WINDOW_SHORT_S = 600       # 10 minutes (rate-of-change)
WINDOW_LONG_S = 10800      # 3 hours (trend classification)

# Minimum samples for valid rate calculation
MIN_SAMPLES_SHORT = 30     # ~30 seconds of 1Hz data
MIN_SAMPLES_LONG = 60      # ~1 minute of 1Hz data


# ---------------------------------------------------------------------------
# Data point
# ---------------------------------------------------------------------------

@dataclass
class _Sample:
    ts: float               # monotonic timestamp
    pressure_hpa: float
    humidity_pct: float
    temp_c: float
    dew_point_c: float


# ---------------------------------------------------------------------------
# Trend result
# ---------------------------------------------------------------------------

@dataclass
class WeatherTrend:
    """Current weather trend assessment."""
    pressure_trend_hpa_hr: float = 0.0
    humidity_trend_pct_hr: float = 0.0
    dew_point_spread_c: float = 99.0
    threat_level: ThreatLevel = ThreatLevel.CLEAR
    threat_label: str = "CLEAR"
    rain_imminent: bool = False
    fog_risk: bool = False
    snow_risk: bool = False
    cold_front: bool = False


# ---------------------------------------------------------------------------
# Linear regression slope (pure Python, no numpy)
# ---------------------------------------------------------------------------

def _slope_per_hour(samples: list[_Sample], extract_val) -> float:
    """Compute slope of value over time using least-squares linear regression.

    Returns rate of change per hour. Positive = rising, negative = falling.
    """
    n = len(samples)
    if n < 2:
        return 0.0

    t0 = samples[0].ts
    sum_t = 0.0
    sum_v = 0.0
    sum_tt = 0.0
    sum_tv = 0.0

    for s in samples:
        t = (s.ts - t0) / 3600.0  # hours since first sample
        v = extract_val(s)
        sum_t += t
        sum_v += v
        sum_tt += t * t
        sum_tv += t * v

    denom = n * sum_tt - sum_t * sum_t
    if abs(denom) < 1e-12:
        return 0.0

    return (n * sum_tv - sum_t * sum_v) / denom


# ---------------------------------------------------------------------------
# Weather Engine
# ---------------------------------------------------------------------------

class WeatherEngine:
    """Processes ambient sensor readings into weather intelligence.

    Call `feed()` at 1Hz with raw sensor values. Read `trend` for current
    assessment. Thread-safe for Qt signal/slot (called from main thread).

    Pass `clock` to override time source (for testing).
    """

    def __init__(self, clock=None) -> None:
        self._short_window: deque[_Sample] = deque()  # 10-min
        self._long_window: deque[_Sample] = deque()   # 3-hr
        self._trend = WeatherTrend()
        self._last_log_ts: float = 0.0
        self._clock = clock or time.monotonic

    @property
    def trend(self) -> WeatherTrend:
        return self._trend

    def feed(
        self,
        pressure_hpa: float,
        humidity_pct: float,
        temp_c: float,
        dew_point_c: float,
        ec_warning_level: str = "none",
        ec_data_age_s: float = 9999.0,
    ) -> WeatherTrend:
        """Ingest a new reading and return updated trend.

        Call at 1Hz from main.py's coaching timer.
        """
        now = self._clock()
        sample = _Sample(
            ts=now,
            pressure_hpa=pressure_hpa,
            humidity_pct=humidity_pct,
            temp_c=temp_c,
            dew_point_c=dew_point_c,
        )

        # Add to both windows
        self._short_window.append(sample)
        self._long_window.append(sample)

        # Trim windows
        cutoff_short = now - WINDOW_SHORT_S
        while self._short_window and self._short_window[0].ts < cutoff_short:
            self._short_window.popleft()

        cutoff_long = now - WINDOW_LONG_S
        while self._long_window and self._long_window[0].ts < cutoff_long:
            self._long_window.popleft()

        # Compute trends
        self._trend = self._compute(sample, ec_warning_level, ec_data_age_s)

        # Log every 60 seconds
        if now - self._last_log_ts >= 60.0:
            t = self._trend
            log.info(
                "Weather: %s | baro %.1f hPa/hr | hum %.1f%%/hr | "
                "dew spread %.1f°C | rain=%s fog=%s snow=%s",
                t.threat_label, t.pressure_trend_hpa_hr,
                t.humidity_trend_pct_hr, t.dew_point_spread_c,
                t.rain_imminent, t.fog_risk, t.snow_risk,
            )
            self._last_log_ts = now

        return self._trend

    def _compute(self, current: _Sample,
                 ec_warning_level: str = "none",
                 ec_data_age_s: float = 9999.0) -> WeatherTrend:
        """Compute full weather assessment from current windows."""
        short_list = list(self._short_window)
        long_list = list(self._long_window)

        # Rate of change from short window
        p_rate = 0.0
        h_rate = 0.0
        if len(short_list) >= MIN_SAMPLES_SHORT:
            p_rate = _slope_per_hour(short_list, lambda s: s.pressure_hpa)
            h_rate = _slope_per_hour(short_list, lambda s: s.humidity_pct)

        # Dew point spread
        dew_spread = current.temp_c - current.dew_point_c

        # Threat level from pressure rate (falling = negative)
        falling_rate = abs(min(0.0, p_rate))  # only care about falling
        if falling_rate >= RATE_STORM:
            threat = ThreatLevel.STORM
        elif falling_rate >= RATE_RAIN_LIKELY:
            threat = ThreatLevel.RAIN_LIKELY
        elif falling_rate >= RATE_CHANGING:
            threat = ThreatLevel.CHANGING
        else:
            threat = ThreatLevel.CLEAR

        # Multi-sensor rain detection (can upgrade threat)
        rain_imminent = (
            falling_rate >= RAIN_BARO_RATE
            and dew_spread <= RAIN_DEW_SPREAD
            and current.humidity_pct >= RAIN_HUMIDITY
        )
        if rain_imminent and threat < ThreatLevel.RAIN_LIKELY:
            threat = ThreatLevel.RAIN_LIKELY

        # Fog risk
        fog_risk = (
            dew_spread <= FOG_DEW_SPREAD
            and current.humidity_pct >= FOG_HUMIDITY
        )

        # Snow risk: cold + moist + system approaching
        snow_risk = (
            current.temp_c <= SNOW_TEMP_C
            and current.humidity_pct >= SNOW_HUMIDITY
            and falling_rate >= SNOW_BARO_RATE
        )
        if snow_risk and threat < ThreatLevel.RAIN_LIKELY:
            threat = ThreatLevel.RAIN_LIKELY

        # Cold front detection (rapid rise after falling)
        rising_rate = max(0.0, p_rate)
        cold_front = rising_rate >= COLD_FRONT_RISE_RATE

        # Rising pressure can also indicate CHANGING conditions
        if rising_rate >= RATE_CHANGING and threat < ThreatLevel.CHANGING:
            threat = ThreatLevel.CHANGING

        # EC fusion: regional warnings extend prediction horizon.
        # Only trust EC data less than 1 hour old. Can upgrade, never downgrade.
        if ec_data_age_s < 3600:
            if ec_warning_level == "warning" and threat < ThreatLevel.RAIN_LIKELY:
                threat = ThreatLevel.RAIN_LIKELY
            elif ec_warning_level in ("watch", "advisory") and threat < ThreatLevel.CHANGING:
                threat = ThreatLevel.CHANGING

        return WeatherTrend(
            pressure_trend_hpa_hr=p_rate,
            humidity_trend_pct_hr=h_rate,
            dew_point_spread_c=dew_spread,
            threat_level=threat,
            threat_label=THREAT_LABELS[threat],
            rain_imminent=rain_imminent,
            fog_risk=fog_risk,
            snow_risk=snow_risk,
            cold_front=cold_front,
        )

    def reset(self) -> None:
        """Clear all history (e.g., on session restart)."""
        self._short_window.clear()
        self._long_window.clear()
        self._trend = WeatherTrend()
