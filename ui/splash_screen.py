"""KiSTI - Splash / Boot Screen

Shows corporate logos and KiSTI branding during startup.
Auto-closes after 3 seconds or on click.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget

from ui.theme import BG_DARK, HIGHLIGHT, WHITE, SILVER, GRAY, CHROME_DARK
from ui.branding import nvidia_logo, link_ecu_logo, kisti_logo
from config import WINDOW_WIDTH, WINDOW_HEIGHT


class SplashScreen(QWidget):
    """Full-screen splash with logos. Closes after timeout or click."""

    def __init__(self, on_done, parent=None):
        super().__init__(parent)
        self._on_done = on_done
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        logo_h = 50
        self._kisti_pm = kisti_logo(logo_h)
        self._nvidia_pm = nvidia_logo(logo_h)
        self._link_pm = link_ecu_logo(logo_h)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._finish)
        self._timer.start(3000)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background gradient
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#0A0A0A"))
        grad.setColorAt(0.5, QColor("#111111"))
        grad.setColorAt(1.0, QColor("#0A0A0A"))
        p.fillRect(0, 0, w, h, grad)

        # Accent line at top
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(HIGHLIGHT))
        p.drawRect(0, 0, w, 3)

        # KiSTI logo (centered hero)
        if not self._kisti_pm.isNull():
            kx = (w - self._kisti_pm.width()) // 2
            p.drawPixmap(kx, 80, self._kisti_pm)

        # Subtitle
        p.setPen(QColor(SILVER))
        p.setFont(QFont("Helvetica", 12))
        p.drawText(0, 145, w, 30, Qt.AlignCenter,
                   "Knowledge-Integrated Smart Telemetry Interface")

        # Logo row: Link (left) ... Nvidia (far right) - all same height
        logo_y = 210
        margin = 60
        logo_h = 50

        if not self._link_pm.isNull():
            ly = logo_y + (logo_h - self._link_pm.height()) // 2
            p.drawPixmap(margin, ly, self._link_pm)

        if not self._nvidia_pm.isNull():
            ny = logo_y + (logo_h - self._nvidia_pm.height()) // 2
            nx = w - margin - self._nvidia_pm.width()
            p.drawPixmap(nx, ny, self._nvidia_pm)

        # "Powered by" text
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 9))
        p.drawText(0, 270, w, 20, Qt.AlignCenter,
                   "Powered by NVIDIA Jetson Orin  |  Link Engine Management")

        # Bottom accent line
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(HIGHLIGHT))
        p.drawRect(0, h - 3, w, 3)

        # Loading text
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 10))
        p.drawText(0, h - 30, w, 20, Qt.AlignCenter, "Initializing sensors...")

        # Version
        p.setPen(QColor(CHROME_DARK))
        p.setFont(QFont("Helvetica", 8))
        p.drawText(w - 80, h - 20, "v0.2.0-alpha")

        p.end()

    def mousePressEvent(self, event):
        self._finish()

    def _finish(self):
        self._timer.stop()
        self.close()
        self._on_done()
