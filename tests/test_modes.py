"""Tests for mode manager — SI Drive transitions, keypad routing, warm-up.

Uses mock bridge (no real CAN hardware).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from model.vehicle_state import DiffStateBridge, SIDriveMode, WarmUpState
from modes.mode_manager import (
    ModeManager,
    DisplayMode,
    CoachingLevel,
    WARMUP_OIL_READY,
    WARMUP_COOLANT_READY,
)
from can.can_config import (
    KEYPAD_K1, KEYPAD_K2, KEYPAD_K3, KEYPAD_K4, KEYPAD_K5, KEYPAD_K6,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def bridge(qapp):
    return DiffStateBridge()


@pytest.fixture
def manager(bridge):
    mgr = ModeManager(bridge)
    return mgr


class TestModeManagerInit:
    def test_default_state(self, manager):
        assert manager.si_drive_mode == SIDriveMode.SPORT
        assert manager.warmup_state == WarmUpState.COLD
        assert manager.display_mode == DisplayMode.KISTI
        assert manager.coaching_level == CoachingLevel.FULL
        assert manager.session_active is False


class TestSIDriveTransitions:
    def test_sport_to_sport_sharp_transition(self, manager, bridge):
        """SI Drive change from Sport to Sport Sharp."""
        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        bridge.update_si_drive(mode=2)  # Sport Sharp

        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP
        assert received == [2]

    def test_sport_to_sport_sharp(self, manager, bridge):
        bridge.update_si_drive(mode=1)
        bridge.update_si_drive(mode=2)
        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP

    def test_no_signal_on_same_mode(self, manager, bridge):
        """No signal emitted when mode doesn't change."""
        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        bridge.update_si_drive(mode=1)  # Already Sport (default)
        assert received == []  # No change signal


class TestKeypadRouting:
    def test_k1_session_toggle(self, manager, bridge):
        """K1 toggles session recording."""
        received = []
        manager.session_toggle.connect(lambda: received.append(True))

        bridge.update_keypad(state=KEYPAD_K1, prev_state=0)

        assert manager.session_active is True
        assert len(received) == 1

    def test_k1_double_toggle(self, manager, bridge):
        """K1 twice: start then stop session."""
        bridge.update_keypad(state=KEYPAD_K1, prev_state=0)
        assert manager.session_active is True

        bridge.update_keypad(state=KEYPAD_K1, prev_state=0)
        assert manager.session_active is False

    def test_k2_segment_mark(self, manager, bridge):
        received = []
        manager.segment_mark.connect(lambda: received.append(True))

        bridge.update_keypad(state=KEYPAD_K2, prev_state=0)
        assert len(received) == 1

    def test_k3_analyze_run(self, manager, bridge):
        received = []
        manager.analyze_run.connect(lambda: received.append(True))

        bridge.update_keypad(state=KEYPAD_K3, prev_state=0)
        assert len(received) == 1

    def test_k4_voice_toggle(self, manager, bridge):
        received = []
        manager.voice_toggle.connect(lambda: received.append(True))

        bridge.update_keypad(state=KEYPAD_K4, prev_state=0)
        assert len(received) == 1

    def test_k5_coaching_cycle(self, manager, bridge):
        """K5 cycles coaching level in Intelligent mode."""
        # Switch to Intelligent mode first (default is now Sport)
        bridge.update_si_drive(mode=0)
        assert manager.si_drive_mode == SIDriveMode.INTELLIGENT
        assert manager.coaching_level == CoachingLevel.FULL

        bridge.update_keypad(state=KEYPAD_K5, prev_state=0)
        assert manager.coaching_level == CoachingLevel.MINIMAL

        bridge.update_keypad(state=KEYPAD_K5, prev_state=0)
        assert manager.coaching_level == CoachingLevel.MODERATE

        bridge.update_keypad(state=KEYPAD_K5, prev_state=0)
        assert manager.coaching_level == CoachingLevel.FULL

    def test_k5_ignored_in_sport(self, manager, bridge):
        """K5 does nothing in Sport mode."""
        bridge.update_si_drive(mode=1)  # Sport
        initial = manager.coaching_level

        bridge.update_keypad(state=KEYPAD_K5, prev_state=0)
        assert manager.coaching_level == initial

    def test_k6_toggles_sharp_subpage_in_sport_sharp(self, manager, bridge):
        """K6 toggles S# sub-page between canyon (0) and track (1)."""
        bridge.update_si_drive(mode=2)  # Sport Sharp
        assert manager.sharp_subpage == 0

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.sharp_subpage == 1

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.sharp_subpage == 0

    def test_k6_ignored_outside_sport_sharp(self, manager, bridge):
        """K6 does nothing outside Sport Sharp mode."""
        bridge.update_si_drive(mode=1)  # Sport
        assert manager.sharp_subpage == 0

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.sharp_subpage == 0


