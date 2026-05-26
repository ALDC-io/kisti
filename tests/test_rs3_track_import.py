"""Tests for tools.rs3_track_import — RS3 track import tool."""

from __future__ import annotations

import json
import math
import uuid

import pytest

from tools.rs3_track_import import (
    manual_entry,
    merge_to_seed,
    parse_csv,
    parse_gpx,
    trace_to_track,
)
from timing.geo import haversine_distance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loop_trace(
    center_lat: float = 49.3,
    center_lon: float = -122.8,
    radius_deg: float = 0.005,
    n_points: int = 100,
) -> list[tuple[float, float]]:
    """Generate a circular GPS trace for testing."""
    points = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        lat = center_lat + radius_deg * math.cos(angle)
        lon = center_lon + radius_deg * math.sin(angle)
        points.append((lat, lon))
    return points


_GPX_11 = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk><trkseg>
    <trkpt lat="49.300" lon="-122.800"/>
    <trkpt lat="49.301" lon="-122.801"/>
    <trkpt lat="49.302" lon="-122.802"/>
  </trkseg></trk>
</gpx>
"""

_GPX_BARE = """\
<?xml version="1.0"?>
<gpx>
  <trk><trkseg>
    <trkpt lat="36.584" lon="-121.753"/>
    <trkpt lat="36.585" lon="-121.754"/>
  </trkseg></trk>
</gpx>
"""

_GPX_WAYPOINTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="49.450" lon="-119.550"/>
  <wpt lat="49.451" lon="-119.551"/>
  <wpt lat="49.452" lon="-119.552"/>
</gpx>
"""

_GPX_EMPTY = """\
<?xml version="1.0"?>
<gpx></gpx>
"""


# ---------------------------------------------------------------------------
# GPX parsing
# ---------------------------------------------------------------------------


class TestParseGpx:
    def test_basic_gpx_with_namespace(self, tmp_path):
        f = tmp_path / "track.gpx"
        f.write_text(_GPX_11)
        points = parse_gpx(f)
        assert len(points) == 3
        assert points[0] == (49.3, -122.8)

    def test_gpx_bare_tags(self, tmp_path):
        f = tmp_path / "track.gpx"
        f.write_text(_GPX_BARE)
        points = parse_gpx(f)
        assert len(points) == 2
        assert points[0] == (36.584, -121.753)

    def test_gpx_waypoints_fallback(self, tmp_path):
        f = tmp_path / "track.gpx"
        f.write_text(_GPX_WAYPOINTS)
        points = parse_gpx(f)
        assert len(points) == 3
        assert points[0] == (49.45, -119.55)

    def test_empty_gpx_raises(self, tmp_path):
        f = tmp_path / "track.gpx"
        f.write_text(_GPX_EMPTY)
        with pytest.raises(ValueError, match="No GPS points"):
            parse_gpx(f)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestParseCsv:
    def test_basic_csv_with_header(self, tmp_path):
        f = tmp_path / "track.csv"
        f.write_text("lat,lon\n49.30,-122.80\n49.31,-122.81\n")
        points = parse_csv(f)
        assert len(points) == 2
        assert points[0] == (49.30, -122.80)

    def test_csv_no_header(self, tmp_path):
        f = tmp_path / "track.csv"
        f.write_text("49.30,-122.80\n49.31,-122.81\n")
        points = parse_csv(f)
        assert len(points) == 2

    def test_empty_csv_raises(self, tmp_path):
        f = tmp_path / "track.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="Empty CSV"):
            parse_csv(f)


# ---------------------------------------------------------------------------
# trace_to_track
# ---------------------------------------------------------------------------


