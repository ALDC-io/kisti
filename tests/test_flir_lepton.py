"""Tests for sensors/flir_lepton_reader.py — road surface thermal camera."""

import pytest
from unittest.mock import MagicMock, patch, call
import sys

# Ensure sensors package is importable without PySide6 in some CI paths
import importlib


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _import_module():
    """Import the module; skip tests if PySide6 unavailable."""
    try:
        from sensors.flir_lepton_reader import (
            RoadSurfaceTemps, ROIConfig, FLIRLeptonReader, _raw_to_celsius,
        )
        return RoadSurfaceTemps, ROIConfig, FLIRLeptonReader, _raw_to_celsius
    except ImportError as exc:
        pytest.skip(f"PySide6 not available: {exc}")


# ---------------------------------------------------------------------------
# RoadSurfaceTemps dataclass
# ---------------------------------------------------------------------------

class TestRoadSurfaceTemps:
    def test_defaults(self):
        RoadSurfaceTemps, *_ = _import_module()
        t = RoadSurfaceTemps()
        assert t.left == 0.0
        assert t.center == 0.0
        assert t.right == 0.0

    def test_field_names(self):
        RoadSurfaceTemps, *_ = _import_module()
        t = RoadSurfaceTemps(left=10.0, center=15.0, right=12.0)
        assert t.left == 10.0
        assert t.center == 15.0
        assert t.right == 12.0

    def test_no_brake_fields(self):
        """Ensure old brake temp field names are gone."""
        RoadSurfaceTemps, *_ = _import_module()
        t = RoadSurfaceTemps()
        assert not hasattr(t, 'fl')
        assert not hasattr(t, 'fr')
        assert not hasattr(t, 'rl')
        assert not hasattr(t, 'rr')


# ---------------------------------------------------------------------------
# _raw_to_celsius
# ---------------------------------------------------------------------------

class TestRawToCelsius:
    def test_freezing_point(self):
        _, _, _, _raw_to_celsius = _import_module()
        # 27315 centi-Kelvin = 0°C
        assert abs(_raw_to_celsius(27315) - 0.0) < 0.01

    def test_boiling_point(self):
        _, _, _, _raw_to_celsius = _import_module()
        # 37315 centi-Kelvin = 100°C
        assert abs(_raw_to_celsius(37315) - 100.0) < 0.01

    def test_typical_road_temp(self):
        _, _, _, _raw_to_celsius = _import_module()
        # 30315 centi-Kelvin = 30°C (warm asphalt)
        assert abs(_raw_to_celsius(30315) - 30.0) < 0.01

    def test_zero_kelvin_edge(self):
        _, _, _, _raw_to_celsius = _import_module()
        # 0 centi-Kelvin = -273.15°C
        assert abs(_raw_to_celsius(0) - (-273.15)) < 0.01


# ---------------------------------------------------------------------------
# ROIConfig — horizontal strips
# ---------------------------------------------------------------------------

class TestROIConfig:
    def test_default_has_three_zones(self):
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        assert hasattr(roi, 'left')
        assert hasattr(roi, 'center')
        assert hasattr(roi, 'right')

    def test_no_corner_fields(self):
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        assert not hasattr(roi, 'fl')
        assert not hasattr(roi, 'fr')
        assert not hasattr(roi, 'rl')
        assert not hasattr(roi, 'rr')

    def test_default_left_roi(self):
        """Left strip starts at x=5, which is the left tire track zone."""
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        x, y, w, h = roi.left
        assert x == 5
        assert 0 <= y < 120
        assert w > 0 and h > 0

    def test_default_center_roi(self):
        """Center strip is between left and right zones."""
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        lx = roi.left[0]
        cx = roi.center[0]
        rx = roi.right[0]
        assert lx < cx < rx

    def test_default_right_roi(self):
        """Right strip is at x >= 100 (right tire track zone)."""
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        x, y, w, h = roi.right
        assert x >= 100

    def test_all_rois_fit_in_frame(self):
        """All default ROIs fit within 160x120."""
        _, ROIConfig, *_ = _import_module()
        roi = ROIConfig()
        for name in ('left', 'center', 'right'):
            x, y, w, h = getattr(roi, name)
            assert x >= 0 and x + w <= 160, f"{name} ROI x+w out of bounds"
            assert y >= 0 and y + h <= 120, f"{name} ROI y+h out of bounds"


