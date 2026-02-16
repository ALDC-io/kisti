"""KiSTI - Pit Summary Modal

Modal dialog showing top 3 KiSTI findings with severity badges
and a corner diagram highlighting affected areas.
STI style: black face, chrome border, red accents.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from ui.theme import (
    BG_PANEL, BG_DARK, HIGHLIGHT, CHERRY, GREEN, YELLOW, RED, WHITE,
    SILVER, GRAY, CHROME_MID, CHROME_DARK, FONT_HEADER, FONT_BASE,
)


_SEVERITY_COLORS = {"info": GREEN, "warning": YELLOW, "critical": RED}


class _CornerDiagram(QWidget):
    """Small 4-corner car diagram highlighting affected corners."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighted = set()
        self.setFixedSize(120, 80)

    def set_highlighted(self, corners):
        self._highlighted = set(corners)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Car body outline - chrome
        p.setPen(QPen(QColor(CHROME_MID), 1))
        p.drawRoundedRect(20, 10, w - 40, h - 20, 8, 8)

        # Wheel positions
        positions = {"FL": (15, 15), "FR": (w - 30, 15), "RL": (15, h - 30), "RR": (w - 30, h - 30)}
        for name, (x, y) in positions.items():
            color = HIGHLIGHT if name in self._highlighted else CHROME_DARK
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(color)))
            p.drawRoundedRect(x, y, 15, 15, 3, 3)
            p.setPen(QColor(WHITE))
            p.setFont(QFont("Helvetica", 7, QFont.Bold))
            p.drawText(x, y, 15, 15, Qt.AlignCenter, name[0])

        p.end()


class PitSummaryModal(QDialog):
    """Modal showing top KiSTI findings and affected corners."""

    def __init__(self, findings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pit Summary")
        self.setFixedSize(500, 340)
        self.setStyleSheet(
            f"background-color: {BG_DARK}; "
            f"border: 2px solid {CHROME_MID};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("KiSTI PIT SUMMARY")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: {FONT_HEADER}px; font-weight: 900; color: {HIGHLIGHT};"
        )
        layout.addWidget(title)

        # Chrome divider
        divider = QLabel("")
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {CHROME_DARK};")
        layout.addWidget(divider)

        all_corners = set()

        for finding in findings[:3]:
            row = QHBoxLayout()
            sev_color = _SEVERITY_COLORS.get(finding.severity, GRAY)
            badge = QLabel(f"\u25cf {finding.severity.upper()}")
            badge.setFixedWidth(100)
            badge.setStyleSheet(f"color: {sev_color}; font-weight: bold;")
            row.addWidget(badge)

            text_col = QVBoxLayout()
            ftitle = QLabel(finding.title)
            ftitle.setStyleSheet(f"font-weight: bold; color: {WHITE};")
            text_col.addWidget(ftitle)
            detail = QLabel(finding.detail)
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {SILVER}; font-size: 12px;")
            text_col.addWidget(detail)
            row.addLayout(text_col, stretch=1)
            layout.addLayout(row)

            all_corners.update(finding.related_corners)

        layout.addSpacing(8)

        diag_row = QHBoxLayout()
        diag_row.addStretch()
        diagram = _CornerDiagram(self)
        diagram.set_highlighted(all_corners)
        diag_row.addWidget(diagram)
        diag_row.addStretch()
        layout.addLayout(diag_row)

        layout.addStretch()

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(48)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
