"""Tests for KiSTI Weather Nowcasting Engine.

Verifies rate-of-change calculation, threat level classification,
multi-sensor detection rules, and edge cases.
"""

import time
from unittest.mock import patch

import pytest

from sensors.weather_engine import (
    WeatherEngine,
    WeatherTrend,
    ThreatLevel,
    THREAT_LABELS,
    _slope_per_hour,
    _Sample,
    RATE_CHANGING,
    RATE_RAIN_LIKELY,
    RATE_STORM,
    MIN_SAMPLES_SHORT,
)


# ---------------------------------------------------------------------------
# Synthetic clock for deterministic tests
# ---------------------------------------------------------------------------

class _FakeClock:
    """Monotonic clock that advances by a fixed step on each call."""
    def __init__(self, start: float = 0.0, step: float = 1.0):
        self._now = start
        self._step = step

    def __call__(self) -> float:
        t = self._now
        self._now += self._step
        return t


def _make_engine(dt: float = 1.0) -> WeatherEngine:
    """Create a WeatherEngine with a synthetic clock advancing dt per feed."""
    return WeatherEngine(clock=_FakeClock(start=0.0, step=dt))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feed_stable(engine: WeatherEngine, n: int = 60, pressure: float = 1013.0,
                 humidity: float = 45.0, temp: float = 22.0, dew: float = 10.0,
                 dt: float = 1.0) -> WeatherTrend:
    """Feed n stable readings with monotonic time advancing by dt each."""
    trend = None
    for _ in range(n):
        trend = engine.feed(pressure, humidity, temp, dew)
    return trend


def _feed_falling(engine: WeatherEngine, n: int = 60, start_pressure: float = 1013.0,
                  rate_hpa_hr: float = 1.0, humidity: float = 45.0,
                  temp: float = 22.0, dew: float = 10.0, dt: float = 1.0) -> WeatherTrend:
    """Feed n readings with pressure falling at given rate."""
    p = start_pressure
    dp_per_sample = -rate_hpa_hr * dt / 3600.0  # hPa per sample
    trend = None
    for _ in range(n):
        trend = engine.feed(p, humidity, temp, dew)
        p += dp_per_sample
    return trend


def _feed_rising(engine: WeatherEngine, n: int = 60, start_pressure: float = 1000.0,
                 rate_hpa_hr: float = 1.0, humidity: float = 45.0,
                 temp: float = 22.0, dew: float = 10.0, dt: float = 1.0) -> WeatherTrend:
    """Feed n readings with pressure rising at given rate."""
    p = start_pressure
    dp_per_sample = rate_hpa_hr * dt / 3600.0
    trend = None
    for _ in range(n):
        trend = engine.feed(p, humidity, temp, dew)
        p += dp_per_sample
    return trend


# ---------------------------------------------------------------------------
# slope_per_hour unit tests
# ---------------------------------------------------------------------------

class TestSlopePerHour:
    def test_flat_data_returns_zero(self):
        samples = [_Sample(ts=i, pressure_hpa=1013.0, humidity_pct=45.0,
                           temp_c=22.0, dew_point_c=10.0) for i in range(60)]
        slope = _slope_per_hour(samples, lambda s: s.pressure_hpa)
        assert abs(slope) < 0.01

    def test_linear_falling_1hpa_hr(self):
        """1 hPa/hr falling over 10 minutes = ~0.167 hPa in 600s."""
        samples = []
        for i in range(600):
            p = 1013.0 - (i / 3600.0) * 1.0  # 1 hPa/hr
            samples.append(_Sample(ts=i, pressure_hpa=p, humidity_pct=45.0,
                                   temp_c=22.0, dew_point_c=10.0))
        slope = _slope_per_hour(samples, lambda s: s.pressure_hpa)
        assert abs(slope - (-1.0)) < 0.01

    def test_linear_rising_2hpa_hr(self):
        samples = []
        for i in range(600):
            p = 1000.0 + (i / 3600.0) * 2.0
            samples.append(_Sample(ts=i, pressure_hpa=p, humidity_pct=45.0,
                                   temp_c=22.0, dew_point_c=10.0))
        slope = _slope_per_hour(samples, lambda s: s.pressure_hpa)
        assert abs(slope - 2.0) < 0.01

    def test_single_sample_returns_zero(self):
        samples = [_Sample(ts=0, pressure_hpa=1013.0, humidity_pct=45.0,
                           temp_c=22.0, dew_point_c=10.0)]
        slope = _slope_per_hour(samples, lambda s: s.pressure_hpa)
        assert slope == 0.0

    def test_empty_returns_zero(self):
        slope = _slope_per_hour([], lambda s: s.pressure_hpa)
        assert slope == 0.0

    def test_humidity_slope(self):
        samples = []
        for i in range(600):
            h = 40.0 + (i / 3600.0) * 10.0  # 10%/hr rising
            samples.append(_Sample(ts=i, pressure_hpa=1013.0, humidity_pct=h,
                                   temp_c=22.0, dew_point_c=10.0))
        slope = _slope_per_hour(samples, lambda s: s.humidity_pct)
        assert abs(slope - 10.0) < 0.1


# ---------------------------------------------------------------------------
# Threat level classification
# ---------------------------------------------------------------------------

