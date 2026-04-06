"""Tests for TimingManager — Qt integration layer for race analysis timing.

Uses a synthetic rectangular track (same geometry as test_lap_timer.py)
for timing tests, and the Laguna Seca seed for detection tests.

Track layout (clockwise driving direction):

       NW ─────────── NE       (top: vehicle heads west)
        │              │
        │   (center)   │       left: vehicle heads south
        │              │       right: vehicle heads north
        │              │
       SW ─── SF ──── SE       (bottom: vehicle heads east)

Test classes:
  - TestTrackDetection (4 tests)
  - TestLapCompletion (4 tests)
  - TestSectorCompletion (3 tests)
  - TestBridgeTimingState (3 tests)
  - TestDuckDBRecording (2 tests)
  - TestSessionLifecycle (3 tests)
  - TestSessionSummary (2 tests)
  - TestP2PMode (2 tests)
  - TestEdgeCases (3 tests)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from model.vehicle_state import DiffStateBridge
from data.duckdb_store import DuckDBStore
from timing.timing_manager import TimingManager
from timing.track_db import TrackDatabase, StartFinishLine, TrackDefinition, SectorDefinition


# ── Synthetic rectangular track (matches test_lap_timer.py) ───────────

_BASE_LAT = 45.0
_BASE_LON = -122.0
_HALF = 0.0018  # ~200m per half-side

_SYNTH_TRACK_ID = "synth-rect-0001"

# Start/finish: N-S segment at bottom-edge midpoint (lon = _BASE_LON)
_SYNTH_SF = StartFinishLine(
    lat1=_BASE_LAT - _HALF - 0.0002, lon1=_BASE_LON,
    lat2=_BASE_LAT - _HALF + 0.0002, lon2=_BASE_LON,
)

# Sector 0: E-W line at midpoint of right edge (vehicle heads north)
_SEC0 = StartFinishLine(
    lat1=_BASE_LAT, lon1=_BASE_LON + _HALF - 0.0002,
    lat2=_BASE_LAT, lon2=_BASE_LON + _HALF + 0.0002,
)
# Sector 1: N-S line at midpoint of top edge (vehicle heads west)
_SEC1 = StartFinishLine(
    lat1=_BASE_LAT + _HALF - 0.0002, lon1=_BASE_LON,
    lat2=_BASE_LAT + _HALF + 0.0002, lon2=_BASE_LON,
)
# Sector 2: E-W line at midpoint of left edge (vehicle heads south)
_SEC2 = StartFinishLine(
    lat1=_BASE_LAT, lon1=_BASE_LON - _HALF - 0.0002,
    lat2=_BASE_LAT, lon2=_BASE_LON - _HALF + 0.0002,
)

_SYNTH_TRACK = TrackDefinition(
    track_id=_SYNTH_TRACK_ID,
    name="Synthetic Rectangle",
    center_lat=_BASE_LAT,
    center_lon=_BASE_LON,
    radius_m=2000.0,
    track_type="circuit",
    start_finish=_SYNTH_SF,
    country="XX", region="Test",
    length_m=1600.0,
    source="manual",
)

_SYNTH_SECTORS = [
    SectorDefinition("sec0", _SYNTH_TRACK_ID, 0, _SEC0, "Right Mid"),
    SectorDefinition("sec1", _SYNTH_TRACK_ID, 1, _SEC1, "Top Mid"),
    SectorDefinition("sec2", _SYNTH_TRACK_ID, 2, _SEC2, "Left Mid"),
]

# Corners
_SW = (_BASE_LAT - _HALF, _BASE_LON - _HALF)
_SE = (_BASE_LAT - _HALF, _BASE_LON + _HALF)
_NE = (_BASE_LAT + _HALF, _BASE_LON + _HALF)
_NW = (_BASE_LAT + _HALF, _BASE_LON - _HALF)

# GPS trace: one clockwise revolution (crosses S/F once at bottom edge).
# S/F is N-S at bottom, so crossing = lon goes through _BASE_LON.
# Only the bottom edge crosses S/F. All other edges are far from S/F.
_SYNTH_LAP = [
    (_BASE_LAT - _HALF, _BASE_LON - 0.0010),  # 0: W of S/F (bottom)
    (_BASE_LAT - _HALF, _BASE_LON + 0.0010),  # 1: E of S/F — S/F CROSSING
    _SE,                                        # 2: SE corner
    (_BASE_LAT, _BASE_LON + _HALF),             # 3: mid-right — SEC0 CROSSING
    _NE,                                        # 4: NE corner
    (_BASE_LAT + _HALF, _BASE_LON),             # 5: mid-top — SEC1 CROSSING
    _NW,                                        # 6: NW corner
    (_BASE_LAT, _BASE_LON - _HALF),             # 7: mid-left — SEC2 CROSSING
    _SW,                                        # 8: SW corner
]

# Complete one lap: wrap back to S/F crossing
_SYNTH_LAP_COMPLETE = _SYNTH_LAP + [
    (_BASE_LAT - _HALF, _BASE_LON + 0.0010),  # S/F CROSSING — lap 1 complete
]

# Complete two laps: second revolution
_SYNTH_TWO_LAPS = _SYNTH_LAP_COMPLETE + [
    _SE,
    (_BASE_LAT, _BASE_LON + _HALF),
    _NE,
    (_BASE_LAT + _HALF, _BASE_LON),
    _NW,
    (_BASE_LAT, _BASE_LON - _HALF),
    _SW,
    (_BASE_LAT - _HALF, _BASE_LON + 0.0010),  # S/F CROSSING — lap 2 complete
]


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def bridge(qapp):
    return DiffStateBridge()


@pytest.fixture
def db_store(tmp_path):
    """In-memory-like DuckDB store using a temp file."""
    store = DuckDBStore(db_path=tmp_path / "test.duckdb")
    store.open()
    yield store
    store.close()


@pytest.fixture
def synth_db(db_store):
    """DuckDB with synthetic rectangular track seeded."""
    track_db = TrackDatabase(db_store._conn)
    track_db.save_track(_SYNTH_TRACK)
    track_db.save_sectors(_SYNTH_TRACK_ID, _SYNTH_SECTORS)
    return db_store


@pytest.fixture
def laguna_db(db_store):
    """DuckDB with Laguna Seca track seeded (for detection tests)."""
    track_db = TrackDatabase(db_store._conn)
    seed_path = Path(__file__).resolve().parent.parent / "data" / "tracks_seed.json"
    track_db.seed_tracks(seed_path)
    return db_store


@pytest.fixture
def timing_mgr(bridge, synth_db):
    """TimingManager wired to bridge with synthetic track."""
    mgr = TimingManager(bridge=bridge, db_store=synth_db)
    mgr.start()
    yield mgr
    mgr.stop()


def _feed_gps(bridge, points):
    """Feed GPS points through the bridge."""
    for lat, lon in points:
        bridge.update_gps(latitude=lat, longitude=lon)
        bridge.update_gps_ext(
            altitude_m=100.0, speed_mps=30.0,
            heading=0.0, satellites=12, fix_quality=2,
        )


# ── TestTrackDetection ────────────────────────────────────────────────

class TestTrackDetection:
    """Track auto-detection from GPS position."""

    def test_detects_laguna_seca(self, bridge, laguna_db, qapp):
        """First GPS fix within Laguna Seca radius triggers track_detected."""
        mgr = TimingManager(bridge=bridge, db_store=laguna_db)
        mgr.start()
        detected = []
        mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=36.5842, longitude=-121.7534)

        assert len(detected) == 1
        assert "Laguna Seca" in detected[0]
        mgr.stop()

    def test_detects_synthetic_track(self, timing_mgr, bridge):
        """GPS within synthetic track radius triggers detection."""
        detected = []
        timing_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)

        assert len(detected) == 1
        assert detected[0] == "Synthetic Rectangle"

    def test_no_detection_outside_radius(self, bridge, synth_db, qapp):
        """GPS far from any track — no detection."""
        mgr = TimingManager(bridge=bridge, db_store=synth_db)
        mgr.start()
        detected = []
        mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=10.0, longitude=10.0)

        assert len(detected) == 0
        mgr.stop()

    def test_detects_only_once(self, timing_mgr, bridge):
        """Track detection happens only on first GPS fix, not repeated."""
        detected = []
        timing_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        bridge.update_gps(latitude=_BASE_LAT + 0.0001, longitude=_BASE_LON)

        assert len(detected) == 1


# ── TestLapCompletion ─────────────────────────────────────────────────

class TestLapCompletion:
    """Full lap detection from GPS trace crossing start/finish."""

    def test_single_lap_fires_signal(self, timing_mgr, bridge):
        """Complete circuit → lap_completed signal emitted."""
        laps = []
        timing_mgr.lap_completed.connect(lambda e: laps.append(e))

        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        assert len(laps) == 1
        assert laps[0]["lap_number"] == 1
        assert laps[0]["time_s"] > 0

    def test_two_laps(self, timing_mgr, bridge):
        """Two complete circuits → two lap_completed signals."""
        laps = []
        timing_mgr.lap_completed.connect(lambda e: laps.append(e))

        _feed_gps(bridge, _SYNTH_TWO_LAPS)

        assert len(laps) == 2
        assert laps[0]["lap_number"] == 1
        assert laps[1]["lap_number"] == 2

    def test_lap_has_delta(self, timing_mgr, bridge):
        """Second lap has non-zero delta_s (vs first lap as reference)."""
        laps = []
        timing_mgr.lap_completed.connect(lambda e: laps.append(e))

        _feed_gps(bridge, _SYNTH_TWO_LAPS)

        assert len(laps) >= 2
        # First lap delta is 0 (no reference yet)
        assert laps[0]["delta_s"] == 0.0
        # Second lap has a delta
        assert isinstance(laps[1]["delta_s"], float)

    def test_no_lap_without_full_circuit(self, timing_mgr, bridge):
        """Partial trace (no S/F re-crossing) → no lap_completed."""
        laps = []
        timing_mgr.lap_completed.connect(lambda e: laps.append(e))

        _feed_gps(bridge, _SYNTH_LAP[:6])

        assert len(laps) == 0


# ── TestSectorCompletion ──────────────────────────────────────────────

class TestSectorCompletion:
    """Sector boundary crossing detection."""

    def test_sectors_fire_during_lap(self, timing_mgr, bridge):
        """Crossing sector lines emits sector_completed signals."""
        sectors = []
        timing_mgr.sector_completed.connect(lambda e: sectors.append(e))

        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        assert len(sectors) == 3

    def test_sector_indices_in_order(self, timing_mgr, bridge):
        """Sectors fire in index order: 0, 1, 2."""
        sectors = []
        timing_mgr.sector_completed.connect(lambda e: sectors.append(e))

        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        indices = [s["sector_index"] for s in sectors]
        assert indices == [0, 1, 2]

    def test_sector_times_positive(self, timing_mgr, bridge):
        """Each sector has a positive time."""
        sectors = []
        timing_mgr.sector_completed.connect(lambda e: sectors.append(e))

        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        for s in sectors:
            assert s["time_s"] > 0


# ── TestBridgeTimingState ─────────────────────────────────────────────

class TestBridgeTimingState:
    """TimingManager pushes state to DiffStateBridge."""

    def test_track_name_on_bridge(self, timing_mgr, bridge):
        """After track detection, bridge snapshot has track_name."""
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        snap = bridge.snapshot()
        assert snap.track_name == "Synthetic Rectangle"

    def test_timing_mode_circuit(self, timing_mgr, bridge):
        """After track detection, timing_mode is 'circuit'."""
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        snap = bridge.snapshot()
        assert snap.timing_mode == "circuit"

    def test_lap_count_increments(self, timing_mgr, bridge):
        """After completing a lap, bridge lap_count increments."""
        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)
        snap = bridge.snapshot()
        assert snap.lap_count >= 2  # lap_number advances to 2 after first lap


# ── TestDuckDBRecording ───────────────────────────────────────────────

class TestDuckDBRecording:
    """Lap recording to DuckDB when session is active."""

    def test_records_lap_with_session(self, timing_mgr, bridge, synth_db):
        """Completed lap recorded to DuckDB when session_id is set."""
        sid = synth_db.start_session(si_drive_mode="Intelligent")
        timing_mgr.set_session_id(sid)

        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        laps = synth_db.get_session_laps(sid)
        assert len(laps) == 1
        assert laps[0]["lap_number"] == 1
        assert laps[0]["lap_time_s"] > 0

    def test_no_record_without_session(self, timing_mgr, bridge, synth_db):
        """Completed lap NOT recorded when no session_id."""
        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        rows = synth_db._conn.execute(
            "SELECT COUNT(*) FROM lap_times"
        ).fetchone()
        assert rows[0] == 0


# ── TestSessionLifecycle ──────────────────────────────────────────────

class TestSessionLifecycle:
    """Session start/stop resets timing state."""

    def test_set_session_id(self, timing_mgr):
        """Setting session_id stores it internally."""
        timing_mgr.set_session_id("test-session-123")
        assert timing_mgr._session_id == "test-session-123"

    def test_clear_session_resets_timer(self, timing_mgr, bridge):
        """Setting session_id to None resets LapTimer and track detection."""
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        assert timing_mgr._track_detected is True

        timing_mgr.set_session_id(None)

        assert timing_mgr._track_detected is False
        assert timing_mgr._timer._track is None

    def test_re_detect_after_reset(self, timing_mgr, bridge):
        """After session reset, track is re-detected on next GPS fix."""
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        timing_mgr.set_session_id(None)

        detected = []
        timing_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_BASE_LAT + 0.0001, longitude=_BASE_LON)
        assert len(detected) == 1


# ── TestSessionSummary ────────────────────────────────────────────────

class TestSessionSummary:
    """Voice debrief session summary."""

    def test_summary_after_laps(self, timing_mgr, bridge):
        """get_session_summary returns correct data after completing laps."""
        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)

        summary = timing_mgr.get_session_summary()
        assert summary["total_laps"] == 1
        assert summary["best_lap_number"] == 1
        assert summary["best_lap_time_s"] > 0
        assert summary["track_name"] == "Synthetic Rectangle"

    def test_empty_summary_no_laps(self, timing_mgr, bridge):
        """get_session_summary returns empty dict with no completed laps."""
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        summary = timing_mgr.get_session_summary()
        assert summary == {}


# ── TestP2PMode ───────────────────────────────────────────────────────

class TestP2PMode:
    """Point-to-point timing through TimingManager."""

    def test_p2p_signal_fires(self, bridge, synth_db, qapp):
        """P2P segment completion emits p2p_completed signal."""
        mgr = TimingManager(bridge=bridge, db_store=synth_db)
        mgr.start()
        segments = []
        mgr.p2p_completed.connect(lambda e: segments.append(e))

        # Configure P2P with two simple E-W lines
        start_line = StartFinishLine(
            _BASE_LAT - 0.0005, _BASE_LON - 0.0002,
            _BASE_LAT + 0.0005, _BASE_LON - 0.0002,
        )
        end_line = StartFinishLine(
            _BASE_LAT - 0.0005, _BASE_LON + 0.0020,
            _BASE_LAT + 0.0005, _BASE_LON + 0.0020,
        )
        mgr._timer.set_p2p_mode(start_line, end_line)

        # Feed points that cross start then end (heading east)
        _feed_gps(bridge, [
            (_BASE_LAT, _BASE_LON - 0.0010),  # before start
            (_BASE_LAT, _BASE_LON),             # cross start
            (_BASE_LAT, _BASE_LON + 0.0010),   # mid-segment
            (_BASE_LAT, _BASE_LON + 0.0030),   # cross end
        ])

        assert len(segments) == 1
        assert segments[0]["time_s"] > 0
        mgr.stop()

    def test_p2p_timing_mode_on_bridge(self, bridge, synth_db, qapp):
        """Bridge timing_mode shows 'point_to_point' in P2P mode."""
        mgr = TimingManager(bridge=bridge, db_store=synth_db)
        mgr.start()
        mgr._track_detected = True

        start_line = StartFinishLine(
            _BASE_LAT - 0.0005, _BASE_LON - 0.0002,
            _BASE_LAT + 0.0005, _BASE_LON - 0.0002,
        )
        end_line = StartFinishLine(
            _BASE_LAT - 0.0005, _BASE_LON + 0.0020,
            _BASE_LAT + 0.0005, _BASE_LON + 0.0020,
        )
        mgr._timer.set_p2p_mode(start_line, end_line)

        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON - 0.0010)
        snap = bridge.snapshot()
        assert snap.timing_mode == "point_to_point"
        mgr.stop()


# ── TestEdgeCases ─────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and error handling."""

    def test_zero_gps_ignored(self, timing_mgr, bridge):
        """GPS at (0, 0) is ignored — no processing."""
        detected = []
        timing_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=0.0, longitude=0.0)

        assert len(detected) == 0

    def test_duplicate_gps_skipped(self, timing_mgr, bridge):
        """Same GPS position twice → only processed once."""
        detected = []
        timing_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)
        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)

        assert len(detected) == 1

    def test_stop_disconnects(self, bridge, synth_db, qapp):
        """After stop(), GPS updates don't trigger processing."""
        mgr = TimingManager(bridge=bridge, db_store=synth_db)
        mgr.start()
        mgr.stop()

        detected = []
        mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_BASE_LAT, longitude=_BASE_LON)

        assert len(detected) == 0


