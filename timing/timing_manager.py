"""Qt integration for KiSTI race analysis timing.

Bridges the pure-Python LapTimer engine to the Qt event loop
by connecting to DiffStateBridge GPS updates and emitting
timing events as Qt signals.

Data flow:
    DiffStateBridge.state_changed → TimingManager._on_state_changed
        → LapTimer.update(lat, lon, ts)
        → TimingEvent → Qt signals + bridge.update_timing() + DuckDB
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from timing.lap_timer import LapTimer, TimingEvent, TimingEventType
from timing.track_db import TrackDatabase

log = logging.getLogger("kisti.timing.timing_manager")


class TimingManager(QObject):
    """Connects LapTimer to DiffStateBridge for real-time race timing.

    Create after bridge + db_store, call :meth:`start` to begin processing.
    Follows the same lifecycle pattern as SyncManager.
    """

    # Signals — payload is dict for flexibility
    lap_completed = Signal(object)       # {lap_number, time_s, delta_s, split_times, theoretical_best_s}
    sector_completed = Signal(object)    # {lap_number, sector_index, time_s, split_times}
    track_detected = Signal(str)         # track name
    p2p_completed = Signal(object)       # {segment_number, time_s}

    def __init__(
        self,
        bridge,           # DiffStateBridge
        db_store=None,    # DuckDBStore (optional, for recording laps)
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._db_store = db_store
        self._timer = LapTimer()
        self._track_db: Optional[TrackDatabase] = None
        self._track_detected = False
        self._session_id: Optional[str] = None
        self._active = False

        # Initialize TrackDatabase if DuckDB available
        if db_store is not None:
            try:
                self._track_db = TrackDatabase(db_store._conn)
            except Exception as exc:
                log.warning("TrackDatabase init failed: %s", exc)

        # Previous GPS for change detection
        self._prev_gps_lat: float = 0.0
        self._prev_gps_lon: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin processing GPS updates from the bridge."""
        self._active = True
        self._bridge.state_changed.connect(self._on_state_changed)
        log.info("TimingManager started")

    def stop(self) -> None:
        """Stop processing GPS updates."""
        self._active = False
        try:
            self._bridge.state_changed.disconnect(self._on_state_changed)
        except RuntimeError:
            pass  # Already disconnected
        log.info("TimingManager stopped")

    def set_session_id(self, session_id: Optional[str]) -> None:
        """Set current DuckDB session ID for lap recording."""
        self._session_id = session_id
        if session_id is None:
            # Session ended — reset timing for next session
            self._timer.reset()
            self._track_detected = False

    def get_session_summary(self) -> dict:
        """Build a summary dict for voice debrief on session end."""
        completed = self._timer._completed_laps
        if not completed:
            return {}

        best_lap = min(completed, key=lambda l: l.total_time)
        last_lap = completed[-1]
        theoretical = self._timer.get_theoretical_best()

        return {
            "total_laps": len(completed),
            "best_lap_number": best_lap.lap_number,
            "best_lap_time_s": best_lap.total_time,
            "last_lap_time_s": last_lap.total_time,
            "theoretical_best_s": theoretical,
            "track_name": self._timer._track.name if self._timer._track else "Unknown",
        }

    @property
    def lap_timer(self) -> LapTimer:
        """Direct access to the LapTimer for voice queries."""
        return self._timer

    @property
    def track_name(self) -> str:
        """Current detected track name, or empty string."""
        if self._timer._track is not None:
            return self._timer._track.name
        return ""

    # ── Internal ──────────────────────────────────────────────────────

    def _on_state_changed(self) -> None:
        """Process bridge state updates — extract GPS and feed LapTimer."""
        if not self._active:
            return

        snap = self._bridge.snapshot()
        lat = snap.gps_latitude
        lon = snap.gps_longitude

        # Skip if no GPS fix or position hasn't changed
        if lat == 0.0 and lon == 0.0:
            return
        if lat == self._prev_gps_lat and lon == self._prev_gps_lon:
            return

        self._prev_gps_lat = lat
        self._prev_gps_lon = lon

        # Auto-detect track on first GPS fix
        if not self._track_detected and self._track_db is not None:
            self._try_detect_track(lat, lon)

        # Feed LapTimer
        ts = time.monotonic()
        events = self._timer.update(lat, lon, ts)

        # Process events
        for event in events:
            self._handle_event(event)

        # Update bridge with current timing state
        self._update_bridge_timing()

    def _try_detect_track(self, lat: float, lon: float) -> None:
        """Attempt to auto-detect track from GPS position."""
        track = self._track_db.find_track(lat, lon)
        if track is None:
            return

        sectors = track.sectors
        self._timer.set_track(track, sectors)
        self._track_detected = True

        log.info("Track detected: %s (%d sectors)", track.name, len(sectors))
        self.track_detected.emit(track.name)

    def _handle_event(self, event: TimingEvent) -> None:
        """Emit Qt signals and record to DuckDB for a timing event."""
        if event.event_type == TimingEventType.LAP_COMPLETE:
            payload = {
                "lap_number": event.lap_number,
                "time_s": event.time_s,
                "delta_s": event.delta_s,
                "split_times": event.split_times,
                "theoretical_best_s": event.theoretical_best_s,
            }
            self.lap_completed.emit(payload)

            # Record to DuckDB
            if self._db_store and self._session_id and self._timer._track:
                try:
                    self._db_store.record_lap_time(
                        session_id=self._session_id,
                        track_id=self._timer._track.track_id,
                        lap_number=event.lap_number,
                        lap_time_s=event.time_s,
                        sector_times=event.split_times or None,
                        delta_vs_best=event.delta_s,
                        theoretical_best_s=event.theoretical_best_s,
                    )
                except Exception as exc:
                    log.warning("Failed to record lap: %s", exc)

        elif event.event_type == TimingEventType.SECTOR_COMPLETE:
            payload = {
                "lap_number": event.lap_number,
                "sector_index": event.sector_index,
                "time_s": event.time_s,
                "split_times": event.split_times,
            }
            self.sector_completed.emit(payload)

        elif event.event_type == TimingEventType.P2P_SEGMENT_COMPLETE:
            payload = {
                "segment_number": event.lap_number,
                "time_s": event.time_s,
            }
            self.p2p_completed.emit(payload)

    def _update_bridge_timing(self) -> None:
        """Push current timing state to the bridge.

        Uses blockSignals to prevent re-entrant state_changed emission —
        update_timing() would otherwise fire state_changed, re-triggering
        _on_state_changed and doubling signal traffic on every GPS tick.
        """
        delta = self._timer.get_delta()
        predicted = self._timer.get_predicted_lap()
        theoretical = self._timer.get_theoretical_best()

        # Current lap elapsed time
        current_lap_ms = 0
        if self._timer._lap_start_ts is not None and self._timer._prev_ts is not None:
            current_lap_ms = int(
                (self._timer._prev_ts - self._timer._lap_start_ts) * 1000
            )

        self._bridge.blockSignals(True)
        try:
            self._bridge.update_timing(
            lap_count=self._timer._lap_number,
            current_sector=self._timer._sector_index,
            sector_count=len(self._timer._sectors),
            current_lap_time_ms=current_lap_ms,
            last_sector_time_ms=(
                int(self._timer._current_sector_times[-1] * 1000)
                if self._timer._current_sector_times
                else 0
            ),
            delta_ms=int(delta * 1000) if delta is not None else 0,
            predicted_lap_ms=int(predicted * 1000) if predicted is not None else 0,
            theoretical_best_ms=int(theoretical * 1000) if theoretical is not None else 0,
            track_name=self._timer._track.name if self._timer._track else "",
            timing_mode=(
                "point_to_point"
                if self._timer._p2p_mode
                else ("circuit" if self._timer._track else "")
            ),
            lap_distance_m=self._timer.get_current_distance(),
            )
        finally:
            self._bridge.blockSignals(False)
