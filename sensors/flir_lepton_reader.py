"""KiSTI - FLIR Lepton Thermal Camera Reader

Reads road surface temperatures from a FLIR Lepton module via PureThermal 3
USB board. Appears as a V4L2 device (/dev/videoX) and is read with OpenCV.

Polls at ~9 Hz (Lepton native frame rate) via QTimer. Falls back
gracefully if the camera is unplugged or OpenCV is unavailable.

The Lepton captures a 160x120 thermal image. Three horizontal ROI strips
map to left/center/right road surface zones as seen from a forward-facing
camera pointing at the road ahead.

Temperature conversion: Lepton 3.x radiometric mode outputs raw
centi-Kelvin values (uint16). Convert: temp_C = raw / 100.0 - 273.15
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.sensors.flir")

POLL_INTERVAL_MS = 111  # ~9 Hz (Lepton native frame rate)
DEVICE_INDEX_AUTO = -1   # auto-detect


@dataclass
class RoadSurfaceTemps:
    """Road surface temperatures across left/center/right zones (°C)."""
    left: float = 0.0
    center: float = 0.0
    right: float = 0.0


@dataclass
class WarmObjectDetection:
    """A warm object detected in the FLIR thermal frame."""
    position: str          # "LEFT", "CENTER", "RIGHT"
    peak_temp_c: float     # hottest pixel in blob (Celsius)
    blob_pixels: int       # number of pixels in blob
    timestamp: float = field(default_factory=time.monotonic)


# Warm object detection parameters
WARM_THRESHOLD_C = 10.0    # degrees above road baseline to trigger
WARM_MIN_BLOB_PX = 20      # minimum blob size (pixels)
WARM_DEBOUNCE_FRAMES = 2   # consecutive frames required
WARM_BASELINE_ALPHA = 0.1  # EMA smoothing (lower = slower adaptation)

# Zone boundaries for 160px wide frame
_ZONE_LEFT_MAX = 53        # pixels 0-52 = LEFT
_ZONE_CENTER_MAX = 107     # pixels 53-106 = CENTER, 107-159 = RIGHT


@dataclass
class ROIConfig:
    """Region of Interest rectangles for road surface zones in the 160x120 frame.

    Each ROI is (x, y, w, h) in pixel coordinates. The mean temperature
    within each ROI is reported as that zone's road surface temp.

    Default ROIs assume a forward-facing camera viewing the road ahead,
    with three horizontal strips covering left tire track, center, and
    right tire track zones.
    """
    left:   tuple[int, int, int, int] = (5,   45, 45, 30)  # left tire track zone
    center: tuple[int, int, int, int] = (58,  45, 45, 30)  # center / between tracks
    right:  tuple[int, int, int, int] = (110, 45, 45, 30)  # right tire track zone


def _raw_to_celsius(raw_value: float) -> float:
    """Convert Lepton radiometric raw (centi-Kelvin) to Celsius."""
    return raw_value / 100.0 - 273.15


class FLIRLeptonReader(QObject):
    """Polls FLIR Lepton via PureThermal USB for road surface temperatures.

    Follows the same QObject + QTimer + Signal pattern as YoctopuceReader.
    """

    temps_updated = Signal(object)          # emits RoadSurfaceTemps
    frame_updated = Signal(object)          # emits raw uint16 numpy frame (before ROI processing)
    warm_object_detected = Signal(object)   # emits WarmObjectDetection

    def __init__(
        self,
        device_index: int = DEVICE_INDEX_AUTO,
        roi: Optional[ROIConfig] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._device_index = device_index
        self._roi = roi or ROIConfig()
        self._cap = None  # cv2.VideoCapture
        self._available = False
        self._last_temps = RoadSurfaceTemps()
        self._np = None   # numpy module reference
        self._cv2 = None  # cv2 module reference

        # Warm object detection state
        self._baseline_temp_ck: float = 0.0  # EMA of frame median in centi-Kelvin
        self._baseline_ready = False          # True after first frame seeds baseline
        self._consecutive_warm: int = 0       # consecutive frames with warm blob(s)
        self._last_warm_position: str = ""    # zone of last detected blob

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> bool:
        """Initialize camera and start polling.

        Returns True if FLIR Lepton found, False otherwise.
        """
        try:
            import cv2
            import numpy as np
            self._cv2 = cv2
            self._np = np
        except ImportError:
            log.warning("opencv-python not installed — FLIR Lepton disabled")
            return False

        # Auto-detect: try /dev/video0 through /dev/video4
        if self._device_index == DEVICE_INDEX_AUTO:
            for idx in range(5):
                cap = self._cv2.VideoCapture(idx)
                if cap.isOpened():
                    # Check if this is a thermal camera (160x120)
                    w = cap.get(self._cv2.CAP_PROP_FRAME_WIDTH)
                    h = cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT)
                    if w == 160 and h == 120:
                        self._cap = cap
                        self._device_index = idx
                        log.info("FLIR Lepton found at /dev/video%d (%.0fx%.0f)", idx, w, h)
                        break
                    cap.release()
            else:
                log.info("No FLIR Lepton (160x120) found on /dev/video0-4")
                return False
        else:
            self._cap = self._cv2.VideoCapture(self._device_index)
            if not self._cap.isOpened():
                log.warning("Could not open /dev/video%d", self._device_index)
                return False

        # Configure for raw 16-bit radiometric output (Y16 = centi-Kelvin)
        self._cap.set(self._cv2.CAP_PROP_CONVERT_RGB, 0)
        y16_fourcc = self._cv2.VideoWriter_fourcc('Y', '1', '6', ' ')
        self._cap.set(self._cv2.CAP_PROP_FOURCC, y16_fourcc)
        self._cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 160)
        self._cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 120)

        self._available = True
        self._timer.start()
        self._poll()  # immediate first read
        return True

    def stop(self) -> None:
        """Stop polling and release camera."""
        self._timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._available = False
        log.info("FLIR Lepton reader stopped")

    @property
    def available(self) -> bool:
        return self._available

    def last_temps(self) -> RoadSurfaceTemps:
        return self._last_temps

    def _poll(self) -> None:
        """Read a frame, emit raw frame, then extract road surface temps from ROI regions."""
        if not self._available or self._cap is None:
            return

        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return

            # Log frame format once for diagnostics
            if not hasattr(self, '_logged_format'):
                self._logged_format = True
                log.info("FLIR frame: dtype=%s, shape=%s, mean=%.0f",
                         frame.dtype, frame.shape, float(self._np.mean(frame)))

            # OpenCV Y16 bug: may return uint16 data as flattened uint8 (120,320,1)
            if frame.dtype == self._np.uint8 and frame.shape != (120, 160):
                try:
                    frame = frame.view(self._np.uint16).reshape(120, 160)
                except (ValueError, AttributeError):
                    pass  # fall through to normal handling

            # Frame may be uint16 (radiometric) or uint8 (non-radiometric)
            if frame.dtype == self._np.uint16:
                thermal = frame
            elif len(frame.shape) == 3:
                # BGR/RGB frame — non-radiometric AGC mode, no absolute temps
                thermal = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY).astype(self._np.uint16)
                self.frame_updated.emit(thermal)
                return  # cannot extract reliable Celsius from non-radiometric frame
            else:
                thermal = frame.astype(self._np.uint16)

            # Emit raw frame for live display before ROI averaging
            self.frame_updated.emit(thermal)

            left_temp   = self._roi_mean_temp(thermal, self._roi.left)
            center_temp = self._roi_mean_temp(thermal, self._roi.center)
            right_temp  = self._roi_mean_temp(thermal, self._roi.right)

            self._last_temps = RoadSurfaceTemps(left=left_temp, center=center_temp, right=right_temp)
            self.temps_updated.emit(self._last_temps)

            # Warm object detection (radiometric frames only)
            if frame.dtype == self._np.uint16:
                self._detect_warm_objects(thermal)

        except Exception as exc:
            log.debug("FLIR poll error: %s", exc)

    def _roi_mean_temp(self, thermal_frame, roi: tuple[int, int, int, int]) -> float:
        """Extract mean temperature from an ROI rectangle.

        For radiometric Lepton: raw values are centi-Kelvin.
        For non-radiometric: values are pre-scaled in _poll.
        """
        x, y, w, h = roi
        # Clamp to frame bounds
        fh, fw = thermal_frame.shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = min(w, fw - x)
        h = min(h, fh - y)

        if w <= 0 or h <= 0:
            return 0.0

        region = thermal_frame[y:y + h, x:x + w]
        mean_raw = float(self._np.mean(region))

        # If values are in centi-Kelvin range (> 20000 = ~-73°C), convert
        if mean_raw > 20000:
            return _raw_to_celsius(mean_raw)
        # Non-radiometric values — cannot be converted to Celsius
        return 0.0

    def set_roi(self, roi: ROIConfig) -> None:
        """Update ROI configuration (e.g., after camera repositioning)."""
        self._roi = roi
        log.info("FLIR ROI updated: left=%s center=%s right=%s",
                 roi.left, roi.center, roi.right)

    # ------------------------------------------------------------------
    # Warm object detection (numpy-only, no scipy)
    # ------------------------------------------------------------------

    def _detect_warm_objects(self, thermal: 'numpy.ndarray') -> None:
        """Detect warm objects above road baseline using thresholding + blob analysis.

        Algorithm:
        1. Update road baseline via EMA of frame median (robust to outliers)
        2. Threshold: pixels > baseline + WARM_THRESHOLD_C
        3. Find connected blobs via numpy flood fill
        4. Filter blobs >= WARM_MIN_BLOB_PX pixels
        5. Debounce: require WARM_DEBOUNCE_FRAMES consecutive detections
        6. Emit warm_object_detected signal with position (LEFT/CENTER/RIGHT)
        """
        np = self._np
        if np is None:
            return

        # Convert threshold to centi-Kelvin (raw frame units)
        threshold_ck = WARM_THRESHOLD_C * 100.0

        # Update baseline using frame median (resistant to hot-spot outliers)
        frame_median = float(np.median(thermal))
        if not self._baseline_ready:
            self._baseline_temp_ck = frame_median
            self._baseline_ready = True
            return  # need at least one frame to establish baseline
        self._baseline_temp_ck += WARM_BASELINE_ALPHA * (frame_median - self._baseline_temp_ck)

        # Threshold: pixels significantly warmer than road baseline
        hot_mask = thermal > (self._baseline_temp_ck + threshold_ck)
        hot_count = int(np.sum(hot_mask))

        if hot_count < WARM_MIN_BLOB_PX:
            self._consecutive_warm = 0
            return

        # Find connected blobs via label_blobs (numpy-only)
        labels, n_labels = _label_blobs(hot_mask, np)
        if n_labels == 0:
            self._consecutive_warm = 0
            return

        # Find largest blob that meets minimum size
        best_size = 0
        best_label = 0
        for lbl in range(1, n_labels + 1):
            size = int(np.sum(labels == lbl))
            if size >= WARM_MIN_BLOB_PX and size > best_size:
                best_size = size
                best_label = lbl

        if best_label == 0:
            self._consecutive_warm = 0
            return

        # Debounce: require consecutive frames
        self._consecutive_warm += 1
        if self._consecutive_warm < WARM_DEBOUNCE_FRAMES:
            return

        # Classify position by blob centroid x-coordinate
        blob_mask = labels == best_label
        ys, xs = np.where(blob_mask)
        centroid_x = float(np.mean(xs))
        if centroid_x < _ZONE_LEFT_MAX:
            position = "LEFT"
        elif centroid_x < _ZONE_CENTER_MAX:
            position = "CENTER"
        else:
            position = "RIGHT"

        # Peak temp in blob
        peak_raw = float(np.max(thermal[blob_mask]))
        peak_c = _raw_to_celsius(peak_raw)

        detection = WarmObjectDetection(
            position=position,
            peak_temp_c=peak_c,
            blob_pixels=best_size,
        )
        self.warm_object_detected.emit(detection)


def _label_blobs(mask: 'numpy.ndarray', np) -> tuple:
    """Connected component labeling using iterative flood fill (numpy-only).

    Args:
        mask: 2D boolean array of hot pixels.
        np: numpy module reference.

    Returns:
        (labels, n_labels) where labels is an int32 array with component IDs
        and n_labels is the number of components found.
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current_label = 0

    for y in range(h):
        for x in range(w):
            if mask[y, x] and labels[y, x] == 0:
                current_label += 1
                # Iterative flood fill using a stack
                stack = [(y, x)]
                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h or cx < 0 or cx >= w:
                        continue
                    if not mask[cy, cx] or labels[cy, cx] != 0:
                        continue
                    labels[cy, cx] = current_label
                    stack.append((cy - 1, cx))
                    stack.append((cy + 1, cx))
                    stack.append((cy, cx - 1))
                    stack.append((cy, cx + 1))

    return labels, current_label
