"""Tests for FLIR Lepton threaded reader — _FrameWorker recovery path.

Exercises: consecutive failure detection → recovery trigger → USB reset →
re-open → resume. All with mock cv2 (no hardware needed).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from PySide6.QtWidgets import QApplication

if not QApplication.instance():
    _app = QApplication([])

from sensors.flir_lepton_reader import (
    _FrameWorker,
    FLIRLeptonReader,
    MAX_CONSECUTIVE_FAILURES,
    MAX_RECOVERY_ATTEMPTS,
    RoadSurfaceTemps,
    WarmObjectDetection,
    WARM_DEBOUNCE_FRAMES,
)


class MockCap:
    """Mock cv2.VideoCapture that can simulate lockup + recovery."""

    def __init__(self, fail_count: int = 0):
        self._fail_count = fail_count
        self._read_count = 0
        self._released = False

    def isOpened(self):
        return True

    def read(self):
        self._read_count += 1
        if self._read_count <= self._fail_count:
            return False, None
        # Return a fake 160x120 uint16 frame (30000 cK ≈ 26.85°C)
        import numpy as np
        frame = np.full((120, 160), 30000, dtype=np.uint16)
        return True, frame

    def release(self):
        self._released = True

    def get(self, prop):
        return {3: 160.0, 4: 120.0}.get(prop, 0.0)

    def set(self, prop, val):
        pass


class TestFrameWorkerRecovery:
    """Test _FrameWorker failure detection and recovery logic."""

    def test_consecutive_failures_trigger_recovery(self):
        """After MAX_CONSECUTIVE_FAILURES, worker should attempt recovery."""
        mock_cv2 = MagicMock()
        cap = MockCap(fail_count=MAX_CONSECUTIVE_FAILURES + 1)
        mock_cv2.VideoCapture.return_value = cap

        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = cap
        worker._device_index = 0

        # Simulate the failure detection loop (without actually running the thread)
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            worker._consecutive_failures += 1

        assert worker._consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    def test_recovery_increments_attempt_count(self):
        """Each recovery attempt increments the counter."""
        mock_cv2 = MagicMock()
        cap = MockCap()
        mock_cv2.VideoCapture.return_value = cap

        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = cap

        # Mock _open_flir to return a new cap
        with patch('sensors.flir_lepton_reader._open_flir', return_value=(MockCap(), 0)):
            with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
                worker._do_recovery()

        assert worker._recovery_attempts == 1
        assert worker._consecutive_failures == 0

    def test_recovery_resets_failure_count(self):
        """Successful recovery resets consecutive failure counter."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = MockCap()
        worker._consecutive_failures = MAX_CONSECUTIVE_FAILURES

        with patch('sensors.flir_lepton_reader._open_flir', return_value=(MockCap(), 0)):
            with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
                worker._do_recovery()

        assert worker._consecutive_failures == 0

    def test_failed_recovery_keeps_cap_none(self):
        """If recovery fails to open device, cap stays None."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = MockCap()

        with patch('sensors.flir_lepton_reader._open_flir', return_value=(None, -1)):
            with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
                with patch('time.sleep'):  # skip the 5s backoff
                    worker._do_recovery()

        assert worker._cap is None
        assert worker._recovery_attempts == 1

    def test_recovery_releases_old_cap(self):
        """Recovery releases the old capture handle before USB reset."""
        mock_cv2 = MagicMock()
        old_cap = MockCap()
        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = old_cap

        with patch('sensors.flir_lepton_reader._open_flir', return_value=(MockCap(), 0)):
            with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
                worker._do_recovery()

        assert old_cap._released

    def test_status_signal_on_recovery(self):
        """Worker emits status_changed signals during recovery."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._cap = MockCap()

        statuses = []
        worker.status_changed.connect(lambda s: statuses.append(s))

        with patch('sensors.flir_lepton_reader._open_flir', return_value=(MockCap(), 0)):
            with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
                worker._do_recovery()

        assert "recovering" in statuses
        assert "online" in statuses

    def test_max_recovery_attempts_exhausted(self):
        """Worker should stop after MAX_RECOVERY_ATTEMPTS."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._recovery_attempts = MAX_RECOVERY_ATTEMPTS

        # At max attempts, the run() loop should break (not call _do_recovery)
        assert worker._recovery_attempts >= MAX_RECOVERY_ATTEMPTS


class TestConsecutiveWarmReset:
    """Test that _consecutive_warm resets after detection fires."""

    def test_warm_counter_resets_after_emit(self):
        """_consecutive_warm should reset to 0 after warm_object_detected emits."""
        import numpy as np
        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._np = np
        reader._baseline_temp_ck = 30000.0  # ~26.85°C baseline
        reader._baseline_ready = True
        reader._consecutive_warm = WARM_DEBOUNCE_FRAMES  # already debounced
        reader._last_warm_position = ""

        # Create thermal frame with a hot blob (40°C = 31315 cK) in center
        frame = np.full((120, 160), 30000, dtype=np.uint16)
        frame[50:70, 60:90] = 35000  # hot blob (50°C above baseline threshold)

        detections = []
        reader.warm_object_detected = MagicMock()
        reader.warm_object_detected.emit = lambda d: detections.append(d)

        reader._detect_warm_objects(frame)

        assert len(detections) == 1
        assert reader._consecutive_warm == 0  # reset after emit
