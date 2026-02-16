"""KiSTI - Bottom Softkey Bar

Six-button navigation bar: KiSTI, STREET, TRACK, VIDEO, LOG, SETTINGS.
KiSTI button uses the logo icon. All modes use mode_changed signal.
"""

from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

from ui.theme import BG_PANEL, BG_ACCENT, HIGHLIGHT, WHITE
from ui.branding import kisti_logo


class BottomSoftkeyBar(QWidget):
    """Fixed 60px softkey bar at bottom of screen."""

    mode_changed = Signal(str)

    _BUTTONS = ["KiSTI", "STREET", "TRACK", "DIFF", "VIDEO", "LOG", "SETTINGS"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setStyleSheet(f"background-color: {BG_PANEL};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._buttons = {}
        for name in self._BUTTONS:
            btn = QPushButton(name)
            btn.setMinimumHeight(48)
            if name == "KiSTI":
                # Use KiSTI logo as icon instead of text
                pm = kisti_logo(28)
                if not pm.isNull():
                    btn.setText("")
                    btn.setIcon(QIcon(pm))
                    btn.setIconSize(QSize(pm.width(), pm.height()))
            btn.clicked.connect(lambda checked=False, n=name: self._on_click(n))
            layout.addWidget(btn, stretch=1)
            self._buttons[name] = btn

        self._active = "KiSTI"
        self._update_highlight()

    def _on_click(self, name):
        self._active = name
        self._update_highlight()
        self.mode_changed.emit(name)

    def _update_highlight(self):
        for name, btn in self._buttons.items():
            if name == self._active:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_active(self, mode):
        self._active = mode
        self._update_highlight()
