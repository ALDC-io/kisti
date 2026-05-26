"""KiSTI - FLIR Lepton Thermal Camera Reader

Reads road surface temperatures from a FLIR Lepton module via PureThermal 3
USB board. Appears as a V4L2 device (/dev/videoX) and is read with OpenCV.

Architecture: Worker thread owns cap.read() so the Qt main thread NEVER
blocks on V4L2 I/O. The worker emits frames via signal; the main thread
processes them (fast numpy ops only). Self-healing: worker detects read
timeouts, USB-resets the PureThermal, and re-opens the device automatically.

The Lepton captures a 160x120 thermal image. Three horizontal ROI strips
map to left/center/right road surface zones as seen from a forward-facing
camera pointing at the road ahead.

Temperature conversion: Lepton 3.x radiometric mode outputs raw
centi-Kelvin values (uint16). Convert: temp_C = raw / 100.0 - 273.15
"""

from __future__ import annotations

import glob
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger("kisti.sensors.flir")

POLL_INTERVAL_MS = 111  # ~9 Hz (Lepton native frame rate)
DEVICE_INDEX_AUTO = -1   # auto-detect
MAX_CONSECUTIVE_FAILURES = 5  # trigger recovery after this many failed reads
MAX_RECOVERY_ATTEMPTS = 10    # give up after this many attempts per session


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

# Lepton resolution — detected at runtime, defaults updated by _detect_lepton_res()
_LEPTON_W = 160
_LEPTON_H = 120

# Zone boundaries for warm-object detection (updated by _detect_lepton_res)
_ZONE_LEFT_MAX = 53        # pixels 0-52 = LEFT
_ZONE_CENTER_MAX = 107     # pixels 53-106 = CENTER, 107-159 = RIGHT

# ROI presets per resolution
_ROI_160x120 = (
    (5,   45, 45, 30),   # left
    (58,  45, 45, 30),   # center
    (110, 45, 45, 30),   # right
)
_ROI_80x60 = (
    (2,  22, 23, 15),    # left  (half of 160x120)
    (29, 22, 23, 15),    # center
    (55, 22, 23, 15),    # right
)


def _detect_lepton_res(w: float, h: float) -> None:
    """Set module globals to match detected Lepton sensor resolution."""
    global _LEPTON_W, _LEPTON_H, _ZONE_LEFT_MAX, _ZONE_CENTER_MAX
    if w <= 80:
        _LEPTON_W, _LEPTON_H = 80, 60
        _ZONE_LEFT_MAX = 26
        _ZONE_CENTER_MAX = 53
    else:
        _LEPTON_W, _LEPTON_H = 160, 120
        _ZONE_LEFT_MAX = 53
        _ZONE_CENTER_MAX = 107


@dataclass
class ROIConfig:
    """Region of Interest rectangles for road surface zones in the thermal frame."""
    left:   tuple[int, int, int, int] = (5,   45, 45, 30)
    center: tuple[int, int, int, int] = (58,  45, 45, 30)
    right:  tuple[int, int, int, int] = (110, 45, 45, 30)

    @classmethod
    def for_resolution(cls, w: int) -> "ROIConfig":
        """Return ROI preset for detected resolution."""
        roi = _ROI_80x60 if w <= 80 else _ROI_160x120
        return cls(left=roi[0], center=roi[1], right=roi[2])


def _raw_to_celsius(raw_value: float) -> float:
    """Convert Lepton radiometric raw (centi-Kelvin) to Celsius."""
    return raw_value / 100.0 - 273.15


def _open_flir(cv2, device_index: int = DEVICE_INDEX_AUTO):
    """Open FLIR Lepton and configure Y16 radiometric mode.

    Returns (cap, device_index) or (None, -1) on failure.
    """
    if device_index != DEVICE_INDEX_AUTO:
        cap = cv2.VideoCapture(device_index)
        if cap.isOpened():
            _configure_y16(cap, cv2)
            return cap, device_index
        return None, -1

    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if (w == 160 and h == 120) or (w == 80 and h in (60, 63)):
                _detect_lepton_res(w, h)
                log.info("FLIR Lepton found at /dev/video%d (%.0fx%.0f), using %dx%d",
                         idx, w, h, _LEPTON_W, _LEPTON_H)
                _configure_y16(cap, cv2)
                return cap, idx
            cap.release()
    return None, -1


