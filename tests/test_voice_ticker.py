"""Tests for voice activity ticker on all 3 SI-Drive screens."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestVoiceTickerSport:
    def test_initial_empty(self, qapp):
        from ui.sport_screen import SportScreenWidget
        w = SportScreenWidget()
        assert w._voice_ticker == []

    def test_update_stores_lines(self, qapp):
        from ui.sport_screen import SportScreenWidget
        w = SportScreenWidget()
        w.update_voice_ticker(["Lap 3: 91.5 seconds.", "Track detected: Laguna Seca."])
        assert len(w._voice_ticker) == 2
        assert w._voice_ticker[0] == "Lap 3: 91.5 seconds."

    def test_empty_list_clears(self, qapp):
        from ui.sport_screen import SportScreenWidget
        w = SportScreenWidget()
        w.update_voice_ticker(["something"])
        w.update_voice_ticker([])
        assert w._voice_ticker == []


class TestVoiceTickerIntelligent:
    def test_initial_empty(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        w = IntelligentScreenWidget()
        assert w._voice_ticker == []

    def test_update_stores_lines(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        w = IntelligentScreenWidget()
        w.update_voice_ticker(["Road surface cold.", "Ice risk."])
        assert len(w._voice_ticker) == 2


class TestVoiceTickerSharp:
    def test_initial_empty(self, qapp):
        from ui.sharp_screen import SportSharpScreenWidget
        w = SportSharpScreenWidget()
        assert w._voice_ticker == []

    def test_update_stores_lines(self, qapp):
        from ui.sharp_screen import SportSharpScreenWidget
        w = SportSharpScreenWidget()
        w.update_voice_ticker(["P B. 89.3.", "S1: 28.1."])
        assert len(w._voice_ticker) == 2


class TestCoachingAPISport:
    def test_update_coaching(self, qapp):
        from ui.sport_screen import SportScreenWidget
        w = SportScreenWidget()
        w.update_coaching("Smooth braking", "green")
        assert w._coaching_text == "Smooth braking"
        assert w._coaching_sentiment == "green"


class TestCoachingAPIIntelligent:
    def test_update_coaching(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        w = IntelligentScreenWidget()
        w.update_coaching("Ice risk — reduce corner speed", "amber")
        assert w._coaching_text == "Ice risk — reduce corner speed"

    def test_set_coaching_level(self, qapp):
        from ui.intelligent_screen import IntelligentScreenWidget
        w = IntelligentScreenWidget()
        w.set_coaching_level(0)
        assert w._coaching_level == 0
