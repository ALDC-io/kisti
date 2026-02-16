"""KiSTI - Simulated Camera Feed Widgets

Mock visualizations of front sensor array:
  - RGB: Canyon road with fall foliage (Duffey Lake Road, BC)
  - Teledyne IR: False-color thermal view
  - LiDAR: Point cloud / depth wireframe
  - Weather: Conditions overlay

All scenes depict a fall day canyon drive on Duffey Lake Road.
"""

import math
import random
import time

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QLinearGradient, QRadialGradient,
    QPolygonF, QPainterPath,
)
from PySide6.QtWidgets import QWidget

from ui.theme import (
    BG_DARK, BG_PANEL, HIGHLIGHT, RED, GREEN, YELLOW, WHITE,
    GRAY, CYAN, CHROME_DARK, CHROME_MID,
)


class _BaseCameraFeed(QWidget):
    """Base class for camera feed widgets with label overlay."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._label = label
        self._frame = 0
        self._t = 0.0

    def advance_frame(self):
        self._frame += 1
        self._t = time.monotonic()
        self.update()

    def _draw_label(self, p, w, h):
        """Draw camera label and REC indicator."""
        # Label background
        p.fillRect(0, 0, w, 16, QColor(0, 0, 0, 160))
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 8, QFont.Bold))
        p.drawText(4, 12, self._label)

        # REC dot
        if self._frame % 20 < 15:
            p.setBrush(QColor(RED))
            p.setPen(Qt.NoPen)
            p.drawEllipse(w - 14, 4, 8, 8)
        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(w - 40, 12, "REC")


class RGBCameraFeed(_BaseCameraFeed):
    """Simulated RGB camera - Duffey Lake Road canyon with fall colors."""

    def __init__(self, parent=None):
        super().__init__("RGB  1920x1080  60fps", parent)
        # Pre-generate tree positions for consistency
        self._trees_left = [(random.uniform(0.02, 0.35), random.uniform(0.25, 0.65),
                             random.choice(["#CC4400", "#DD6600", "#BB2200", "#EE8800",
                                            "#996600", "#AA3300", "#DD4400", "#CC5500"]))
                            for _ in range(25)]
        self._trees_right = [(random.uniform(0.65, 0.98), random.uniform(0.25, 0.65),
                              random.choice(["#CC4400", "#DD6600", "#BB2200", "#EE8800",
                                             "#996600", "#AA3300", "#DD4400", "#CC5500"]))
                             for _ in range(25)]
        self._road_offset = 0.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Sky gradient - fall overcast BC sky
        sky = QLinearGradient(0, 0, 0, h * 0.45)
        sky.setColorAt(0.0, QColor("#6688AA"))
        sky.setColorAt(0.5, QColor("#8899AA"))
        sky.setColorAt(1.0, QColor("#99AABB"))
        p.fillRect(0, 0, w, int(h * 0.45), sky)

        # Distant mountains (Coast Range)
        mtn = QPainterPath()
        mtn.moveTo(0, h * 0.4)
        peaks = [(0.0, 0.38), (0.08, 0.32), (0.15, 0.35), (0.22, 0.28),
                 (0.32, 0.33), (0.4, 0.26), (0.48, 0.30), (0.55, 0.24),
                 (0.62, 0.29), (0.7, 0.25), (0.78, 0.31), (0.85, 0.27),
                 (0.92, 0.34), (1.0, 0.30)]
        for px, py in peaks:
            mtn.lineTo(px * w, py * h)
        mtn.lineTo(w, h * 0.45)
        mtn.lineTo(0, h * 0.45)
        p.fillPath(mtn, QColor("#445566"))

        # Treeline / hillside
        hill = QLinearGradient(0, h * 0.35, 0, h * 0.55)
        hill.setColorAt(0.0, QColor("#664422"))
        hill.setColorAt(1.0, QColor("#553311"))
        p.fillRect(0, int(h * 0.40), w, int(h * 0.15), hill)

        # Fall foliage trees - left side
        for tx, ty, color in self._trees_left:
            cx, cy = int(tx * w), int(ty * h)
            sz = int(8 + (1.0 - ty / h) * 15)
            # Trunk
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3D2B1F"))
            p.drawRect(cx - 1, cy, 3, sz // 2)
            # Canopy
            p.setBrush(QColor(color))
            p.drawEllipse(cx - sz // 2, cy - sz // 2, sz, sz)

        # Fall foliage trees - right side
        for tx, ty, color in self._trees_right:
            cx, cy = int(tx * w), int(ty * h)
            sz = int(8 + (1.0 - ty / h) * 15)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3D2B1F"))
            p.drawRect(cx - 1, cy, 3, sz // 2)
            p.setBrush(QColor(color))
            p.drawEllipse(cx - sz // 2, cy - sz // 2, sz, sz)

        # Road surface - perspective converging
        road = QPainterPath()
        # Road vanishing point
        vx, vy = w * 0.48, h * 0.42
        # Slight curve offset (animated)
        curve = math.sin(self._frame * 0.02) * w * 0.03
        road.moveTo(w * 0.15, h)
        road.lineTo(vx - 8 + curve, vy)
        road.lineTo(vx + 8 + curve, vy)
        road.lineTo(w * 0.85, h)
        road.closeSubpath()
        p.fillPath(road, QColor("#3A3A3A"))

        # Road center line (dashed yellow)
        p.setPen(QPen(QColor("#DDAA00"), 2, Qt.DashLine))
        segments = 12
        for i in range(segments):
            t0 = i / segments
            t1 = (i + 0.5) / segments
            x0 = vx + curve + (w * 0.5 - vx - curve) * 0 + (t0 * (w * 0.5 - vx))
            y0 = vy + t0 * (h - vy)
            x1 = vx + curve + (t1 * (w * 0.5 - vx))
            y1 = vy + t1 * (h - vy)
            lw = 1 + t0 * 2
            if i % 2 == 0:
                p.setPen(QPen(QColor("#DDAA00"), lw))
                p.drawLine(int(x0), int(y0), int(x1), int(y1))

        # Road edge lines (white)
        p.setPen(QPen(QColor("#AAAAAA"), 1))
        p.drawLine(int(w * 0.15), h, int(vx - 8 + curve), int(vy))
        p.drawLine(int(w * 0.85), h, int(vx + 8 + curve), int(vy))

        # Guardrail posts (left side)
        for i in range(6):
            t = 0.2 + i * 0.13
            gx = w * 0.15 + (vx - 8 - w * 0.15) * t + curve * t
            gy = h - (h - vy) * t
            ph = 6 + (1 - t) * 8
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#888888"))
            p.drawRect(int(gx) - 5, int(gy) - int(ph), 2, int(ph))

        # Lake glimpse (Duffey Lake in the distance)
        p.setBrush(QColor("#3366778"))
        p.setPen(Qt.NoPen)
        lake = QPainterPath()
        lake.moveTo(w * 0.3, h * 0.42)
        lake.quadTo(w * 0.4, h * 0.40, w * 0.55, h * 0.42)
        lake.lineTo(w * 0.55, h * 0.44)
        lake.quadTo(w * 0.4, h * 0.43, w * 0.3, h * 0.44)
        lake.closeSubpath()
        p.fillPath(lake, QColor(51, 102, 119, 120))

        self._draw_label(p, w, h)
        p.end()


class IRCameraFeed(_BaseCameraFeed):
    """Simulated Teledyne IR - false-color thermal view of the same scene."""

    def __init__(self, parent=None):
        super().__init__("TELEDYNE IR  640x480  30fps", parent)
        self._heat_spots = [(random.uniform(0.1, 0.9), random.uniform(0.3, 0.9),
                             random.uniform(0.3, 0.8)) for _ in range(8)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # IR base - deep purple/blue (cold scene - fall day ~8C)
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#0D0030"))
        bg.setColorAt(0.4, QColor("#1A0050"))
        bg.setColorAt(1.0, QColor("#220066"))
        p.fillRect(0, 0, w, h, bg)

        # Road surface - slightly warmer (residual heat)
        road = QPainterPath()
        vx, vy = w * 0.48, h * 0.42
        curve = math.sin(self._frame * 0.02) * w * 0.03
        road.moveTo(w * 0.15, h)
        road.lineTo(vx - 8 + curve, vy)
        road.lineTo(vx + 8 + curve, vy)
        road.lineTo(w * 0.85, h)
        road.closeSubpath()
        road_grad = QLinearGradient(0, vy, 0, h)
        road_grad.setColorAt(0.0, QColor("#442200"))
        road_grad.setColorAt(0.5, QColor("#664400"))
        road_grad.setColorAt(1.0, QColor("#885500"))
        p.fillPath(road, road_grad)

        # Engine heat ahead (simulated vehicle ahead in distance)
        if self._frame % 60 < 45:
            eng_x = w * 0.48 + curve
            eng_y = h * 0.50
            rad = QRadialGradient(eng_x, eng_y, 30)
            rad.setColorAt(0.0, QColor("#FF4400"))
            rad.setColorAt(0.3, QColor("#CC2200"))
            rad.setColorAt(0.7, QColor("#661100"))
            rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(rad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(eng_x) - 30, int(eng_y) - 15, 60, 30)

        # Tree canopy thermal signatures (slightly warm from sun absorption)
        for tx, ty, intensity in self._heat_spots:
            cx, cy = int(tx * w), int(ty * h)
            sz = int(12 + intensity * 20)
            rad = QRadialGradient(cx, cy, sz)
            r = int(80 + intensity * 100)
            g = int(40 + intensity * 60)
            rad.setColorAt(0.0, QColor(r, g, 0, 180))
            rad.setColorAt(0.5, QColor(r // 2, g // 2, 20, 100))
            rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(rad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - sz, cy - sz, sz * 2, sz * 2)

        # Guardrail (metal - reflects ambient, cool)
        p.setPen(QPen(QColor("#332266"), 1))
        for i in range(6):
            t = 0.2 + i * 0.13
            gx = w * 0.15 + (vx - 8 - w * 0.15) * t + curve * t
            gy = h - (h - vy) * t
            p.drawLine(int(gx), int(gy), int(gx), int(gy) - 8)

        # IR temperature scale bar (right edge)
        scale_x = w - 12
        scale_h = h - 30
        for i in range(int(scale_h)):
            t = i / scale_h
            r = int(255 * t)
            g = int(180 * t * (1 - t) * 4)
            b = int(255 * (1 - t))
            p.setPen(QColor(r, g, b))
            p.drawLine(scale_x, 20 + i, scale_x + 6, 20 + i)

        p.setPen(QColor(WHITE))
        p.setFont(QFont("Helvetica", 6))
        p.drawText(scale_x - 12, 18, "35°")
        p.drawText(scale_x - 10, h - 8, "-5°")

        # Crosshair center
        cx, cy = w // 2, h // 2
        p.setPen(QPen(QColor(WHITE), 1))
        p.drawLine(cx - 8, cy, cx - 3, cy)
        p.drawLine(cx + 3, cy, cx + 8, cy)
        p.drawLine(cx, cy - 8, cx, cy - 3)
        p.drawLine(cx, cy + 3, cx, cy + 8)

        self._draw_label(p, w, h)
        p.end()


class LiDARCameraFeed(_BaseCameraFeed):
    """Simulated LiDAR - point cloud / wireframe depth view."""

    def __init__(self, parent=None):
        super().__init__("LiDAR  1024x64  10fps", parent)
        self._points = []
        self._regenerate_points()

    def _regenerate_points(self):
        """Generate point cloud for canyon road scene."""
        self._points = []
        # Road surface points
        for _ in range(120):
            x = random.uniform(0.15, 0.85)
            depth = random.uniform(0.4, 1.0)
            y = 0.45 + depth * 0.55
            # Converge toward center with depth
            x = 0.5 + (x - 0.5) * depth
            self._points.append((x, y, depth, "road"))

        # Cliff wall points (left)
        for _ in range(60):
            x = random.uniform(0.0, 0.2)
            y = random.uniform(0.2, 0.9)
            depth = 0.3 + (y - 0.2) * 0.8
            self._points.append((x, y, depth, "cliff"))

        # Cliff wall points (right)
        for _ in range(60):
            x = random.uniform(0.8, 1.0)
            y = random.uniform(0.2, 0.9)
            depth = 0.3 + (y - 0.2) * 0.8
            self._points.append((x, y, depth, "cliff"))

        # Tree canopy points
        for _ in range(40):
            x = random.uniform(0.0, 1.0)
            y = random.uniform(0.15, 0.5)
            depth = random.uniform(0.2, 0.6)
            self._points.append((x, y, depth, "tree"))

        # Guardrail line
        for i in range(20):
            t = i / 20
            depth = 0.3 + t * 0.7
            x = 0.15 + (0.48 - 0.15) * (1 - depth)
            y = 0.42 + (1.0 - 0.42) * depth
            self._points.append((x, y, depth, "guard"))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Black background
        p.fillRect(0, 0, w, h, QColor("#020208"))

        # Refresh some points periodically
        if self._frame % 5 == 0:
            # Jitter existing points slightly
            new_pts = []
            for x, y, depth, kind in self._points:
                jx = x + random.uniform(-0.005, 0.005)
                jy = y + random.uniform(-0.003, 0.003)
                new_pts.append((jx, jy, depth, kind))
            self._points = new_pts

        # Draw point cloud
        for x, y, depth, kind in self._points:
            px, py = int(x * w), int(y * h)

            if kind == "road":
                intensity = int(80 + (1 - depth) * 175)
                color = QColor(0, intensity, 0)
                sz = 2
            elif kind == "cliff":
                intensity = int(60 + (1 - depth) * 120)
                color = QColor(0, intensity // 2, intensity)
                sz = 2
            elif kind == "tree":
                intensity = int(100 + (1 - depth) * 155)
                color = QColor(intensity // 3, intensity, 0)
                sz = 3
            elif kind == "guard":
                color = QColor(200, 200, 0)
                sz = 3
            else:
                color = QColor(0, 100, 0)
                sz = 2

            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRect(px, py, sz, sz)

        # Distance rings
        p.setPen(QPen(QColor(0, 60, 0), 1, Qt.DotLine))
        for d in [0.3, 0.5, 0.7]:
            y_pos = int(0.42 * h + d * (h - 0.42 * h))
            p.drawLine(0, y_pos, w, y_pos)

        # Distance labels
        p.setPen(QColor(0, 120, 0))
        p.setFont(QFont("Courier", 7))
        p.drawText(4, int(h * 0.55), "50m")
        p.drawText(4, int(h * 0.72), "25m")
        p.drawText(4, int(h * 0.88), "10m")

        # Point count
        p.setPen(QColor(0, 150, 0))
        p.setFont(QFont("Courier", 7))
        p.drawText(w - 70, h - 6, f"pts: {len(self._points)}")

        self._draw_label(p, w, h)
        p.end()


class WeatherOverlayFeed(_BaseCameraFeed):
    """Weather camera + conditions overlay for Duffey Lake Road, BC."""

    def __init__(self, parent=None):
        super().__init__("WEATHER  1280x720  15fps", parent)
        self._conditions = {
            "location": "Duffey Lake Rd, BC",
            "highway": "Hwy 99 - Lillooet to Pemberton",
            "elevation": "1,147m",
            "temp": "8°C",
            "feels_like": "5°C",
            "condition": "Partly Cloudy",
            "wind": "NW 15 km/h",
            "gusts": "25 km/h",
            "visibility": "12 km",
            "humidity": "72%",
            "precip": "0%",
            "road_surface": "Dry",
            "grip": "Good",
            "sunset": "17:42 PST",
        }

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Scene background - overcast BC fall sky with hints of canyon
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0.0, QColor("#556677"))
        sky.setColorAt(0.3, QColor("#778899"))
        sky.setColorAt(0.6, QColor("#667755"))
        sky.setColorAt(1.0, QColor("#445533"))
        p.fillRect(0, 0, w, h, sky)

        # Distant treeline silhouette
        tree_path = QPainterPath()
        tree_path.moveTo(0, h * 0.45)
        for i in range(20):
            x = (i / 20) * w
            y_base = h * 0.40
            y = y_base + math.sin(i * 1.3) * h * 0.04 + math.sin(i * 0.7) * h * 0.02
            tree_path.lineTo(x, y)
        tree_path.lineTo(w, h * 0.5)
        tree_path.lineTo(w, h)
        tree_path.lineTo(0, h)
        tree_path.closeSubpath()
        p.fillPath(tree_path, QColor("#2A3322"))

        # Semi-transparent overlay panel
        panel_x = 6
        panel_y = 20
        panel_w = w - 12
        panel_h = h - 26
        p.fillRect(panel_x, panel_y, panel_w, panel_h, QColor(0, 0, 0, 160))
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawRect(panel_x, panel_y, panel_w, panel_h)

        # Header
        p.setPen(QColor(HIGHLIGHT))
        p.setFont(QFont("Helvetica", 10, QFont.Bold))
        p.drawText(panel_x + 6, panel_y + 16, self._conditions["location"])

        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(panel_x + 6, panel_y + 28, self._conditions["highway"])

        # Divider
        p.setPen(QPen(QColor(CHROME_DARK), 1))
        p.drawLine(panel_x + 6, panel_y + 32, panel_x + panel_w - 6, panel_y + 32)

        # Two-column layout
        col1_x = panel_x + 8
        col2_x = panel_x + panel_w // 2 + 4
        y = panel_y + 46

        def draw_row(label, value, x, y_pos, value_color=WHITE):
            p.setPen(QColor(GRAY))
            p.setFont(QFont("Helvetica", 8))
            p.drawText(x, y_pos, label)
            p.setPen(QColor(value_color))
            p.setFont(QFont("Helvetica", 9, QFont.Bold))
            p.drawText(x + 70, y_pos, value)

        # Left column
        draw_row("Temp", self._conditions["temp"], col1_x, y, CYAN)
        draw_row("Feels Like", self._conditions["feels_like"], col1_x, y + 16, CYAN)
        draw_row("Condition", self._conditions["condition"], col1_x, y + 32)
        draw_row("Wind", self._conditions["wind"], col1_x, y + 48)
        draw_row("Gusts", self._conditions["gusts"], col1_x, y + 64, YELLOW)
        draw_row("Humidity", self._conditions["humidity"], col1_x, y + 80)
        draw_row("Visibility", self._conditions["visibility"], col1_x, y + 96)

        # Right column
        draw_row("Elevation", self._conditions["elevation"], col2_x, y)
        draw_row("Precip", self._conditions["precip"], col2_x, y + 16, GREEN)
        draw_row("Road", self._conditions["road_surface"], col2_x, y + 32, GREEN)
        draw_row("Grip", self._conditions["grip"], col2_x, y + 48, GREEN)
        draw_row("Sunset", self._conditions["sunset"], col2_x, y + 64)

        # Animated wind indicator
        p.setPen(QPen(QColor(CYAN), 1))
        wind_x = col2_x + 30
        wind_y = y + 90
        angle = math.radians(315 + math.sin(self._frame * 0.1) * 10)  # NW
        ax = wind_x + math.cos(angle) * 15
        ay = wind_y - math.sin(angle) * 15
        p.drawLine(wind_x, wind_y, int(ax), int(ay))
        # Arrowhead
        p.drawLine(int(ax), int(ay),
                   int(ax - math.cos(angle + 0.4) * 5),
                   int(ay + math.sin(angle + 0.4) * 5))
        p.drawLine(int(ax), int(ay),
                   int(ax - math.cos(angle - 0.4) * 5),
                   int(ay + math.sin(angle - 0.4) * 5))

        p.setPen(QColor(GRAY))
        p.setFont(QFont("Helvetica", 7))
        p.drawText(wind_x - 10, wind_y + 18, "NW")

        self._draw_label(p, w, h)
        p.end()