def _configure_y16(cap, cv2) -> None:
    """Configure VideoCapture for Y16 radiometric output.

    Skips resolution change if the device already reports the target size —
    mid-stream V4L2 format renegotiation can stall Lepton 2 on PureThermal.
    """
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    y16 = cv2.VideoWriter_fourcc('Y', '1', '6', ' ')
    cap.set(cv2.CAP_PROP_FOURCC, y16)
    cur_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    cur_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if cur_w != _LEPTON_W or cur_h != _LEPTON_H:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, _LEPTON_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _LEPTON_H)


def _usb_reset_purethermal() -> bool:
    """USB-reset the PureThermal board via sysfs. No shell injection."""
    try:
        for auth_path in glob.glob("/sys/bus/usb/devices/*/authorized"):
            prod_path = auth_path.replace("authorized", "product")
            try:
                with open(prod_path) as f:
                    product = f.read().strip()
            except (OSError, IOError):
                continue
            if "WebCam" not in product and "PureThermal" not in product:
                continue
            log.info("FLIR USB reset: %s", auth_path)
            # Direct sysfs write — no shell, no injection
            try:
                with open(auth_path, 'w') as f:
                    f.write('0\n')
                time.sleep(1)
                with open(auth_path, 'w') as f:
                    f.write('1\n')
                time.sleep(2)
                return True
            except PermissionError:
                # Fall back to sudo if no udev rule grants write access
                subprocess.run(
                    ["sudo", "-n", "sh", "-c",
                     "echo 0 > " + auth_path + " && sleep 1 && echo 1 > " + auth_path],
                    timeout=5, capture_output=True,
                )
                time.sleep(2)
                return True
    except Exception as exc:
        log.debug("USB reset failed: %s", exc)
    return False


