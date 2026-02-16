"""KiSTI - GT7-Style Tire Indicator Widget

Replicates Gran Turismo 7's tire display: rounded rectangle tire shapes
with internal fill bars. Color transitions blue (cold) → green (optimal)
→ yellow (warm) → red (overheating). Fill level shows tire wear remaining.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QRadialGradient, QFont, QLinearGradient,
    QPainterPath,
)
from PySide6.QtWidgets import QWidget

from ui.theme import (
    GREEN, YELLOW, RED, WHITE, SILVER, GRAY, DIM,
    BG_DARK, BG_PANEL, HIGHLIGHT, CHERRY,
    CHROME_LIGHT, CHROME_MID, CHROME_DARK,
    TIRE_BLUE, TIRE_BLUE_DARK, TIRE_GREEN, TIRE_YELLOW, TIRE_RED,
)
from config import (
    TIRE_TEMP_GREEN_MAX, TIRE_TEMP_YELLOW_MAX,
    BRAKE_TEMP_GREEN_MAX, BRAKE_TEMP_YELLOW_MAX,
    TIRE_TEMP_BASELINE, BRAKE_TEMP_BASELINE,
)


def _tire_temp_color(temp_c):
    """Return GT7-style color based on tire temperature.

    Blue (cold) → Green (optimal) → Yellow (warm) → Red (hot).
    """
    if temp_c < 75:
        return QColor(TIRE_BLUE)
    elif temp_c < TIRE_TEMP_GREEN_MAX:
        # Blend blue → green
        t = (temp_c - 75) / (TIRE_TEMP_GREEN_MAX - 75)
        r = int(0 * (1 - t) + 0 * t)
        g = int(119 * (1 - t) + 204 * t)
        b = int(221 * (1 - t) + 102 * t)
        return QColor(r, g, b)
    elif temp_c < TIRE_TEMP_YELLOW_MAX:
        # Blend green → yellow
        t = (temp_c - TIRE_TEMP_GREEN_MAX) / (TIRE_TEMP_YELLOW_MAX - TIRE_TEMP_GREEN_MAX)
        r = int(0 * (1 - t) + 255 * t)
        g = int(204 * (1 - t) + 170 * t)
        b = int(102 * (1 - t) + 0 * t)
        return QColor(r, g, b)
    else:
        # Blend yellow → red
        overshoot = min(1.0, (temp_c - TIRE_TEMP_YELLOW_MAX) / 20.0)
        r = 255
        g = int(170 * (1 - overshoot))
        return QColor(r, g, 0)


def _brake_temp_color(temp_c):
    """Return color for brake temperature."""
    if temp_c < BRAKE_TEMP_GREEN_MAX:
        return QColor(TIRE_GREEN)
    elif temp_c < BRAKE_TEMP_YELLOW_MAX:
        return QColor(TIRE_YELLOW)
    else:
        return QColor(TIRE_RED)


class CornerCell(QWidget):
    """GT7-style tire indicator with rounded tire shape and internal fill bar.

    Displays:
    - Tire-shaped rounded rectangle with wear fill level
    - Color based on tire temperature (blue/green/yellow/red)
    - Brake temperature as a thin strip beside the tire
    - Numeric readouts for both temperatures
    """

    def __init__(self, corner_name, parent=None):
        super().__init__(parent)
        self._name = corner_name
        self._highlighted = False
        self._tire_temp = 85.0
        self._brake_temp = 250.0
        self._tire_wear = 1.0  # 1.0 = new, 0.0 = gone
        self._tire_pct = 0.0   # Temp as 0-1 within range

    def update_data(self, corner_data):
        self._tire_temp = corner_data.tire_temp_c
        self._brake_temp = corner_data.brake_temp_c
        self._tire_wear = corner_data.tire_wear_pct
        # Temperature percentage for visual reference
        t_lo, t_hi = TIRE_TEMP_BASELINE[0] - 10, TIRE_TEMP_BASELINE[1] + 15
        self._tire_pct = max(0, min(1, (corner_data.tire_temp_c - t_lo) / (t_hi - t_lo)))
        self.update()

    def set_highlighted(self, on):
        self._highlighted = on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Black face background
        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        # Subtle bezel
        bezel_color = HIGHLIGHT if self._highlighted else CHROME_DARK
        p.setPen(QPen(QColor(bezel_color), 2 if self._highlighted else 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        # Corner name - top left
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.drawText(6, 14, self._name)

        # --- GT7 Tire Shape ---
        # The tire is a tall rounded rectangle (like a tire from above)
        top_margin = 20
        bottom_margin = 4
        available_h = h - top_margin - bottom_margin

        # Tire shape dimensions
        tire_x = int(w * 0.08)
        tire_w = int(w * 0.48)
        tire_y = top_margin
        tire_h = available_h
        tire_radius = min(tire_w, tire_h) * 0.15

        # Brake strip dimensions (thin bar to the right of tire)
        brake_x = tire_x + tire_w + int(w * 0.04)
        brake_w = int(w * 0.08)
        brake_h = int(tire_h * 0.75)
        brake_y = tire_y + (tire_h - brake_h)

        # --- Draw tire outline (dark recessed background) ---
        tire_rect = QRectF(tire_x, tire_y, tire_w, tire_h)
        p.setPen(QPen(QColor("#2A2A2A"), 1.5))
        p.setBrush(QColor("#0D0D0D"))
        p.drawRoundedRect(tire_rect, tire_radius, tire_radius)

        # --- Draw tire fill (wear level with temperature color) ---
        fill_h = int(tire_h * self._tire_wear)
        if fill_h > 0:
            fill_y = tire_y + (tire_h - fill_h)
            fill_rect = QRectF(tire_x + 2, fill_y, tire_w - 4, fill_h - 1)

            # Clip fill to tire shape
            clip_path = QPainterPath()
            clip_inner = QRectF(tire_x + 1, tire_y + 1, tire_w - 2, tire_h - 2)
            clip_path.addRoundedRect(clip_inner, tire_radius - 1, tire_radius - 1)
            p.setClipPath(clip_path)

            # Fill color based on temperature
            base_color = _tire_temp_color(self._tire_temp)

            # Gradient fill: slightly darker at bottom, brighter at top
            grad = QLinearGradient(tire_x, fill_y, tire_x, fill_y + fill_h)
            brighter = QColor(
                min(255, base_color.red() + 30),
                min(255, base_color.green() + 30),
                min(255, base_color.blue() + 30),
            )
            grad.setColorAt(0.0, brighter)
            grad.setColorAt(1.0, base_color)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, tire_radius - 2, tire_radius - 2)

            # Subtle tread lines (horizontal stripes across the fill)
            p.setPen(QPen(QColor(0, 0, 0, 35), 1))
            tread_spacing = max(4, int(tire_h / 20))
            for ty in range(int(fill_y), int(fill_y + fill_h), tread_spacing):
                p.drawLine(tire_x + 4, ty, tire_x + tire_w - 4, ty)

            # Glossy highlight at top of fill
            highlight_h = min(6, fill_h // 3)
            if highlight_h > 0:
                gloss = QLinearGradient(tire_x, fill_y, tire_x, fill_y + highlight_h)
                gloss.setColorAt(0.0, QColor(255, 255, 255, 60))
                gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(gloss))
                p.drawRect(QRectF(tire_x + 3, fill_y, tire_w - 6, highlight_h))

            p.setClipping(False)

        # --- Wear indicator marks (notches on left edge of tire) ---
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        for frac in [0.25, 0.50, 0.75]:
            ny = tire_y + int(tire_h * (1 - frac))
            p.drawLine(tire_x - 3, ny, tire_x, ny)

        # --- Tire outline overlay (crisp border on top) ---
        p.setPen(QPen(QColor("#3A3A3A"), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(tire_rect, tire_radius, tire_radius)

        # --- Draw brake temperature strip ---
        brake_rect = QRectF(brake_x, brake_y, brake_w, brake_h)
        p.setPen(QPen(QColor("#2A2A2A"), 1))
        p.setBrush(QColor("#0D0D0D"))
        p.drawRoundedRect(brake_rect, 2, 2)

        # Brake fill
        b_lo, b_hi = BRAKE_TEMP_BASELINE[0] - 30, BRAKE_TEMP_BASELINE[1] + 50
        brake_pct = max(0, min(1, (self._brake_temp - b_lo) / (b_hi - b_lo)))
        brake_fill_h = int(brake_h * brake_pct)
        if brake_fill_h > 0:
            bf_y = brake_y + (brake_h - brake_fill_h)
            brake_color = _brake_temp_color(self._brake_temp)
            # Clip to brake rect
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(brake_x + 1, brake_y + 1, brake_w - 2, brake_h - 2), 1, 1)
            p.setClipPath(clip)
            p.setPen(Qt.NoPen)
            p.setBrush(brake_color)
            p.drawRect(QRectF(brake_x + 1, bf_y, brake_w - 2, brake_fill_h))
            p.setClipping(False)

        # Brake strip border
        p.setPen(QPen(QColor("#3A3A3A"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(brake_rect, 2, 2)

        # --- Temperature readouts (right side) ---
        readout_x = int(w * 0.72)

        # Tire temp
        tire_color = _tire_temp_color(self._tire_temp)
        p.setPen(tire_color)
        p.setFont(QFont("Helvetica", 14, QFont.Bold))
        p.drawText(readout_x, tire_y + int(tire_h * 0.30), f"{self._tire_temp:.0f}")
        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(readout_x, tire_y + int(tire_h * 0.30) + 12, "\u00b0C")

        # Wear percentage
        wear_color = QColor(TIRE_GREEN) if self._tire_wear > 0.5 else (
            QColor(TIRE_YELLOW) if self._tire_wear > 0.25 else QColor(TIRE_RED)
        )
        p.setPen(wear_color)
        p.setFont(QFont("Helvetica", 9))
        p.drawText(readout_x, tire_y + int(tire_h * 0.55), f"{self._tire_wear * 100:.0f}%")
        p.setPen(QColor(DIM))
        p.setFont(QFont("Helvetica", 6))
        p.drawText(readout_x, tire_y + int(tire_h * 0.55) + 10, "WEAR")

        # Brake temp
        bk_color = _brake_temp_color(self._brake_temp)
        p.setPen(bk_color)
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.drawText(readout_x, tire_y + int(tire_h * 0.82), f"{self._brake_temp:.0f}")
        p.setPen(QColor(DIM))
        p.setFont(QFont("Helvetica", 6))
        p.drawText(readout_x, tire_y + int(tire_h * 0.82) + 10, "BRK")

        # --- Highlighted glow ---
        if self._highlighted:
            glow = QRadialGradient(w / 2, h / 2, max(w, h) * 0.6)
            glow.setColorAt(0, QColor(255, 0, 0, 25))
            glow.setColorAt(1, QColor(255, 0, 0, 0))
            p.fillRect(0, 0, w, h, QBrush(glow))

        p.end()
