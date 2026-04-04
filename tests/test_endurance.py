"""Tests for 12-hour endurance estimation and data retention."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

duckdb = pytest.importorskip("duckdb")

from data.duckdb_store import DuckDBStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_kisti.duckdb"
    s = DuckDBStore(db_path=db_path)
    s.open()
    yield s
    s.close()


class TestEnduranceEstimation:
    def test_12hr_telemetry_row_estimate(self):
        """50Hz CAN telemetry * 12 hours = ~2.16M rows. DuckDB handles this."""
        hz = 50
        hours = 12
        rows = hz * 3600 * hours
        assert rows == 2_160_000
        # DuckDB columnar storage: ~42 doubles per row = 336 bytes
        # 2.16M * 336 = ~726 MB uncompressed. DuckDB compresses ~5-10x.
        estimated_mb = (rows * 42 * 8) / (1024 * 1024)
        assert estimated_mb < 1000  # Under 1GB uncompressed

    def test_12hr_flir_row_estimate(self):
        """3Hz FLIR * 12 hours = ~129,600 rows. Trivial for DuckDB."""
        hz = 3
        hours = 12
        rows = hz * 3600 * hours
        assert rows == 129_600

    def test_12hr_ambient_row_estimate(self):
        """1Hz Yocto * 12 hours = ~43,200 rows. Trivial."""
        hz = 1
        hours = 12
        rows = hz * 3600 * hours
        assert rows == 43_200

    def test_batch_insert_bulk(self, store):
        """Verify DuckDB can handle bulk inserts without error."""
        sid = store.start_session(session_name="Endurance Test", route_tag="bench")

        # Insert 1000 FLIR readings (simulating ~5.5 minutes at 3Hz)
        for i in range(1000):
            store.record_flir_temps(sid, 5.0 + i * 0.001, 4.8, 5.2, "DRY")

        count = store._conn.execute(
            "SELECT COUNT(*) FROM flir_readings WHERE session_id = ?", [sid],
        ).fetchone()[0]
        assert count == 1000

    def test_session_with_all_new_tables(self, store):
        """Verify a complete session touches all new tables without error."""
        sid = store.start_session(
            session_name="Integration Test",
            route_tag="rogers-pass",
        )

        # Telemetry
        for i in range(10):
            store._conn.execute(
                "INSERT INTO telemetry (timestamp, session_id, rpm, speed_kph) "
                "VALUES (NOW(), ?, ?, ?)",
                [sid, 3000 + i * 100, 60 + i * 5],
            )

        # FLIR
        for _ in range(5):
            store.record_flir_temps(sid, 4.0, 3.5, 4.2, "COLD")

        # Surface transitions
        store.record_surface_transition(sid, "DRY", "WET", 5.0, 4.0)
        store.record_surface_transition(sid, "WET", "COLD", 2.0, 1.5)

        # Knock events
        store.record_knock_event(sid, 2, rpm=5500, boost_psi=18.0, gear=3, iam=0.95)

        # Patterns
        store.record_pattern(sid, "ice_risk_trending", "warning", 1.5)

        # Alerts
        store.record_alert(sid, "oil_pressure_low", "warning", "Test", 22.0)

        # End session
        store.end_session(sid)

        # Verify stats
        stats = store.db_stats()
        assert stats["sessions"] == 1
        assert stats["telemetry"] == 10
        assert stats["flir_readings"] == 5
        assert stats["surface_transitions"] == 2
        assert stats["knock_events"] == 1
        assert stats["patterns"] == 1
        assert stats["alerts"] == 1

    def test_purge_30day_rolling_window(self, store):
        """Verify 30-day purge works for all tables including new ones."""
        sid = store.start_session()
        store.record_flir_temps(sid, 5.0, 5.0, 5.0)
        store.record_knock_event(sid, 1)
        store.record_surface_transition(sid, "DRY", "WET")
        store.record_pattern(sid, "test")
        store.end_session(sid)
        store.mark_synced(sid)

        # Backdate to make it purgeable
        store._conn.execute(
            "UPDATE sessions SET end_time = '2020-01-01' WHERE session_id = ?", [sid],
        )

        count = store.purge_synced(keep_days=30)
        assert count == 1

        # All data should be gone
        for table in ["telemetry", "flir_readings", "surface_transitions", "knock_events", "patterns"]:
            c = store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert c == 0, f"{table} not purged"

    def test_export_includes_all_new_tables(self, store, tmp_path):
        """Verify Parquet export covers all new tables."""
        sid = store.start_session()
        store.record_flir_temps(sid, 5.0, 5.0, 5.0)
        store.record_knock_event(sid, 1, rpm=4000, boost_psi=15.0, gear=2, iam=1.0)
        store.record_surface_transition(sid, "DRY", "WET", 5.0, 4.0)
        store.record_pattern(sid, "test", value=1.0)
        store.end_session(sid)

        export_dir = tmp_path / "export"
        files = store.export_session_parquet(sid, export_dir)
        names = [f.name for f in files]

        assert any("flir_readings" in n for n in names)
        assert any("knock_events" in n for n in names)
        assert any("surface_transitions" in n for n in names)
        assert any("patterns" in n for n in names)