# ── TestTrackLearning ─────────────────────────────────────────────────

# Learning trace: rectangular loop at a location far from any seeded track
_LEARN_LAT = 50.0
_LEARN_LON = -100.0
_LEARN_HALF = 0.0018


def _make_learn_loop(pts_per_side: int = 20) -> list[tuple[float, float]]:
    """Rectangular GPS loop at (_LEARN_LAT, _LEARN_LON) for learning tests."""
    sw = (_LEARN_LAT - _LEARN_HALF, _LEARN_LON - _LEARN_HALF)
    se = (_LEARN_LAT - _LEARN_HALF, _LEARN_LON + _LEARN_HALF)
    ne = (_LEARN_LAT + _LEARN_HALF, _LEARN_LON + _LEARN_HALF)
    nw = (_LEARN_LAT + _LEARN_HALF, _LEARN_LON - _LEARN_HALF)
    corners = [sw, se, ne, nw, sw]
    trace = []
    for i in range(len(corners) - 1):
        lat0, lon0 = corners[i]
        lat1, lon1 = corners[i + 1]
        for j in range(pts_per_side):
            frac = j / pts_per_side
            trace.append((lat0 + frac * (lat1 - lat0), lon0 + frac * (lon1 - lon0)))
    trace.append(sw)
    return trace


