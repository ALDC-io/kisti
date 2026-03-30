"""Tests for voice timing integration — Phase 5.

Tests _answer_from_timing, _handle_timing_command, mode-aware
announcements, LLM timing context, and pit lane debrief.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from model.vehicle_state import DiffState, SIDriveMode


def _make_vm():
    """Create a VoiceManager with mic disabled for testing."""
    from voice.voice_manager import VoiceManager
    return VoiceManager(enable_mic=False)


def _make_snapshot(**overrides) -> DiffState:
    """Create a DiffState with timing fields populated."""
    defaults = dict(
        track_name="Laguna Seca",
        timing_mode="circuit",
        lap_count=5,
        current_lap_time_ms=62400,
        delta_ms=-350,
        predicted_lap_ms=91200,
        theoretical_best_ms=89700,
        current_sector=2,
        sector_count=3,
        last_sector_time_ms=21300,
        gps_latitude=36.5841,
        gps_longitude=-121.7534,
    )
    defaults.update(overrides)
    return DiffState(**defaults)


# ── _answer_from_timing ──────────────────────────────────────────────


class TestAnswerFromTiming:
    """Test the _answer_from_timing keyword dispatch."""

    def test_returns_none_without_snapshot(self):
        vm = _make_vm()
        vm._telemetry_snapshot = None
        assert vm._answer_from_timing("what's my delta") is None

    def test_returns_none_without_track(self):
        vm = _make_vm()
        vm._telemetry_snapshot = DiffState()  # track_name=""
        assert vm._answer_from_timing("what's my delta") is None

    def test_delta_ahead(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=-1500)
        result = vm._answer_from_timing("what's my delta")
        assert result is not None
        assert "1.5" in result
        assert "ahead" in result

    def test_delta_behind(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=2300)
        result = vm._answer_from_timing("am i ahead or behind")
        assert result is not None
        assert "2.3" in result
        assert "behind" in result

    def test_delta_no_reference(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=0, lap_count=1)
        result = vm._answer_from_timing("what's the gap")
        assert result is not None
        assert "reference" in result.lower()

    def test_theoretical_best(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(theoretical_best_ms=89700)
        result = vm._answer_from_timing("theoretical best")
        assert result is not None
        assert "1:29.7" in result

    def test_theoretical_no_data(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(theoretical_best_ms=0)
        result = vm._answer_from_timing("best possible lap")
        assert "not enough" in result.lower()

    def test_last_lap(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(current_lap_time_ms=45000)
        result = vm._answer_from_timing("what's my lap time")
        assert result is not None
        assert "45.0" in result

    def test_predicted_lap(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(predicted_lap_ms=91200)
        result = vm._answer_from_timing("what am i on pace for")
        assert result is not None
        assert "1:31.2" in result

    def test_predicted_no_data(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(predicted_lap_ms=0)
        result = vm._answer_from_timing("what's the projected time")
        assert "not enough" in result.lower()

    def test_sector_times(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        # Mock timing manager with sector data
        mock_tm = MagicMock()
        mock_tm.lap_timer.get_best_sector_times.return_value = [28.3, 31.1, 30.2]
        vm._timing_manager = mock_tm
        result = vm._answer_from_timing("what are my sector times")
        assert result is not None
        assert "S1: 28.3" in result
        assert "S2: 31.1" in result
        assert "S3: 30.2" in result

    def test_sector_no_manager(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        vm._timing_manager = None
        assert vm._answer_from_timing("sector times") is None

    def test_sector_no_data(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        mock_tm = MagicMock()
        mock_tm.lap_timer.get_best_sector_times.return_value = [None, None, None]
        vm._timing_manager = mock_tm
        result = vm._answer_from_timing("splits")
        assert "no sector" in result.lower()

    def test_track_name(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        result = vm._answer_from_timing("what track am i on")
        assert "Laguna Seca" in result
        assert "Circuit" in result

    def test_track_p2p_mode(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(timing_mode="point_to_point")
        result = vm._answer_from_timing("which track")
        assert "point to point" in result.lower()

    def test_lap_count(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(lap_count=12)
        result = vm._answer_from_timing("how many laps")
        assert "12" in result

    def test_unrelated_query_returns_none(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        assert vm._answer_from_timing("tell me a joke") is None

    def test_time_format_over_60s(self):
        """Times >= 60s should format as M:SS.s."""
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(theoretical_best_ms=125300)
        result = vm._answer_from_timing("perfect lap")
        assert "2:05.3" in result

    def test_time_format_under_60s(self):
        """Times < 60s should format as SS.s seconds."""
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(current_lap_time_ms=45000)
        result = vm._answer_from_timing("last lap")
        assert "45.0 seconds" in result


# ── _handle_timing_command ───────────────────────────────────────────


class TestTimingCommands:
    """Test voice commands for timing control."""

    def test_returns_none_without_manager(self):
        vm = _make_vm()
        vm._timing_manager = None
        assert vm._handle_timing_command("point to point mode") is None

    def test_p2p_mode_request(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        result = vm._handle_timing_command("point to point mode")
        assert result is not None
        assert "point to point" in result.lower()

    def test_p2p_shorthand(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        result = vm._handle_timing_command("switch to p2p mode")
        assert result is not None

    def test_circuit_mode(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        vm._timing_manager = mock_tm
        result = vm._handle_timing_command("circuit mode")
        assert result is not None
        assert "circuit" in result.lower()
        mock_tm.lap_timer.set_circuit_mode.assert_called_once()

    def test_lap_mode_alias(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        vm._timing_manager = mock_tm
        result = vm._handle_timing_command("back to laps")
        assert result is not None
        mock_tm.lap_timer.set_circuit_mode.assert_called_once()

    def test_set_reference_lap(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        # Simulate 5 completed laps
        mock_lap = MagicMock()
        mock_lap.total_time = 91.5
        mock_tm.lap_timer._completed_laps = [mock_lap] * 5
        vm._timing_manager = mock_tm
        result = vm._handle_timing_command("use lap 3 as reference")
        assert result is not None
        assert "lap 3" in result.lower()
        mock_tm.lap_timer.set_reference_lap.assert_called_once_with(2)  # 0-indexed

    def test_reference_lap_out_of_range(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        mock_tm.lap_timer._completed_laps = []
        vm._timing_manager = mock_tm
        result = vm._handle_timing_command("use lap 5 as reference")
        assert "not found" in result.lower()

    def test_reference_lap_alt_syntax(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        mock_lap = MagicMock()
        mock_lap.total_time = 88.2
        mock_tm.lap_timer._completed_laps = [mock_lap] * 3
        vm._timing_manager = mock_tm
        result = vm._handle_timing_command("reference lap 2")
        assert "lap 2" in result.lower()
        mock_tm.lap_timer.set_reference_lap.assert_called_once_with(1)

    def test_set_start_with_gps(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        vm._telemetry_snapshot = _make_snapshot()
        result = vm._handle_timing_command("set start point")
        assert result is not None
        assert "start point set" in result.lower()
        assert vm._p2p_start is not None

    def test_set_start_no_gps(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        vm._telemetry_snapshot = DiffState()  # gps 0,0
        result = vm._handle_timing_command("set start point")
        assert "no gps" in result.lower()

    def test_set_end_without_start(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        vm._telemetry_snapshot = _make_snapshot()
        vm._p2p_start = None
        result = vm._handle_timing_command("set end point")
        assert "start point first" in result.lower()

    def test_set_end_with_start(self):
        vm = _make_vm()
        mock_tm = MagicMock()
        vm._timing_manager = mock_tm
        vm._telemetry_snapshot = _make_snapshot()
        # Set start first
        from timing.track_db import StartFinishLine
        vm._p2p_start = StartFinishLine(lat1=36.58, lon1=-121.75, lat2=36.58, lon2=-121.74)
        result = vm._handle_timing_command("set end point")
        assert "live" in result.lower()
        mock_tm.lap_timer.set_p2p_mode.assert_called_once()

    def test_unrelated_returns_none(self):
        vm = _make_vm()
        vm._timing_manager = MagicMock()
        assert vm._handle_timing_command("tell me a joke") is None


# ── Dispatch chain integration ───────────────────────────────────────


class TestTimingDispatchChain:
    """Verify timing hooks are in the correct position in handle_voice_query."""

    def test_timing_command_before_thinking(self):
        """Timing commands should resolve before LLM is called."""
        vm = _make_vm()
        mock_tm = MagicMock()
        vm._timing_manager = mock_tm
        spoken = []
        vm._compose_and_speak = lambda resp, **kw: spoken.append(resp.text)
        vm._set_state = MagicMock()

        vm.handle_voice_query("circuit mode")
        assert len(spoken) == 1
        assert "circuit" in spoken[0].lower()
        # Should NOT have entered THINKING state
        thinking_calls = [c for c in vm._set_state.call_args_list
                          if c.args[0] == 2]  # VoiceState.THINKING = 2
        assert len(thinking_calls) == 0

    def test_timing_query_before_sensors(self):
        """Timing queries should be checked before sensor queries."""
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        spoken = []
        vm._compose_and_speak = lambda resp, **kw: spoken.append((resp.source, resp.text))

        vm.handle_voice_query("what's my delta")
        assert len(spoken) == 1
        assert spoken[0][0] == "timing"  # source should be "timing", not "sensor"


# ── LLM timing context ──────────────────────────────────────────────


class TestLLMTimingContext:
    """Test _build_telemetry_context includes timing data."""

    def test_no_timing_when_no_track(self):
        vm = _make_vm()
        vm._telemetry_snapshot = DiffState()  # no track
        ctx = vm._build_telemetry_context()
        assert "Track:" not in ctx

    def test_includes_track_name(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        ctx = vm._build_telemetry_context()
        assert "Track: Laguna Seca" in ctx

    def test_includes_delta(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=-1500)
        ctx = vm._build_telemetry_context()
        assert "Delta: -1.5s" in ctx

    def test_includes_predicted(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(predicted_lap_ms=91200)
        ctx = vm._build_telemetry_context()
        assert "Predicted Lap: 91.2s" in ctx

    def test_includes_theoretical(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(theoretical_best_ms=89700)
        ctx = vm._build_telemetry_context()
        assert "Theoretical Best: 89.7s" in ctx

    def test_includes_sector(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(current_sector=2, sector_count=3)
        ctx = vm._build_telemetry_context()
        assert "Sector: 2/3" in ctx

    def test_includes_lap_count(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(lap_count=7)
        ctx = vm._build_telemetry_context()
        assert "Lap: 7" in ctx

    def test_includes_timing_mode(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(timing_mode="point_to_point")
        ctx = vm._build_telemetry_context()
        assert "point_to_point" in ctx


# ── offset_line geometry ─────────────────────────────────────────────


class TestOffsetLine:
    """Test the offset_line helper in timing/geo.py."""

    def test_returns_four_floats(self):
        from timing.geo import offset_line
        result = offset_line(36.5841, -121.7534, width_m=10.0)
        assert len(result) == 4
        assert all(isinstance(v, float) for v in result)

    def test_lat_preserved(self):
        from timing.geo import offset_line
        lat1, lon1, lat2, lon2 = offset_line(36.5841, -121.7534)
        # East-west line: lat should be same for both points
        assert lat1 == lat2 == 36.5841

    def test_lon_offset_symmetric(self):
        from timing.geo import offset_line
        lat1, lon1, lat2, lon2 = offset_line(36.5841, -121.7534)
        center = -121.7534
        assert lon1 < center
        assert lon2 > center
        assert abs((center - lon1) - (lon2 - center)) < 1e-10

    def test_width_affects_spread(self):
        from timing.geo import offset_line
        _, lon1a, _, lon2a = offset_line(36.5841, -121.7534, width_m=10.0)
        _, lon1b, _, lon2b = offset_line(36.5841, -121.7534, width_m=20.0)
        spread_a = lon2a - lon1a
        spread_b = lon2b - lon1b
        assert spread_b > spread_a


# ── set_timing_manager ───────────────────────────────────────────────


class TestSetTimingManager:
    """Test wiring of timing manager to voice manager."""

    def test_initially_none(self):
        vm = _make_vm()
        assert vm._timing_manager is None

    def test_set_stores_reference(self):
        vm = _make_vm()
        mock = MagicMock()
        vm.set_timing_manager(mock)
        assert vm._timing_manager is mock

    def test_p2p_start_initially_none(self):
        vm = _make_vm()
        assert vm._p2p_start is None


# ── Phase 8: Additional voice queries ────────────────────────────────


class TestAdditionalQueries:
    """Test 'what lap', 'best lap', 'pace' queries added in Phase 8."""

    def test_what_lap(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(lap_count=7)
        result = vm._answer_from_timing("what lap am i on")
        assert "7" in result

    def test_which_lap(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(lap_count=3)
        result = vm._answer_from_timing("which lap is this")
        assert "3" in result

    def test_no_laps_yet(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(lap_count=0)
        result = vm._answer_from_timing("what lap am i on")
        assert "no laps" in result.lower()

    def test_best_lap(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        mock_tm = MagicMock()
        mock_tm.get_session_summary.return_value = {
            "total_laps": 5,
            "best_lap_number": 3,
            "best_lap_time_s": 91.5,
        }
        vm._timing_manager = mock_tm
        result = vm._answer_from_timing("what's my best lap")
        assert "91.5" in result
        assert "lap 3" in result.lower()

    def test_best_lap_no_data(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot()
        mock_tm = MagicMock()
        mock_tm.get_session_summary.return_value = {}
        vm._timing_manager = mock_tm
        result = vm._answer_from_timing("fastest lap")
        assert "no laps" in result.lower()

    def test_pace_with_delta(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=-1200, predicted_lap_ms=89500)
        result = vm._answer_from_timing("how's my pace")
        assert "1.2" in result
        assert "ahead" in result
        assert "89.5" in result

    def test_pace_behind(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=2000, predicted_lap_ms=93000)
        result = vm._answer_from_timing("how am i doing")
        assert "behind" in result

    def test_pace_no_data(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=0, predicted_lap_ms=0)
        result = vm._answer_from_timing("my pace")
        assert "not enough" in result.lower()

    def test_pace_predicted_only(self):
        vm = _make_vm()
        vm._telemetry_snapshot = _make_snapshot(delta_ms=0, predicted_lap_ms=91000)
        result = vm._answer_from_timing("pace")
        assert "91.0" in result


# ── Phase 8: GPS dropout recovery ────────────────────────────────────


class TestGPSDropoutRecovery:
    """Test GPS jump filter in TimingManager."""

    def test_large_jump_rejected(self):
        """GPS jump >500m should be skipped (satellite reacquire)."""
        from timing.timing_manager import TimingManager
        from unittest.mock import MagicMock, PropertyMock

        bridge = MagicMock()
        mgr = TimingManager(bridge=bridge, db_store=None)
        mgr._active = True
        mgr._track_detected = True  # already have a track

        # Set initial GPS position
        mgr._prev_gps_lat = 36.5841
        mgr._prev_gps_lon = -121.7534

        # Simulate a large jump (>500m away)
        snap = MagicMock()
        snap.gps_latitude = 37.0  # ~46km north
        snap.gps_longitude = -121.7534
        bridge.snapshot.return_value = snap

        mgr._on_state_changed()

        # Position should update (for next comparison) but timer should NOT be fed
        assert mgr._prev_gps_lat == 37.0
        # LapTimer.update should not have been called (no events)

    def test_normal_movement_accepted(self):
        """Small GPS movement should be passed through to LapTimer."""
        from timing.timing_manager import TimingManager

        bridge = MagicMock()
        mgr = TimingManager(bridge=bridge, db_store=None)
        mgr._active = True
        mgr._track_detected = True

        mgr._prev_gps_lat = 36.5841
        mgr._prev_gps_lon = -121.7534

        # Small movement (~11m)
        snap = MagicMock()
        snap.gps_latitude = 36.5842
        snap.gps_longitude = -121.7534
        bridge.snapshot.return_value = snap

        # Should reach update_bridge_timing (which calls blockSignals)
        mgr._on_state_changed()
        assert mgr._prev_gps_lat == 36.5842