class TestDisplayModeEnum:
    def test_labels(self):
        assert DisplayMode.KISTI.label == "KiSTI"
        assert DisplayMode.STREET.label == "STREET"
        assert DisplayMode.TRACK.label == "TRACK"
        assert DisplayMode.DIFF.label == "DIFF"


class TestCoachingLevelEnum:
    def test_labels(self):
        assert CoachingLevel.MINIMAL.label == "Minimal"
        assert CoachingLevel.MODERATE.label == "Moderate"
        assert CoachingLevel.FULL.label == "Full"


# ============================================================
# KiSTI-20: SI-Drive display switching tests
# ============================================================


class TestSIDriveDisplaySwitch:
    """SI-Drive controls the display — 3 screens, no sub-pages."""

    def test_k6_reserved(self, manager, bridge):
        """K6 is reserved — no sub-page cycling."""
        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        # No crash, no state change — K6 is a no-op now

    def test_mode_switch_sport_to_intelligent(self, manager, bridge):
        """SI-Drive switch from Sport to Intelligent."""
        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))
        bridge.update_si_drive(mode=0)
        assert manager.si_drive_mode == SIDriveMode.INTELLIGENT
        assert received == [0]

    def test_mode_switch_sport_to_sharp(self, manager, bridge):
        """SI-Drive switch from Sport to Sport Sharp."""
        bridge.update_si_drive(mode=1)
        bridge.update_si_drive(mode=2)
        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP

    def test_full_cycle(self, manager, bridge):
        """Full SI-Drive cycle: S -> S# -> I -> S (default is Sport)."""
        modes = []
        manager.si_drive_changed.connect(lambda v: modes.append(v))
        bridge.update_si_drive(mode=2)  # Sport Sharp
        bridge.update_si_drive(mode=0)  # Intelligent
        bridge.update_si_drive(mode=1)  # Sport
        assert modes == [2, 0, 1]


class TestSIDriveStaleness:
    """SI-Drive staleness fallback to Intelligent."""

    def test_staleness_fallback(self, manager, bridge):
        """After stale timeout, falls back to Intelligent."""
        import time

        # Switch to Sport
        bridge.update_si_drive(mode=1)
        assert manager.si_drive_mode == SIDriveMode.SPORT

        # Manually set the frame timestamp past the stale timeout
        timeout = manager.SI_DRIVE_STALE_TIMEOUT_S
        with bridge._lock:
            bridge._state.si_drive_frame_ts = time.monotonic() - (timeout + 1.0)

        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        # Trigger staleness check
        state = bridge.snapshot()
        manager._check_si_drive_staleness(state)

        assert manager.si_drive_mode == SIDriveMode.INTELLIGENT
        assert 0 in received  # Emitted Intelligent (0)

    def test_no_fallback_when_fresh(self, manager, bridge):
        """No fallback when SI-Drive frame is recent."""
        bridge.update_si_drive(mode=2)  # Sport Sharp
        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP

        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        state = bridge.snapshot()
        manager._check_si_drive_staleness(state)

        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP
        assert received == []  # No fallback

    def test_no_fallback_when_already_intelligent(self, manager, bridge):
        """No signal emitted if already in Intelligent and stale."""
        import time

        bridge.update_si_drive(mode=0)  # Intelligent
        with bridge._lock:
            bridge._state.si_drive_frame_ts = time.monotonic() - 10.0

        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        state = bridge.snapshot()
        manager._check_si_drive_staleness(state)

        assert received == []  # Already Intelligent, no signal

    def test_no_fallback_when_never_received(self, manager, bridge):
        """No fallback when SI-Drive frame was never received (ts=0.0)."""
        bridge.update_si_drive(mode=1)
        with bridge._lock:
            bridge._state.si_drive_frame_ts = 0.0

        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        state = bridge.snapshot()
        manager._check_si_drive_staleness(state)

        # Should not fallback — never received means default is fine
        assert received == []


