"""Tests for Pattern Detection Engine — thermal, drivetrain, dynamics patterns."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

duckdb = pytest.importorskip("duckdb")

from data.duckdb_store import DuckDBStore
from analysis.pattern_engine import PatternEngine, WINDOW_SECONDS


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_kisti.duckdb"
    s = DuckDBStore(db_path=db_path)
    s.open()
    yield s
    s.close()


@pytest.fixture
def engine(store):
    sid_holder = [None]
    eng = PatternEngine(store, lambda: sid_holder[0])
    eng._sid_holder = sid_holder  # expose for tests
    return eng


class TestThermalPatterns:
    def test_ice_risk_imminent(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        # Record ambient with dew point at 2.0C
        store.record_ambient(3.0, 80.0, 1013.0, 0.0, 2.0)

        # Record FLIR readings just above dew point (delta < 1C)
        for _ in range(10):
            store.record_flir_temps(sid, 2.5, 2.3, 2.6, "COLD")

        engine._run_thermal_patterns(sid)

        patterns = store._conn.execute(
            "SELECT pattern_type, severity FROM patterns WHERE session_id = ?",
            [sid],
        ).fetchall()
        types = [p[0] for p in patterns]
        assert "ice_risk_imminent" in types

    def test_no_pattern_when_warm(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        store.record_ambient(20.0, 50.0, 1013.0, 0.0, 10.0)

        for _ in range(10):
            store.record_flir_temps(sid, 20.0, 20.5, 19.8, "DRY")

        engine._run_thermal_patterns(sid)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM patterns WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 0

    def test_road_temp_variance(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        store.record_ambient(10.0, 50.0, 1013.0, 0.0, 5.0)

        # Record FLIR with significant L/C/R variance (>2C spread)
        for _ in range(10):
            store.record_flir_temps(sid, 2.0, 8.0, 3.0, "DRY")

        engine._run_thermal_patterns(sid)

        patterns = store._conn.execute(
            "SELECT pattern_type FROM patterns WHERE session_id = ?", [sid],
        ).fetchall()
        types = [p[0] for p in patterns]
        assert "road_temp_variance" in types


class TestDrivetrainPatterns:
    def test_knock_burst(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        # Record 4 knock events (burst threshold is 3)
        for i in range(4):
            store.record_knock_event(sid, 1, rpm=5000, boost_psi=18.0, gear=3, iam=0.95)

        engine._run_drivetrain_patterns(sid)

        patterns = store._conn.execute(
            "SELECT pattern_type, severity FROM patterns WHERE session_id = ?",
            [sid],
        ).fetchall()
        types = [p[0] for p in patterns]
        assert "knock_burst" in types

    def test_iam_low(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        # Record knock events with IAM below 0.9
        for _ in range(6):
            store.record_knock_event(sid, 1, rpm=4000, boost_psi=15.0, gear=2, iam=0.85)

        engine._run_drivetrain_patterns(sid)

        patterns = store._conn.execute(
            "SELECT pattern_type FROM patterns WHERE session_id = ?", [sid],
        ).fetchall()
        types = [p[0] for p in patterns]
        assert "iam_low" in types

    def test_no_knock_pattern_when_clean(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        # No knock events = no knock patterns
        engine._run_drivetrain_patterns(sid)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM patterns WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 0


class TestDynamicsPatterns:
    def test_wheel_speed_spread_high(self, store, engine):
        """Test high wheel speed spread detection (simulated via telemetry)."""
        sid = store.start_session()
        engine._sid_holder[0] = sid

        # We need telemetry rows with high wheel speed spread
        # Insert directly since record_telemetry needs a DiffState
        for i in range(20):
            store._conn.execute(
                "INSERT INTO telemetry (timestamp, session_id, "
                "wheel_fl, wheel_fr, wheel_rl, wheel_rr) "
                "VALUES (NOW(), ?, ?, ?, ?, ?)",
                [sid, 80.0, 72.0, 80.0, 73.0],  # 8 km/h spread front, 7 rear
            )

        engine._run_dynamics_patterns(sid)

        patterns = store._conn.execute(
            "SELECT pattern_type FROM patterns WHERE session_id = ?", [sid],
        ).fetchall()
        types = [p[0] for p in patterns]
        assert "wheel_speed_spread_high" in types

    def test_no_spread_when_normal(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        for i in range(20):
            store._conn.execute(
                "INSERT INTO telemetry (timestamp, session_id, "
                "wheel_fl, wheel_fr, wheel_rl, wheel_rr) "
                "VALUES (NOW(), ?, ?, ?, ?, ?)",
                [sid, 80.0, 80.5, 79.8, 80.2],  # <1 km/h spread
            )

        engine._run_dynamics_patterns(sid)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM patterns WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 0


class TestPatternDebounce:
    def test_same_pattern_debounced_30s(self, store, engine):
        sid = store.start_session()
        engine._sid_holder[0] = sid

        store.record_ambient(3.0, 80.0, 1013.0, 0.0, 2.0)
        for _ in range(10):
            store.record_flir_temps(sid, 2.5, 2.3, 2.6, "COLD")

        # Run twice — should only emit once (30s debounce)
        engine._run_thermal_patterns(sid)
        engine._run_thermal_patterns(sid)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM patterns WHERE session_id = ? AND pattern_type = 'ice_risk_imminent'",
            [sid],
        ).fetchone()[0]
        assert count == 1
