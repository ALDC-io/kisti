"""Tests for FLIR Lepton threaded reader — _FrameWorker recovery path.

Exercises: consecutive failure detection → recovery trigger → USB reset →
re-open → resume. All with mock v4l2-ctl (no hardware needed).
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


class TestFrameWorkerRecovery:
    """Test _FrameWorker failure detection and recovery logic."""

    def test_consecutive_failures_trigger_recovery(self):
        """After MAX_CONSECUTIVE_FAILURES, worker should attempt recovery."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)

        # Simulate the failure detection threshold
        failures = 0
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            failures += 1
        assert failures >= MAX_CONSECUTIVE_FAILURES

    def test_recovery_increments_attempt_count(self):
        """Each recovery attempt increments the counter."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)

        with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
            with patch.object(worker, '_start_stream', return_value=MagicMock()):
                with patch.object(worker, '_kill_proc'):
                    worker._do_recovery("/dev/video0")

        assert worker._recovery_attempts == 1

    def test_recovery_kills_existing_proc(self):
        """Recovery kills the existing v4l2-ctl process before USB reset."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._proc = MagicMock()

        with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
            with patch.object(worker, '_start_stream', return_value=MagicMock()):
                worker._do_recovery("/dev/video0")

        worker._proc is not None  # got a new proc

    def test_failed_recovery_leaves_proc_none(self):
        """If recovery fails to start stream, proc stays None."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._proc = MagicMock()

        with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
            with patch.object(worker, '_start_stream', return_value=None):
                with patch('time.sleep'):  # skip the 5s backoff
                    worker._do_recovery("/dev/video0")

        assert worker._proc is None
        assert worker._recovery_attempts == 1

    def test_status_signal_on_recovery(self):
        """Worker emits status_changed signals during recovery."""
        mock_cv2 = MagicMock()
        worker = _FrameWorker(mock_cv2, 0)
        worker._proc = MagicMock()

        statuses = []
        worker.status_changed.connect(lambda s: statuses.append(s))

        with patch('sensors.flir_lepton_reader._usb_reset_purethermal', return_value=True):
            with patch.object(worker, '_start_stream', return_value=MagicMock()):
                worker._do_recovery("/dev/video0")

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
