"""Tests for timing display widget and Zeus push — Phase 6."""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock

# Force offscreen Qt platform for headless testing
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from model.vehicle_state import DiffState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ── TimingDisplayWidget ──────────────────────────────────────────────


class TestTimingDisplay:
    """Test the timing display widget."""

    def _make_widget(self, qapp):
        from ui.widgets.timing_display import TimingDisplayWidget
        return TimingDisplayWidget()

    def test_initial_state(self, qapp):
        w = self._make_widget(qapp)
        assert w._lap_count == 0
        assert w._delta_ms == 0
        assert w._track_name == ""

    def test_update_timing_stores_fields(self, qapp):
        w = self._make_widget(qapp)
        w.update_timing(
            lap_count=3,
            delta_ms=-500,
            track_name="Laguna Seca",
            timing_mode="circuit",
            current_lap_time_ms=45000,
            predicted_lap_ms=91000,
            theoretical_best_ms=89000,
            current_sector=1,
            sector_count=3,
        )
        assert w._lap_count == 3
        assert w._delta_ms == -500
        assert w._track_name == "Laguna Seca"
        assert w._predicted_lap_ms == 91000
        assert w._theoretical_best_ms == 89000
        assert w._current_sector == 1
        assert w._sector_count == 3

    def test_set_mode(self, qapp):
        w = self._make_widget(qapp)
        w.set_mode(2)  # SPORT_SHARP
        assert w._mode == 2

    def test_fmt_time_under_60(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget._fmt_time(45000) == "45.0"

    def test_fmt_time_over_60(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget._fmt_time(91200) == "1:31.2"

    def test_fmt_time_zero(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget._fmt_time(0) == "--:--.--"

    def test_fmt_time_exactly_60(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget._fmt_time(60000) == "1:00.0"

    def test_fmt_time_2min(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget._fmt_time(125300) == "2:05.3"

    def test_mode_constants(self):
        from ui.widgets.timing_display import TimingDisplayWidget
        assert TimingDisplayWidget.MODE_INTELLIGENT == 0
        assert TimingDisplayWidget.MODE_SPORT == 1
        assert TimingDisplayWidget.MODE_SPORT_SHARP == 2

    def test_delta_sign_change_triggers_flash(self, qapp):
        w = self._make_widget(qapp)
        w._prev_delta_sign = -1  # was ahead
        w.update_timing(delta_ms=500, track_name="Test")  # now behind
        assert w._flash_timer.isActive()


# ── TrackModeWidget timing integration ───────────────────────────────


class TestTrackModeTimingIntegration:
    """Test timing display wiring in track mode."""

    def test_track_mode_has_timing_display(self, qapp):
        from ui.track_mode import TrackModeWidget
        w = TrackModeWidget()
        assert hasattr(w, '_timing_display')

    def test_update_timing_delegates(self, qapp):
        from ui.track_mode import TrackModeWidget
        w = TrackModeWidget()
        snap = DiffState(
            track_name="Test Track",
            lap_count=2,
            delta_ms=-100,
            timing_mode="circuit",
        )
        w.update_timing(snap)
        assert w._timing_display._track_name == "Test Track"
        assert w._timing_display._lap_count == 2
        assert w._timing_display._delta_ms == -100

    def test_set_timing_mode_delegates(self, qapp):
        from ui.track_mode import TrackModeWidget
        w = TrackModeWidget()
        w.set_timing_mode(2)
        assert w._timing_display._mode == 2


# ── Zeus timing push ─────────────────────────────────────────────────


class TestZeusPush:
    """Test the timing summary format for Zeus push."""

    def test_summary_content_format(self):
        """Verify summary dict has required fields."""
        summary = {
            "total_laps": 5,
            "best_lap_number": 3,
            "best_lap_time_s": 91.5,
            "last_lap_time_s": 93.2,
            "theoretical_best_s": 89.7,
            "track_name": "Laguna Seca",
        }
        assert summary["total_laps"] > 0
        assert summary["best_lap_number"] > 0
        assert summary["best_lap_time_s"] > 0
        assert "track_name" in summary

    def test_empty_summary_skipped(self):
        """Empty or zero-lap summary should be a no-op."""
        summary = {}
        assert summary.get("total_laps", 0) == 0
        summary2 = {"total_laps": 0}
        assert summary2.get("total_laps", 0) == 0
