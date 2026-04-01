"""KiSTI - Bottom Softkey Bar

SI-Drive-aware sub-page navigation. 4 context-sensitive buttons per mode.
Labels and accent colors change when SI-Drive mode changes.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

from ui.theme import (
    BG_PANEL, BG_ACCENT, WHITE, SILVER, CHROME_DARK,
    MODE_I_ACCENT, MODE_S_ACCENT, MODE_SS_ACCENT,
)

# Sub-page labels per SI-Drive mode
_MODE_LABELS: dict[int, list[str]] = {
    0: ["HOME", "HEALTH", "DIAG", "SETTINGS"],     # Intelligent
    1: ["PERF", "DIFF", "MAP", "SETTINGS"],         # Sport
    2: ["LAP", "TRACK", "VIDEO", "SETTINGS"],       # Sport Sharp
}

_MODE_ACCENTS: dict[int, str] = {
    0: MODE_I_ACCENT,   # Blue
    1: MODE_S_ACCENT,   # Amber
    2: MODE_SS_ACCENT,  # Red
}


class BottomSoftkeyBar(QWidget):
    """Fixed 60px softkey bar with 4 dynamic sub-page buttons."""

    subpage_changed = Signal(int)

    # Keep legacy signal for backward compat during migration
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setStyleSheet(f"background-color: {BG_PANEL};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._btns: list[QPushButton] = []
        for i in range(4):
            btn = QPushButton("")
            btn.setMinimumHeight(48)
            btn.clicked.connect(lambda checked=False, idx=i: self._on_click(idx))
            layout.addWidget(btn, stretch=1)
            self._btns.append(btn)

        self._si_drive_mode: int = 0
        self._active_subpage: int = 0
        self._accent: str = MODE_I_ACCENT

        self._update_labels()
        self._update_highlight()

    def set_si_drive_mode(self, mode: int) -> None:
        """Update button labels and accent color for new SI-Drive mode."""
        if mode == self._si_drive_mode:
            return
        self._si_drive_mode = mode
        self._accent = _MODE_ACCENTS.get(mode, MODE_I_ACCENT)
        self._active_subpage = 0
        self._update_labels()
        self._update_highlight()

    def set_active_subpage(self, index: int) -> None:
        """Highlight the active sub-page button."""
        if 0 <= index < 4:
            self._active_subpage = index
            self._update_highlight()

    @property
    def active_subpage(self) -> int:
        return self._active_subpage

    @property
    def si_drive_mode(self) -> int:
        return self._si_drive_mode

    def _on_click(self, idx: int) -> None:
        self._active_subpage = idx
        self._update_highlight()
        self.subpage_changed.emit(idx)
        # Legacy compat: emit mode_changed with the label text
        labels = _MODE_LABELS.get(self._si_drive_mode, _MODE_LABELS[0])
        if idx < len(labels):
            self.mode_changed.emit(labels[idx])

    def _update_labels(self) -> None:
        labels = _MODE_LABELS.get(self._si_drive_mode, _MODE_LABELS[0])
        for i, btn in enumerate(self._btns):
            btn.setText(labels[i] if i < len(labels) else "")

    def _update_highlight(self) -> None:
        accent = self._accent
        # Darken the accent for active background (70% opacity on dark)
        for i, btn in enumerate(self._btns):
            if i == self._active_subpage:
                btn.setStyleSheet(
                    f"background-color: {accent}; color: {WHITE}; "
                    f"border: 2px solid {accent}; font-weight: bold; "
                    f"border-radius: 4px; min-height: 48px;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {BG_PANEL}; color: {SILVER}; "
                    f"border: 1px solid {CHROME_DARK}; font-weight: bold; "
                    f"border-radius: 4px; min-height: 48px;"
                )
