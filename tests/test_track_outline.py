"""Tests for timing/track_outline.py — GPS normalization, RDP, and cache I/O."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from timing.track_outline import (
    normalize_outline,
    downsample_rdp,
    save_outline,
    load_outline,
    import_ztracks_outline,
    _rdp,
    _perp_distance,
)


# ---------------------------------------------------------------------------
# _perp_distance
# ---------------------------------------------------------------------------

class TestPerpDistance:
    def test_point_on_line_is_zero(self):
        # Point exactly on the line from (0,0) to (1,0)
        assert _perp_distance((0.5, 0.0), (0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)

    def test_point_perpendicular(self):
        # (0.5, 1.0) is 1.0 unit above the line y=0
        assert _perp_distance((0.5, 1.0), (0.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)

    def test_degenerate_line(self):
        # start == end → returns point-to-point distance
        dist = _perp_distance((1.0, 0.0), (0.0, 0.0), (0.0, 0.0))
        assert dist == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# normalize_outline
# ---------------------------------------------------------------------------

class TestNormalizeOutline:
    def test_output_in_01_range(self):
        # Simple rectangle of GPS points
        pts = [(49.12, -122.32), (49.13, -122.32), (49.13, -122.33), (49.12, -122.33)]
        result = normalize_outline(pts)
        for x, y in result:
            assert 0.0 <= x <= 1.0, f"x={x} out of range"
            assert 0.0 <= y <= 1.0, f"y={y} out of range"

    def test_same_point_count(self):
        pts = [(49.127 + i * 0.001, -122.327) for i in range(10)]
        result = normalize_outline(pts)
        assert len(result) == len(pts)

    def test_returns_empty_for_single_point(self):
        assert normalize_outline([(49.127, -122.327)]) == []

    def test_returns_empty_for_no_points(self):
        assert normalize_outline([]) == []

    def test_northward_trace_has_decreasing_y(self):
        # Going north = smaller y (screen top is north)
        pts = [(49.120, -122.327), (49.125, -122.327), (49.130, -122.327)]
        result = normalize_outline(pts)
        # y values should decrease as we go north
        assert result[0][1] > result[1][1] > result[2][1]

    def test_eastward_trace_has_increasing_x(self):
        # Going east = larger x
        pts = [(49.127, -122.330), (49.127, -122.327), (49.127, -122.324)]
        result = normalize_outline(pts)
        assert result[0][0] < result[1][0] < result[2][0]

    def test_margin_applied(self):
        # Output should have margin (not exactly 0 or 1 at extremes)
        pts = [(49.127, -122.327), (49.128, -122.328), (49.129, -122.329)]
        result = normalize_outline(pts)
        xs = [p[0] for p in result]
        ys = [p[1] for p in result]
        assert min(xs) > 0.0
        assert max(xs) < 1.0
        assert min(ys) > 0.0
        assert max(ys) < 1.0


# ---------------------------------------------------------------------------
# downsample_rdp
# ---------------------------------------------------------------------------

class TestDownsampleRdp:
    def test_preserves_endpoints(self):
        pts = [(float(i) / 100, float(i) / 100) for i in range(200)]
        result = downsample_rdp(pts, epsilon=0.005)
        assert result[0] == pts[0]
        assert result[-1] == pts[-1]

    def test_fewer_points_than_input(self):
        # A straight line — all intermediate points should be removed
        pts = [(float(i) / 100, 0.5) for i in range(100)]
        result = downsample_rdp(pts, epsilon=0.001)
        assert len(result) < len(pts)

    def test_respects_max_points(self):
        pts = [(math.sin(i / 10), math.cos(i / 10)) for i in range(500)]
        result = downsample_rdp(pts, epsilon=0.001, max_points=80)
        assert len(result) <= 80

    def test_two_points_unchanged(self):
        pts = [(0.0, 0.0), (1.0, 1.0)]
        result = downsample_rdp(pts)
        assert result == pts

    def test_curved_path_retains_shape(self):
        # A quarter-circle — should retain more points than a straight line
        pts = [(math.cos(i * math.pi / 200), math.sin(i * math.pi / 200)) for i in range(101)]
        straight = [(float(i) / 100, 0.0) for i in range(101)]
        curve_result = downsample_rdp(pts, epsilon=0.005)
        straight_result = downsample_rdp(straight, epsilon=0.005)
        assert len(curve_result) > len(straight_result)


# ---------------------------------------------------------------------------
# save_outline / load_outline
# ---------------------------------------------------------------------------

class TestSaveLoadOutline:
    def test_roundtrip(self, tmp_path):
        track_id = "test-track-id-001"
        outline = [(0.1, 0.2), (0.3, 0.4), (0.5, 0.6)]
        save_outline(track_id, outline, tmp_path)
        loaded = load_outline(track_id, tmp_path)
        assert loaded is not None
        assert len(loaded) == len(outline)
        for (ox, oy), (lx, ly) in zip(outline, loaded):
            assert abs(ox - lx) < 1e-9
            assert abs(oy - ly) < 1e-9

    def test_save_creates_json_file(self, tmp_path):
        save_outline("abc-123", [(0.1, 0.2)], tmp_path)
        assert (tmp_path / "abc-123.json").exists()

    def test_load_missing_returns_none(self, tmp_path):
        result = load_outline("nonexistent-id", tmp_path)
        assert result is None

    def test_load_corrupt_returns_none(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("not valid json{{{")
        result = load_outline("broken", tmp_path)
        assert result is None

    def test_save_creates_dir_if_missing(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        save_outline("test-id", [(0.5, 0.5)], nested)
        assert (nested / "test-id.json").exists()

    def test_json_format_is_list_of_pairs(self, tmp_path):
        outline = [(0.1, 0.9), (0.5, 0.5)]
        save_outline("fmt-test", outline, tmp_path)
        raw = json.loads((tmp_path / "fmt-test.json").read_text())
        assert isinstance(raw, list)
        assert all(len(item) == 2 for item in raw)


# ---------------------------------------------------------------------------
# import_ztracks_outline (integration — requires synthetic .ztracks)
# ---------------------------------------------------------------------------

class TestImportZtracksOutline:
    def test_import_synthetic_ztracks(self, tmp_path):
        import io
        import struct
        import zipfile

        # Build a tiny .ztracks with a triangle of GPS points
        pts_raw = b''
        coords = [(49.127, -122.327), (49.130, -122.330), (49.125, -122.335)]
        for lat, lon in coords:
            pts_raw += struct.pack('<iii', int(lat * 1e7), int(lon * 1e7), 0)

        tkk = b'<hPtkk' + b'Test Circuit\x00' + b'<hVnfo' + b'Testville\x00' + b'<hpts' + pts_raw

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("track.tkk", tkk)
        ztracks_path = tmp_path / "test.ztracks"
        ztracks_path.write_bytes(buf.getvalue())

        outlines_dir = tmp_path / "outlines"
        outline = import_ztracks_outline(ztracks_path, "test-track-id", outlines_dir)

        assert isinstance(outline, list)
        assert len(outline) >= 2
        for x, y in outline:
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0

    def test_import_caches_to_disk(self, tmp_path):
        import io
        import struct
        import zipfile

        pts_raw = b''
        for i in range(5):
            pts_raw += struct.pack('<iii', int((49.127 + i * 0.001) * 1e7),
                                   int((-122.327 - i * 0.001) * 1e7), 0)

        tkk = b'<hPtkk' + b'Cache Test\x00' + b'<hpts' + pts_raw
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("t.tkk", tkk)
        ztracks_path = tmp_path / "cache_test.ztracks"
        ztracks_path.write_bytes(buf.getvalue())

        outlines_dir = tmp_path / "outlines"
        import_ztracks_outline(ztracks_path, "cache-id", outlines_dir)

        assert (outlines_dir / "cache-id.json").exists()

    def test_import_bad_file_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.ztracks"
        bad.write_bytes(b"garbage data")
        result = import_ztracks_outline(bad, "any-id", tmp_path / "out")
        assert result == []