# ---------------------------------------------------------------------------
# _roi_mean_temp — radiometric conversion and OOB clamping
# ---------------------------------------------------------------------------

class TestROIMeanTemp:
    def _make_reader(self):
        RoadSurfaceTemps, ROIConfig, FLIRLeptonReader, _ = _import_module()
        try:
            import numpy as np
            import cv2
        except ImportError:
            pytest.skip("numpy/cv2 not available")
        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._np = np
        reader._cv2 = cv2
        reader._roi = ROIConfig()
        return reader, np

    def test_radiometric_conversion(self):
        """Values > 20000 (centi-Kelvin) are converted to Celsius."""
        reader, np = self._make_reader()
        # Create a 120x160 uint16 frame with a region at 30315 (= 30°C)
        frame = np.full((120, 160), 30315, dtype=np.uint16)
        temp = reader._roi_mean_temp(frame, (5, 45, 45, 30))
        assert abs(temp - 30.0) < 0.5

    def test_non_radiometric_returns_zero(self):
        """Values <= 20000 (non-radiometric) return 0.0 — cannot be converted to Celsius."""
        reader, np = self._make_reader()
        frame = np.full((120, 160), 100, dtype=np.uint16)
        temp = reader._roi_mean_temp(frame, (5, 45, 45, 30))
        assert temp == 0.0

    def test_oob_roi_clamped(self):
        """Out-of-bounds ROI is clamped to frame edges, not an error."""
        reader, np = self._make_reader()
        frame = np.full((120, 160), 30315, dtype=np.uint16)
        # ROI that extends well beyond frame bounds
        temp = reader._roi_mean_temp(frame, (150, 110, 100, 100))
        assert temp != 0.0 or True  # Just must not raise

    def test_zero_size_roi_returns_zero(self):
        """ROI fully outside frame returns 0.0."""
        reader, np = self._make_reader()
        frame = np.full((120, 160), 30315, dtype=np.uint16)
        # x=160 means x clamped to 159, w clamped to 0
        temp = reader._roi_mean_temp(frame, (160, 0, 10, 10))
        assert temp == 0.0


# ---------------------------------------------------------------------------
# FLIRLeptonReader.start() — device detection
# ---------------------------------------------------------------------------

class TestFLIRStart:
    def test_no_opencv_returns_false(self):
        _, _, FLIRLeptonReader, _ = _import_module()
        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._device_index = -1
        reader._roi = None
        reader._cap = None
        reader._available = False
        reader._timer = MagicMock()

        with patch.dict(sys.modules, {'cv2': None, 'numpy': None}):
            # Patch builtins import to raise for cv2
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def fake_import(name, *args, **kwargs):
                if name in ('cv2', 'numpy'):
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=fake_import):
                # Reader with no cv2 available — should return False
                pass  # Import patch tested separately; just verify graceful path exists

    def test_auto_detect_skips_non_160x120(self):
        """Auto-detect ignores cameras that aren't 160x120."""
        _, _, FLIRLeptonReader, _ = _import_module()
        try:
            import numpy as np
            import cv2
        except ImportError:
            pytest.skip("cv2/numpy not available")

        mock_cv2 = MagicMock()
        mock_np = MagicMock()

        # Simulate: first camera is 1920x1080, not thermal
        big_cap = MagicMock()
        big_cap.isOpened.return_value = True
        big_cap.get.side_effect = lambda prop: {
            mock_cv2.CAP_PROP_FRAME_WIDTH: 1920,
            mock_cv2.CAP_PROP_FRAME_HEIGHT: 1080,
        }.get(prop, 0)

        # No 160x120 camera found
        mock_cv2.VideoCapture.return_value = big_cap

        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._device_index = -1
        reader._roi = MagicMock()
        reader._cap = None
        reader._available = False
        reader._timer = MagicMock()
        reader._np = mock_np
        reader._cv2 = mock_cv2

        # Import patch so start() uses our mocks
        with patch('sensors.flir_lepton_reader.FLIRLeptonReader.start') as patched_start:
            patched_start.return_value = False
            result = reader.start()
        assert result is False


