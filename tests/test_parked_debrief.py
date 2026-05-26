"""Tests for Parked Haiku Debrief — session summary generation and API mocking."""

import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

duckdb = pytest.importorskip("duckdb")

from data.duckdb_store import DuckDBStore
from analysis.parked_debrief import ParkedDebrief


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_kisti.duckdb"
    s = DuckDBStore(db_path=db_path)
    s.open()
    yield s
    s.close()


@pytest.fixture
def populated_session(store):
    """Create a session with representative data."""
    sid = store.start_session(
        session_name="Test Drive",
        route_tag="test-route",
    )
    # Telemetry (insert directly — no DiffState needed)
    for i in range(20):
        store._conn.execute(
            "INSERT INTO telemetry (timestamp, session_id, rpm, speed_kph, "
            "coolant_temp, oil_temp_c, gear, wheel_fl, wheel_fr, wheel_rl, wheel_rr) "
            "VALUES (NOW(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [sid, 3000 + i * 100, 60 + i * 2, 85 + i * 0.5, 90 + i * 0.3,
             3, 80.0, 80.2, 79.8, 80.1],
        )
    # Knock events
    store.record_knock_event(sid, 2, rpm=5500, boost_psi=18.0, gear=3, iam=0.95)
    store.record_knock_event(sid, 1, rpm=5200, boost_psi=17.5, gear=3, iam=0.93)
    # Surface transitions
    store.record_surface_transition(sid, "DRY", "WET", 5.0, 4.0)
    store.record_surface_transition(sid, "WET", "COLD", 2.0, 1.5)
    # FLIR readings
    for _ in range(10):
        store.record_flir_temps(sid, 4.0, 3.5, 4.2, "COLD")
    # Patterns
    store.record_pattern(sid, "ice_risk_trending", "warning", 1.5,
                         {"road_temp": 3.5, "dew_point": 2.0})
    # Alerts
    store.record_alert(sid, "oil_pressure_low", "warning", "Oil low", 22.0)

    store.end_session(sid)
    return sid


class TestBuildSessionSummary:
    def test_summary_has_telemetry(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert summary["telemetry_rows"] == 20
        assert "rpm" in summary
        assert "coolant_c" in summary

    def test_summary_has_knock_events(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert summary["knock_events"]["count"] == 2
        assert summary["knock_events"]["total_knocks"] == 3

    def test_summary_has_surface_transitions(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert len(summary["surface_transitions"]) == 2
        assert summary["surface_transitions"][0]["from"] == "DRY"
        assert summary["surface_transitions"][0]["to"] == "WET"

    def test_summary_has_flir(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert summary["flir"]["readings"] == 10

    def test_summary_has_patterns(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert len(summary["patterns"]) == 1
        assert summary["patterns"][0]["type"] == "ice_risk_trending"

    def test_summary_has_alerts(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert "oil_pressure_low" in summary["alerts"]

    def test_summary_has_session_metadata(self, store, populated_session):
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(populated_session)
        assert summary["session_name"] == "Test Drive"
        assert summary["route_tag"] == "test-route"

    def test_empty_session_has_no_telemetry(self, store):
        sid = store.start_session()
        store.end_session(sid)
        debrief = ParkedDebrief(store)
        summary = debrief.build_session_summary(sid)
        assert "telemetry_rows" not in summary


class TestGenerate:
    def test_no_api_key_returns_none(self, store, populated_session):
        debrief = ParkedDebrief(store, api_key="")
        result = debrief.generate(populated_session)
        assert result is None

    def test_empty_session_returns_none(self, store):
        sid = store.start_session()
        store.end_session(sid)
        debrief = ParkedDebrief(store, api_key="test-key")
        result = debrief.generate(sid)
        assert result is None

    @patch("analysis.parked_debrief.urllib.request.urlopen")
    def test_successful_debrief(self, mock_urlopen, store, populated_session):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "1. Knock events at 5500 RPM. 2. Ice risk detected. 3. Oil pressure low."}],
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        debrief = ParkedDebrief(store, api_key="test-key")
        result = debrief.generate(populated_session)

        assert result is not None
        assert "insights" in result
        assert "Knock events" in result["insights"]
        assert result["session_id"] == populated_session

        # Verify summary was stored in DuckDB
        summaries = store._conn.execute(
            "SELECT content, tier FROM summaries WHERE session_id = ?",
            [populated_session],
        ).fetchall()
        assert len(summaries) == 1
        assert summaries[0][1] == "haiku"

    @patch("analysis.parked_debrief.urllib.request.urlopen")
    def test_api_failure_returns_none(self, mock_urlopen, store, populated_session):
        mock_urlopen.side_effect = Exception("Connection refused")

        debrief = ParkedDebrief(store, api_key="test-key")
        result = debrief.generate(populated_session)
        assert result is None
