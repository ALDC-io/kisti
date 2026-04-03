"""Tests for Sport# sector insight text."""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSectorInsight:
    def _insight(self, sector_ms, best_ms):
        from ui.sharp_screen import SportSharpScreenWidget
        return SportSharpScreenWidget._sector_insight(sector_ms, best_ms)

    def test_big_gain(self, qapp):
        text, color = self._insight(30000, 31000)
        assert text == "big gain"

    def test_faster(self, qapp):
        text, color = self._insight(32000, 32200)
        assert text == "faster"

    def test_matched(self, qapp):
        text, color = self._insight(32000, 32000)
        assert text == "matched"

    def test_close(self, qapp):
        text, color = self._insight(32300, 32000)
        assert text == "close"

    def test_a_bit_slow(self, qapp):
        text, color = self._insight(33000, 32000)
        assert text == "a bit slow"

    def test_lost_time(self, qapp):
        text, color = self._insight(35000, 32000)
        assert text == "lost time"

    def test_none_best(self, qapp):
        text, color = self._insight(32000, None)
        assert text == ""

    def test_zero_best(self, qapp):
        text, color = self._insight(32000, 0)
        assert text == ""