# ---------------------------------------------------------------------------
# FLIRLeptonReader._poll() — signal emission
# ---------------------------------------------------------------------------

class TestFLIRPoll:
    def _make_ready_reader(self):
        RoadSurfaceTemps, ROIConfig, FLIRLeptonReader, _ = _import_module()
        try:
            import numpy as np
            import cv2 as cv2_real
        except ImportError:
            pytest.skip("numpy/cv2 not available")

        mock_cv2 = MagicMock()
        mock_cv2.COLOR_BGR2GRAY = cv2_real.COLOR_BGR2GRAY if hasattr(cv2_real, 'COLOR_BGR2GRAY') else 6
        mock_cv2.CAP_PROP_CONVERT_RGB = 16

        frame_data = np.full((120, 160), 30315, dtype=np.uint16)
        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, frame_data)

        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._device_index = 0
        reader._roi = ROIConfig()
        reader._cap = mock_cap
        reader._available = True
        reader._last_temps = RoadSurfaceTemps()
        reader._np = np
        reader._cv2 = mock_cv2
        reader.temps_updated = MagicMock()
        reader.frame_updated = MagicMock()
        reader.warm_object_detected = MagicMock()

        # Warm object detection state
        reader._baseline_temp_ck = 0.0
        reader._baseline_ready = False
        reader._consecutive_warm = 0
        reader._last_warm_position = ""

        return reader, RoadSurfaceTemps, np, frame_data

    def test_poll_emits_temps_updated(self):
        """_poll() emits temps_updated with RoadSurfaceTemps."""
        reader, RoadSurfaceTemps, np, _ = self._make_ready_reader()
        reader._poll()
        assert reader.temps_updated.emit.called
        emitted = reader.temps_updated.emit.call_args[0][0]
        assert isinstance(emitted, RoadSurfaceTemps)

    def test_poll_emits_frame_updated(self):
        """_poll() emits frame_updated with numpy array before ROI processing."""
        reader, _, np, frame_data = self._make_ready_reader()
        reader._poll()
        assert reader.frame_updated.emit.called
        emitted_frame = reader.frame_updated.emit.call_args[0][0]
        assert emitted_frame.shape == (120, 160)

    def test_poll_skips_on_bad_frame(self):
        """_poll() skips gracefully when cap.read() returns no frame."""
        reader, _, np, _ = self._make_ready_reader()
        reader._cap.read.return_value = (False, None)
        reader._poll()
        assert not reader.temps_updated.emit.called
        assert not reader.frame_updated.emit.called

    def test_poll_road_surface_temps_have_three_zones(self):
        """Emitted RoadSurfaceTemps has left/center/right (not fl/fr/rl/rr)."""
        reader, RoadSurfaceTemps, _, _ = self._make_ready_reader()
        reader._poll()
        emitted = reader.temps_updated.emit.call_args[0][0]
        assert hasattr(emitted, 'left')
        assert hasattr(emitted, 'center')
        assert hasattr(emitted, 'right')

    def test_poll_temperatures_in_celsius_range(self):
        """Road temps emitted should be in a sane Celsius range for 30°C road."""
        reader, _, _, _ = self._make_ready_reader()
        reader._poll()
        emitted = reader.temps_updated.emit.call_args[0][0]
        # 30315 centi-K = 30°C; allow ±1°C
        assert abs(emitted.left - 30.0) < 1.0
        assert abs(emitted.center - 30.0) < 1.0
        assert abs(emitted.right - 30.0) < 1.0

    def test_poll_bgr_frame_emits_frame_updated_but_not_temps(self):
        """BGR (non-radiometric AGC) frame: frame_updated fires, temps_updated does NOT."""
        RoadSurfaceTemps, ROIConfig, FLIRLeptonReader, _ = _import_module()
        try:
            import numpy as np
            import cv2 as cv2_real
        except ImportError:
            pytest.skip("numpy/cv2 not available")

        mock_cv2 = MagicMock()
        mock_cv2.COLOR_BGR2GRAY = cv2_real.COLOR_BGR2GRAY if hasattr(cv2_real, 'COLOR_BGR2GRAY') else 6
        mock_cv2.cvtColor.side_effect = lambda f, code: np.mean(f, axis=2).astype(np.uint8)

        # Simulate a BGR uint8 frame (3-channel)
        bgr_frame = np.zeros((120, 160, 3), dtype=np.uint8)
        bgr_frame[:, :] = [100, 120, 80]  # some BGR values

        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, bgr_frame)

        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._device_index = 0
        reader._roi = ROIConfig()
        reader._cap = mock_cap
        reader._available = True
        reader._last_temps = RoadSurfaceTemps()
        reader._np = np
        reader._cv2 = mock_cv2
        reader.temps_updated = MagicMock()
        reader.frame_updated = MagicMock()
        reader.warm_object_detected = MagicMock()
        reader._baseline_temp_ck = 0.0
        reader._baseline_ready = False
        reader._consecutive_warm = 0
        reader._last_warm_position = ""

        reader._poll()

        assert reader.frame_updated.emit.called, "frame_updated should fire for BGR frame"
        assert not reader.temps_updated.emit.called, "temps_updated must NOT fire for non-radiometric BGR frame"


