"""Unit tests for GPS geometry primitives — timing/geo.py.

Tests cover:
  - haversine_distance: known distances, zero distance, antipodal, equator/meridian
  - line_segment_crossing: crossing, miss, parallel, grazing, edge cases
  - interpolate_crossing_time: midpoint, boundary, weighted
  - perpendicular_line: cardinal headings, diagonal, symmetry
  - point_in_radius: inside, outside, on boundary
  - cumulative_distance: empty, single, straight line, known circuit
  - bearing: cardinal directions, diagonal, wrap-around
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timing.geo import (
    bearing,
    cumulative_distance,
    haversine_distance,
    interpolate_crossing_time,
    line_segment_crossing,
    perpendicular_line,
    point_in_radius,
)


# ── haversine_distance ──────────────────────────────────────────────

class TestHaversineDistance:
    def test_zero_distance(self):
        """Same point returns 0."""
        assert haversine_distance(36.5842, -121.7528, 36.5842, -121.7528) == 0.0

    def test_known_distance_laguna_seca_start_to_t1(self):
        """Laguna Seca start/finish to Turn 1 is roughly 350m."""
        d = haversine_distance(36.5842, -121.7528, 36.5862, -121.7498)
        assert 200 < d < 500

    def test_known_distance_sf_to_la(self):
        """San Francisco to Los Angeles ~559 km."""
        d = haversine_distance(37.7749, -122.4194, 34.0522, -118.2437)
        assert 540_000 < d < 580_000

    def test_known_distance_equator_one_degree(self):
        """One degree of longitude at equator ~111.32 km."""
        d = haversine_distance(0, 0, 0, 1)
        assert 111_000 < d < 112_000

    def test_known_distance_one_degree_lat(self):
        """One degree of latitude ~111.32 km."""
        d = haversine_distance(0, 0, 1, 0)
        assert 111_000 < d < 112_000

    def test_symmetry(self):
        """Distance A→B equals B→A."""
        d1 = haversine_distance(36.5842, -121.7528, 37.7749, -122.4194)
        d2 = haversine_distance(37.7749, -122.4194, 36.5842, -121.7528)
        assert d1 == pytest.approx(d2, rel=1e-10)

    def test_short_distance_meters(self):
        """Two points ~10m apart at mid latitudes."""
        # ~10m north at 45° latitude
        d = haversine_distance(45.0, -122.0, 45.0 + 10 / 111320, -122.0)
        assert 9 < d < 11

    def test_antipodal(self):
        """Antipodal points should be ~20,015 km (half circumference)."""
        d = haversine_distance(0, 0, 0, 180)
        assert 20_000_000 < d < 20_100_000


# ── line_segment_crossing ───────────────────────────────────────────

class TestLineSegmentCrossing:
    # Laguna Seca approximate start/finish line (perpendicular to track)
    # Line segment ~30m wide across the track
    SF_LAT1, SF_LON1 = 36.58430, -121.75290
    SF_LAT2, SF_LON2 = 36.58410, -121.75270

    def test_crossing_returns_fraction(self):
        """Vehicle path crossing a line returns a fraction 0-1."""
        # Drive south across a horizontal line
        frac = line_segment_crossing(
            0.001, 0.0,   # prev: north of line
            -0.001, 0.0,  # curr: south of line
            0.0, -0.001,  # line west
            0.0, 0.001,   # line east
        )
        assert frac is not None
        assert 0.0 <= frac <= 1.0

    def test_crossing_midpoint(self):
        """Symmetric crossing should return ~0.5 fraction."""
        frac = line_segment_crossing(
            0.001, 0.0,
            -0.001, 0.0,
            0.0, -0.001,
            0.0, 0.001,
        )
        assert frac == pytest.approx(0.5, abs=0.01)

    def test_no_crossing_parallel(self):
        """Parallel paths return None."""
        frac = line_segment_crossing(
            0.001, 0.0,
            0.001, 0.002,  # moving east, same latitude
            0.0, 0.0,
            0.0, 0.002,    # line also east-west
        )
        assert frac is None

    def test_no_crossing_miss(self):
        """Vehicle passes above the line segment."""
        frac = line_segment_crossing(
            0.002, -0.001,  # prev: north and west
            0.002, 0.001,   # curr: north and east (never crosses)
            0.0, -0.0005,
            0.0, 0.0005,
        )
        assert frac is None

    def test_no_crossing_short_segment(self):
        """Vehicle crosses the line's extension but not the segment itself."""
        frac = line_segment_crossing(
            0.001, 0.0,
            -0.001, 0.0,
            0.0, 0.005,     # line far to the east
            0.0, 0.010,     # doesn't reach the vehicle path
        )
        assert frac is None

    def test_crossing_at_start(self):
        """Crossing near the start of the vehicle path (fraction ~0)."""
        frac = line_segment_crossing(
            0.00001, 0.0,   # barely north
            -0.01, 0.0,     # far south
            0.0, -0.01,
            0.0, 0.01,
        )
        assert frac is not None
        assert frac < 0.01

    def test_crossing_at_end(self):
        """Crossing near the end of the vehicle path (fraction ~1)."""
        frac = line_segment_crossing(
            0.01, 0.0,      # far north
            -0.00001, 0.0,  # barely south
            0.0, -0.01,
            0.0, 0.01,
        )
        assert frac is not None
        assert frac > 0.99

    def test_crossing_diagonal(self):
        """Diagonal vehicle path crossing a diagonal line."""
        frac = line_segment_crossing(
            0.001, -0.001,   # NW
            -0.001, 0.001,   # SE
            -0.001, -0.001,  # SW
            0.001, 0.001,    # NE
        )
        assert frac is not None
        assert frac == pytest.approx(0.5, abs=0.01)

    def test_crossing_real_scale(self):
        """Realistic track-scale crossing at Laguna Seca lat/lon."""
        # Vehicle approaching from south, crossing northward
        prev_lat = self.SF_LAT1 - 0.0002
        prev_lon = (self.SF_LON1 + self.SF_LON2) / 2
        curr_lat = self.SF_LAT1 + 0.0002
        curr_lon = prev_lon
        frac = line_segment_crossing(
            prev_lat, prev_lon, curr_lat, curr_lon,
            self.SF_LAT1, self.SF_LON1, self.SF_LAT2, self.SF_LON2,
        )
        assert frac is not None


