"""Tests for TrackLearner — GPS trace learning and track auto-generation.

Uses a synthetic rectangular loop trace with known geometry:
  - ~1600m total (4 sides of ~400m)
  - Loop closure returns to within 50m of origin
  - Deterministic sector placement at 25%/50%/75% of total distance

Test classes:
  - TestLoopDetection (6 tests)
  - TestTrackGeneration (7 tests)
  - TestTrackNaming (2 tests)
  - TestCustomSectors (2 tests)
  - TestResetAndReuse (3 tests)
  - TestEdgeCases (2 tests)
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from timing.geo import haversine_distance, point_in_radius
from timing.track_db import StartFinishLine, TrackDefinition, SectorDefinition
from timing.track_learner import TrackLearner


# ── Synthetic loop geometry ───────────────────────────────────────────

_BASE_LAT = 50.0    # Far from any seeded track
_BASE_LON = -100.0
_HALF = 0.0018       # ~200m per half-side (~400m per side, ~1600m total)

_SW = (_BASE_LAT - _HALF, _BASE_LON - _HALF)
_SE = (_BASE_LAT - _HALF, _BASE_LON + _HALF)
_NE = (_BASE_LAT + _HALF, _BASE_LON + _HALF)
_NW = (_BASE_LAT + _HALF, _BASE_LON - _HALF)


def _make_loop_trace(points_per_side: int = 20) -> list[tuple[float, float]]:
    """Generate a rectangular GPS trace that closes back to start.

    Clockwise: SW → SE → NE → NW → SW.
    Total distance ~1600m.
    """
    trace = []
    corners = [_SW, _SE, _NE, _NW, _SW]  # close the loop
    for i in range(len(corners) - 1):
        lat0, lon0 = corners[i]
        lat1, lon1 = corners[i + 1]
        for j in range(points_per_side):
            frac = j / points_per_side
            trace.append((
                lat0 + frac * (lat1 - lat0),
                lon0 + frac * (lon1 - lon0),
            ))
    # Add final closing point (back at SW)
    trace.append(_SW)
    return trace


def _make_partial_trace(points: int = 20) -> list[tuple[float, float]]:
    """Generate a short trace along the bottom edge only (~400m, no loop)."""
    trace = []
    lat0, lon0 = _SW
    lat1, lon1 = _SE
    for j in range(points):
        frac = j / (points - 1)
        trace.append((
            lat0 + frac * (lat1 - lat0),
            lon0 + frac * (lon1 - lon0),
        ))
    return trace


# ── TestLoopDetection ─────────────────────────────────────────────────

class TestLoopDetection:
    """Loop closure detection from GPS trace."""

    def test_detects_loop_closure(self):
        """Complete rectangular loop triggers closure."""
        learner = TrackLearner()
        trace = _make_loop_trace()

        closed = False
        for lat, lon in trace:
            if learner.update(lat, lon):
                closed = True
                break

        assert closed
        assert learner.is_complete

    def test_no_closure_before_min_distance(self):
        """Short loop (< 500m) does not trigger closure."""
        learner = TrackLearner(min_trace_distance_m=500.0)

        # Create a tiny loop (~100m)
        tiny_half = 0.00045  # ~50m per half-side, ~200m total
        tiny_corners = [
            (_BASE_LAT - tiny_half, _BASE_LON - tiny_half),
            (_BASE_LAT - tiny_half, _BASE_LON + tiny_half),
            (_BASE_LAT + tiny_half, _BASE_LON + tiny_half),
            (_BASE_LAT + tiny_half, _BASE_LON - tiny_half),
            (_BASE_LAT - tiny_half, _BASE_LON - tiny_half),
        ]
        for lat, lon in tiny_corners:
            assert not learner.update(lat, lon)

        assert not learner.is_complete

    def test_no_closure_when_far_from_start(self):
        """Partial trace (no return) does not trigger closure."""
        learner = TrackLearner()
        trace = _make_partial_trace()

        for lat, lon in trace:
            learner.update(lat, lon)

        assert not learner.is_complete

    def test_closure_threshold_configurable(self):
        """Closure threshold controls detection distance."""
        # Very tight threshold — loop that ends 30m from start won't close
        learner = TrackLearner(closure_threshold_m=10.0, min_trace_distance_m=100.0)
        trace = _make_loop_trace()
        # Offset the last point to be ~30m from origin
        trace[-1] = (_SW[0] + 0.0003, _SW[1])  # ~33m north of SW

        for lat, lon in trace:
            learner.update(lat, lon)

        assert not learner.is_complete

    def test_min_distance_configurable(self):
        """Higher min_trace_distance prevents premature detection."""
        learner = TrackLearner(min_trace_distance_m=5000.0)
        trace = _make_loop_trace()  # ~1600m

        for lat, lon in trace:
            learner.update(lat, lon)

        # 1600m < 5000m threshold → no closure even though loop is complete
        assert not learner.is_complete

    def test_stationary_points_ignored(self):
        """Same position repeated → only first recorded."""
        learner = TrackLearner()

        for _ in range(100):
            learner.update(_BASE_LAT, _BASE_LON)

        assert learner.point_count == 1
        assert learner.total_distance == 0.0


# ── TestTrackGeneration ───────────────────────────────────────────────

class TestTrackGeneration:
    """Auto-generated track definition from GPS trace."""

    @pytest.fixture
    def learned(self):
        """Complete a loop and return the TrackLearner."""
        learner = TrackLearner()
        trace = _make_loop_trace()
        for lat, lon in trace:
            learner.update(lat, lon)
        assert learner.is_complete
        return learner

    def test_result_returns_track_definition(self, learned):
        """result() returns a TrackDefinition with source='learned'."""
        track, sectors = learned.result()
        assert isinstance(track, TrackDefinition)
        assert track.source == "learned"

    def test_start_finish_line_generated(self, learned):
        """Track has a non-None start_finish line."""
        track, _ = learned.result()
        assert track.start_finish is not None
        sf = track.start_finish
        # S/F endpoints should be near the closure point (SW corner)
        mid_lat = (sf.lat1 + sf.lat2) / 2
        mid_lon = (sf.lon1 + sf.lon2) / 2
        dist = haversine_distance(mid_lat, mid_lon, _SW[0], _SW[1])
        assert dist < 60  # within 60m of closure point

    def test_start_finish_has_width(self, learned):
        """S/F line endpoints are separated by approximately 2 * half_width."""
        track, _ = learned.result()
        sf = track.start_finish
        width = haversine_distance(sf.lat1, sf.lon1, sf.lat2, sf.lon2)
        assert 20 < width < 40  # default half_width=15m → ~30m total

    def test_three_sectors_generated(self, learned):
        """Default 3 sectors are generated."""
        _, sectors = learned.result()
        assert len(sectors) == 3

    def test_sector_indices_sequential(self, learned):
        """Sector indices are 0, 1, 2."""
        _, sectors = learned.result()
        indices = [s.sector_index for s in sectors]
        assert indices == [0, 1, 2]

    def test_track_center_is_centroid(self, learned):
        """Center lat/lon is approximately the centroid of the trace."""
        track, _ = learned.result()
        # For a rectangle centered at (_BASE_LAT, _BASE_LON), centroid ≈ center
        assert abs(track.center_lat - _BASE_LAT) < 0.001
        assert abs(track.center_lon - _BASE_LON) < 0.001

    def test_track_radius_contains_all_points(self, learned):
        """Radius is large enough to contain all corners."""
        track, _ = learned.result()
        for corner in [_SW, _SE, _NE, _NW]:
            assert point_in_radius(
                corner[0], corner[1],
                track.center_lat, track.center_lon,
                track.radius_m,
            )


# ── TestTrackNaming ───────────────────────────────────────────────────

class TestTrackNaming:
    """Track naming and metadata."""

    def test_default_track_name(self):
        """Name matches format 'Track at {lat:.4f}, {lon:.4f}'."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        track, _ = learner.result()
        assert track.name.startswith("Track at ")
        assert "." in track.name  # has decimal coordinates

    def test_source_is_learned(self):
        """Track source is 'learned'."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        track, _ = learner.result()
        assert track.source == "learned"


# ── TestCustomSectors ─────────────────────────────────────────────────

class TestCustomSectors:
    """Configurable sector count."""

    def test_five_sectors(self):
        """num_sectors=5 produces 5 sector boundaries."""
        learner = TrackLearner(num_sectors=5)
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        _, sectors = learner.result()
        assert len(sectors) == 5

    def test_single_sector(self):
        """num_sectors=1 produces 1 sector boundary."""
        learner = TrackLearner(num_sectors=1)
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        _, sectors = learner.result()
        assert len(sectors) == 1


# ── TestResetAndReuse ─────────────────────────────────────────────────

class TestResetAndReuse:
    """Reset and reuse TrackLearner."""

    def test_reset_clears_state(self):
        """After closure, reset() clears everything."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        assert learner.is_complete

        learner.reset()

        assert not learner.is_complete
        assert learner.total_distance == 0.0
        assert learner.point_count == 0

    def test_reuse_after_reset(self):
        """After reset, a new loop can be learned."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        learner.reset()

        # Learn a second loop at a different location
        offset = 0.01
        for lat, lon in _make_loop_trace():
            learner.update(lat + offset, lon + offset)

        assert learner.is_complete
        track, _ = learner.result()
        assert abs(track.center_lat - (_BASE_LAT + offset)) < 0.001

    def test_result_raises_before_closure(self):
        """result() raises RuntimeError before loop closure."""
        learner = TrackLearner()
        learner.update(_BASE_LAT, _BASE_LON)

        with pytest.raises(RuntimeError, match="Loop closure not yet detected"):
            learner.result()


# ── TestEdgeCases ─────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases."""

    def test_update_after_complete_is_noop(self):
        """After closure, update() returns False and doesn't change state."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)
        assert learner.is_complete

        dist_before = learner.total_distance
        assert not learner.update(99.0, 99.0)
        assert learner.total_distance == dist_before

    def test_total_distance_accurate(self):
        """Total distance is approximately the known rectangle perimeter."""
        learner = TrackLearner()
        for lat, lon in _make_loop_trace():
            learner.update(lat, lon)

        # Rectangle ~400m per side = ~1600m (closure triggers before full perimeter)
        assert 1000 < learner.total_distance < 1800
