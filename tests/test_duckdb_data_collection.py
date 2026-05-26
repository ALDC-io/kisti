"""Tests for data collection DuckDB additions — FLIR, surface transitions, knock events, patterns."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

duckdb = pytest.importorskip("duckdb")

from data.duckdb_store import DuckDBStore


@pytest.fixture
def store(tmp_path):
    """Create a temporary DuckDB store for each test."""
    db_path = tmp_path / "test_kisti.duckdb"
    s = DuckDBStore(db_path=db_path)
    s.open()
    yield s
    s.close()


class TestSessionNaming:
    def test_session_name_and_route_tag(self, store):
        sid = store.start_session(
            session_name="Rogers Pass Day 1",
            route_tag="coquitlam-rogers-pass",
        )
        session = store.get_session(sid)
        assert session["session_name"] == "Rogers Pass Day 1"
        assert session["route_tag"] == "coquitlam-rogers-pass"

    def test_session_name_defaults_null(self, store):
        sid = store.start_session()
        session = store.get_session(sid)
        assert session["session_name"] is None
        assert session["route_tag"] is None


class TestFlirReadings:
    def test_record_flir_temps(self, store):
        sid = store.start_session()
        store.record_flir_temps(sid, 5.2, 4.8, 5.5, "DRY", False)
        store.record_flir_temps(sid, 3.1, 2.9, 3.4, "COLD", False)
        store.record_flir_temps(sid, 2.0, 1.5, 2.2, "COLD", True)

        rows = store._conn.execute(
            "SELECT * FROM flir_readings WHERE session_id = ? ORDER BY timestamp",
            [sid],
        ).fetchall()
        assert len(rows) == 3
        # Check third row has warm object
        assert rows[2][6] is True  # warm_object_detected

    def test_flir_readings_in_stats(self, store):
        sid = store.start_session()
        store.record_flir_temps(sid, 5.0, 5.0, 5.0)
        stats = store.db_stats()
        assert stats["flir_readings"] == 1


class TestSurfaceTransitions:
    def test_record_surface_transition(self, store):
        sid = store.start_session()
        tid = store.record_surface_transition(sid, "DRY", "WET", 3.5, 2.0)
        assert len(tid) == 36

        rows = store._conn.execute(
            "SELECT * FROM surface_transitions WHERE session_id = ?", [sid],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][3] == "DRY"   # from_state
        assert rows[0][4] == "WET"   # to_state
        assert rows[0][5] == 3.5     # road_temp_c
        assert rows[0][6] == 2.0     # dew_point_c
        assert rows[0][7] == 1.5     # delta_c (3.5 - 2.0)

    def test_multiple_transitions(self, store):
        sid = store.start_session()
        store.record_surface_transition(sid, "DRY", "WET", 5.0, 4.0)
        store.record_surface_transition(sid, "WET", "COLD", 2.0, 1.5)
        store.record_surface_transition(sid, "COLD", "LOW_GRIP", 0.5, 0.3)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM surface_transitions WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 3


class TestKnockEvents:
    def test_record_knock_event(self, store):
        sid = store.start_session()
        eid = store.record_knock_event(sid, 2, rpm=5500, boost_psi=18.5, gear=3, iam=0.95)
        assert len(eid) == 36

        rows = store._conn.execute(
            "SELECT * FROM knock_events WHERE session_id = ?", [sid],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][3] == 2       # knock_count_delta
        assert rows[0][4] == 5500.0  # rpm
        assert rows[0][5] == 18.5    # boost_psi
        assert rows[0][6] == 3       # gear
        assert rows[0][7] == 0.95    # iam

    def test_knock_burst_detection_query(self, store):
        """Verify we can query knock bursts (3+ in 10 seconds)."""
        sid = store.start_session()
        # Record 4 knock events
        for i in range(4):
            store.record_knock_event(sid, 1, rpm=5000 + i * 100, boost_psi=17.0, gear=3, iam=0.92)

        count = store._conn.execute(
            "SELECT COUNT(*) FROM knock_events WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 4


class TestPatterns:
    def test_record_pattern(self, store):
        sid = store.start_session()
        pid = store.record_pattern(
            sid, "ice_risk_trending", severity="warning", value=1.2,
            context={"road_temp": 2.5, "dew_point": 1.3, "trend": "decreasing"},
        )
        assert len(pid) == 36

        rows = store._conn.execute(
            "SELECT * FROM patterns WHERE session_id = ?", [sid],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][3] == "ice_risk_trending"
        assert rows[0][4] == "warning"
        assert rows[0][5] == 1.2

    def test_pattern_no_context(self, store):
        sid = store.start_session()
        pid = store.record_pattern(sid, "iam_decay", severity="info", value=0.88)
        rows = store._conn.execute(
            "SELECT context_json FROM patterns WHERE pattern_id = ?", [pid],
        ).fetchall()
        assert rows[0][0] is None

    def test_patterns_in_stats(self, store):
        sid = store.start_session()
        store.record_pattern(sid, "test_pattern")
        stats = store.db_stats()
        assert stats["patterns"] == 1


class TestExportIncludesNewTables:
    def test_export_parquet_includes_flir_and_knock(self, store, tmp_path):
        sid = store.start_session()
        store.record_flir_temps(sid, 5.0, 5.0, 5.0)
        store.record_knock_event(sid, 1, rpm=4000, boost_psi=15.0, gear=2, iam=1.0)
        store.record_surface_transition(sid, "DRY", "WET", 5.0, 4.0)
        store.record_pattern(sid, "test", value=1.0)

        export_dir = tmp_path / "export"
        files = store.export_session_parquet(sid, export_dir)
        names = [f.name for f in files]
        assert any("flir_readings" in n for n in names)
        assert any("knock_events" in n for n in names)
        assert any("surface_transitions" in n for n in names)
        assert any("patterns" in n for n in names)


class TestPurgeIncludesNewTables:
    def test_purge_cleans_new_tables(self, store):
        sid = store.start_session()
        store.record_flir_temps(sid, 5.0, 5.0, 5.0)
        store.record_knock_event(sid, 1)
        store.record_surface_transition(sid, "DRY", "WET")
        store.record_pattern(sid, "test")
        store.end_session(sid)
        store.mark_synced(sid)

        # Backdate end_time so purge considers it old enough
        store._conn.execute(
            "UPDATE sessions SET end_time = '2020-01-01' WHERE session_id = ?",
            [sid],
        )

        count = store.purge_synced(keep_days=0)
        assert count == 1

        for table in ["flir_readings", "surface_transitions", "knock_events", "patterns"]:
            c = store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert c == 0, f"{table} not purged"
