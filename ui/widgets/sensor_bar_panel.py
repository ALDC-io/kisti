"""KiSTI - Sensor Bar Panel

Full right-side telemetry panel for STREET mode.
Vertical bar graphs grouped: OIL (PSI, Temp), TIRES (FL FR RL RR),
BRAKES (FL FR RL RR). Bars fill bottom-to-top and color-code
green → yellow → red based on thresholds.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_PANEL, BG_ACCENT, CHROME_DARK, GREEN, YELLOW, RED, WHITE,
    GRAY, DIM, HIGHLIGHT,
)
from config import (
    OIL_PSI_LOW_WARN, OIL_PSI_LOW_CRIT, OIL_PSI_HIGH_WARN, OIL_TEMP_WARN,
    TIRE_TEMP_GREEN_MAX, TIRE_TEMP_YELLOW_MAX,
    BRAKE_TEMP_GREEN_MAX, BRAKE_TEMP_YELLOW_MAX,
)

# Bar definitions: (label, min, max, warn_lo, warn_hi, crit_lo, crit_hi)
# None means no threshold on that side
_OIL_PSI = dict(label="PSI", mn=0, mx=100,
                warn_lo=OIL_PSI_LOW_WARN, crit_lo=OIL_PSI_LOW_CRIT,
                warn_hi=OIL_PSI_HIGH_WARN, crit_hi=100)
_OIL_TEMP = dict(label="T\u00b0C", mn=0, mx=160,
                 warn_lo=None, crit_lo=None,
                 warn_hi=OIL_TEMP_WARN, crit_hi=150)
_TIRE = dict(mn=40, mx=140,
             warn_lo=None, crit_lo=None,
             warn_hi=TIRE_TEMP_YELLOW_MAX, crit_hi=115)
_BRAKE = dict(mn=50, mx=800,
              warn_lo=None, crit_lo=None,
              warn_hi=BRAKE_TEMP_YELLOW_MAX, crit_hi=550)


def _bar_color(value, spec):
    """Determine bar color from value and thresholds."""
    # Check critical (red)
    if spec.get("crit_hi") is not None and value >= spec["crit_hi"]:
        return QColor(RED)
    if spec.get("crit_lo") is not None and value <= spec["crit_lo"]:
        return QColor(RED)
    # Check warning (yellow)
    if spec.get("warn_hi") is not None and value >= spec["warn_hi"]:
        return QColor(YELLOW)
    if spec.get("warn_lo") is not None and value <= spec["warn_lo"]:
        return QColor(YELLOW)
    return QColor(GREEN)


def _bar_fill(value, mn, mx):
    """Return 0.0-1.0 fill ratio."""
    if mx <= mn:
        return 0.0
    return max(0.0, min(1.0, (value - mn) / (mx - mn)))


class SensorBarPanel(QWidget):
    """Vertical bar graph panel for all street-mode sensors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._oil_psi = 45.0
        self._oil_temp = 95.0
        self._corners = {}

    def update_data(self, vehicle_state):
        self._oil_psi = vehicle_state.oil.psi
        self._oil_temp = vehicle_state.oil.temp_c
        self._corners = vehicle_state.corners
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BG_PANEL))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # Layout constants
        header_h = 16      # Group header height
        label_h = 14        # Bottom label height
        value_h = 14        # Top value height
        pad_x = 6           # Left/right padding
        group_gap = 8       # Gap between groups
        bar_gap = 3         # Gap between bars within group

        # Collect bar data: list of (group_label, [(bar_label, value, spec), ...])
        corner_order = ["FL", "FR", "RL", "RR"]
        groups = []

        # Oil group
        oil_bars = [
            ("PSI", self._oil_psi, _OIL_PSI),
            ("T\u00b0C", self._oil_temp, _OIL_TEMP),
        ]
        groups.append(("OIL", oil_bars))

        # Tire group
        tire_bars = []
        for c in corner_order:
            if c in self._corners:
                spec = dict(_TIRE, label=c)
                tire_bars.append((c, self._corners[c].tire_temp_c, spec))
        if tire_bars:
            groups.append(("TIRE", tire_bars))

        # Brake group
        brake_bars = []
        for c in corner_order:
            if c in self._corners:
                spec = dict(_BRAKE, label=c)
                brake_bars.append((c, self._corners[c].brake_temp_c, spec))
        if brake_bars:
            groups.append(("BRAKE", brake_bars))

        # Calculate total bars and widths
        total_bars = sum(len(bars) for _, bars in groups)
        num_groups = len(groups)
        if total_bars == 0:
            p.end()
            return

        total_gaps = (total_bars - num_groups) * bar_gap + (num_groups - 1) * group_gap
        avail_w = w - pad_x * 2 - total_gaps
        bar_w = max(8, avail_w / total_bars)

        # Bar area (between header and labels)
        bar_top = value_h + header_h + 4
        bar_bot = h - label_h - 4
        bar_h = bar_bot - bar_top

        # Draw groups
        x = pad_x
        for gi, (group_label, bars) in enumerate(groups):
            group_start_x = x
            group_w = len(bars) * bar_w + (len(bars) - 1) * bar_gap

            # Group header
            p.setFont(QFont("Helvetica", 8, QFont.Bold))
            p.setPen(QPen(QColor(HIGHLIGHT)))
            p.drawText(QRectF(group_start_x, 2, group_w, header_h),
                       Qt.AlignCenter, group_label)

            # Draw each bar
            for bi, (bar_label, value, spec) in enumerate(bars):
                bx = x
                fill = _bar_fill(value, spec["mn"], spec["mx"])
                color = _bar_color(value, spec)

                # Bar track (dim background)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(DIM))
                p.drawRoundedRect(QRectF(bx, bar_top, bar_w, bar_h), 2, 2)

                # Filled portion (from bottom)
                fill_h = fill * bar_h
                if fill_h > 1:
                    p.setBrush(color)
                    p.drawRoundedRect(
                        QRectF(bx, bar_bot - fill_h, bar_w, fill_h), 2, 2
                    )

                # Value text (above bar)
                p.setFont(QFont("Helvetica", 8, QFont.Bold))
                p.setPen(QPen(color))
                val_text = f"{value:.0f}"
                p.drawText(QRectF(bx - 2, header_h + 2, bar_w + 4, value_h),
                           Qt.AlignCenter, val_text)

                # Label text (below bar)
                p.setFont(QFont("Helvetica", 7))
                p.setPen(QPen(QColor(GRAY)))
                p.drawText(QRectF(bx - 2, bar_bot + 2, bar_w + 4, label_h),
                           Qt.AlignCenter, bar_label)

                x += bar_w + bar_gap

            # Remove last bar_gap, add group_gap
            if gi < num_groups - 1:
                x += group_gap - bar_gap

                # Group separator line
                sep_x = x - group_gap / 2
                p.setPen(QPen(QColor(CHROME_DARK), 1))
                p.drawLine(int(sep_x), bar_top - 4, int(sep_x), bar_bot + 4)

        p.end()
