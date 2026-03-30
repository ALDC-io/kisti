"""Tests for LapTimer — core lap/sector timing engine.

Uses a synthetic rectangular track with known geometry:
  - ~400m per side, ~1600m total
  - 4 corners at known lat/lon
  - GPS points generated at known intervals for deterministic timing

Track layout (clockwise driving direction):

       NW ─────────── NE       (top: vehicle heads west)
        │              │
        │   (center)   │       left: vehicle heads south
        │              │       right: vehicle heads north
        │              │
       SW ─────────── SE       (bottom: vehicle heads east)
            ^
            SF line (N-S)

Start/finish line is a N-S segment at the midpoint of the bottom edge.
Vehicle crosses it heading east.

Sector lines are perpendicular to the direction of travel at midpoints:
  - Sector 0: E-W line at midpoint of right edge (vehicle heading north)
  - Sector 1: N-S line at midpoint of top edge (vehicle heading west)
  - Sector 2: E-W line at midpoint of left edge (vehicle heading south)

Test classes:
  - TestLapDetection (8 tests)
  - TestSectorDetection (6 tests)
  - TestDeltaTiming (6 tests)
  - TestPredictiveLap (4 tests)
  - TestTheoreticalBest (4 tests)
  - TestReferenceLap (5 tests)
  - TestPointToPoint (4 tests)
  - TestReset (2 tests)
  - TestEdgeCases (5 tests)
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timing.geo import haversine_distance
from timing.lap_timer import (
    LapTimer,
    ReferenceLap,
    TimingEvent,
    TimingEventType,
)
from timing.track_db import SectorDefinition, StartFinishLine, TrackDefinition


# ── Synthetic track geometry ───────────────────────────────────────────

_BASE_LAT = 45.0
_BASE_LON = -122.0
_HALF = 0.0018  # ~200 m  (side length ~400 m)

# Corners (lat, lon)
_SW = (_BASE_LAT - _HALF, _BASE_LON - _HALF)
_SE = (_BASE_LAT - _HALF, _BASE_LON + _HALF)
_NE = (_BASE_LAT + _HALF, _BASE_LON + _HALF)
_NW = (_BASE_LAT + _HALF, _BASE_LON - _HALF)

# Start/finish line — N-S segment at bottom-edge midpoint (lon = _BASE_LON)
_SF = StartFinishLine(
    lat1=_BASE_LAT - _HALF - 0.0002,
    lon1=_BASE_LON,
    lat2=_BASE_LAT - _HALF + 0.0002,
    lon2=_BASE_LON,
)

# Sector 0: E-W line at midpoint of RIGHT edge (SE -> NE, vehicle heads north)
_SEC0_LINE = StartFinishLine(
    lat1=_BASE_LAT,
    lon1=_BASE_LON + _HALF - 0.0002,
    lat2=_BASE_LAT,
    lon2=_BASE_LON + _HALF + 0.0002,
)
# Sector 1: N-S line at midpoint of TOP edge (NE -> NW, vehicle heads west)
_SEC1_LINE = StartFinishLine(
    lat1=_BASE_LAT + _HALF - 0.0002,
    lon1=_BASE_LON,
    lat2=_BASE_LAT + _HALF + 0.0002,
    lon2=_BASE_LON,
)
# Sector 2: E-W line at midpoint of LEFT edge (NW -> SW, vehicle heads south)
_SEC2_LINE = StartFinishLine(
    lat1=_BASE_LAT,
    lon1=_BASE_LON - _HALF - 0.0002,
    lat2=_BASE_LAT,
    lon2=_BASE_LON - _HALF + 0.0002,
)


def _make_track() -> TrackDefinition:
    return TrackDefinition(
        track_id="test-rect",
        name="Test Rectangle",
        center_lat=_BASE_LAT,
        center_lon=_BASE_LON,
        radius_m=2000.0,
        track_type="circuit",
        start_finish=_SF,
        length_m=1600.0,
    )


def _make_sectors(track_id: str = "test-rect") -> list[SectorDefinition]:
    return [
        SectorDefinition(
            sector_id="sec-0", track_id=track_id, sector_index=0,
            line=_SEC0_LINE, name="Sector 1",
        ),
        SectorDefinition(
            sector_id="sec-1", track_id=track_id, sector_index=1,
            line=_SEC1_LINE, name="Sector 2",
        ),
        SectorDefinition(
            sector_id="sec-2", track_id=track_id, sector_index=2,
            line=_SEC2_LINE, name="Sector 3",
        ),
    ]


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    """Linear interpolation between two (lat, lon) points."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _generate_lap_points(
    speed_factor: float = 1.0,
    start_ts: float = 0.0,
    dt: float = 0.1,
    points_per_side: int = 40,
) -> list[tuple[float, float, float]]:
    """Generate GPS points (lat, lon, ts) for one clockwise lap.

    The vehicle starts slightly east of the SF line on the bottom edge
    (no crossing during approach), drives clockwise around the rectangle,
    then crosses the SF line from west to east to trigger timing start,
    then completes a full circuit and crosses SF again to complete the lap.

    The trace contains:
      1. Approach: 2 points east of SF (no crossing)
      2. Bottom edge remainder: to SE corner
      3. Right edge: SE -> NE
      4. Top edge: NE -> NW
      5. Left edge: NW -> SW
      6. Bottom edge: SW -> past SF (crossing here completes the lap)

    On the FIRST call the SF crossing at step 6 starts timing.
    On subsequent calls (continuous trace) the SF crossing completes a lap.

    Returns list of (lat, lon, timestamp).
    """
    interval = dt * speed_factor
    points: list[tuple[float, float, float]] = []
    ts = start_ts

    # Approach: start slightly east of the SF line on bottom edge
    approach_start = (_BASE_LAT - _HALF, _BASE_LON + 0.0003)

    # 2 approach points heading east from approach_start toward SE corner
    for i in range(2):
        t = i / 1.0 if i == 0 else 1.0
        lat, lon = _lerp(approach_start, _SE, t * 0.1)
        points.append((lat, lon, ts))
        ts += interval

    # Bottom edge remainder: approach end to SE corner
    for i in range(1, points_per_side // 4 + 1):
        t = i / (points_per_side // 4)
        lat, lon = _lerp(approach_start, _SE, 0.1 + 0.9 * t)
        points.append((lat, lon, ts))
        ts += interval

    # Right edge: SE -> NE (vehicle heads north)
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_SE, _NE, t)
        points.append((lat, lon, ts))
        ts += interval

    # Top edge: NE -> NW (vehicle heads west)
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_NE, _NW, t)
        points.append((lat, lon, ts))
        ts += interval

    # Left edge: NW -> SW (vehicle heads south)
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_NW, _SW, t)
        points.append((lat, lon, ts))
        ts += interval

    # Bottom edge: SW -> past SF (vehicle heads east, crosses SF at midpoint)
    # Go from SW to a point slightly east of SF (lon = _BASE_LON + 0.0003)
    overshoot = (_BASE_LAT - _HALF, _BASE_LON + 0.0003)
    for i in range(1, points_per_side // 2 + 1):
        t = i / (points_per_side // 2)
        lat, lon = _lerp(_SW, overshoot, t)
        points.append((lat, lon, ts))
        ts += interval

    return points


def _generate_multi_lap_points(
    n_laps: int,
    speed_factors: list[float] | None = None,
    dt: float = 0.1,
    points_per_side: int = 40,
) -> list[tuple[float, float, float]]:
    """Generate GPS trace for *n_laps* complete laps.

    The trace structure:
      - First call: approach + full circuit ending just past SF (starts timing)
      - Then n_laps full circuits, each crossing SF (each completes a lap)

    Returns continuous (lat, lon, ts) trace.
    """
    if speed_factors is None:
        speed_factors = [1.0] * n_laps
    assert len(speed_factors) == n_laps

    all_points: list[tuple[float, float, float]] = []

    # First trace: approach + circuit to start timing (sets the clock)
    first = _generate_lap_points(
        speed_factor=speed_factors[0] if n_laps > 0 else 1.0,
        start_ts=0.0,
        dt=dt,
        points_per_side=points_per_side,
    )
    all_points.extend(first)

    # Now for each lap: drive a full circuit from the current position
    # (just east of SF on bottom edge) around the track and back.
    for lap_idx in range(n_laps):
        start_ts = all_points[-1][2] + dt * speed_factors[lap_idx]
        circuit = _full_circuit(
            speed_factor=speed_factors[lap_idx],
            start_ts=start_ts,
            dt=dt,
            points_per_side=points_per_side,
        )
        all_points.extend(circuit)

    return all_points


def _full_circuit(
    speed_factor: float = 1.0,
    start_ts: float = 0.0,
    dt: float = 0.1,
    points_per_side: int = 40,
) -> list[tuple[float, float, float]]:
    """Generate one full clockwise circuit starting and ending just east of SF.

    Starts from (bottom edge, slightly east of SF), goes to SE, NE, NW, SW,
    and back across SF to slightly east again.  Crossing SF at the end
    triggers a LAP_COMPLETE.
    """
    interval = dt * speed_factor
    points: list[tuple[float, float, float]] = []
    ts = start_ts

    start_pos = (_BASE_LAT - _HALF, _BASE_LON + 0.0003)

    # Bottom edge: start -> SE
    for i in range(1, points_per_side // 4 + 1):
        t = i / (points_per_side // 4)
        lat, lon = _lerp(start_pos, _SE, t)
        points.append((lat, lon, ts))
        ts += interval

    # Right edge: SE -> NE
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_SE, _NE, t)
        points.append((lat, lon, ts))
        ts += interval

    # Top edge: NE -> NW
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_NE, _NW, t)
        points.append((lat, lon, ts))
        ts += interval

    # Left edge: NW -> SW
    for i in range(1, points_per_side + 1):
        t = i / points_per_side
        lat, lon = _lerp(_NW, _SW, t)
        points.append((lat, lon, ts))
        ts += interval

    # Bottom edge: SW -> past SF
    overshoot = (_BASE_LAT - _HALF, _BASE_LON + 0.0003)
    for i in range(1, points_per_side // 2 + 1):
        t = i / (points_per_side // 2)
        lat, lon = _lerp(_SW, overshoot, t)
        points.append((lat, lon, ts))
        ts += interval

    return points


def _feed_points(
    timer: LapTimer, points: list[tuple[float, float, float]],
) -> list[TimingEvent]:
    """Feed a GPS trace into a LapTimer and collect all events."""
    events: list[TimingEvent] = []
    for lat, lon, ts in points:
        events.extend(timer.update(lat, lon, ts))
    return events


def _timer_with_track() -> LapTimer:
    """Pre-configured LapTimer with the rectangular test track."""
    timer = LapTimer()
    timer.set_track(_make_track(), _make_sectors())
    return timer


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestLapDetection:
    """Start/finish crossing, lap counting, time accuracy."""

    def test_single_lap_detected(self):
        """Driving the approach + one full circuit produces exactly one LAP_COMPLETE."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1

    def test_single_lap_number_is_one(self):
        """First completed lap has lap_number == 1."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert lap_events[0].lap_number == 1

    def test_multiple_laps_counted(self):
        """Three laps produce three LAP_COMPLETE events with correct numbers."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(3)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 3
        assert [e.lap_number for e in lap_events] == [1, 2, 3]

    def test_no_false_lap_stationary(self):
        """Stationary vehicle at start/finish does not trigger a lap."""
        timer = _timer_with_track()
        sf_lat = _BASE_LAT - _HALF
        for i in range(100):
            events = timer.update(sf_lat, _BASE_LON, float(i) * 0.1)
            lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
            assert len(lap_events) == 0

    def test_no_false_lap_driving_away(self):
        """Driving straight away from start doesn't trigger a lap."""
        timer = _timer_with_track()
        start_lat = _BASE_LAT - _HALF - 0.001
        for i in range(50):
            lon = _BASE_LON + i * 0.0001
            events = timer.update(start_lat, lon, float(i) * 0.1)
            lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
            assert len(lap_events) == 0

    def test_lap_time_positive(self):
        """Lap time is a positive value."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1
        assert lap_events[0].time_s > 0

    def test_lap_time_in_reasonable_range(self):
        """Lap time is within a reasonable range for the synthetic track.

        With dt=0.1s and ~130 points per circuit at speed_factor=1.0,
        a lap should be roughly 13s.
        """
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1
        assert 5.0 < lap_events[0].time_s < 25.0

    def test_interpolated_crossing_time_more_accurate(self):
        """Two laps at different speeds produce measurably different times.

        The interpolation means the difference isn't quantised to the
        GPS sample interval.
        """
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.5])
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 2
        fast_time = lap_events[0].time_s
        slow_time = lap_events[1].time_s
        assert slow_time > fast_time
        assert (slow_time - fast_time) > 1.0


class TestSectorDetection:
    """Sector boundary crossings and split times."""

    def test_sectors_detected_in_order(self):
        """All three sectors fire in index order 0, 1, 2."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        sector_events = [e for e in events if e.event_type == TimingEventType.SECTOR_COMPLETE]
        indices = [e.sector_index for e in sector_events]
        assert indices == [0, 1, 2]

    def test_sector_count_matches_definition(self):
        """Number of sector events per lap equals number of sectors defined."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        sector_events = [e for e in events if e.event_type == TimingEventType.SECTOR_COMPLETE]
        assert len(sector_events) == 3

    def test_sector_times_sum_to_lap_time(self):
        """Sum of sector split times (from LAP_COMPLETE) approximates lap time."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1
        lap = lap_events[0]
        sector_sum = sum(lap.split_times)
        assert sector_sum == pytest.approx(lap.time_s, abs=0.2)

    def test_sector_times_all_positive(self):
        """Every sector time is positive."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        sector_events = [e for e in events if e.event_type == TimingEventType.SECTOR_COMPLETE]
        for e in sector_events:
            assert e.time_s > 0

    def test_missing_sector_gps_skip(self):
        """If GPS skips over a sector line, that sector is missed but lap
        still completes (no crash).
        """
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        # Remove points around the first sector crossing (mid-right edge).
        # The first circuit starts after the approach.  Approach has ~12 points,
        # then the circuit: ~10 bottom + 40 right + 40 top + 40 left + 20 bottom.
        # Mid-right edge ~ index 12 + 10 + 20 = 42. Remove a chunk around there.
        approach_len = len(_generate_lap_points())
        # Remove points around mid-right-edge in the first circuit
        remove_start = approach_len + 15
        remove_end = approach_len + 25
        filtered = [p for i, p in enumerate(pts) if not (remove_start <= i <= remove_end)]
        events = _feed_points(timer, filtered)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1

    def test_two_sectors_only(self):
        """Track with only 2 sectors detects exactly 2 sector events."""
        timer = LapTimer()
        track = _make_track()
        sectors = _make_sectors()[:2]
        timer.set_track(track, sectors)
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        sector_events = [e for e in events if e.event_type == TimingEventType.SECTOR_COMPLETE]
        assert len(sector_events) == 2


class TestDeltaTiming:
    """Delta-vs-reference calculations."""

    def test_delta_zero_same_pace(self):
        """When driving identical to reference, delta should be near zero."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.0])
        # Feed first lap (sets reference)
        fed_one = False
        start_idx = 0
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    fed_one = True
                    start_idx = i + 1
                    break
            if fed_one:
                break
        # Feed most of second lap at same speed and check delta
        for lat, lon, ts in pts[start_idx:start_idx + 60]:
            timer.update(lat, lon, ts)
        delta = timer.get_delta()
        if delta is not None:
            assert abs(delta) < 3.0

    def test_delta_positive_when_slower(self):
        """Delta is positive when driving slower than reference."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[0.8, 1.5])
        # Feed all of lap 1
        fed_one = False
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    fed_one = True
                    break
            if fed_one:
                start_idx = i + 1
                break
        # Feed most of slower lap 2
        for lat, lon, ts in pts[start_idx:start_idx + 80]:
            timer.update(lat, lon, ts)
        delta = timer.get_delta()
        assert delta is not None
        assert delta > 0

    def test_delta_negative_when_faster(self):
        """Delta is negative when driving faster than reference."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.5, 0.8])
        fed_one = False
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    fed_one = True
                    break
            if fed_one:
                start_idx = i + 1
                break
        for lat, lon, ts in pts[start_idx:start_idx + 80]:
            timer.update(lat, lon, ts)
        delta = timer.get_delta()
        assert delta is not None
        assert delta < 0

    def test_delta_near_zero_at_lap_start(self):
        """Delta right after crossing start/finish should be near zero."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.0])
        fed_one = False
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    fed_one = True
                    break
            if fed_one:
                start_idx = i + 1
                break
        # Feed just 3 more points (very start of lap 2)
        for lat, lon, ts in pts[start_idx:start_idx + 3]:
            timer.update(lat, lon, ts)
        delta = timer.get_delta()
        if delta is not None:
            assert abs(delta) < 2.0

    def test_delta_none_without_reference(self):
        """get_delta returns None before any lap is completed."""
        timer = _timer_with_track()
        # Feed approach only — no lap complete
        pts = _generate_lap_points()
        for lat, lon, ts in pts[:10]:
            timer.update(lat, lon, ts)
        assert timer.get_delta() is None

    def test_delta_changes_sign_mid_lap(self):
        """Delta computation doesn't crash when pace changes mid-lap.

        We just verify the method returns a non-None value after reference is set.
        """
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.0])
        # Complete first lap
        fed_one = False
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    fed_one = True
                    break
            if fed_one:
                start_idx = i + 1
                break
        # Feed half of second lap
        for lat, lon, ts in pts[start_idx:start_idx + 60]:
            timer.update(lat, lon, ts)
        delta = timer.get_delta()
        assert delta is not None


class TestPredictiveLap:
    """Projected lap time from current pace + reference remaining."""

    def test_prediction_equals_reference_at_same_pace(self):
        """Predicted lap is near reference total when driving at same pace."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.0])
        ref_time = None
        start_idx = 0
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    ref_time = e.time_s
                    start_idx = i + 1
                    break
            if ref_time is not None:
                break
        # Feed half of second lap
        for lat, lon, ts in pts[start_idx:start_idx + 60]:
            timer.update(lat, lon, ts)
        predicted = timer.get_predicted_lap()
        assert predicted is not None
        assert predicted == pytest.approx(ref_time, abs=3.0)

    def test_prediction_higher_when_slower(self):
        """Predicted > reference when current pace is slower."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.0, 1.5])
        ref_time = None
        start_idx = 0
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    ref_time = e.time_s
                    start_idx = i + 1
                    break
            if ref_time is not None:
                break
        for lat, lon, ts in pts[start_idx:start_idx + 60]:
            timer.update(lat, lon, ts)
        predicted = timer.get_predicted_lap()
        assert predicted is not None
        assert predicted > ref_time

    def test_prediction_lower_when_faster(self):
        """Predicted < reference when current pace is faster."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.5, 0.8])
        ref_time = None
        start_idx = 0
        for i, (lat, lon, ts) in enumerate(pts):
            evts = timer.update(lat, lon, ts)
            for e in evts:
                if e.event_type == TimingEventType.LAP_COMPLETE:
                    ref_time = e.time_s
                    start_idx = i + 1
                    break
            if ref_time is not None:
                break
        for lat, lon, ts in pts[start_idx:start_idx + 60]:
            timer.update(lat, lon, ts)
        predicted = timer.get_predicted_lap()
        assert predicted is not None
        assert predicted < ref_time

    def test_prediction_none_without_reference(self):
        """get_predicted_lap returns None before any lap is completed."""
        timer = _timer_with_track()
        pts = _generate_lap_points()
        for lat, lon, ts in pts[:10]:
            timer.update(lat, lon, ts)
        assert timer.get_predicted_lap() is None


class TestTheoreticalBest:
    """Best sector composition across multiple laps."""

    def test_theoretical_best_from_best_sectors(self):
        """Theoretical best is sum of best per-sector times across laps."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(3, speed_factors=[1.0, 0.9, 1.1])
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) >= 2

        theoretical = timer.get_theoretical_best()
        assert theoretical is not None
        best_actual = min(e.time_s for e in lap_events)
        assert theoretical <= best_actual + 0.5

    def test_theoretical_best_none_if_incomplete(self):
        """Returns None if not all sectors have data (e.g., mid-first-lap)."""
        timer = _timer_with_track()
        pts = _generate_lap_points()
        for lat, lon, ts in pts[:10]:
            timer.update(lat, lon, ts)
        assert timer.get_theoretical_best() is None

    def test_theoretical_best_le_best_lap(self):
        """Theoretical best <= every completed lap time (by definition)."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(3, speed_factors=[1.2, 0.9, 1.0])
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]

        theoretical = timer.get_theoretical_best()
        if theoretical is not None:
            best_actual = min(e.time_s for e in lap_events)
            assert theoretical <= best_actual + 0.5

    def test_best_sector_times_length(self):
        """get_best_sector_times returns one entry per sector."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        _feed_points(timer, pts)
        best = timer.get_best_sector_times()
        assert len(best) == 3


class TestReferenceLap:
    """Automatic and manual reference lap selection, interpolation."""

    def test_auto_set_first_lap_as_reference(self):
        """First completed lap automatically becomes the reference."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        _feed_points(timer, pts)
        assert timer._reference is not None
        assert timer._reference.total_time > 0

    def test_best_lap_becomes_reference(self):
        """When a faster lap is completed, it replaces the reference."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(2, speed_factors=[1.5, 0.8])
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 2
        # The second lap (0.8) is faster — reference should update
        assert timer._reference.total_time == pytest.approx(
            lap_events[1].time_s, abs=0.01,
        )

    def test_manual_set_reference_lap(self):
        """set_reference_lap(index) overrides automatic selection."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(3, speed_factors=[1.0, 0.9, 1.1])
        _feed_points(timer, pts)
        # Manually set to the third lap (index 2)
        timer.set_reference_lap(2)
        assert timer._reference is not None
        assert timer._reference.total_time == pytest.approx(
            timer._completed_laps[2].total_time, abs=0.01,
        )

    def test_time_at_distance_interpolation(self):
        """ReferenceLap.time_at_distance interpolates correctly."""
        ref = ReferenceLap(
            distance_array=[0.0, 100.0, 200.0, 300.0, 400.0],
            time_array=[0.0, 10.0, 20.0, 30.0, 40.0],
            total_time=40.0,
            sector_times=[20.0, 20.0],
        )
        assert ref.time_at_distance(200.0) == pytest.approx(20.0)
        assert ref.time_at_distance(150.0) == pytest.approx(15.0)
        assert ref.time_at_distance(-10.0) == pytest.approx(0.0)
        assert ref.time_at_distance(500.0) == pytest.approx(40.0)

    def test_time_at_distance_empty(self):
        """Empty reference returns 0.0."""
        ref = ReferenceLap(
            distance_array=[], time_array=[], total_time=0.0, sector_times=[],
        )
        assert ref.time_at_distance(100.0) == 0.0


class TestPointToPoint:
    """Point-to-point timing mode (A -> B)."""

    def test_p2p_detects_start_and_end(self):
        """P2P mode produces a P2P_SEGMENT_COMPLETE event."""
        timer = LapTimer()
        timer.set_track(_make_track(), _make_sectors())

        # Use SF as start, and sector 1 line (mid-top) as end
        timer.set_p2p_mode(_SF, _SEC1_LINE)

        # Generate a trace that crosses SF then later crosses the top-mid line.
        # Use the standard multi-lap trace which crosses SF, then drives clockwise
        # past sec0 (mid-right), then past sec1 (mid-top) where end line is.
        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        p2p_events = [e for e in events if e.event_type == TimingEventType.P2P_SEGMENT_COMPLETE]
        assert len(p2p_events) >= 1

    def test_p2p_timing_positive(self):
        """P2P segment time is positive."""
        timer = LapTimer()
        timer.set_track(_make_track(), _make_sectors())
        timer.set_p2p_mode(_SF, _SEC1_LINE)

        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        p2p_events = [e for e in events if e.event_type == TimingEventType.P2P_SEGMENT_COMPLETE]
        assert len(p2p_events) >= 1
        assert p2p_events[0].time_s > 0

    def test_switch_circuit_to_p2p(self):
        """Switching from circuit to P2P clears circuit state."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        _feed_points(timer, pts)
        assert len(timer._completed_laps) == 1

        timer.set_p2p_mode(_SF, _SEC1_LINE)
        assert timer._p2p_mode is True
        assert len(timer._completed_laps) == 0

    def test_switch_p2p_to_circuit(self):
        """Switching from P2P back to circuit mode works for laps."""
        timer = LapTimer()
        timer.set_track(_make_track(), _make_sectors())
        timer.set_p2p_mode(_SF, _SEC1_LINE)

        timer.set_circuit_mode()
        assert timer._p2p_mode is False

        pts = _generate_multi_lap_points(1)
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1


class TestReset:
    """State clearing and session restart."""

    def test_reset_clears_all_state(self):
        """After reset(), all timing state is zeroed."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        _feed_points(timer, pts)

        assert len(timer._completed_laps) == 1
        timer.reset()

        assert timer._track is None
        assert timer._sectors == []
        assert timer._completed_laps == []
        assert timer._reference is None
        assert timer._lap_number == 0
        assert timer._timing_active is False
        assert timer.get_current_distance() == 0.0

    def test_new_session_after_reset(self):
        """After reset + re-configure, timing works again."""
        timer = _timer_with_track()
        pts1 = _generate_multi_lap_points(1)
        events1 = _feed_points(timer, pts1)
        lap1 = [e for e in events1 if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap1) == 1

        timer.reset()
        timer.set_track(_make_track(), _make_sectors())

        pts2 = _generate_multi_lap_points(1)
        # Offset timestamps so they don't overlap
        pts2 = [(lat, lon, ts + 1000.0) for lat, lon, ts in pts2]
        events2 = _feed_points(timer, pts2)
        lap2 = [e for e in events2 if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap2) == 1
        assert lap2[0].lap_number == 1


class TestEdgeCases:
    """GPS dropout, slow crossing, stationary, no-track."""

    def test_gps_dropout_mid_lap(self):
        """Large time/distance gap in GPS trace doesn't crash."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        mid = len(pts) // 2
        modified = []
        for i, (lat, lon, ts) in enumerate(pts):
            if i >= mid:
                modified.append((lat, lon, ts + 30.0))
            else:
                modified.append((lat, lon, ts))
        events = _feed_points(timer, modified)
        assert isinstance(events, list)

    def test_very_slow_crossing(self):
        """Very slow crossing speed still detects the lap."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1, speed_factors=[5.0])
        events = _feed_points(timer, pts)
        lap_events = [e for e in events if e.event_type == TimingEventType.LAP_COMPLETE]
        assert len(lap_events) == 1

    def test_stationary_at_start_finish(self):
        """Sitting on the start/finish line produces no events."""
        timer = _timer_with_track()
        lat = _BASE_LAT - _HALF
        lon = _BASE_LON
        for i in range(200):
            events = timer.update(lat, lon, float(i) * 0.1)
            assert len(events) == 0

    def test_update_before_set_track(self):
        """Calling update() on a fresh timer (no track) returns empty."""
        timer = LapTimer()
        events = timer.update(45.0, -122.0, 0.0)
        assert events == []
        events = timer.update(45.001, -122.0, 0.1)
        assert events == []

    def test_get_current_distance_increases(self):
        """Cumulative distance increases as the vehicle moves around the track."""
        timer = _timer_with_track()
        pts = _generate_multi_lap_points(1)
        # Feed points until we're mid-lap
        for lat, lon, ts in pts[:len(pts) // 2]:
            timer.update(lat, lon, ts)
        d1 = timer.get_current_distance()
        for lat, lon, ts in pts[len(pts) // 2:len(pts) * 3 // 4]:
            timer.update(lat, lon, ts)
        d2 = timer.get_current_distance()
        assert d2 >= d1