class TestThreatLevels:
    def test_stable_pressure_is_clear(self):
        engine = _make_engine()
        trend = _feed_stable(engine, n=60, pressure=1013.0)
        assert trend.threat_level == ThreatLevel.CLEAR
        assert trend.threat_label == "CLEAR"

    def test_slow_fall_is_changing(self):
        """0.8 hPa/hr falling should be CHANGING."""
        engine = _make_engine()
        trend = _feed_falling(engine, n=120, rate_hpa_hr=0.8)
        assert trend.threat_level == ThreatLevel.CHANGING

    def test_moderate_fall_is_rain_likely(self):
        """2.0 hPa/hr falling should be RAIN_LIKELY."""
        engine = _make_engine()
        trend = _feed_falling(engine, n=120, rate_hpa_hr=2.0)
        assert trend.threat_level == ThreatLevel.RAIN_LIKELY

    def test_rapid_fall_is_storm(self):
        """4.0 hPa/hr falling should be STORM."""
        engine = _make_engine()
        trend = _feed_falling(engine, n=120, rate_hpa_hr=4.0)
        assert trend.threat_level == ThreatLevel.STORM

    def test_rising_pressure_is_changing(self):
        """Rising pressure above threshold should be CHANGING."""
        engine = _make_engine()
        trend = _feed_rising(engine, n=120, rate_hpa_hr=0.8)
        assert trend.threat_level >= ThreatLevel.CHANGING

    def test_threat_labels_match_enum(self):
        for level in ThreatLevel:
            assert level in THREAT_LABELS

    def test_below_threshold_is_clear(self):
        """0.3 hPa/hr should be CLEAR."""
        engine = _make_engine()
        trend = _feed_falling(engine, n=120, rate_hpa_hr=0.3)
        assert trend.threat_level == ThreatLevel.CLEAR


# ---------------------------------------------------------------------------
# Multi-sensor rain detection
# ---------------------------------------------------------------------------

class TestRainDetection:
    def test_rain_imminent_all_conditions(self):
        """Falling baro + low dew spread + high humidity = rain imminent."""
        engine = _make_engine()
        trend = _feed_falling(
            engine, n=120, rate_hpa_hr=2.0,
            humidity=90.0, temp=15.0, dew=13.0,  # spread=2.0
        )
        assert trend.rain_imminent is True
        assert trend.threat_level >= ThreatLevel.RAIN_LIKELY

    def test_no_rain_when_dry(self):
        """Falling baro but dry air = no rain detection."""
        engine = _make_engine()
        trend = _feed_falling(
            engine, n=120, rate_hpa_hr=2.0,
            humidity=40.0, temp=22.0, dew=8.0,  # spread=14.0
        )
        assert trend.rain_imminent is False

    def test_no_rain_when_stable(self):
        """High humidity but stable pressure = no rain."""
        engine = _make_engine()
        trend = _feed_stable(
            engine, n=120, pressure=1013.0,
            humidity=90.0, temp=15.0, dew=13.0,
        )
        assert trend.rain_imminent is False

    def test_rain_upgrades_threat(self):
        """Rain conditions should upgrade threat to at least RAIN_LIKELY."""
        engine = _make_engine()
        # Moderate fall that would normally be RAIN_LIKELY anyway
        trend = _feed_falling(
            engine, n=120, rate_hpa_hr=1.6,
            humidity=90.0, temp=15.0, dew=13.0,
        )
        assert trend.threat_level >= ThreatLevel.RAIN_LIKELY


# ---------------------------------------------------------------------------
# Fog detection
# ---------------------------------------------------------------------------

class TestFogDetection:
    def test_fog_risk_conditions(self):
        """Very small dew spread + very high humidity = fog risk."""
        engine = _make_engine()
        trend = _feed_stable(
            engine, n=60,
            humidity=95.0, temp=10.0, dew=9.0,  # spread=1.0
        )
        assert trend.fog_risk is True

    def test_no_fog_when_dry(self):
        """Large dew spread = no fog."""
        engine = _make_engine()
        trend = _feed_stable(
            engine, n=60,
            humidity=40.0, temp=22.0, dew=8.0,
        )
        assert trend.fog_risk is False


# ---------------------------------------------------------------------------
# Cold front detection
# ---------------------------------------------------------------------------

class TestColdFront:
    def test_cold_front_rapid_rise(self):
        """Rapid pressure rise = cold front passage."""
        engine = _make_engine()
        trend = _feed_rising(engine, n=120, rate_hpa_hr=2.5)
        assert trend.cold_front is True

    def test_no_cold_front_slow_rise(self):
        """Slow rise = not a cold front."""
        engine = _make_engine()
        trend = _feed_rising(engine, n=120, rate_hpa_hr=0.5)
        assert trend.cold_front is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_insufficient_samples_returns_clear(self):
        """Less than MIN_SAMPLES_SHORT should return CLEAR with zero rates."""
        engine = _make_engine()
        trend = engine.feed(1013.0, 45.0, 22.0, 10.0)
        assert trend.threat_level == ThreatLevel.CLEAR
        assert trend.pressure_trend_hpa_hr == 0.0

    def test_reset_clears_history(self):
        engine = _make_engine()
        _feed_falling(engine, n=120, rate_hpa_hr=4.0)
        assert engine.trend.threat_level == ThreatLevel.STORM
        engine.reset()
        assert engine.trend.threat_level == ThreatLevel.CLEAR
        assert len(engine._short_window) == 0
        assert len(engine._long_window) == 0

    def test_dew_point_spread_calculation(self):
        engine = _make_engine()
        trend = _feed_stable(engine, n=60, temp=22.0, dew=10.0)
        assert abs(trend.dew_point_spread_c - 12.0) < 0.01

    def test_default_trend_is_safe(self):
        """Fresh engine with no data should be safe defaults."""
        engine = _make_engine()
        t = engine.trend
        assert t.threat_level == ThreatLevel.CLEAR
        assert t.dew_point_spread_c == 99.0
        assert t.rain_imminent is False
        assert t.fog_risk is False

    def test_window_trimming(self):
        """Old samples should be evicted from windows."""
        engine = _make_engine()
        # Feed 700 samples (> 600s window)
        _feed_stable(engine, n=700)
        assert len(engine._short_window) <= 601  # 600s + margin
