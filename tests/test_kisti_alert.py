"""Tests for encode_kisti_alert() — CAN frame 0x6C2 encoder.

Covers baseline 3-param behavior, weather_threat_level integration,
priority chain ordering, and CAN frame format.
"""

import struct

import pytest

from can.kisti_can import encode_kisti_alert


def _decode(data: bytes) -> int:
    """Unpack single-byte CAN alert status."""
    return struct.unpack("B", data)[0]


# ---------------------------------------------------------------------------
# Baseline — existing 3-param behavior (backward compatibility)
# ---------------------------------------------------------------------------


class TestEncodeKistiAlertBaseline:
    """All existing enum values work with 3-param calls (no weather_threat_level)."""

    def test_dry_no_events_returns_ok(self):
        assert _decode(encode_kisti_alert("DRY", "", "none")) == 0

    def test_empty_strings_returns_ok(self):
        assert _decode(encode_kisti_alert("", "", "")) == 0

    def test_wet_returns_1(self):
        assert _decode(encode_kisti_alert("WET", "", "none")) == 1

    def test_moist_returns_1(self):
        assert _decode(encode_kisti_alert("MOIST", "", "none")) == 1

    def test_slushy_returns_1(self):
        assert _decode(encode_kisti_alert("SLUSHY", "", "none")) == 1

    def test_icy_returns_2(self):
        assert _decode(encode_kisti_alert("ICY", "", "none")) == 2

    def test_snowy_returns_2(self):
        assert _decode(encode_kisti_alert("SNOWY", "", "none")) == 2

    def test_frosty_returns_2(self):
        assert _decode(encode_kisti_alert("FROSTY", "", "none")) == 2

    def test_cold_returns_2(self):
        assert _decode(encode_kisti_alert("COLD", "", "none")) == 2

    def test_ec_warning_returns_4(self):
        assert _decode(encode_kisti_alert("DRY", "", "warning")) == 4

    def test_ec_watch_returns_4(self):
        assert _decode(encode_kisti_alert("DRY", "", "watch")) == 4

    def test_major_event_returns_4(self):
        assert _decode(encode_kisti_alert("DRY", "MAJOR", "none")) == 4

    def test_closure_returns_5(self):
        assert _decode(encode_kisti_alert("DRY", "CLOSURE", "none")) == 5


# ---------------------------------------------------------------------------
# Weather threat level integration (4th param)
# ---------------------------------------------------------------------------


class TestEncodeKistiAlertWeather:
    """Weather_threat_level correctly maps to CAN status."""

    def test_storm_on_dry_road_returns_4(self):
        assert _decode(encode_kisti_alert("DRY", "", "none", "STORM")) == 4

    def test_rain_likely_on_dry_road_returns_3(self):
        assert _decode(encode_kisti_alert("DRY", "", "none", "RAIN_LIKELY")) == 3

    def test_changing_on_dry_road_returns_ok(self):
        # CHANGING is advisory only — not severe enough for Strada alert
        assert _decode(encode_kisti_alert("DRY", "", "none", "CHANGING")) == 0

    def test_clear_default_returns_ok(self):
        # Default param value = CLEAR
        assert _decode(encode_kisti_alert("DRY", "", "none")) == 0


# ---------------------------------------------------------------------------
# Priority chain — higher-priority conditions override weather
# ---------------------------------------------------------------------------


class TestEncodeKistiAlertPriority:
    """Priority chain ordering is correct."""

    def test_closure_beats_storm(self):
        assert _decode(encode_kisti_alert("DRY", "CLOSURE", "none", "STORM")) == 5

    def test_icy_beats_storm(self):
        assert _decode(encode_kisti_alert("ICY", "", "none", "STORM")) == 2

    def test_major_event_beats_rain_likely(self):
        assert _decode(encode_kisti_alert("DRY", "MAJOR", "none", "RAIN_LIKELY")) == 4

    def test_ec_warning_beats_weather_storm(self):
        # Both map to 4, but EC takes priority in the chain
        assert _decode(encode_kisti_alert("DRY", "", "warning", "STORM")) == 4

    def test_weather_storm_beats_wet(self):
        assert _decode(encode_kisti_alert("WET", "", "none", "STORM")) == 4

    def test_weather_rain_likely_beats_wet(self):
        assert _decode(encode_kisti_alert("WET", "", "none", "RAIN_LIKELY")) == 3

    def test_wet_wins_over_changing(self):
        assert _decode(encode_kisti_alert("WET", "", "none", "CHANGING")) == 1

    def test_closure_beats_everything(self):
        assert _decode(encode_kisti_alert("ICY", "CLOSURE", "warning", "STORM")) == 5

    def test_icy_beats_major_and_weather(self):
        assert _decode(encode_kisti_alert("ICY", "MAJOR", "none", "STORM")) == 2


# ---------------------------------------------------------------------------
# CAN frame format
# ---------------------------------------------------------------------------


class TestEncodeKistiAlertFormat:
    """Output is always a valid single-byte CAN frame."""

    @pytest.mark.parametrize("road,event,ec,weather", [
        ("DRY", "", "none", "CLEAR"),
        ("WET", "", "none", "CLEAR"),
        ("ICY", "", "none", "CLEAR"),
        ("DRY", "", "none", "RAIN_LIKELY"),
        ("DRY", "", "none", "STORM"),
        ("DRY", "CLOSURE", "none", "CLEAR"),
    ])
    def test_returns_single_byte(self, road, event, ec, weather):
        result = encode_kisti_alert(road, event, ec, weather)
        assert len(result) == 1

    @pytest.mark.parametrize("road,event,ec,weather", [
        ("DRY", "", "none", "CLEAR"),
        ("WET", "", "none", "CLEAR"),
        ("ICY", "", "none", "CLEAR"),
        ("DRY", "", "none", "RAIN_LIKELY"),
        ("DRY", "", "none", "STORM"),
        ("DRY", "CLOSURE", "none", "CLEAR"),
        ("DRY", "MAJOR", "warning", "STORM"),
    ])
    def test_all_values_in_valid_range(self, road, event, ec, weather):
        status = _decode(encode_kisti_alert(road, event, ec, weather))
        assert 0 <= status <= 5
