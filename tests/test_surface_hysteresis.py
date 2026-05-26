"""Tests for surface state hysteresis — DRY↔WET↔COLD require N consecutive readings."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from model.vehicle_state import DiffStateBridge, SurfaceState, classify_surface

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


class TestClassifySurface:
    """Tests for the standalone classify_surface() helper."""

    def test_sub_zero_is_low_grip(self):
        assert classify_surface(-2.0, 20.0, 0.0, 30.0, True) == SurfaceState.LOW_GRIP

    def test_at_dew_point_is_low_grip(self):
        assert classify_surface(5.0, 20.0, 5.0, 90.0, True) == SurfaceState.LOW_GRIP

    def test_cold_road(self):
        assert classify_surface(3.0, 20.0, 0.0, 30.0, True) == SurfaceState.COLD

    def test_condensation_risk_is_wet(self):
        # Road temp < dew_point + 3
        assert classify_surface(12.0, 20.0, 10.0, 70.0, True) == SurfaceState.WET

    def test_warm_dry_road(self):
        assert classify_surface(25.0, 20.0, 5.0, 30.0, True) == SurfaceState.DRY

    def test_no_ambient_skips_dew_checks(self):
        # Without ambient data, dew point checks are skipped
        # 3.0°C → COLD (not LOW_GRIP even though dew_point=10)
        assert classify_surface(3.0, 20.0, 10.0, 90.0, False) == SurfaceState.COLD

    def test_humidity_wet(self):
        # High humidity + road much colder than air → WET
        assert classify_surface(10.0, 20.0, 0.0, 80.0, True) == SurfaceState.WET


class TestPerZoneClassification:
    """Per-zone surface state classification — L/C/R independent."""

    def test_mixed_zones_overall_worst(self, bridge):
        """Overall surface_state = worst of 3 zones."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Left=DRY, Center=COLD, Right=DRY — overall should be COLD
        for _ in range(n + 1):
            bridge.update_road_surface(20.0, 3.0, 20.0)
        snap = bridge.snapshot()
        assert snap.surface_state_left == SurfaceState.DRY
        assert snap.surface_state_center == SurfaceState.COLD
        assert snap.surface_state_right == SurfaceState.DRY
        assert snap.surface_state == SurfaceState.COLD

    def test_one_zone_low_grip_immediate(self, bridge):
        """LOW_GRIP in one zone → immediate, overall = LOW_GRIP."""
        bridge.update_road_surface(20.0, 20.0, 20.0)
        snap = bridge.snapshot()
        assert snap.surface_state == SurfaceState.DRY

        # Right zone sub-zero → immediate LOW_GRIP
        bridge.update_road_surface(20.0, 20.0, -1.0)
        snap = bridge.snapshot()
        assert snap.surface_state_right == SurfaceState.LOW_GRIP
        assert snap.surface_state_left == SurfaceState.DRY
        assert snap.surface_state == SurfaceState.LOW_GRIP

    def test_per_zone_hysteresis_independent(self, bridge):
        """Each zone has independent hysteresis counters."""
        n = DiffStateBridge.SURFACE_HYSTERESIS_N
        # Start all DRY
        bridge.update_road_surface(20.0, 20.0, 20.0)

        # Left goes cold, center/right stay warm
        for _ in range(n - 1):
            bridge.update_road_surface(3.0, 20.0, 20.0)
        snap = bridge.snapshot()
        assert snap.surface_state_left == SurfaceState.DRY  # not yet

        bridge.update_road_surface(3.0, 20.0, 20.0)
        snap = bridge.snapshot()
        assert snap.surface_state_left == SurfaceState.COLD
        assert snap.surface_state_center == SurfaceState.DRY
        assert snap.surface_state_right == SurfaceState.DRY

    def test_all_zones_default_dry(self, bridge):
        """New bridge starts with all zones DRY."""
        snap = bridge.snapshot()
        assert snap.surface_state_left == SurfaceState.DRY
        assert snap.surface_state_center == SurfaceState.DRY
        assert snap.surface_state_right == SurfaceState.DRY

    def test_can_diff_sets_all_zones(self, bridge):
        """CAN diff frame sets all 3 zone states."""
        bridge.update_diff(
            dccd_command_pct=30.0,
            dccd_dial_pct=None,
            surface_state=SurfaceState.WET,
            brake=False,
            handbrake=False,
            abs_active=False,
            vdc_tc=False,
            slip_delta=None,
        )
        snap = bridge.snapshot()
        assert snap.surface_state_left == SurfaceState.WET
        assert snap.surface_state_center == SurfaceState.WET
        assert snap.surface_state_right == SurfaceState.WET