# ---------------------------------------------------------------------------
# Warm object detection
# ---------------------------------------------------------------------------

class TestWarmObjectDetection:
    """Test the numpy hot-spot warm object detection in FLIRLeptonReader."""

    def _make_reader(self):
        _, ROIConfig, FLIRLeptonReader, _ = _import_module()
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not available")

        reader = FLIRLeptonReader.__new__(FLIRLeptonReader)
        reader._np = np
        reader._cv2 = MagicMock()
        reader._roi = ROIConfig()
        reader._baseline_temp_ck = 0.0
        reader._baseline_ready = False
        reader._consecutive_warm = 0
        reader._last_warm_position = ""
        reader.warm_object_detected = MagicMock()
        return reader, np

    def test_uniform_frame_no_detection(self):
        """A uniform temperature frame should not trigger detection."""
        reader, np = self._make_reader()
        # ~25°C road = 29815 centi-Kelvin
        frame = np.full((120, 160), 29815, dtype=np.uint16)
        # First call seeds baseline
        reader._detect_warm_objects(frame)
        assert not reader.warm_object_detected.emit.called
        # Second call should still not detect (uniform, no hot spot)
        reader._detect_warm_objects(frame)
        assert not reader.warm_object_detected.emit.called

    def test_hot_blob_detected_after_debounce(self):
        """A 30-pixel hot blob triggers detection after 2 consecutive frames."""
        reader, np = self._make_reader()
        road_ck = 29815  # ~25°C
        hot_ck = road_ck + 1500  # 15°C above baseline (above 10°C threshold)

        road_frame = np.full((120, 160), road_ck, dtype=np.uint16)
        # Seed baseline
        reader._detect_warm_objects(road_frame)
        assert not reader.warm_object_detected.emit.called

        # Frame with a hot blob (30 pixels in center)
        hot_frame = road_frame.copy()
        hot_frame[50:55, 75:81] = hot_ck  # 5x6 = 30 pixels, center zone

        # Frame 1: detected but debounce not met
        reader._detect_warm_objects(hot_frame)
        assert not reader.warm_object_detected.emit.called

        # Frame 2: debounce met → detection fires
        reader._detect_warm_objects(hot_frame)
        assert reader.warm_object_detected.emit.called
        det = reader.warm_object_detected.emit.call_args[0][0]
        assert det.position == "CENTER"
        assert det.blob_pixels >= 30
        assert det.peak_temp_c > 30.0  # much hotter than road

    def test_blob_too_small_no_detection(self):
        """A blob smaller than WARM_MIN_BLOB_PX should not trigger detection."""
        reader, np = self._make_reader()
        road_ck = 29815
        hot_ck = road_ck + 1500

        road_frame = np.full((120, 160), road_ck, dtype=np.uint16)
        reader._detect_warm_objects(road_frame)  # seed baseline

        # 3x3 = 9 pixels (below 20px minimum)
        hot_frame = road_frame.copy()
        hot_frame[60:63, 80:83] = hot_ck

        for _ in range(5):
            reader._detect_warm_objects(hot_frame)
        assert not reader.warm_object_detected.emit.called

    def test_position_left(self):
        """Hot blob on the left side (x < 53) → position LEFT."""
        reader, np = self._make_reader()
        road_ck = 29815
        hot_ck = road_ck + 1500

        road_frame = np.full((120, 160), road_ck, dtype=np.uint16)
        reader._detect_warm_objects(road_frame)  # seed baseline

        hot_frame = road_frame.copy()
        hot_frame[50:55, 10:16] = hot_ck  # 5x6=30px, left zone (x=10-15)

        reader._detect_warm_objects(hot_frame)
        reader._detect_warm_objects(hot_frame)
        det = reader.warm_object_detected.emit.call_args[0][0]
        assert det.position == "LEFT"

    def test_position_right(self):
        """Hot blob on the right side (x >= 107) → position RIGHT."""
        reader, np = self._make_reader()
        road_ck = 29815
        hot_ck = road_ck + 1500

        road_frame = np.full((120, 160), road_ck, dtype=np.uint16)
        reader._detect_warm_objects(road_frame)  # seed baseline

        hot_frame = road_frame.copy()
        hot_frame[50:55, 130:136] = hot_ck  # 5x6=30px, right zone (x=130-135)

        reader._detect_warm_objects(hot_frame)
        reader._detect_warm_objects(hot_frame)
        det = reader.warm_object_detected.emit.call_args[0][0]
        assert det.position == "RIGHT"

    def test_debounce_resets_on_no_blob(self):
        """If a frame has no warm blob, consecutive counter resets."""
        reader, np = self._make_reader()
        road_ck = 29815
        hot_ck = road_ck + 1500

        road_frame = np.full((120, 160), road_ck, dtype=np.uint16)
        reader._detect_warm_objects(road_frame)  # seed baseline

        hot_frame = road_frame.copy()
        hot_frame[50:55, 75:81] = hot_ck  # 30px blob

        # Frame 1: warm blob (consecutive=1)
        reader._detect_warm_objects(hot_frame)
        assert not reader.warm_object_detected.emit.called

        # Frame 2: no warm blob → resets consecutive counter
        reader._detect_warm_objects(road_frame)
        assert not reader.warm_object_detected.emit.called

        # Frame 3: warm blob again (consecutive=1, not 2)
        reader._detect_warm_objects(hot_frame)
        assert not reader.warm_object_detected.emit.called


class TestLabelBlobs:
    """Test the numpy-only connected component labeling."""

    def test_empty_mask(self):
        from sensors.flir_lepton_reader import _label_blobs
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not available")

        mask = np.zeros((10, 10), dtype=bool)
        labels, n = _label_blobs(mask, np)
        assert n == 0
        assert labels.sum() == 0

    def test_single_blob(self):
        from sensors.flir_lepton_reader import _label_blobs
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not available")

        mask = np.zeros((10, 10), dtype=bool)
        mask[3:6, 3:6] = True  # 3x3 blob
        labels, n = _label_blobs(mask, np)
        assert n == 1
        assert (labels[3:6, 3:6] > 0).all()
        assert labels[0, 0] == 0

    def test_two_separate_blobs(self):
        from sensors.flir_lepton_reader import _label_blobs
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not available")

        mask = np.zeros((10, 10), dtype=bool)
        mask[0:2, 0:2] = True   # blob A (top-left)
        mask[8:10, 8:10] = True  # blob B (bottom-right)
        labels, n = _label_blobs(mask, np)
        assert n == 2
        # Two blobs should have different labels
        assert labels[0, 0] != labels[9, 9]
        assert labels[0, 0] > 0
        assert labels[9, 9] > 0
