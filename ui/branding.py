"""KiSTI - Corporate Branding

Loads and caches Nvidia and Link ECU logos for use across the UI.
Nvidia: PNG from /usr/share/backgrounds/
Link ECU: SVG from assets/
"""

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_NVIDIA_PATH = os.path.join(_ASSETS_DIR, "nvidia_logo.png")
_LINK_SVG_PATH = os.path.join(_ASSETS_DIR, "link_ecu_logo.svg")
_KISTI_PATH = os.path.join(_ASSETS_DIR, "kisti_logo.png")

_cache = {}


def _svg_to_pixmap(path: str, size: QSize) -> QPixmap:
    renderer = QSvgRenderer(path)
    pm = QPixmap(size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def nvidia_logo(height: int = 24) -> QPixmap:
    """Return Nvidia logo scaled to given height, preserving aspect ratio."""
    key = f"nvidia_{height}"
    if key not in _cache:
        pm = QPixmap(_NVIDIA_PATH)
        if pm.isNull():
            return QPixmap()
        _cache[key] = pm.scaledToHeight(height, Qt.SmoothTransformation)
    return _cache[key]


def kisti_logo(height: int = 24) -> QPixmap:
    """Return KiSTI logo scaled to given height, preserving aspect ratio.
    Auto-crops padding from the source image (logo has ~30% padding on all sides).
    """
    key = f"kisti_{height}"
    if key not in _cache:
        pm = QPixmap(_KISTI_PATH)
        if pm.isNull():
            return QPixmap()
        # Crop to content bounds — the source image has massive padding
        # Content region: (114,333) to (1425,641) in the 1536x1024 image
        margin = 20  # keep a small margin around the text
        cx, cy, cw, ch = 114 - margin, 333 - margin, 1311 + 2 * margin, 308 + 2 * margin
        cropped = pm.copy(cx, cy, cw, ch)
        _cache[key] = cropped.scaledToHeight(height, Qt.SmoothTransformation)
    return _cache[key]


def link_ecu_logo(height: int = 24) -> QPixmap:
    """Return Link ECU logo scaled to given height, preserving aspect ratio."""
    key = f"link_{height}"
    if key not in _cache:
        # Render SVG at target height (use generous width, then crop)
        aspect = 3.5  # Link logo is wide
        w = int(height * aspect)
        pm = _svg_to_pixmap(_LINK_SVG_PATH, QSize(w, height))
        if pm.isNull():
            return QPixmap()
        _cache[key] = pm
    return _cache[key]