class TestTraceToTrack:
    def test_center_is_centroid(self):
        trace = _make_loop_trace(center_lat=49.3, center_lon=-122.8)
        track = trace_to_track(trace, name="Test Track")
        # Centroid should be close to the center of the circle
        assert abs(track["center_lat"] - 49.3) < 0.001
        assert abs(track["center_lon"] - (-122.8)) < 0.001

    def test_radius_covers_all_points(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track")
        for lat, lon in trace:
            dist = haversine_distance(
                track["center_lat"], track["center_lon"], lat, lon
            )
            assert dist <= track["radius_m"], f"Point ({lat}, {lon}) outside radius"

    def test_length_is_positive(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track")
        assert track["length_m"] > 0

    def test_start_finish_exists(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track")
        sf = track["start_finish"]
        assert sf is not None
        assert all(k in sf for k in ("lat1", "lon1", "lat2", "lon2"))

    def test_default_3_sectors(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track")
        assert len(track["sectors"]) == 3

    def test_custom_sector_count(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track", num_sectors=5)
        assert len(track["sectors"]) == 5

    def test_sector_schema(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Test Track")
        for sector in track["sectors"]:
            assert all(k in sector for k in ("line_lat1", "line_lon1", "line_lat2", "line_lon2", "name"))

    def test_output_schema_matches_seed(self):
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Area 27", country="CA", region="BC")
        required_keys = {
            "track_id", "name", "center_lat", "center_lon", "radius_m",
            "track_type", "country", "region", "length_m", "start_finish", "sectors",
        }
        assert set(track.keys()) == required_keys
        assert track["name"] == "Area 27"
        assert track["country"] == "CA"
        assert track["track_type"] == "circuit"
        # track_id should be a valid UUID
        uuid.UUID(track["track_id"])

    def test_too_few_points_raises(self):
        trace = [(49.3, -122.8), (49.31, -122.81)]
        with pytest.raises(ValueError, match="at least 10"):
            trace_to_track(trace, name="Short")


# ---------------------------------------------------------------------------
# manual_entry
# ---------------------------------------------------------------------------


class TestManualEntry:
    def test_minimal_entry(self):
        track = manual_entry("Area 27", 49.45, -119.55)
        assert track["name"] == "Area 27"
        assert track["center_lat"] == 49.45
        assert track["center_lon"] == -119.55
        assert track["radius_m"] == 2000.0

    def test_no_sectors_no_sf(self):
        track = manual_entry("Area 27", 49.45, -119.55)
        assert track["sectors"] == []
        assert track["start_finish"] is None

    def test_custom_radius(self):
        track = manual_entry("PIR", 45.37, -122.26, radius_m=3000.0)
        assert track["radius_m"] == 3000.0


# ---------------------------------------------------------------------------
# merge_to_seed
# ---------------------------------------------------------------------------


class TestMergeToSeed:
    def test_merge_appends(self, tmp_path):
        seed = tmp_path / "tracks.json"
        seed.write_text(json.dumps([{"name": "Existing", "track_id": "aaa"}]))
        new_track = manual_entry("New Track", 49.0, -122.0)
        merge_to_seed(new_track, seed)
        data = json.loads(seed.read_text())
        assert len(data) == 2
        assert data[1]["name"] == "New Track"

    def test_merge_creates_file(self, tmp_path):
        seed = tmp_path / "new_seed.json"
        new_track = manual_entry("First Track", 49.0, -122.0)
        merge_to_seed(new_track, seed)
        data = json.loads(seed.read_text())
        assert len(data) == 1

    def test_duplicate_name_still_merges(self, tmp_path):
        seed = tmp_path / "tracks.json"
        seed.write_text(json.dumps([{"name": "Area 27", "track_id": "aaa"}]))
        new_track = manual_entry("Area 27", 49.45, -119.55)
        merge_to_seed(new_track, seed)
        data = json.loads(seed.read_text())
        assert len(data) == 2

    def test_roundtrip_through_seed_tracks(self, tmp_path):
        """Merged output loads cleanly through TrackDatabase.seed_tracks()."""
        import duckdb
        from timing.track_db import TrackDatabase

        # Generate a track from GPS trace
        trace = _make_loop_trace()
        track = trace_to_track(trace, name="Roundtrip Test", country="CA", region="BC")

        # Write to seed file
        seed = tmp_path / "tracks.json"
        seed.write_text(json.dumps([track], indent=2))

        # Import through the real seed_tracks path
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE tracks (
                track_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                center_lat DOUBLE, center_lon DOUBLE,
                radius_m DOUBLE DEFAULT 2000.0,
                track_type TEXT DEFAULT 'circuit',
                start_lat1 DOUBLE, start_lon1 DOUBLE,
                start_lat2 DOUBLE, start_lon2 DOUBLE,
                country TEXT, region TEXT, length_m DOUBLE,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE track_sectors (
                sector_id TEXT PRIMARY KEY, track_id TEXT,
                sector_index INTEGER,
                line_lat1 DOUBLE, line_lon1 DOUBLE,
                line_lat2 DOUBLE, line_lon2 DOUBLE,
                name TEXT
            )
        """)

        db = TrackDatabase(conn)
        count = db.seed_tracks(seed)
        assert count == 1

        # Verify track was imported correctly
        loaded = db.find_track(track["center_lat"], track["center_lon"])
        assert loaded is not None
        assert loaded.name == "Roundtrip Test"
        assert loaded.source == "seed"
        assert len(loaded.sectors) == 3
        conn.close()
