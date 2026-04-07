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
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from timing.lap_timer import LapTimer, TimingEvent, TimingEventType
from timing.track_db import TrackDatabase
from timing.track_learner import TrackLearner
from timing.track_outline import load_outline, import_ztracks_outline

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

        # Track outline cache directory
        self._outlines_dir = Path(__file__).parent.parent / "data" / "track_outlines"

        # Initialize TrackDatabase if DuckDB available
        if db_store is not None:
            try:
                self._track_db = TrackDatabase(db_store._conn)
                # Seed tracks on first run so GPS detection has real names
                seed_path = Path(__file__).parent.parent / "data" / "tracks_seed.json"
                if self._track_db.track_count() == 0 and seed_path.exists():
                    n = self._track_db.seed_tracks(seed_path)
                    log.info("Seeded %d tracks from %s", n, seed_path.name)
            except Exception as exc:
                log.warning("TrackDatabase init failed: %s", exc)

        # Auto-import .ztracks outlines from ~/tracks/ if not already cached
        self._auto_import_ztracks()

        # Loaded outline for the currently-detected track (runtime cache)
        # Pre-load first available outline so S# Track shows a circuit before GPS detection
        self._active_outline: list[tuple[float, float]] = self._load_first_available_outline()

        # Track learning (when no seeded track matches)
        self._track_learner: Optional[TrackLearner] = None
        self._learning_active: bool = False

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
            self._track_learner = None
            self._learning_active = False

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

    def get_timing_data(self) -> dict:
        """Build timing dict for SportSharpScreenWidget.update_timing().

        Returns keys expected by sharp_screen: lap_count, current_lap_time_ms,
        delta_ms, predicted_lap_ms, best_lap_ms, theoretical_best_ms,
        track_name, sector_count, current_sector, sector_times, best_sector_times.
        """
        timer = self._timer

        # Current lap elapsed time (ms)
        current_lap_ms = 0
        if timer._lap_start_ts is not None and timer._prev_ts is not None:
            current_lap_ms = int(
                (timer._prev_ts - timer._lap_start_ts) * 1000
            )

        # Delta and predicted (seconds → ms)
        delta = timer.get_delta()
        predicted = timer.get_predicted_lap()
        theoretical = timer.get_theoretical_best()

        # Best lap time (ms) — use round() not int() to handle sub-ms precision
        # in tests where monotonic timestamps are microseconds apart
        best_lap_ms = 0
        if timer._completed_laps:
            best_s = min(lap.total_time for lap in timer._completed_laps)
            best_lap_ms = max(1, round(best_s * 1000)) if best_s > 0 else 0

        # Current sector times (seconds → ms)
        sector_times = [
            int(t * 1000) for t in timer._current_sector_times
        ]

        # Best sector times (seconds → ms, None → None)
        best_sectors_s = timer.get_best_sector_times()
        best_sector_times = [
            int(t * 1000) if t is not None else None
            for t in best_sectors_s
        ]

        return {
            "lap_count": timer._lap_number,
            "current_lap_time_ms": current_lap_ms,
            "delta_ms": int(delta * 1000) if delta is not None else 0,
            "predicted_lap_ms": int(predicted * 1000) if predicted is not None else 0,
            "best_lap_ms": best_lap_ms,
            "theoretical_best_ms": int(theoretical * 1000) if theoretical is not None else 0,
            "track_name": timer._track.name if timer._track else "",
            "sector_count": len(timer._sectors),
            "current_sector": timer._sector_index,
            "sector_times": sector_times,
            "best_sector_times": best_sector_times,
            "lap_in_progress": timer._lap_start_ts is not None,
            "track_outline": self._active_outline,
            "lap_distance_m": timer.get_current_distance(),
            "track_length_m": timer._track.length_m if timer._track else 0.0,
        }

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

        # GPS jump filter — reject fixes >500m from last known position
        # (satellite reacquire after dropout can cause false S/F crossings)
        if self._prev_gps_lat != 0.0 and self._prev_gps_lon != 0.0:
            from timing.geo import haversine_distance
            jump_m = haversine_distance(
                self._prev_gps_lat, self._prev_gps_lon, lat, lon,
            )
            if jump_m > 500.0:
                log.warning(
                    "GPS jump %.0fm — skipping (dropout recovery)",
                    jump_m,
                )
                # Update position but don't feed LapTimer
                self._prev_gps_lat = lat
                self._prev_gps_lon = lon
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

    def _load_first_available_outline(self) -> list[tuple[float, float]]:
        """Return the first cached outline found in the outlines directory."""
        if not self._outlines_dir.exists():
            return []
        for outline_file in sorted(self._outlines_dir.glob("*.json")):
            outline = load_outline(outline_file.stem, self._outlines_dir)
            if outline:
                log.info("Pre-loaded outline from %s (%d pts)", outline_file.name, len(outline))
                return outline
        return []

    def _auto_import_ztracks(self) -> None:
        """Import any *.ztracks files from ~/tracks/ that aren't yet cached.

        Matches files by track name against the seeded track list.
        Saves outlines to data/track_outlines/{track_id}.json.
        Runs once at startup; silent on errors.
        """
        ztracks_dir = Path.home() / "tracks"
        if not ztracks_dir.exists():
            return

        ztracks_files = list(ztracks_dir.glob("*.ztracks"))
        if not ztracks_files:
            return

        # Build name→track_id map from DuckDB if available
        track_name_map: dict[str, str] = {}
        if self._track_db is not None:
            try:
                tracks = self._track_db.list_tracks()
                log.info("ztracks matching: %d tracks in DB", len(tracks))
                for track in tracks:
                    track_name_map[track.name.lower()] = track.track_id
            except Exception as exc:
                log.warning("Could not load track names for ztracks matching: %s", exc)
        else:
            log.warning("ztracks matching: _track_db is None — name match unavailable")

        for ztracks_path in ztracks_files:
            # Try to determine track_id from filename or name in file.
            # Filename heuristic: mission_raceway_park.ztracks → "mission raceway park"
            stem_words = ztracks_path.stem.replace('_', ' ').lower()

            # Find matching track_id by name similarity (filename stem)
            track_id = None
            for db_name, tid in track_name_map.items():
                if stem_words in db_name or db_name in stem_words:
                    track_id = tid
                    break

            if track_id is None:
                if not track_name_map:
                    # No DB available — skip rather than writing a hash-named file.
                    # Pre-committed canonical outline files will be loaded at startup.
                    log.debug("Skipping %s — no DB for name match", ztracks_path.name)
                    continue
                import hashlib
                track_id = hashlib.md5(ztracks_path.name.encode()).hexdigest()[:8] + \
                           "-0000-0000-0000-000000000000"
                log.warning("No DB match for %s (stem=%r) — using hash ID %s",
                            ztracks_path.name, stem_words, track_id[:8])

            cached = self._outlines_dir / f"{track_id}.json"
            if cached.exists():
                log.debug("Outline already cached for %s", ztracks_path.name)
                continue

            log.info("Auto-importing .ztracks: %s → %s", ztracks_path.name, track_id[:8])
            try:
                import_ztracks_outline(ztracks_path, track_id, self._outlines_dir)
            except Exception as exc:
                log.warning("Failed to import %s: %s", ztracks_path.name, exc)

    def _try_detect_track(self, lat: float, lon: float) -> None:
        """Attempt to auto-detect track, or learn a new one from GPS trace."""
        # Check database first (seeded or previously learned)
        track = self._track_db.find_track(lat, lon)
        if track is not None:
            sectors = track.sectors

            # Load cached GPS outline if available
            outline = load_outline(track.track_id, self._outlines_dir)
            if outline:
                track.outline = outline
                self._active_outline = outline
                log.info("Loaded outline for %s (%d pts)", track.name, len(outline))
            else:
                self._active_outline = []

            self._timer.set_track(track, sectors)
            self._track_detected = True
            self._track_learner = None
            self._learning_active = False
            log.info("Track detected: %s (%d sectors)", track.name, len(sectors))
            self.track_detected.emit(track.name)
            return

        # No known track — start or continue learning
        if self._track_learner is None:
            self._track_learner = TrackLearner()
            self._learning_active = True
            log.info("No known track — learning started")

        if self._learning_active:
            closed = self._track_learner.update(lat, lon)
            if closed:
                self._finish_track_learning()

    def _finish_track_learning(self) -> None:
        """Handle track learner loop closure — save and configure."""
        track, sectors = self._track_learner.result()

        # Save to DuckDB
        self._track_db.save_track(track)
        self._track_db.save_sectors(track.track_id, sectors)

        # Configure LapTimer
        self._timer.set_track(track, sectors)
        self._track_detected = True
        self._learning_active = False

        log.info(
            "Learned track: %s (%.0fm, %d sectors)",
            track.name, track.length_m, len(sectors),
        )
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