@pytest.fixture
def learning_mgr(bridge, db_store):
    """TimingManager with empty track DB (no seeded tracks) for learning tests."""
    mgr = TimingManager(bridge=bridge, db_store=db_store)
    mgr.start()
    yield mgr
    mgr.stop()


class TestTrackLearning:
    """Track learning when no seeded track matches GPS position."""

    def test_learning_starts_when_no_track_found(self, learning_mgr, bridge):
        """GPS at unknown location starts a TrackLearner."""
        bridge.update_gps(latitude=_LEARN_LAT, longitude=_LEARN_LON)
        assert learning_mgr._track_learner is not None
        assert learning_mgr._learning_active is True

    def test_learning_detects_loop_and_saves(self, learning_mgr, bridge, db_store):
        """Complete loop at unknown location → track detected + saved to DB."""
        detected = []
        learning_mgr.track_detected.connect(lambda name: detected.append(name))

        _feed_gps(bridge, _make_learn_loop())

        assert len(detected) == 1
        assert detected[0] == "New track"

        # Verify saved to DuckDB
        from timing.track_db import TrackDatabase
        tdb = TrackDatabase(db_store._conn)
        found = tdb.find_track(_LEARN_LAT, _LEARN_LON)
        assert found is not None

    def test_learned_track_has_correct_source(self, learning_mgr, bridge, db_store):
        """Learned track has source='learned'."""
        _feed_gps(bridge, _make_learn_loop())

        from timing.track_db import TrackDatabase
        tdb = TrackDatabase(db_store._conn)
        track = tdb.find_track(_LEARN_LAT, _LEARN_LON)
        assert track.source == "learned"

    def test_learned_track_configures_lap_timer(self, learning_mgr, bridge):
        """After learning, LapTimer has a track configured."""
        _feed_gps(bridge, _make_learn_loop())
        assert learning_mgr._timer._track is not None

    def test_subsequent_session_finds_learned_track(self, learning_mgr, bridge):
        """After learning + session reset, next GPS fix finds learned track."""
        _feed_gps(bridge, _make_learn_loop())
        learning_mgr.set_session_id(None)  # reset

        detected = []
        learning_mgr.track_detected.connect(lambda name: detected.append(name))

        bridge.update_gps(latitude=_LEARN_LAT, longitude=_LEARN_LON)
        assert len(detected) == 1

    def test_learning_cancelled_on_session_reset(self, learning_mgr, bridge):
        """Session reset cancels active learning."""
        bridge.update_gps(latitude=_LEARN_LAT, longitude=_LEARN_LON)
        assert learning_mgr._track_learner is not None

        learning_mgr.set_session_id(None)

        assert learning_mgr._track_learner is None
        assert learning_mgr._learning_active is False


