"""KiSTI - FLIR Lepton Thermal Camera Reader

Reads brake disc temperatures from a FLIR Lepton module via PureThermal
USB breakout board. Appears as a V4L2 device (/dev/videoX) and is read
with OpenCV.

Polls at ~9 Hz (Lepton native frame rate) via QTimer. Falls back
gracefully if the camera is unplugged or OpenCV is unavailable.

The Lepton captures a 160x120 thermal image. Four ROI (Region of
Interest) rectangles map to the four brake disc positions. The camera
must be mounted with a known field of view pointing at the car's
underside or wheel wells. ROI coordinates are configurable.

Temperature conversion: Lepton 3.x radiometric mode outputs raw
centi-Kelvin values (uint16). Convert: temp_C = raw / 100.0 - 273.15
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.sensors.flir")

POLL_INTERVAL_MS = 111  # ~9 Hz (Lepton native frame rate)
DEVICE_INDEX_AUTO = -1   # auto-detect


@dataclass
class BrakeTemps:
    """Brake disc temperatures per corner (°C)."""
    fl: float = 0.0
    fr: float = 0.0
    rl: float = 0.0
    rr: float = 0.0


@dataclass
class ROIConfig:
    """Region of Interest rectangles for each brake disc in the 160x120 frame.

    Each ROI is (x, y, w, h) in pixel coordinates. The mean temperature
    within each ROI is reported as that corner's brake temp.

    Default ROIs assume a forward-facing underbody camera with the car
    centered in frame. Adjust via config or calibration.
    """
    fl: tuple[int, int, int, int] = (10, 10, 30, 30)
    fr: tuple[int, int, int, int] = (120, 10, 30, 30)
    rl: tuple[int, int, int, int] = (10, 80, 30, 30)
    rr: tuple[int, int, int, int] = (120, 80, 30, 30)


def _raw_to_celsius(raw_value: float) -> float:
    """Convert Lepton radiometric raw (centi-Kelvin) to Celsius."""
    return raw_value / 100.0 - 273.15


class FLIRLeptonReader(QObject):
    """Polls FLIR Lepton via PureThermal USB for brake disc temperatures.

    Follows the same QObject + QTimer + Signal pattern as YoctopuceReader.
    """

    temps_updated = Signal(object)  # emits BrakeTemps

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
        self._last_temps = BrakeTemps()
        self._np = None   # numpy module reference
        self._cv2 = None  # cv2 module reference

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

        # Configure for raw 16-bit radiometric output
        self._cap.set(self._cv2.CAP_PROP_CONVERT_RGB, 0)

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

    def last_temps(self) -> BrakeTemps:
        return self._last_temps

    def _poll(self) -> None:
        """Read a frame and extract brake temps from ROI regions."""
        if not self._available or self._cap is None:
            return

        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return

            # Frame may be uint16 (radiometric) or uint8 (non-radiometric)
            if frame.dtype == self._np.uint16:
                thermal = frame
            elif len(frame.shape) == 3:
                # RGB/BGR frame — convert to grayscale, treat as relative temp
                thermal = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY).astype(self._np.uint16)
                # Scale 0-255 to rough brake temp range (100-600°C)
                thermal = (thermal.astype(self._np.float32) / 255.0 * 500 + 100)
                thermal = thermal.astype(self._np.uint16)
            else:
                thermal = frame.astype(self._np.uint16)

            fl_temp = self._roi_mean_temp(thermal, self._roi.fl)
            fr_temp = self._roi_mean_temp(thermal, self._roi.fr)
            rl_temp = self._roi_mean_temp(thermal, self._roi.rl)
            rr_temp = self._roi_mean_temp(thermal, self._roi.rr)

            self._last_temps = BrakeTemps(fl=fl_temp, fr=fr_temp, rl=rl_temp, rr=rr_temp)
            self.temps_updated.emit(self._last_temps)

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
        # Otherwise assume already in rough Celsius scale
        return mean_raw

    def set_roi(self, roi: ROIConfig) -> None:
        """Update ROI configuration (e.g., after camera repositioning)."""
        self._roi = roi
        log.info("FLIR ROI updated: FL=%s FR=%s RL=%s RR=%s",
                 roi.fl, roi.fr, roi.rl, roi.rr)