class TestMainWindowSIDrive:
    """MainWindow switches screens based on SI-Drive."""

    def test_si_drive_switches_stack(self, qapp):
        from ui.main_window import MainWindow
        win = MainWindow()
        assert win._stack.currentIndex() == 0  # Starts on Intelligent (default)

        win._on_si_drive_changed(1)
        assert win._stack.currentIndex() == 1  # Sport

        win._on_si_drive_changed(2)
        assert win._stack.currentIndex() == 2  # Sport Sharp

        win._on_si_drive_changed(0)
        assert win._stack.currentIndex() == 0  # Back to Intelligent

    def test_invalid_mode_ignored(self, qapp):
        from ui.main_window import MainWindow
        win = MainWindow()
        win._on_si_drive_changed(99)
        assert win._stack.currentIndex() == 0  # Unchanged (stays on Intelligent default)


class TestStatusBar:
    """Status bar SI-Drive badge and warm-up tests."""

    def test_initial_badge(self, qapp):
        from ui.status_bar import TopStatusBar
        bar = TopStatusBar()
        assert "INTELLIGENT" in bar._mode_badge.text()

    def test_si_drive_badge_update(self, qapp):
        from ui.status_bar import TopStatusBar
        bar = TopStatusBar()
        bar.set_si_drive_mode(1)
        assert "SPORT" in bar._mode_badge.text()

    def test_si_drive_badge_sport_sharp(self, qapp):
        from ui.status_bar import TopStatusBar
        bar = TopStatusBar()
        bar.set_si_drive_mode(2)
        assert "SPORT" in bar._mode_badge.text()  # "SPORT SHARP"

    def test_warmup_state_update(self, qapp):
        from ui.status_bar import TopStatusBar
        bar = TopStatusBar()
        bar.set_warmup_state(2)  # READY
        assert "READY" in bar._warmup_label.text()

    def test_can_status(self, qapp):
        from ui.status_bar import TopStatusBar
        bar = TopStatusBar()
        bar.set_can_status(True)
        # CAN dot should be green (we check the stylesheet contains GREEN)
        from ui.theme import GREEN
        assert GREEN in bar._can_dot.styleSheet()


# ===================================================================
# FLIR thermal fields
# ===================================================================

