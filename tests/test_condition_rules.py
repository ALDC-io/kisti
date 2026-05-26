"""Tests for condition-to-action coaching rules."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.vehicle_state import DiffState, SurfaceState
from coaching.condition_rules import evaluate


def _snap(**kwargs) -> DiffState:
    return DiffState(**kwargs)


class TestConditionRules:
    def test_ice_risk_any_level(self):
        """Ice risk (road < 3C) shows at all coaching levels."""
        snap = _snap(brake_temp_fl=2.0, flir_available=True,
                     flir_frame_ts=time.monotonic())
        result = evaluate(snap, 0)  # MINIMAL
        assert result is not None
        text, sentiment = result
        assert "ice" in text.lower()
        assert sentiment == "amber"

    def test_cold_road_full_only(self):
        """Road 4C coaching only at FULL level."""
        snap = _snap(brake_temp_fl=4.0, flir_available=True,
                     flir_frame_ts=time.monotonic())
        # FULL — should show
        result = evaluate(snap, 2)
        assert result is not None
        assert "grip" in result[0].lower()

        # MINIMAL — should NOT show (level 2 rule)
        result = evaluate(snap, 0)
        assert result is None

    def test_wet_surface_moderate(self):
        """Wet surface shows at MODERATE and FULL."""
        snap = _snap(surface_state=SurfaceState.WET)
        result = evaluate(snap, 1)
        assert result is not None
        assert "wet" in result[0].lower()

        # MINIMAL — should NOT show
        result = evaluate(snap, 0)
        assert result is None

    def test_low_grip_always(self):
        """Low grip shows at all levels with action-only coaching (no redundant label)."""
        snap = _snap(surface_state=SurfaceState.LOW_GRIP)
        result = evaluate(snap, 0)
        assert result is not None
        assert "braking" in result[0].lower()
        assert result[1] == "amber"

    def test_oil_temp_warning(self):
        """High oil temp warning at MODERATE+."""
        snap = _snap(oil_temp_c=135.0)
        result = evaluate(snap, 1)
        assert result is not None
        assert "oil" in result[0].lower()
        assert sentiment_is(result, "amber")

    def test_cold_ambient_full(self):
        """Cold ambient tip at FULL only."""
        snap = _snap(ambient_temp_c=2.0, ambient_available=True)
        result = evaluate(snap, 2)
        assert result is not None
        assert "cold" in result[0].lower() or "warm" in result[0].lower()

        result = evaluate(snap, 0)
        assert result is None

    def test_humidity_full(self):
        """High humidity at FULL only."""
        snap = _snap(ambient_humidity_pct=90.0, ambient_temp_c=20.0,
                     ambient_available=True)
        result = evaluate(snap, 2)
        assert result is not None
        assert "humidity" in result[0].lower()

    def test_good_conditions(self):
        """Dry + warm road = positive feedback at FULL."""
        snap = _snap(
            surface_state=SurfaceState.DRY,
            brake_temp_fl=25.0,
            flir_available=True,
            flir_frame_ts=time.monotonic(),
        )
        result = evaluate(snap, 2)
        assert result is not None
        text, sentiment = result
        assert "good" in text.lower() or "push" in text.lower()
        assert sentiment == "green"

    def test_no_data_returns_none(self):
        """Default DiffState with no sensors returns None."""
        snap = _snap()
        result = evaluate(snap, 2)
        assert result is None

    def test_priority_ice_over_wet(self):
        """Ice risk (priority 0) beats wet surface (priority 2)."""
        snap = _snap(
            brake_temp_fl=1.0,
            flir_available=True,
            flir_frame_ts=time.monotonic(),
            surface_state=SurfaceState.WET,
        )
        result = evaluate(snap, 2)
        assert result is not None
        assert "ice" in result[0].lower()


def sentiment_is(result, expected):
    return result[1] == expected