# ── interpolate_crossing_time ───────────────────────────────────────

class TestInterpolateCrossingTime:
    def test_midpoint(self):
        """Fraction 0.5 returns midpoint time."""
        t = interpolate_crossing_time(100.0, 200.0, 0.5)
        assert t == pytest.approx(150.0)

    def test_start(self):
        """Fraction 0.0 returns prev_ts."""
        t = interpolate_crossing_time(100.0, 200.0, 0.0)
        assert t == pytest.approx(100.0)

    def test_end(self):
        """Fraction 1.0 returns curr_ts."""
        t = interpolate_crossing_time(100.0, 200.0, 1.0)
        assert t == pytest.approx(200.0)

    def test_quarter(self):
        """Fraction 0.25 returns 25% of the way."""
        t = interpolate_crossing_time(0.0, 0.1, 0.25)
        assert t == pytest.approx(0.025)

    def test_high_precision_timestamps(self):
        """Works with high-precision float timestamps."""
        t = interpolate_crossing_time(1711900000.123, 1711900000.223, 0.73)
        expected = 1711900000.123 + 0.1 * 0.73
        assert t == pytest.approx(expected, rel=1e-9)


# ── perpendicular_line ──────────────────────────────────────────────

class TestPerpendicularLine:
    def test_north_heading(self):
        """Heading 0 (north): perpendicular line runs east-west."""
        (lat1, lon1), (lat2, lon2) = perpendicular_line(45.0, -122.0, 0.0, 15.0)
        # Lat should be ~same for both endpoints (east-west line)
        assert lat1 == pytest.approx(lat2, abs=1e-6)
        # Lon should differ (one east, one west)
        assert lon1 != pytest.approx(lon2, abs=1e-7)

    def test_east_heading(self):
        """Heading 90 (east): perpendicular line runs north-south."""
        (lat1, lon1), (lat2, lon2) = perpendicular_line(45.0, -122.0, 90.0, 15.0)
        # Lon should be ~same for both endpoints (north-south line)
        assert lon1 == pytest.approx(lon2, abs=1e-6)
        # Lat should differ
        assert lat1 != pytest.approx(lat2, abs=1e-7)

    def test_symmetry(self):
        """Endpoints are equidistant from center."""
        center_lat, center_lon = 45.0, -122.0
        (lat1, lon1), (lat2, lon2) = perpendicular_line(center_lat, center_lon, 45.0, 15.0)
        d1 = haversine_distance(center_lat, center_lon, lat1, lon1)
        d2 = haversine_distance(center_lat, center_lon, lat2, lon2)
        assert d1 == pytest.approx(d2, rel=0.01)

    def test_width(self):
        """Total line width is approximately 2 * half_width_m."""
        (lat1, lon1), (lat2, lon2) = perpendicular_line(45.0, -122.0, 0.0, 15.0)
        width = haversine_distance(lat1, lon1, lat2, lon2)
        assert width == pytest.approx(30.0, rel=0.02)

    def test_custom_width(self):
        """Custom half_width_m produces correct total width."""
        (lat1, lon1), (lat2, lon2) = perpendicular_line(45.0, -122.0, 0.0, 50.0)
        width = haversine_distance(lat1, lon1, lat2, lon2)
        assert width == pytest.approx(100.0, rel=0.02)


