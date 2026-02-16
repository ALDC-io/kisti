"""Unit tests for CAN frame decoding — pure Python, no CAN hardware required.

Tests cover:
  - DIFF frame (0x6A0) decode: normal, N/A signals, edge values
  - CONTEXT frame (0x6A1) decode: normal, neutral gear, max values
  - Encode/decode round-trip consistency
  - Error handling for short frames
  - DiffState staleness detection
"""

import struct
import time

import pytest

# Allow running from project root or tests/
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from can.kisti_can import (
    decode_context_frame,
    decode_diff_frame,
    encode_context_frame,
    encode_diff_frame,
)
from can.can_config import (
    DIFF_DCCD_DIAL_NA,
    DIFF_SLIP_NA,
)
from model.vehicle_state import DiffState, SurfaceState


# ========================================================================
# DIFF frame decode tests
# ========================================================================

class TestDecodeDiffFrame:
    """Tests for decode_diff_frame()."""

    def test_normal_all_signals(self):
        """All signals present with typical values."""
        data = encode_diff_frame(
            dccd_cmd=87.5,
            dccd_dial=45.2,
            surface=0,  # DRY
            flags=0x01,  # brake only
            slip=2.34,
        )
        result = decode_diff_frame(data)

        assert abs(result["dccd_command_pct"] - 87.5) < 0.15
        assert result["dccd_dial_pct"] is not None
        assert abs(result["dccd_dial_pct"] - 45.2) < 0.15
        assert result["surface_state"] == SurfaceState.DRY
        assert result["brake"] is True
        assert result["handbrake"] is False
        assert result["abs_active"] is False
        assert result["vdc_tc"] is False
        assert result["slip_delta"] is not None
        assert abs(result["slip_delta"] - 2.34) < 0.015

    def test_dial_not_available(self):
        """DCCD dial marked as N/A (0xFFFF)."""
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=None, surface=1, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["dccd_dial_pct"] is None
        assert result["surface_state"] == SurfaceState.WET

    def test_slip_not_available(self):
        """Slip delta marked as N/A (0x7FFF)."""
        data = encode_diff_frame(dccd_cmd=0.0, dccd_dial=0.0, surface=0, flags=0, slip=None)
        result = decode_diff_frame(data)

        assert result["slip_delta"] is None

    def test_negative_slip(self):
        """Negative slip delta (front spinning faster than rear)."""
        data = encode_diff_frame(dccd_cmd=60.0, dccd_dial=60.0, surface=0, flags=0, slip=-5.67)
        result = decode_diff_frame(data)

        assert result["slip_delta"] is not None
        assert abs(result["slip_delta"] - (-5.67)) < 0.015

    def test_all_flags_set(self):
        """All event flags active."""
        data = encode_diff_frame(dccd_cmd=100.0, dccd_dial=100.0, surface=3, flags=0x0F, slip=10.0)
        result = decode_diff_frame(data)

        assert result["brake"] is True
        assert result["handbrake"] is True
        assert result["abs_active"] is True
        assert result["vdc_tc"] is True
        assert result["surface_state"] == SurfaceState.LOW_GRIP

    def test_zero_lock(self):
        """DCCD fully unlocked (0%)."""
        data = encode_diff_frame(dccd_cmd=0.0, dccd_dial=0.0, surface=0, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["dccd_command_pct"] == 0.0

    def test_full_lock(self):
        """DCCD fully locked (100%)."""
        data = encode_diff_frame(dccd_cmd=100.0, dccd_dial=100.0, surface=0, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert abs(result["dccd_command_pct"] - 100.0) < 0.15

    def test_surface_cold(self):
        """Surface state = COLD."""
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=50.0, surface=2, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["surface_state"] == SurfaceState.COLD

    def test_unknown_surface_fallback(self):
        """Unknown surface enum falls back to DRY."""
        # Manually encode with invalid surface byte
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=50.0, surface=0, flags=0, slip=0.0)
        data = bytearray(data)
        data[4] = 99  # invalid enum
        result = decode_diff_frame(bytes(data))

        assert result["surface_state"] == SurfaceState.DRY

    def test_short_frame_raises(self):
        """Frame shorter than 8 bytes raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_diff_frame(b"\x00\x00\x00")


# ========================================================================
# CONTEXT frame decode tests
# ========================================================================

class TestDecodeContextFrame:
    """Tests for decode_context_frame()."""

    def test_normal(self):
        """Typical driving context: 3rd gear, 90 km/h, 55% throttle."""
        data = encode_context_frame(gear=3, speed_kph=90.0, throttle_pct=55.0)
        result = decode_context_frame(data)

        assert result["gear"] == 3
        assert abs(result["speed_kph"] - 90.0) < 0.015
        assert abs(result["throttle_pct"] - 55.0) < 0.15

    def test_neutral(self):
        """Neutral gear (0)."""
        data = encode_context_frame(gear=0, speed_kph=0.0, throttle_pct=0.0)
        result = decode_context_frame(data)

        assert result["gear"] == 0
        assert result["speed_kph"] == 0.0
        assert result["throttle_pct"] == 0.0

    def test_high_speed(self):
        """High speed: 6th gear, 220 km/h, 100% throttle."""
        data = encode_context_frame(gear=6, speed_kph=220.0, throttle_pct=100.0)
        result = decode_context_frame(data)

        assert result["gear"] == 6
        assert abs(result["speed_kph"] - 220.0) < 0.015
        assert abs(result["throttle_pct"] - 100.0) < 0.15

    def test_short_frame_raises(self):
        """Frame shorter than 5 bytes raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_context_frame(b"\x00\x00")


# ========================================================================
# Round-trip encode/decode tests
# ========================================================================

class TestRoundTrip:
    """Verify encode → decode round-trip consistency."""

    def test_diff_round_trip(self):
        """DIFF frame encode/decode preserves values within scaling precision."""
        for dccd in [0.0, 25.3, 50.0, 75.8, 100.0]:
            for slip in [-10.0, -1.23, 0.0, 5.67, 15.0]:
                data = encode_diff_frame(dccd, dccd, 0, 0, slip)
                result = decode_diff_frame(data)
                assert abs(result["dccd_command_pct"] - dccd) < 0.15
                assert abs(result["slip_delta"] - slip) < 0.015

    def test_context_round_trip(self):
        """CONTEXT frame encode/decode preserves values."""
        for gear in range(7):
            for speed in [0, 60, 120, 200]:
                data = encode_context_frame(gear, float(speed), 50.0)
                result = decode_context_frame(data)
                assert result["gear"] == gear
                assert abs(result["speed_kph"] - speed) < 0.015


# ========================================================================
# DiffState staleness tests
# ========================================================================

class TestDiffStateStaleness:
    """Tests for DiffState.is_diff_stale() / is_context_stale()."""

    def test_fresh_state_not_stale(self):
        now = time.monotonic()
        state = DiffState(diff_frame_ts=now, context_frame_ts=now)
        assert state.is_diff_stale(now, timeout=0.5) is False
        assert state.is_context_stale(now, timeout=0.5) is False
        assert state.is_any_stale(now, timeout=0.5) is False

    def test_zero_timestamp_is_stale(self):
        """Default timestamps (0.0) are always stale."""
        state = DiffState()
        assert state.is_diff_stale() is True
        assert state.is_context_stale() is True

    def test_old_timestamp_is_stale(self):
        now = time.monotonic()
        state = DiffState(diff_frame_ts=now - 1.0, context_frame_ts=now)
        assert state.is_diff_stale(now, timeout=0.5) is True
        assert state.is_context_stale(now, timeout=0.5) is False
        assert state.is_any_stale(now, timeout=0.5) is True


# ========================================================================
# SurfaceState enum tests
# ========================================================================

class TestSurfaceState:
    """Tests for SurfaceState enum properties."""

    def test_labels(self):
        assert SurfaceState.DRY.label == "DRY"
        assert SurfaceState.WET.label == "WET"
        assert SurfaceState.COLD.label == "COLD"
        assert SurfaceState.LOW_GRIP.label == "LOW GRIP"

    def test_colors(self):
        for s in SurfaceState:
            assert s.color.startswith("#")
            assert len(s.color) == 7

    def test_int_values(self):
        assert int(SurfaceState.DRY) == 0
        assert int(SurfaceState.WET) == 1
        assert int(SurfaceState.COLD) == 2
        assert int(SurfaceState.LOW_GRIP) == 3
