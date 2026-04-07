"""Tests for tools/ztracks_parser.py — AiM .ztracks binary format decoder."""

from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

from tools.ztracks_parser import (
    ZtracksResult,
    parse_ztracks,
    _extract_string,
    _extract_gps_points,
    _parse_points,
    _section_data,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic TKK binaries
# ---------------------------------------------------------------------------

def _make_tkk(name: str = "Test Track", city: str = "Testville",
               points: list[tuple[float, float, float]] | None = None) -> bytes:
    """Build a minimal .tkk binary with correct section format."""
    if points is None:
        points = [(49.127, -122.327, 10.0), (49.128, -122.328, 10.0), (49.129, -122.329, 10.0)]

    name_bytes = name.encode('utf-8') + b'\x00'
    city_bytes = city.encode('utf-8') + b'\x00'

    pts_bytes = b''
    for lat, lon, alt in points:
        pts_bytes += struct.pack('<iii',
                                 int(lat * 1e7),
                                 int(lon * 1e7),
                                 int(alt * 1e7))

    data = b'<hPtkk' + name_bytes
    data += b'<hVnfo' + city_bytes
    data += b'<hpts' + pts_bytes
    return data


def _make_ztracks(tkk_data: bytes, tkk_name: str = "track.tkk") -> bytes:
    """Wrap TKK binary in a ZIP archive (returned as bytes)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(tkk_name, tkk_data)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------

class TestSectionData:
    def test_extracts_between_tags(self):
        data = b'<hPtkk' + b'Hello\x00' + b'<hVnfo' + b'World\x00'
        result = _section_data(data, b'<hPtkk')
        assert result == b'Hello\x00'

    def test_returns_to_end_if_no_next_section(self):
        data = b'<hpts' + b'\x01\x02\x03'
        result = _section_data(data, b'<hpts')
        assert result == b'\x01\x02\x03'

    def test_missing_tag_returns_empty(self):
        assert _section_data(b'nothing here', b'<hPtkk') == b''


class TestParsePoints:
    def test_valid_mission_raceway_point(self):
        lat, lon, alt = 49.127, -122.327, 10.0
        raw = struct.pack('<iii', int(lat * 1e7), int(lon * 1e7), int(alt * 1e7))
        pts = _parse_points(raw)
        assert len(pts) == 1
        assert abs(pts[0][0] - lat) < 1e-6
        assert abs(pts[0][1] - lon) < 1e-6

    def test_filters_zero_zero(self):
        raw = struct.pack('<iii', 0, 0, 0)
        pts = _parse_points(raw)
        assert pts == []

    def test_filters_out_of_range_lat(self):
        raw = struct.pack('<iii', int(91.0 * 1e7), int(10.0 * 1e7), 0)
        pts = _parse_points(raw)
        assert pts == []

    def test_multiple_points(self):
        raw = b''
        coords = [(49.127, -122.327, 0.0), (49.128, -122.328, 0.0)]
        for lat, lon, alt in coords:
            raw += struct.pack('<iii', int(lat * 1e7), int(lon * 1e7), int(alt * 1e7))
        pts = _parse_points(raw)
        assert len(pts) == 2

    def test_partial_chunk_ignored(self):
        raw = struct.pack('<iii', int(49.127 * 1e7), int(-122.327 * 1e7), 0) + b'\x00\x00'
        pts = _parse_points(raw)
        assert len(pts) == 1  # partial tail ignored


class TestExtractString:
    def test_null_terminated(self):
        data = b'<hPtkk' + b'Mission Raceway\x00' + b'<hVnfo'
        assert _extract_string(data, b'<hPtkk') == 'Mission Raceway'

    def test_missing_section_returns_empty(self):
        assert _extract_string(b'no tags here', b'<hPtkk') == ''


class TestExtractGpsPoints:
    def test_extracts_from_hpts_section(self):
        lat, lon, alt = 49.127, -122.327, 10.0
        pt_bytes = struct.pack('<iii', int(lat * 1e7), int(lon * 1e7), int(alt * 1e7))
        data = b'<hPtkk' + b'Track\x00' + b'<hpts' + pt_bytes
        pts = _extract_gps_points(data)
        assert len(pts) == 1
        assert abs(pts[0][0] - lat) < 1e-5

    def test_no_hpts_returns_empty(self):
        data = b'<hPtkk' + b'Track\x00'
        pts = _extract_gps_points(data)
        assert pts == []


# ---------------------------------------------------------------------------
# Integration: parse a synthetic .ztracks ZIP
# ---------------------------------------------------------------------------

class TestParseZtracks:
    def test_parses_name_and_city(self, tmp_path):
        tkk = _make_tkk(name="Test Circuit", city="Testburg")
        zfile = tmp_path / "test.ztracks"
        zfile.write_bytes(_make_ztracks(tkk))

        result = parse_ztracks(zfile)
        assert result.name == "Test Circuit"
        assert result.city == "Testburg"

    def test_parses_gps_points(self, tmp_path):
        pts = [(49.127, -122.327, 5.0), (49.128, -122.328, 5.0), (49.129, -122.329, 5.0)]
        tkk = _make_tkk(points=pts)
        zfile = tmp_path / "test.ztracks"
        zfile.write_bytes(_make_ztracks(tkk))

        result = parse_ztracks(zfile)
        assert len(result.points) == 3
        assert abs(result.points[0][0] - 49.127) < 1e-5
        assert abs(result.points[0][1] - (-122.327)) < 1e-5

    def test_result_dataclass_has_correct_fields(self, tmp_path):
        zfile = tmp_path / "test.ztracks"
        zfile.write_bytes(_make_ztracks(_make_tkk()))
        result = parse_ztracks(zfile)
        assert isinstance(result, ZtracksResult)
        assert isinstance(result.name, str)
        assert isinstance(result.points, list)

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            parse_ztracks(Path("/nonexistent/path.ztracks"))

    def test_raises_on_bad_zip(self, tmp_path):
        bad = tmp_path / "bad.ztracks"
        bad.write_bytes(b"not a zip file")
        with pytest.raises(ValueError, match="valid .ztracks"):
            parse_ztracks(bad)

    def test_raises_on_zip_without_tkk(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("readme.txt", "no tkk here")
        zfile = tmp_path / "no_tkk.ztracks"
        zfile.write_bytes(buf.getvalue())
        with pytest.raises(ValueError, match="No .tkk"):
            parse_ztracks(zfile)

    def test_points_are_valid_coordinates(self, tmp_path):
        pts = [(49.12 + i * 0.001, -122.32 - i * 0.001, 10.0) for i in range(20)]
        zfile = tmp_path / "multi.ztracks"
        zfile.write_bytes(_make_ztracks(_make_tkk(points=pts)))
        result = parse_ztracks(zfile)
        for lat, lon, _ in result.points:
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180


# ---------------------------------------------------------------------------
# Optional: test against real Mission Raceway file (skip on CI)
# ---------------------------------------------------------------------------

MISSION_ZTRACKS = Path.home() / "tracks" / "mission_raceway_park.ztracks"


@pytest.mark.skipif(
    not MISSION_ZTRACKS.exists(),
    reason="Mission Raceway .ztracks not present on this machine",
)
class TestMissionRaceway:
    def test_parses_without_error(self):
        result = parse_ztracks(MISSION_ZTRACKS)
        assert result.name != ""
        assert len(result.points) >= 10

    def test_coordinates_near_mission_raceway(self):
        result = parse_ztracks(MISSION_ZTRACKS)
        lats = [p[0] for p in result.points]
        lons = [p[1] for p in result.points]
        # Mission Raceway Park is at ~49.127°N, -122.327°W
        assert 48.5 <= min(lats) <= 50.0, f"Latitude out of range: {min(lats)}"
        assert -123.5 <= min(lons) <= -121.0, f"Longitude out of range: {min(lons)}"