# ── point_in_radius ─────────────────────────────────────────────────

class TestPointInRadius:
    def test_same_point(self):
        """Point at center is inside any positive radius."""
        assert point_in_radius(45.0, -122.0, 45.0, -122.0, 1.0) is True

    def test_inside(self):
        """Point 500m away is inside 1000m radius."""
        # ~500m north
        lat = 45.0 + 500 / 111320
        assert point_in_radius(lat, -122.0, 45.0, -122.0, 1000.0) is True

    def test_outside(self):
        """Point 2000m away is outside 1000m radius."""
        lat = 45.0 + 2000 / 111320
        assert point_in_radius(lat, -122.0, 45.0, -122.0, 1000.0) is False

    def test_on_boundary(self):
        """Point exactly on boundary is inside (<=)."""
        # Approximately 1000m north
        lat = 45.0 + 1000 / 111320
        d = haversine_distance(lat, -122.0, 45.0, -122.0)
        assert point_in_radius(lat, -122.0, 45.0, -122.0, d) is True


# ── cumulative_distance ─────────────────────────────────────────────

class TestCumulativeDistance:
    def test_empty(self):
        """Empty trace returns empty list."""
        assert cumulative_distance([]) == []

    def test_single_point(self):
        """Single point returns [0.0]."""
        assert cumulative_distance([(45.0, -122.0)]) == [0.0]

    def test_two_points(self):
        """Two points returns [0, distance]."""
        trace = [(45.0, -122.0), (45.0 + 100 / 111320, -122.0)]
        dists = cumulative_distance(trace)
        assert len(dists) == 2
        assert dists[0] == 0.0
        assert dists[1] == pytest.approx(100.0, rel=0.01)

    def test_monotonic(self):
        """Cumulative distance is monotonically non-decreasing."""
        trace = [
            (45.0, -122.0),
            (45.001, -122.0),
            (45.001, -121.999),
            (45.002, -121.999),
        ]
        dists = cumulative_distance(trace)
        for i in range(1, len(dists)):
            assert dists[i] >= dists[i - 1]

    def test_straight_line_north(self):
        """Straight line north: total ≈ haversine of endpoints."""
        n = 10
        step = 100 / 111320  # 100m steps
        trace = [(45.0 + i * step, -122.0) for i in range(n)]
        dists = cumulative_distance(trace)
        total = haversine_distance(trace[0][0], trace[0][1], trace[-1][0], trace[-1][1])
        assert dists[-1] == pytest.approx(total, rel=0.001)

    def test_known_circuit_length(self):
        """A roughly 3.6 km loop should report ~3600m total distance."""
        # Generate a circular GPS trace (oval approximation)
        center_lat, center_lon = 36.5842, -121.7528
        radius_m = 573  # ~3600m circumference
        n_points = 100
        trace = []
        for i in range(n_points + 1):  # +1 to close the loop
            angle = 2 * math.pi * i / n_points
            dlat = (radius_m * math.cos(angle)) / 111320
            dlon = (radius_m * math.sin(angle)) / (111320 * math.cos(math.radians(center_lat)))
            trace.append((center_lat + dlat, center_lon + dlon))
        dists = cumulative_distance(trace)
        # Circumference = 2πr ≈ 3601m
        assert 3500 < dists[-1] < 3700


# ── bearing ─────────────────────────────────────────────────────────

class TestBearing:
    def test_north(self):
        """Due north bearing is ~0 degrees."""
        b = bearing(45.0, -122.0, 46.0, -122.0)
        assert b == pytest.approx(0.0, abs=0.5)

    def test_east(self):
        """Due east bearing is ~90 degrees."""
        b = bearing(45.0, -122.0, 45.0, -121.0)
        assert b == pytest.approx(90.0, abs=1.0)

    def test_south(self):
        """Due south bearing is ~180 degrees."""
        b = bearing(46.0, -122.0, 45.0, -122.0)
        assert b == pytest.approx(180.0, abs=0.5)

    def test_west(self):
        """Due west bearing is ~270 degrees."""
        b = bearing(45.0, -121.0, 45.0, -122.0)
        assert b == pytest.approx(270.0, abs=1.0)

    def test_range_0_360(self):
        """Bearing is always in [0, 360)."""
        b = bearing(45.0, -122.0, 44.0, -123.0)  # SW
        assert 0 <= b < 360