class _FrameWorker(QThread):
    """Worker thread that streams FLIR frames via v4l2-ctl subprocess.

    OpenCV's V4L2 cap.read() uses select() which times out on some
    Lepton/PureThermal combos (especially Lepton 2 at 80x60). The
    v4l2-ctl --stream-mmap path uses DQBUF directly and works reliably.

    Frames are read from the subprocess stdout pipe as raw Y16 bytes,
    then reshaped to numpy uint16 arrays and emitted via signal.
    """
    frame_ready = Signal(object)   # emits numpy ndarray (uint16 thermal)
    status_changed = Signal(str)   # "online", "recovering", "offline"

    def __init__(self, cv2_mod, device_index: int, parent=None):
        super().__init__(parent)
        self._cv2 = cv2_mod
        self._device_index = device_index
        self._proc = None
        self._stop = False
        self._recovery_attempts = 0

    def run(self):
        import numpy as np
        self._np = np

        frame_bytes = _LEPTON_W * _LEPTON_H * 2  # Y16 = 2 bytes/pixel
        dev = f"/dev/video{self._device_index}"

        self._proc = self._start_stream(dev)
        if self._proc is None:
            self.status_changed.emit("offline")
            return

        self.status_changed.emit("online")
        consecutive_failures = 0

        while not self._stop:
            try:
                data = self._proc.stdout.read(frame_bytes)
            except Exception:
                data = b""

            if len(data) == frame_bytes:
                consecutive_failures = 0
                frame = self._np.frombuffer(data, dtype=np.uint16).reshape(
                    _LEPTON_H, _LEPTON_W
                )
                self.frame_ready.emit(frame)
            else:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    if self._recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
                        log.error("FLIR: %d recovery attempts exhausted — giving up",
                                  MAX_RECOVERY_ATTEMPTS)
                        self.status_changed.emit("offline")
                        break
                    self._do_recovery(dev)
                    consecutive_failures = 0
                else:
                    time.sleep(0.1)

        self._kill_proc()

    def _start_stream(self, dev: str):
        """Launch v4l2-ctl streaming subprocess.

        Sets Y16 format in a separate call before streaming — combining
        --set-fmt-video with --stream-mmap in one invocation silently
        fails on some v4l2-ctl versions (the 'Y16 ' fourcc trailing
        space gets mangled).
        """
        try:
            # Set Y16 radiometric format (trailing space in fourcc is required)
            subprocess.run(
                ["v4l2-ctl", "-d", dev, "--set-fmt-video",
                 f"width={_LEPTON_W},height={_LEPTON_H},pixelformat=Y16 "],
                capture_output=True, timeout=5,
            )
            proc = subprocess.Popen(
                ["v4l2-ctl", "-d", dev, "--stream-mmap", "--stream-to=-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            log.info("v4l2-ctl stream started on %s (%dx%d Y16)", dev, _LEPTON_W, _LEPTON_H)
            return proc
        except FileNotFoundError:
            log.error("v4l2-ctl not found — install v4l-utils")
            return None
        except Exception as exc:
            log.error("v4l2-ctl launch failed: %s", exc)
            return None

    def _kill_proc(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _do_recovery(self, dev: str):
        """Kill stream, USB-reset, re-launch."""
        self._recovery_attempts += 1
        self.status_changed.emit("recovering")
        log.warning("FLIR recovery attempt %d — restarting stream", self._recovery_attempts)

        self._kill_proc()
        _usb_reset_purethermal()

        self._proc = self._start_stream(dev)
        if self._proc is not None:
            self.status_changed.emit("online")
            log.info("FLIR recovered on %s (attempt %d)", dev, self._recovery_attempts)
        else:
            log.warning("FLIR recovery failed — will retry in 5s")
            time.sleep(5)

    def stop(self):
        self._stop = True


class FLIRLeptonReader(QObject):
    """FLIR Lepton reader with threaded I/O — UI never blocks.

    Worker thread handles all cap.read() and recovery. Main thread
    processes frames via signal (fast numpy ops only).
    """

    temps_updated = Signal(object)          # emits RoadSurfaceTemps
    frame_updated = Signal(object)          # emits raw uint16 numpy frame
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
        self._available = False
        self._last_temps = RoadSurfaceTemps()
        self._np = None
        self._cv2 = None
        self._worker: Optional[_FrameWorker] = None

        # Warm object detection state
        self._baseline_temp_ck: float = 0.0
        self._baseline_ready = False
        self._consecutive_warm: int = 0
        self._last_warm_position: str = ""

    def start(self) -> bool:
        """Initialize camera and start worker thread.

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

        # Probe for device on main thread (fast — just open/check/close)
        cap, idx = _open_flir(cv2, self._device_index)
        if cap is None:
            log.info("No FLIR Lepton found on /dev/video0-4")
            return False
        cap.release()  # worker will re-open

        # Update ROIs for detected resolution
        self._roi = ROIConfig.for_resolution(_LEPTON_W)

        # Start worker thread
        self._worker = _FrameWorker(cv2, idx)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.status_changed.connect(self._on_status)
        self._worker.start()

        self._available = True
        log.info("FLIR Lepton online: road surface thermal imaging (threaded)")
        return True

    def stop(self) -> None:
        """Stop worker thread and release camera."""
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(5000)
            self._worker = None
        self._available = False
        log.info("FLIR Lepton reader stopped")

    @property
    def available(self) -> bool:
        return self._available

    def last_temps(self) -> RoadSurfaceTemps:
        return self._last_temps

    def set_roi(self, roi: ROIConfig) -> None:
        self._roi = roi
        log.info("FLIR ROI updated: left=%s center=%s right=%s",
                 roi.left, roi.center, roi.right)

    def _on_status(self, status: str) -> None:
        """Handle worker status changes."""
        self._available = status == "online"
        if status == "recovering":
            log.info("FLIR recovering...")
        elif status == "offline":
            log.warning("FLIR offline — recovery exhausted")

    def _on_frame(self, frame) -> None:
        """Process a frame from the worker thread (runs on main thread via signal)."""
        np = self._np
        if np is None:
            return

        # Log frame format once
        if not hasattr(self, '_logged_format'):
            self._logged_format = True
            log.info("FLIR frame: dtype=%s, shape=%s, mean=%.0f",
                     frame.dtype, frame.shape, float(np.mean(frame)))

        # OpenCV Y16 bug: may return uint16 data as flattened uint8
        if frame.dtype == np.uint8 and frame.shape != (_LEPTON_H, _LEPTON_W):
            try:
                frame = frame.view(np.uint16).reshape(_LEPTON_H, _LEPTON_W)
            except (ValueError, AttributeError):
                pass

        if frame.dtype == np.uint16:
            thermal = frame
        elif len(frame.shape) == 3:
            thermal = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY).astype(np.uint16)
            self.frame_updated.emit(thermal)
            return
        else:
            thermal = frame.astype(np.uint16)

        self.frame_updated.emit(thermal)

        left_temp = self._roi_mean_temp(thermal, self._roi.left)
        center_temp = self._roi_mean_temp(thermal, self._roi.center)
        right_temp = self._roi_mean_temp(thermal, self._roi.right)

        self._last_temps = RoadSurfaceTemps(left=left_temp, center=center_temp, right=right_temp)
        self.temps_updated.emit(self._last_temps)

        if frame.dtype == np.uint16:
            self._detect_warm_objects(thermal)

    def _roi_mean_temp(self, thermal_frame, roi: tuple[int, int, int, int]) -> float:
        """Extract mean temperature from an ROI rectangle."""
        x, y, w, h = roi
        fh, fw = thermal_frame.shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = min(w, fw - x)
        h = min(h, fh - y)

        if w <= 0 or h <= 0:
            return 0.0

        region = thermal_frame[y:y + h, x:x + w]
        mean_raw = float(self._np.mean(region))

        if mean_raw > 20000:
            return _raw_to_celsius(mean_raw)
        return 0.0

    # ------------------------------------------------------------------
    # Warm object detection (numpy-only, no scipy)
    # ------------------------------------------------------------------

    def _detect_warm_objects(self, thermal: 'numpy.ndarray') -> None:
        """Detect warm objects above road baseline."""
        np = self._np
        if np is None:
            return

        threshold_ck = WARM_THRESHOLD_C * 100.0

        frame_median = float(np.median(thermal))
        if not self._baseline_ready:
            self._baseline_temp_ck = frame_median
            self._baseline_ready = True
            return
        self._baseline_temp_ck += WARM_BASELINE_ALPHA * (frame_median - self._baseline_temp_ck)

        hot_mask = thermal > (self._baseline_temp_ck + threshold_ck)
        hot_count = int(np.sum(hot_mask))

        if hot_count < WARM_MIN_BLOB_PX:
            self._consecutive_warm = 0
            return

        labels, n_labels = _label_blobs(hot_mask, np)
        if n_labels == 0:
            self._consecutive_warm = 0
            return

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

        self._consecutive_warm += 1
        if self._consecutive_warm < WARM_DEBOUNCE_FRAMES:
            return

        blob_mask = labels == best_label
        ys, xs = np.where(blob_mask)
        centroid_x = float(np.mean(xs))
        if centroid_x < _ZONE_LEFT_MAX:
            position = "LEFT"
        elif centroid_x < _ZONE_CENTER_MAX:
            position = "CENTER"
        else:
            position = "RIGHT"

        peak_raw = float(np.max(thermal[blob_mask]))
        peak_c = _raw_to_celsius(peak_raw)

        detection = WarmObjectDetection(
            position=position,
            peak_temp_c=peak_c,
            blob_pixels=best_size,
        )
        self.warm_object_detected.emit(detection)
        # Reset after firing so we don't emit every frame while warm object visible
        self._consecutive_warm = 0


def _label_blobs(mask: 'numpy.ndarray', np) -> tuple:
    """Connected component labeling using iterative flood fill (numpy-only)."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current_label = 0

    for y in range(h):
        for x in range(w):
            if mask[y, x] and labels[y, x] == 0:
                current_label += 1
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
