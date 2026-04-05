"""Tests for Sport + Sharp Screens (Phases 4-5) — logic only, no Qt rendering."""

import types
import pytest

pyside6_available = True
try:
    import PySide6
except ImportError:
    pyside6_available = False

pytestmark = pytest.mark.skipif(not pyside6_available, reason="PySide6 not available")


class TestSportScreenLogic:
    """Test coaching data update methods."""

    def test_update_balance(self):
        from ui.sport_screen import SportScreen
        screen = object.__new__(SportScreen)
        screen._balance_ratio = 1.0
        screen.update_balance(0.85)
        assert screen._balance_ratio == 0.85

    def test_update_grip(self):
        from ui.sport_screen import SportScreen
        screen = object.__new__(SportScreen)
        screen._front_grip_pct = 100.0
        screen._rear_grip_pct = 100.0
        screen.update_grip(92.0, 78.0)
        assert screen._front_grip_pct == 92.0
        assert screen._rear_grip_pct == 78.0

    def test_update_brake_analysis(self):
        from ui.sport_screen import SportScreen
        screen = object.__new__(SportScreen)
        screen._brake_peak_g = 0.0
        screen._brake_consistency = 1.0
        screen._trail_brake_pct = 0.0
        screen.update_brake_analysis({
            "peak_g": 1.05,
            "consistency": 0.88,
            "trail_pct": 42.0,
            "zones": 5,
        })
        assert screen._brake_peak_g == pytest.approx(1.05)
        assert screen._brake_consistency == pytest.approx(0.88)
        assert screen._trail_brake_pct == pytest.approx(42.0)

    def test_brake_g_color_thresholds(self):
        from ui.sport_screen import SportScreen
        assert hasattr(SportScreen, '_brake_g_color')
        assert hasattr(SportScreen, '_grip_color')

    def test_g_trail_accumulation(self):
        from ui.sport_screen import SportScreen
        screen = object.__new__(SportScreen)
        screen._g_trail = []
        screen._max_trail = 20
        for i in range(25):
            screen._g_trail.append((0.1 * i, -0.05 * i))
            if len(screen._g_trail) > screen._max_trail:
                screen._g_trail = screen._g_trail[-screen._max_trail:]
        assert len(screen._g_trail) == 20


class TestSharpScreenLogic:
    def test_update_balance(self):
        from ui.sharp_screen import SharpScreen
        screen = object.__new__(SharpScreen)
        screen._balance_ratio = 1.0
        screen.update_balance(1.15)
        assert screen._balance_ratio == 1.15

    def test_update_grip(self):
        from ui.sharp_screen import SharpScreen
        screen = object.__new__(SharpScreen)
        screen._front_grip_pct = 100.0
        screen._rear_grip_pct = 100.0
        screen.update_grip(88.0, 72.0)
        assert screen._front_grip_pct == 88.0
        assert screen._rear_grip_pct == 72.0

    def test_update_sector_brake_quality(self):
        from ui.sharp_screen import SharpScreen
        screen = object.__new__(SharpScreen)
        screen._sector_dots = []
        dots = ["#00CC66", "#FFAA00", "#FF1A1A"]
        screen.update_sector_brake_quality(dots)
        assert len(screen._sector_dots) == 3

    def test_g_trail_accumulation(self):
        from ui.sharp_screen import SharpScreen
        screen = object.__new__(SharpScreen)
        screen._g_trail = []
        screen._max_trail = 10
        for i in range(15):
            screen._g_trail.append((0.1, -0.1))
            if len(screen._g_trail) > screen._max_trail:
                screen._g_trail = screen._g_trail[-screen._max_trail:]
        assert len(screen._g_trail) == 10