# ── TestGetTimingData ──────────────────────────────────────────────


class TestGetTimingData:
    """Test get_timing_data() returns the dict SportSharpScreenWidget expects."""

    def test_empty_before_any_gps(self, timing_mgr):
        """Before any GPS data, get_timing_data returns zeroed dict."""
        data = timing_mgr.get_timing_data()
        assert data["lap_count"] == 0
        assert data["current_lap_time_ms"] == 0
        assert data["delta_ms"] == 0
        assert data["predicted_lap_ms"] == 0
        assert data["best_lap_ms"] == 0
        assert data["theoretical_best_ms"] == 0
        assert data["track_name"] == ""
        assert data["sector_count"] == 0
        assert data["current_sector"] == 0
        assert data["sector_times"] == []
        assert data["best_sector_times"] == []

    def test_has_track_after_detection(self, timing_mgr, bridge):
        """After track detection, track_name and sector_count populated."""
        _feed_gps(bridge, [(_BASE_LAT, _BASE_LON)])  # trigger detection
        data = timing_mgr.get_timing_data()
        assert data["track_name"] == "Synthetic Rectangle"
        assert data["sector_count"] == 3

    def test_all_keys_present(self, timing_mgr):
        """get_timing_data returns all keys the sharp screen expects."""
        data = timing_mgr.get_timing_data()
        expected_keys = {
            "lap_count", "current_lap_time_ms", "delta_ms",
            "predicted_lap_ms", "best_lap_ms", "theoretical_best_ms",
            "track_name", "sector_count", "current_sector",
            "sector_times", "best_sector_times", "lap_in_progress",
        }
        assert set(data.keys()) == expected_keys

    def test_timing_after_lap(self, timing_mgr, bridge):
        """After completing a lap, best_lap_ms is set."""
        _feed_gps(bridge, _SYNTH_LAP_COMPLETE)
        data = timing_mgr.get_timing_data()
        assert data["lap_count"] >= 1
        assert data["best_lap_ms"] > 0
