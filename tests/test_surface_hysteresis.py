"""Tests for surface state hysteresis — DRY↔WET↔COLD require N consecutive readings."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from model.vehicle_state import DiffStateBridge, SurfaceState

if not QApplication.instance():
    _app = QApplication([])


@pytest.fixture
def bridge():
    b = DiffStateBridge()
    # Set ambient so surface inference activates (requires is_diff_stale=True, which is default).
    # Dew point 0.0C so 3C road → COLD (not LOW_GRIP which would bypass hysteresis).
    b.update_ambient(20.0, 30.0, 1013.0, 0.0, 0.0)
    return b


class TestSurfaceHysteresis:
    def test_dry_to_cold_requires_n_readings(self, bridge):
        """DRY→COLD transition requires SURFACE_HYSTERESIS_N consecutive readings."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Start in DRY — warm road
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Send N-1 cold readings — should NOT transition yet
        for _ in range(n - 1):
            bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # One more cold reading — NOW transitions to COLD
        bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.COLD

    def test_cold_to_dry_requires_n_readings(self, bridge):
        """COLD→DRY transition requires N consecutive readings."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Establish COLD state
        for _ in range(n + 1):
            bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.COLD

        # Send N-1 warm readings — should NOT transition
        for _ in range(n - 1):
            bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.COLD

        # One more warm reading — transitions to DRY
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

    def test_low_grip_transitions_immediately(self, bridge):
        """LOW_GRIP is safety-critical — transitions immediately, no hysteresis."""
        # Start in DRY
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Sub-zero road → immediate LOW_GRIP (single reading)
        bridge.update_road_surface(-1.0, -1.0, -1.0)
        assert bridge.snapshot().surface_state == SurfaceState.LOW_GRIP

    def test_interrupted_transition_resets_counter(self, bridge):
        """Oscillating readings reset the hysteresis counter."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Start in DRY
        bridge.update_road_surface(20.0, 20.0, 20.0)

        # Send N-1 cold readings (almost transitions)
        for _ in range(n - 1):
            bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Warm reading interrupts — resets counter
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Need full N cold readings again to transition
        for _ in range(n - 1):
            bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        bridge.update_road_surface(3.0, 3.0, 3.0)
        assert bridge.snapshot().surface_state == SurfaceState.COLD

    def test_surface_state_changed_signal_with_hysteresis(self, bridge):
        """Signal emits only after hysteresis threshold is met."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Establish DRY baseline first (sets _prev_surface_state)
        bridge.update_road_surface(20.0, 20.0, 20.0)

        transitions = []
        bridge.surface_state_changed.connect(
            lambda f, t: transitions.append((f, t))
        )

        # Cold readings — signal should fire after Nth reading
        for _ in range(n + 1):
            bridge.update_road_surface(3.0, 3.0, 3.0)

        cold_transitions = [t for t in transitions if t[1] == "COLD"]
        assert len(cold_transitions) == 1

    def test_low_grip_from_dew_point_immediate(self, bridge):
        """Road temp at/below dew point → LOW_GRIP immediate (no hysteresis)."""
        # Set ambient with dew point at 5C
        bridge.update_ambient(8.0, 90.0, 1013.0, 0.0, 5.0)
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Road temp drops to dew point → immediate LOW_GRIP
        bridge.update_road_surface(4.5, 4.5, 4.5)
        assert bridge.snapshot().surface_state == SurfaceState.LOW_GRIP

    def test_wet_from_condensation_needs_hysteresis(self, bridge):
        """Condensation risk (road < dew_point + 3) needs hysteresis."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Set ambient with dew point at 10C
        bridge.update_ambient(15.0, 70.0, 1013.0, 0.0, 10.0)
        bridge.update_road_surface(20.0, 20.0, 20.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        # Road temp 12C (< dew_point + 3 = 13) → WET after N readings
        for _ in range(n - 1):
            bridge.update_road_surface(12.0, 12.0, 12.0)
        assert bridge.snapshot().surface_state == SurfaceState.DRY

        bridge.update_road_surface(12.0, 12.0, 12.0)
        assert bridge.snapshot().surface_state == SurfaceState.WET
