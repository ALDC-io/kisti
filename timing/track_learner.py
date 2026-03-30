"""GPS trace learning — auto-detect track layout from driving.

Records GPS positions and detects loop closure (return to starting point).
On closure, auto-generates a TrackDefinition with start/finish line and
sector boundaries, ready for TrackDatabase.save_track().

Pure Python — no Qt dependency.  Follows the same pattern as LapTimer.
"""

from __future__ import annotations

import bisect
import logging
import uuid
from typing import Optional

from timing.geo import (
    bearing,
    cumulative_distance,
    haversine_distance,
    perpendicular_line,
)
from timing.track_db import SectorDefinition, StartFinishLine, TrackDefinition

log = logging.getLogger("kisti.timing.track_learner")


class TrackLearner:
    """Records a GPS trace and detects loop closure to auto-generate a track.

    Usage::

        learner = TrackLearner()
        for lat, lon in gps_stream:
            if learner.update(lat, lon):
                track, sectors = learner.result()
                break
    """

    # Minimum movement between consecutive points (filters stationary noise)
    _MIN_MOVE_M: float = 1.0

    # Margin added to max-distance-from-center for recognition radius
    _RADIUS_MARGIN_M: float = 200.0

    def __init__(
        self,
        closure_threshold_m: float = 50.0,
        min_trace_distance_m: float = 500.0,
        num_sectors: int = 3,
        half_width_m: float = 15.0,
    ) -> None:
        self._closure_threshold = closure_threshold_m
        self._min_trace_dist = min_trace_distance_m
        self._num_sectors = max(1, num_sectors)
        self._half_width = half_width_m
        self._reset_state()

    # ── Public API ────────────────────────────────────────────────────

    def update(self, lat: float, lon: float) -> bool:
        """Feed a GPS position.  Returns True if loop closure detected."""
        if self._complete:
            return False

        # First point — record as origin
        if not self._trace:
            self._origin_lat = lat
            self._origin_lon = lon
            self._trace.append((lat, lon))
            return False

        # Filter stationary noise
        prev_lat, prev_lon = self._trace[-1]
        move = haversine_distance(prev_lat, prev_lon, lat, lon)
        if move < self._MIN_MOVE_M:
            return False

        # Record point and accumulate distance
        self._trace.append((lat, lon))
        self._cumulative_dist += move

        # Check for loop closure (only after minimum distance)
        if self._cumulative_dist < self._min_trace_dist:
            return False

        dist_to_origin = haversine_distance(lat, lon, self._origin_lat, self._origin_lon)
        if dist_to_origin <= self._closure_threshold:
            self._complete = True
            self._generate_track()
            log.info(
                "Loop closure detected: %.0fm trace, %.0fm from origin",
                self._cumulative_dist, dist_to_origin,
            )
            return True

        return False

    @property
    def is_complete(self) -> bool:
        """True after loop closure has been detected."""
        return self._complete

    @property
    def total_distance(self) -> float:
        """Cumulative distance of recorded trace in meters."""
        return self._cumulative_dist

    @property
    def point_count(self) -> int:
        """Number of GPS positions recorded so far."""
        return len(self._trace)

    def result(self) -> tuple[TrackDefinition, list[SectorDefinition]]:
        """Return the learned track + sectors.

        Raises RuntimeError if loop closure has not yet been detected.
        """
        if not self._complete:
            raise RuntimeError("Loop closure not yet detected")
        return (self._track, self._sectors)

    def reset(self) -> None:
        """Clear all recorded data.  Ready for reuse."""
        self._reset_state()

    # ── Internal ──────────────────────────────────────────────────────

    def _reset_state(self) -> None:
        self._trace: list[tuple[float, float]] = []
        self._cumulative_dist: float = 0.0
        self._complete: bool = False
        self._origin_lat: float = 0.0
        self._origin_lon: float = 0.0
        self._track: Optional[TrackDefinition] = None
        self._sectors: list[SectorDefinition] = []

    def _generate_track(self) -> None:
        """Build TrackDefinition + SectorDefinitions from the recorded trace."""
        track_id = str(uuid.uuid4())

        # ── Start/finish line ─────────────────────────────────────
        # Use the heading at the closure point (last few points)
        closure_lat, closure_lon = self._trace[-1]
        sf_heading = self._smoothed_bearing(len(self._trace) - 1)
        (sf_lat1, sf_lon1), (sf_lat2, sf_lon2) = perpendicular_line(
            closure_lat, closure_lon, sf_heading, self._half_width,
        )
        start_finish = StartFinishLine(sf_lat1, sf_lon1, sf_lat2, sf_lon2)

        # ── Track center (centroid) ───────────────────────────────
        n = len(self._trace)
        center_lat = sum(p[0] for p in self._trace) / n
        center_lon = sum(p[1] for p in self._trace) / n

        # ── Track radius ──────────────────────────────────────────
        max_dist = max(
            haversine_distance(center_lat, center_lon, p[0], p[1])
            for p in self._trace
        )
        radius_m = max_dist + self._RADIUS_MARGIN_M

        # ── Sector boundaries ─────────────────────────────────────
        cum_dists = cumulative_distance(self._trace)
        total = cum_dists[-1]
        sectors: list[SectorDefinition] = []

        for i in range(self._num_sectors):
            # Place sector lines at equal-distance fractions
            frac = (i + 1) / (self._num_sectors + 1)
            target_dist = total * frac

            # Find the trace index at this distance (binary search)
            idx = bisect.bisect_right(cum_dists, target_dist) - 1
            idx = max(1, min(idx, n - 2))  # clamp to valid range

            # Interpolate position
            d0 = cum_dists[idx]
            d1 = cum_dists[idx + 1]
            seg_frac = (target_dist - d0) / (d1 - d0) if d1 > d0 else 0.0
            lat0, lon0 = self._trace[idx]
            lat1, lon1 = self._trace[idx + 1]
            sec_lat = lat0 + seg_frac * (lat1 - lat0)
            sec_lon = lon0 + seg_frac * (lon1 - lon0)

            # Heading at sector point
            sec_heading = self._smoothed_bearing(idx)

            # Generate perpendicular line
            (s_lat1, s_lon1), (s_lat2, s_lon2) = perpendicular_line(
                sec_lat, sec_lon, sec_heading, self._half_width,
            )

            sectors.append(SectorDefinition(
                sector_id=str(uuid.uuid4()),
                track_id=track_id,
                sector_index=i,
                line=StartFinishLine(s_lat1, s_lon1, s_lat2, s_lon2),
                name=f"Sector {i + 1}",
            ))

        # ── Build TrackDefinition ─────────────────────────────────
        self._track = TrackDefinition(
            track_id=track_id,
            name=f"Track at {center_lat:.4f}, {center_lon:.4f}",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_m=radius_m,
            track_type="circuit",
            start_finish=start_finish,
            length_m=self._cumulative_dist,
            source="learned",
        )
        self._sectors = sectors

    def _smoothed_bearing(self, idx: int) -> float:
        """Compute bearing at trace index using a 5-point window for stability."""
        n = len(self._trace)
        # Look back and forward up to 2 points
        i0 = max(0, idx - 2)
        i1 = min(n - 1, idx + 2)
        # Ensure we have at least 2 distinct points
        if i0 == i1:
            i0 = max(0, idx - 1)
        lat0, lon0 = self._trace[i0]
        lat1, lon1 = self._trace[i1]
        return bearing(lat0, lon0, lat1, lon1)
