"""KiSTI - Findings List Widget

Scrollable list of KiSTI findings with severity badges.
STI style: black face, red accents, chrome dividers.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
)

from ui.theme import (
    GREEN, YELLOW, RED, GRAY, WHITE, SILVER,
    BG_PANEL, BG_ACCENT, BG_DARK, HIGHLIGHT, CHROME_DARK,
)

_SEVERITY_COLORS = {"info": GREEN, "warning": YELLOW, "critical": RED}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


class _FindingRow(QFrame):
    """Single finding row - STI instrument card style."""

    clicked = Signal(object)

    def __init__(self, finding, parent=None):
        super().__init__(parent)
        self._finding = finding
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"background-color: {BG_PANEL}; "
            f"border: 1px solid {CHROME_DARK}; "
            f"border-radius: 3px; padding: 3px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(8)

        sev_color = _SEVERITY_COLORS.get(finding.severity, GRAY)
        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color: {sev_color}; font-size: 16px;")
        dot.setFixedWidth(20)
        layout.addWidget(dot)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title = QLabel(finding.title)
        title.setStyleSheet(f"font-weight: bold; color: {WHITE}; font-size: 12px;")
        text_col.addWidget(title)
        detail = QLabel(finding.detail)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color: {SILVER}; font-size: 10px;")
        text_col.addWidget(detail)
        layout.addLayout(text_col, stretch=1)

        corners = QLabel(", ".join(finding.related_corners))
        corners.setStyleSheet(f"color: {HIGHLIGHT}; font-size: 11px; font-weight: bold;")
        layout.addWidget(corners)

    def mousePressEvent(self, event):
        self.clicked.emit(self._finding)
        super().mousePressEvent(event)


class FindingsListWidget(QWidget):
    """Scrollable list of KiSTI findings."""

    finding_selected = Signal(object)

    def __init__(self, parent=None, show_header=True):
        super().__init__(parent)
        self._rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        if show_header:
            header = QLabel("KiSTI FINDINGS")
            header.setStyleSheet(
                f"font-weight: 900; color: {HIGHLIGHT}; font-size: 12px;"
            )
            outer.addWidget(header)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(self._scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        self._layout.addStretch()
        self._scroll.setWidget(self._container)

    def update_findings(self, findings):
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        sorted_findings = sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))

        item = self._layout.takeAt(self._layout.count() - 1)

        for f in sorted_findings:
            row = _FindingRow(f, self._container)
            row.clicked.connect(self._on_row_clicked)
            self._layout.addWidget(row)
            self._rows.append(row)

        self._layout.addStretch()

    def _on_row_clicked(self, finding):
        self.finding_selected.emit(finding)
