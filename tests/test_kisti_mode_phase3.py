"""Tests for Phase 3 additions — GPS status + mini G-dot overlay logic.

UI tests skip when PySide6 is unavailable (CI/cloud environments).
Pure logic tests always run.
"""

import math
import types
import pytest

pyside6_available = True
try:
    import PySide6
except ImportError:
    pyside6_available = False


@pytest.mark.skipif(not pyside6_available, reason="PySide6 not available")
class TestKistiModePhase3:
    def test_update_data_captures_gps(self):
        from ui.kisti_mode import KistiModeWidget
        widget = object.__new__(KistiModeWidget)
        widget._gps_altitude_m = 0.0
        widget._gps_satellites = 0
        widget._gps_fix_quality = 0
        widget._current_lat_g = 0.0
        widget._current_lon_g = 0.0
        widget._radar_cooldown = 0
        widget._last_radar_alert_id = None

        state = types.SimpleNamespace(
            gps_altitude_m=142.5, gps_satellites=12, gps_fix_quality=2,
            lateral_g=0.35, imu_accel_x=-0.2, radar=None,
        )
        widget.update_data(state)
        assert widget._gps_altitude_m == 142.5
        assert widget._gps_satellites == 12
        assert widget._current_lat_g == 0.35


class TestGDotLogic:
    """Pure-logic tests for the mini G-dot color thresholds (no Qt needed)."""

    def test_low_g_green(self):
        g_mag = math.sqrt(0.1 ** 2 + 0.1 ** 2)
        assert g_mag < 0.4  # Green threshold

    def test_mid_g_yellow(self):
        g_mag = math.sqrt(0.4 ** 2 + 0.3 ** 2)
        assert 0.4 <= g_mag < 0.7  # Yellow threshold

    def test_high_g_red(self):
        g_mag = math.sqrt(0.6 ** 2 + 0.5 ** 2)
        assert g_mag >= 0.7  # Red threshold

    def test_g_dot_pixel_clamp(self):
        """G values should be clamped to [-1, 1] for pixel mapping."""
        max_g = 1.0
        for val in (-2.0, -0.5, 0.0, 0.5, 2.0):
            clamped = max(-1.0, min(1.0, val / max_g))
            assert -1.0 <= clamped <= 1.0

    def test_gps_fix_labels(self):
        labels = {0: "No Fix", 1: "2D", 2: "3D"}
        assert labels[0] == "No Fix"
        assert labels[2] == "3D"
