"""Tests for DuckDB local semantic layer — session CRUD, telemetry, sync."""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

# DuckDB must be installed
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


class TestSessionLifecycle:
    def test_start_session(self, store):
        sid = store.start_session(driver_id="jk", car_id="kisti-sti")
        assert sid is not None
        assert len(sid) == 36  # UUID format

    def test_get_session(self, store):
        sid = store.start_session(driver_id="jk", car_id="kisti-sti", session_type="track")
        session = store.get_session(sid)
        assert session is not None
        assert session["driver_id"] == "jk"
        assert session["car_id"] == "kisti-sti"
        assert session["session_type"] == "track"
        assert session["synced"] is False

    def test_end_session(self, store):
        sid = store.start_session()
        store.end_session(sid)
        session = store.get_session(sid)
        assert session["end_time"] is not None

    def test_list_sessions(self, store):
        store.start_session(session_type="street")
        store.start_session(session_type="track")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_nonexistent_session(self, store):
        assert store.get_session("nonexistent-id") is None


class TestTelemetryRecording:
    def test_record_telemetry(self, store):
        """Record a telemetry snapshot from a mock DiffState."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from model.vehicle_state import DiffState, SIDriveMode, SurfaceState

        sid = store.start_session()
        state = DiffState(
            rpm=3500, speed_kph=90, gear=3, throttle_pct=55,
            map_kpa=150, lambda_1=1.0, oil_psi=55, oil_temp_c=95,
            coolant_temp=85, iat_c=30, ethanol_pct=0,
            fuel_pressure_kpa=380, battery_v=14.2, injector_duty=35,
            dccd_command_pct=40, steering_angle=15,
            yaw_rate=5, lateral_g=0.3, brake_pressure=0,
            wheel_speed_fl=90, wheel_speed_fr=90.5,
            wheel_speed_rl=89.8, wheel_speed_rr=90.2,
            si_drive_mode=SIDriveMode.INTELLIGENT,
            surface_state=SurfaceState.DRY,
        )

        store.record_telemetry(sid, state)

        stats = store.db_stats()
        assert stats["telemetry"] == 1

    def test_record_multiple(self, store):
        """Record multiple telemetry points."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from model.vehicle_state import DiffState

        sid = store.start_session()
        state = DiffState(rpm=3500, speed_kph=90)

        for _ in range(10):
            store.record_telemetry(sid, state)

        stats = store.db_stats()
        assert stats["telemetry"] == 10


class TestEvents:
    def test_record_event(self, store):
        sid = store.start_session()
        eid = store.record_event(sid, "mode_change", value=1.0, metadata={"from": "I", "to": "S"})
        assert eid is not None
        assert len(eid) == 36

    def test_record_alert(self, store):
        sid = store.start_session()
        aid = store.record_alert(sid, "oil_pressure_low", "warning", "Oil low 20 PSI", value=20.0)
        assert aid is not None

        stats = store.db_stats()
        assert stats["alerts"] == 1


class TestSegments:
    def test_start_end_segment(self, store):
        sid = store.start_session()
        seg_id = store.start_segment(sid, name="Hot Lap 1")
        assert seg_id is not None

        store.end_segment(seg_id)
        stats = store.db_stats()
        assert stats["segments"] == 1


class TestSummaries:
    def test_save_summary(self, store):
        sid = store.start_session()
        sum_id = store.save_summary(sid, "Great session. Best lap 1:19.4.", tier="local")
        assert sum_id is not None

        stats = store.db_stats()
        assert stats["summaries"] == 1


class TestSync:
    def test_unsynced_sessions(self, store):
        sid1 = store.start_session()
        sid2 = store.start_session()
        unsynced = store.get_unsynced_sessions()
        assert len(unsynced) == 2

    def test_mark_synced(self, store):
        sid = store.start_session()
        store.mark_synced(sid)
        unsynced = store.get_unsynced_sessions()
        assert len(unsynced) == 0

    def test_export_parquet(self, store, tmp_path):
        """Export session data to Parquet files."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from model.vehicle_state import DiffState

        sid = store.start_session()
        state = DiffState(rpm=3500, speed_kph=90)
        store.record_telemetry(sid, state)
        store.record_event(sid, "test_event")
        store.record_alert(sid, "test_alert", "info", "Test")

        export_dir = tmp_path / "export"
        files = store.export_session_parquet(sid, export_dir)
        # Only tables with data are exported (telemetry, events, alerts have data)
        assert len(files) >= 2
        for f in files:
            assert f.exists()


class TestPurge:
    def test_purge_never_deletes_unsynced(self, store):
        """Purge should never delete unsynced sessions."""
        sid = store.start_session()
        store.end_session(sid)

        purged = store.purge_synced(keep_days=0)
        assert purged == 0  # Unsynced — should NOT be purged

        sessions = store.list_sessions()
        assert len(sessions) == 1


class TestDBStats:
    def test_stats(self, store):
        stats = store.db_stats()
        assert "sessions" in stats
        assert "telemetry" in stats
        assert "unsynced_sessions" in stats
        assert stats["sessions"] == 0
