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
        assert manager.si_drive_mode == SIDriveMode.INTELLIGENT
        assert manager.warmup_state == WarmUpState.COLD
        assert manager.display_mode == DisplayMode.KISTI
        assert manager.coaching_level == CoachingLevel.FULL
        assert manager.session_active is False


class TestSIDriveTransitions:
    def test_intelligent_to_sport(self, manager, bridge):
        """SI Drive change from Intelligent to Sport."""
        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        bridge.update_si_drive(mode=1)  # Sport

        assert manager.si_drive_mode == SIDriveMode.SPORT
        assert received == [1]

    def test_sport_to_sport_sharp(self, manager, bridge):
        bridge.update_si_drive(mode=1)
        bridge.update_si_drive(mode=2)
        assert manager.si_drive_mode == SIDriveMode.SPORT_SHARP

    def test_no_signal_on_same_mode(self, manager, bridge):
        """No signal emitted when mode doesn't change."""
        received = []
        manager.si_drive_changed.connect(lambda v: received.append(v))

        bridge.update_si_drive(mode=0)  # Already Intelligent
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

    def test_k6_display_cycle(self, manager, bridge):
        """K6 cycles display modes."""
        assert manager.display_mode == DisplayMode.KISTI

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.display_mode == DisplayMode.STREET

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.display_mode == DisplayMode.TRACK

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.display_mode == DisplayMode.DIFF

        bridge.update_keypad(state=KEYPAD_K6, prev_state=0)
        assert manager.display_mode == DisplayMode.KISTI  # Wraps around


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