class TestFLIRFields:
    """DiffState FLIR brake temp fields and staleness."""

    def test_flir_fields_default(self):
        from model.vehicle_state import DiffState
        snap = DiffState()
        assert snap.brake_temp_fl == 0.0
        assert snap.brake_temp_fr == 0.0
        assert snap.brake_temp_rl == 0.0
        assert snap.brake_temp_rr == 0.0
        assert snap.flir_available is False

    def test_flir_stale_when_never_updated(self):
        from model.vehicle_state import DiffState
        snap = DiffState()
        assert snap.is_flir_stale() is True

    def test_flir_not_stale_after_update(self, qapp):
        bridge = DiffStateBridge()
        bridge.update_flir(280.0, 310.0, 220.0, 250.0)
        snap = bridge.snapshot()
        assert snap.brake_temp_fl == 280.0
        assert snap.brake_temp_fr == 310.0
        assert snap.brake_temp_rl == 220.0
        assert snap.brake_temp_rr == 250.0
        assert snap.flir_available is True
        assert snap.is_flir_stale() is False

    def test_flir_snapshot_copies_fields(self, qapp):
        bridge = DiffStateBridge()
        bridge.update_flir(100.0, 200.0, 300.0, 400.0)
        snap1 = bridge.snapshot()
        bridge.update_flir(500.0, 600.0, 700.0, 800.0)
        snap2 = bridge.snapshot()
        # snap1 should be unchanged
        assert snap1.brake_temp_fl == 100.0
        assert snap2.brake_temp_fl == 500.0

    def test_flir_heat_color_cold(self):
        from ui.sharp_screen_track import _brake_heat_color
        color = _brake_heat_color(0.0)  # below 5°C = cold blue (ice risk)
        assert color.blue() > color.red()  # blue dominant

    def test_flir_heat_color_optimal(self):
        from ui.sharp_screen_track import _brake_heat_color
        color = _brake_heat_color(10.0)  # 5-15°C = green zone (cool road)
        assert color.green() > color.red()  # green dominant

    def test_flir_heat_color_hot(self):
        from ui.sharp_screen_track import _brake_heat_color
        color = _brake_heat_color(60.0)  # above 55°C = red hot pavement
        assert color.red() == 255
        assert color.green() < 100

    def test_sport_sharp_accepts_flir(self, qapp):
        from ui.sharp_screen import SportSharpScreenWidget
        w = SportSharpScreenWidget()
        from model.vehicle_state import DiffState
        snap = DiffState()
        snap.brake_temp_fl = 350.0
        snap.flir_available = True
        w.update_state(snap)
        # Should not crash

    def test_sport_accepts_flir(self, qapp):
        from ui.sport_screen import SportScreenWidget
        w = SportScreenWidget()
        from model.vehicle_state import DiffState
        snap = DiffState()
        snap.brake_temp_fl = 350.0
        snap.flir_available = True
        w.update_state(snap)

    def test_intelligent_accepts_flir(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        w = IntelligentScreenWidget()
        from model.vehicle_state import DiffState
        snap = DiffState()
        snap.brake_temp_fl = 350.0
        snap.flir_available = True
        w.update_state(snap)

    # --- Wheel delta color thresholds (Intelligent screen) ---

    def test_wheel_delta_color_small(self):
        from ui.intelligent_screen import _wheel_delta_color
        from ui.theme import CYAN
        assert _wheel_delta_color(1.0) == CYAN

    def test_wheel_delta_color_moderate(self):
        from ui.intelligent_screen import _wheel_delta_color
        from ui.theme import YELLOW
        assert _wheel_delta_color(3.0) == YELLOW

    def test_wheel_delta_color_severe(self):
        from ui.intelligent_screen import _wheel_delta_color
        from ui.theme import RED
        assert _wheel_delta_color(6.0) == RED

    def test_wheel_delta_color_boundary(self):
        from ui.intelligent_screen import _wheel_delta_color
        from ui.theme import CYAN, YELLOW
        assert _wheel_delta_color(2.0) == CYAN   # at threshold = not exceeded
        assert _wheel_delta_color(2.01) == YELLOW  # just above

    # --- Intelligent screen ABS/VDC rendering (no crash) ---

    def test_intelligent_abs_active_render(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        from model.vehicle_state import DiffState
        w = IntelligentScreenWidget()
        snap = DiffState()
        snap.abs_active = True
        snap.vdc_tc = False
        snap.wheel_speed_fl = 80.0
        snap.wheel_speed_fr = 83.5  # 3.5 km/h spread
        snap.wheel_speed_rl = 79.0
        snap.wheel_speed_rr = 79.5
        w.update_state(snap)

    def test_intelligent_vdc_active_render(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        from model.vehicle_state import DiffState
        w = IntelligentScreenWidget()
        snap = DiffState()
        snap.abs_active = False
        snap.vdc_tc = True
        snap.wheel_speed_fl = 60.0
        snap.wheel_speed_fr = 60.0
        snap.wheel_speed_rl = 60.0
        snap.wheel_speed_rr = 60.0
        w.update_state(snap)

    def test_intelligent_wheel_spread_zero(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        from model.vehicle_state import DiffState
        w = IntelligentScreenWidget()
        snap = DiffState()
        snap.wheel_speed_fl = 100.0
        snap.wheel_speed_fr = 100.0
        snap.wheel_speed_rl = 100.0
        snap.wheel_speed_rr = 100.0
        w.update_state(snap)
