"""Core lap/sector timing engine for KiSTI race analysis.

Pure Python — no Qt dependency.  Fully testable with synthetic GPS traces.

Consumes GPS updates at 10 Hz, detects start/finish and sector crossings
using the geometry primitives in ``timing.geo``, and produces TimingEvents
for the UI layer to render.

Supports:
  - Circuit timing (lap + sector splits)
  - Point-to-point timing (A → B)
  - Live delta-vs-reference (distance-indexed)
  - Predicted lap time
  - Theoretical best (best sector composition)
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from timing.geo import haversine_distance, interpolate_crossing_time, line_segment_crossing
from timing.track_db import SectorDefinition, StartFinishLine, TrackDefinition

log = logging.getLogger("kisti.timing.lap_timer")


# ── Data types ─────────────────────────────────────────────────────────

class TimingEventType(Enum):
    LAP_COMPLETE = auto()
    SECTOR_COMPLETE = auto()
    TRACK_DETECTED = auto()
    P2P_SEGMENT_COMPLETE = auto()


@dataclass
class TimingEvent:
    event_type: TimingEventType
    lap_number: int
    sector_index: int
    time_s: float
    delta_s: float
    split_times: list[float] = field(default_factory=list)
    theoretical_best_s: Optional[float] = None


@dataclass
class ReferenceLap:
    """Distance-indexed reference for live delta calculations."""

    distance_array: list[float]
    time_array: list[float]
    total_time: float
    sector_times: list[float]

    def time_at_distance(self, d: float) -> float:
        """Binary search + linear interpolation for reference time at distance *d*."""
        if not self.distance_array:
            return 0.0
        if d <= self.distance_array[0]:
            return self.time_array[0]
        if d >= self.distance_array[-1]:
            return self.time_array[-1]

        idx = bisect.bisect_right(self.distance_array, d) - 1
        # Interpolate between idx and idx+1
        d0 = self.distance_array[idx]
        d1 = self.distance_array[idx + 1]
        t0 = self.time_array[idx]
        t1 = self.time_array[idx + 1]
        if d1 == d0:
            return t0
        frac = (d - d0) / (d1 - d0)
        return t0 + frac * (t1 - t0)


# ── Completed-lap record (internal) ───────────────────────────────────

@dataclass
class _CompletedLap:
    lap_number: int
    total_time: float
    sector_times: list[float]
    distance_array: list[float]
    time_array: list[float]


# ── LapTimer ───────────────────────────────────────────────────────────

class LapTimer:
    """GPS-based lap/sector timer.

    Call :meth:`set_track` once to configure, then feed GPS updates via
    :meth:`update` at 10 Hz.  The method returns a (possibly empty) list
    of :class:`TimingEvent` objects for each crossing detected.
    """

    # Minimum distance between GPS updates to accept (filters stationary noise)
    _MIN_MOVE_M: float = 0.5

    def __init__(self) -> None:
        self._track: Optional[TrackDefinition] = None
        self._sectors: list[SectorDefinition] = []

        # P2P mode
        self._p2p_mode: bool = False
        self._p2p_start_line: Optional[StartFinishLine] = None
        self._p2p_end_line: Optional[StartFinishLine] = None
        self._p2p_started: bool = False

        self._reset_timing_state()

    # ── Configuration ──────────────────────────────────────────────

    def set_track(self, track: TrackDefinition, sectors: list[SectorDefinition]) -> None:
        """Configure for a specific track and its sector boundaries."""
        self._track = track
        self._sectors = sorted(sectors, key=lambda s: s.sector_index)
        self._reset_timing_state()
        log.info("Track set: %s (%d sectors)", track.name, len(sectors))

    def set_p2p_mode(self, start_line: StartFinishLine, end_line: StartFinishLine) -> None:
        """Switch to point-to-point timing between two line segments."""
        self._p2p_mode = True
        self._p2p_start_line = start_line
        self._p2p_end_line = end_line
        self._p2p_started = False
        self._reset_timing_state()

    def set_circuit_mode(self) -> None:
        """Switch back to circuit (lap) timing."""
        self._p2p_mode = False
        self._p2p_start_line = None
        self._p2p_end_line = None
        self._p2p_started = False
        self._reset_timing_state()

    def set_reference_lap(self, lap_index: int) -> None:
        """Manually set which completed lap to use as delta reference (0-indexed)."""
        if 0 <= lap_index < len(self._completed_laps):
            lap = self._completed_laps[lap_index]
            self._reference = ReferenceLap(
                distance_array=list(lap.distance_array),
                time_array=list(lap.time_array),
                total_time=lap.total_time,
                sector_times=list(lap.sector_times),
            )
            log.info("Reference lap set to lap %d (%.3fs)", lap_index + 1, lap.total_time)

    def reset(self) -> None:
        """Clear all state — ready for a new session."""
        self._track = None
        self._sectors = []
        self._p2p_mode = False
        self._p2p_start_line = None
        self._p2p_end_line = None
        self._p2p_started = False
        self._reset_timing_state()

    # ── Core update loop ───────────────────────────────────────────

    def update(self, lat: float, lon: float, ts: float) -> list[TimingEvent]:
        """Process a GPS fix.  Returns list of TimingEvents (may be empty).

        Must be called at regular intervals (typically 10 Hz GPS rate).
        """
        # No track configured — nothing to do
        if self._track is None and not self._p2p_mode:
            return []

        # First fix — store position and return
        if self._prev_lat is None:
            self._prev_lat = lat
            self._prev_lon = lon
            self._prev_ts = ts
            return []

        events: list[TimingEvent] = []

        if self._p2p_mode:
            events = self._update_p2p(lat, lon, ts)
        else:
            events = self._update_circuit(lat, lon, ts)

        self._prev_lat = lat
        self._prev_lon = lon
        self._prev_ts = ts
        return events

    # ── Delta / prediction queries ─────────────────────────────────

    def get_delta(self) -> Optional[float]:
        """Current time delta vs reference lap (positive = slower)."""
        if self._reference is None or self._lap_start_ts is None:
            return None
        if self._prev_ts is None:
            return None
        current_elapsed = self._prev_ts - self._lap_start_ts
        current_dist = self._cumulative_distance
        ref_time = self._reference.time_at_distance(current_dist)
        return current_elapsed - ref_time

    def get_predicted_lap(self) -> Optional[float]:
        """Projected total lap time based on current pace + reference remaining."""
        if self._reference is None or self._lap_start_ts is None:
            return None
        if self._prev_ts is None:
            return None
        current_elapsed = self._prev_ts - self._lap_start_ts
        current_dist = self._cumulative_distance
        ref_time_at_dist = self._reference.time_at_distance(current_dist)
        ref_remaining = self._reference.total_time - ref_time_at_dist
        return current_elapsed + ref_remaining

    def get_theoretical_best(self) -> Optional[float]:
        """Sum of best sector times across all completed laps.

        Returns None if any sector has no completed data.
        """
        best = self.get_best_sector_times()
        if not best:
            return None
        if any(t is None for t in best):
            return None
        return sum(best)

    def get_best_sector_times(self) -> list[Optional[float]]:
        """Best time for each sector across all completed laps.

        Returns a list with one entry per sector.  An entry is None if
        that sector has never been completed.
        """
        if not self._sectors:
            return []
        n_sectors = len(self._sectors)
        best: list[Optional[float]] = [None] * n_sectors
        for lap in self._completed_laps:
            for i, st in enumerate(lap.sector_times):
                if i < n_sectors and (best[i] is None or st < best[i]):
                    best[i] = st
        return best

    def get_current_distance(self) -> float:
        """Cumulative distance in the current lap (meters)."""
        return self._cumulative_distance

    # ── Internal helpers ───────────────────────────────────────────

    def _reset_timing_state(self) -> None:
        """Reset all per-session timing state."""
        self._lap_number: int = 0
        self._sector_index: int = 0
        self._lap_start_ts: Optional[float] = None
        self._sector_start_ts: Optional[float] = None

        self._prev_lat: Optional[float] = None
        self._prev_lon: Optional[float] = None
        self._prev_ts: Optional[float] = None

        self._current_sector_times: list[float] = []
        self._completed_laps: list[_CompletedLap] = []
        self._reference: Optional[ReferenceLap] = None

        # Distance trace for current lap
        self._distance_trace: list[float] = [0.0]
        self._time_trace: list[float] = [0.0]
        self._cumulative_distance: float = 0.0

        # Track whether we have crossed start/finish at least once
        self._timing_active: bool = False

    def _update_circuit(self, lat: float, lon: float, ts: float) -> list[TimingEvent]:
        """Handle a GPS update in circuit (lap) mode."""
        events: list[TimingEvent] = []
        sf = self._track.start_finish
        if sf is None:
            return events

        # Check start/finish crossing
        sf_frac = line_segment_crossing(
            self._prev_lat, self._prev_lon,
            lat, lon,
            sf.lat1, sf.lon1, sf.lat2, sf.lon2,
        )

        if sf_frac is not None:
            crossing_ts = interpolate_crossing_time(self._prev_ts, ts, sf_frac)

            if not self._timing_active:
                # First crossing — start timing
                self._timing_active = True
                self._lap_number = 1
                self._sector_index = 0
                self._lap_start_ts = crossing_ts
                self._sector_start_ts = crossing_ts
                self._current_sector_times = []
                self._cumulative_distance = 0.0
                self._distance_trace = [0.0]
                self._time_trace = [0.0]
            else:
                # Lap complete
                lap_time = crossing_ts - self._lap_start_ts

                # Final sector time (from last sector boundary to finish)
                if self._sector_start_ts is not None:
                    final_sector = crossing_ts - self._sector_start_ts
                    self._current_sector_times.append(final_sector)

                # Build completed lap record
                completed = _CompletedLap(
                    lap_number=self._lap_number,
                    total_time=lap_time,
                    sector_times=list(self._current_sector_times),
                    distance_array=list(self._distance_trace),
                    time_array=list(self._time_trace),
                )
                self._completed_laps.append(completed)

                # Delta vs reference
                delta = 0.0
                if self._reference is not None:
                    delta = lap_time - self._reference.total_time

                # Auto-set reference: first lap, or best lap
                if self._reference is None:
                    self._reference = ReferenceLap(
                        distance_array=list(completed.distance_array),
                        time_array=list(completed.time_array),
                        total_time=completed.total_time,
                        sector_times=list(completed.sector_times),
                    )
                elif lap_time < self._reference.total_time:
                    self._reference = ReferenceLap(
                        distance_array=list(completed.distance_array),
                        time_array=list(completed.time_array),
                        total_time=completed.total_time,
                        sector_times=list(completed.sector_times),
                    )

                theoretical = self.get_theoretical_best()

                events.append(TimingEvent(
                    event_type=TimingEventType.LAP_COMPLETE,
                    lap_number=self._lap_number,
                    sector_index=len(self._current_sector_times) - 1,
                    time_s=lap_time,
                    delta_s=delta,
                    split_times=list(self._current_sector_times),
                    theoretical_best_s=theoretical,
                ))

                log.info(
                    "Lap %d complete: %.3fs (delta %.3fs)",
                    self._lap_number, lap_time, delta,
                )

                # Start next lap
                self._lap_number += 1
                self._sector_index = 0
                self._lap_start_ts = crossing_ts
                self._sector_start_ts = crossing_ts
                self._current_sector_times = []
                self._cumulative_distance = 0.0
                self._distance_trace = [0.0]
                self._time_trace = [0.0]
        else:
            # No start/finish crossing — update distance and check sectors
            if self._timing_active:
                move_d = haversine_distance(self._prev_lat, self._prev_lon, lat, lon)
                if move_d >= self._MIN_MOVE_M:
                    self._cumulative_distance += move_d
                    elapsed = ts - self._lap_start_ts
                    self._distance_trace.append(self._cumulative_distance)
                    self._time_trace.append(elapsed)

                # Check sector crossings
                events.extend(self._check_sectors(lat, lon, ts))

        return events

    def _check_sectors(self, lat: float, lon: float, ts: float) -> list[TimingEvent]:
        """Check for sector boundary crossings in order."""
        events: list[TimingEvent] = []
        if not self._sectors or not self._timing_active:
            return events

        # Only check the next expected sector
        if self._sector_index >= len(self._sectors):
            return events

        sector = self._sectors[self._sector_index]
        frac = line_segment_crossing(
            self._prev_lat, self._prev_lon,
            lat, lon,
            sector.line.lat1, sector.line.lon1,
            sector.line.lat2, sector.line.lon2,
        )

        if frac is not None:
            crossing_ts = interpolate_crossing_time(self._prev_ts, ts, frac)
            sector_time = crossing_ts - self._sector_start_ts
            self._current_sector_times.append(sector_time)

            events.append(TimingEvent(
                event_type=TimingEventType.SECTOR_COMPLETE,
                lap_number=self._lap_number,
                sector_index=self._sector_index,
                time_s=sector_time,
                delta_s=0.0,
                split_times=list(self._current_sector_times),
            ))

            log.debug(
                "Sector %d complete: %.3fs",
                self._sector_index, sector_time,
            )

            self._sector_index += 1
            self._sector_start_ts = crossing_ts

        return events

    def _update_p2p(self, lat: float, lon: float, ts: float) -> list[TimingEvent]:
        """Handle a GPS update in point-to-point mode."""
        events: list[TimingEvent] = []

        if not self._p2p_started:
            # Check for start line crossing
            if self._p2p_start_line is not None:
                frac = line_segment_crossing(
                    self._prev_lat, self._prev_lon,
                    lat, lon,
                    self._p2p_start_line.lat1, self._p2p_start_line.lon1,
                    self._p2p_start_line.lat2, self._p2p_start_line.lon2,
                )
                if frac is not None:
                    crossing_ts = interpolate_crossing_time(self._prev_ts, ts, frac)
                    self._p2p_started = True
                    self._timing_active = True
                    self._lap_number = 1
                    self._lap_start_ts = crossing_ts
                    self._sector_start_ts = crossing_ts
                    self._cumulative_distance = 0.0
                    self._distance_trace = [0.0]
                    self._time_trace = [0.0]
        else:
            # Accumulate distance
            move_d = haversine_distance(self._prev_lat, self._prev_lon, lat, lon)
            if move_d >= self._MIN_MOVE_M:
                self._cumulative_distance += move_d
                elapsed = ts - self._lap_start_ts
                self._distance_trace.append(self._cumulative_distance)
                self._time_trace.append(elapsed)

            # Check sector crossings
            events.extend(self._check_sectors(lat, lon, ts))

            # Check for end line crossing
            if self._p2p_end_line is not None:
                frac = line_segment_crossing(
                    self._prev_lat, self._prev_lon,
                    lat, lon,
                    self._p2p_end_line.lat1, self._p2p_end_line.lon1,
                    self._p2p_end_line.lat2, self._p2p_end_line.lon2,
                )
                if frac is not None:
                    crossing_ts = interpolate_crossing_time(self._prev_ts, ts, frac)
                    segment_time = crossing_ts - self._lap_start_ts

                    completed = _CompletedLap(
                        lap_number=self._lap_number,
                        total_time=segment_time,
                        sector_times=list(self._current_sector_times),
                        distance_array=list(self._distance_trace),
                        time_array=list(self._time_trace),
                    )
                    self._completed_laps.append(completed)

                    events.append(TimingEvent(
                        event_type=TimingEventType.P2P_SEGMENT_COMPLETE,
                        lap_number=self._lap_number,
                        sector_index=0,
                        time_s=segment_time,
                        delta_s=0.0,
                        split_times=list(self._current_sector_times),
                    ))

                    log.info("P2P segment complete: %.3fs", segment_time)

                    # Reset for next run
                    self._p2p_started = False
                    self._timing_active = False
                    self._lap_number += 1
                    self._sector_index = 0
                    self._lap_start_ts = None
                    self._sector_start_ts = None
                    self._current_sector_times = []
                    self._cumulative_distance = 0.0
                    self._distance_trace = [0.0]
                    self._time_trace = [0.0]

        return events
