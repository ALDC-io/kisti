"""KiSTI - DuckDB Local Semantic Layer

Embedded columnar database for session recording, telemetry storage,
alerts, and LLM summaries. Designed for local-first operation with
Parquet export for cloud sync to Zeus via Nextcloud.

Schema from JK's Master Architecture Plan v1.0.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("kisti.data.duckdb")

DEFAULT_DB_PATH = Path("/data/duckdb/kisti.duckdb")

# DuckDB schema DDL
SCHEMA_DDL = """
-- Core session tracking
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    driver_id TEXT,
    car_id TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    session_type TEXT,
    si_drive_mode TEXT,
    synced BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,
    session_id TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    name TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT,
    timestamp TIMESTAMP,
    event_type TEXT,
    value DOUBLE,
    metadata JSON
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    session_id TEXT,
    timestamp TIMESTAMP,
    alert_type TEXT,
    severity TEXT,
    message TEXT,
    value DOUBLE,
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS thermal_state (
    timestamp TIMESTAMP,
    session_id TEXT,
    oil_temp DOUBLE,
    coolant_temp DOUBLE,
    ambient_temp DOUBLE,
    brake_fl DOUBLE,
    brake_fr DOUBLE,
    brake_rl DOUBLE,
    brake_rr DOUBLE
);

CREATE TABLE IF NOT EXISTS telemetry (
    timestamp TIMESTAMP,
    session_id TEXT,
    rpm DOUBLE,
    speed_kph DOUBLE,
    gear INTEGER,
    throttle_pct DOUBLE,
    map_kpa DOUBLE,
    lambda_1 DOUBLE,
    oil_psi DOUBLE,
    oil_temp_c DOUBLE,
    coolant_temp DOUBLE,
    iat_c DOUBLE,
    ethanol_pct DOUBLE,
    fuel_pressure_kpa DOUBLE,
    battery_v DOUBLE,
    injector_duty DOUBLE,
    dccd_command_pct DOUBLE,
    steering_angle DOUBLE,
    yaw_rate DOUBLE,
    lateral_g DOUBLE,
    brake_pressure DOUBLE,
    wheel_fl DOUBLE,
    wheel_fr DOUBLE,
    wheel_rl DOUBLE,
    wheel_rr DOUBLE,
    si_drive_mode TEXT,
    surface_state TEXT
);

CREATE TABLE IF NOT EXISTS summaries (
    summary_id TEXT PRIMARY KEY,
    session_id TEXT,
    generated_at TIMESTAMP,
    tier TEXT,
    content TEXT,
    synced BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS driver_profile_cache (
    driver_id TEXT PRIMARY KEY,
    preferences JSON,
    last_synced TIMESTAMP
);

CREATE TABLE IF NOT EXISTS car_profile_cache (
    car_id TEXT PRIMARY KEY,
    configuration JSON,
    last_synced TIMESTAMP
);
"""


def _new_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def _now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


class DuckDBStore:
    """Local DuckDB session store for KiSTI.

    Usage:
        store = DuckDBStore()
        store.open()
        sid = store.start_session(driver_id="jk", car_id="kisti-sti")
        store.record_telemetry(sid, state)
        store.record_alert(sid, alert)
        store.end_session(sid)
        store.close()
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._conn = None

    def open(self) -> None:
        """Open (or create) the DuckDB database and initialize schema."""
        import duckdb  # type: ignore[import-untyped]
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._db_path))
        self._conn.execute(SCHEMA_DDL)
        log.info("DuckDB opened: %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            log.info("DuckDB closed")

    # -------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------

    def start_session(
        self,
        driver_id: str = "default",
        car_id: str = "kisti-sti",
        session_type: str = "street",
        si_drive_mode: str = "Intelligent",
    ) -> str:
        """Start a new recording session. Returns session_id."""
        sid = _new_id()
        self._conn.execute(
            "INSERT INTO sessions (session_id, driver_id, car_id, start_time, session_type, si_drive_mode) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [sid, driver_id, car_id, _now(), session_type, si_drive_mode],
        )
        log.info("Session started: %s (%s)", sid[:8], session_type)
        return sid

    def end_session(self, session_id: str) -> None:
        """End a recording session."""
        self._conn.execute(
            "UPDATE sessions SET end_time = ? WHERE session_id = ?",
            [_now(), session_id],
        )
        log.info("Session ended: %s", session_id[:8])

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session metadata."""
        result = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", [session_id]
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent sessions."""
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", [limit]
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # -------------------------------------------------------------------
    # Telemetry recording
    # -------------------------------------------------------------------

    def record_telemetry(self, session_id: str, state: Any) -> None:
        """Record a telemetry snapshot from DiffState."""
        from model.vehicle_state import DiffState
        if not isinstance(state, DiffState):
            return

        self._conn.execute(
            "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _now(), session_id,
                state.rpm, state.speed_kph, state.gear, state.throttle_pct,
                state.map_kpa, state.lambda_1, state.oil_psi, state.oil_temp_c,
                state.coolant_temp, state.iat_c, state.ethanol_pct,
                state.fuel_pressure_kpa, state.battery_v, state.injector_duty,
                state.dccd_command_pct, state.steering_angle, state.yaw_rate,
                state.lateral_g, state.brake_pressure,
                state.wheel_speed_fl, state.wheel_speed_fr,
                state.wheel_speed_rl, state.wheel_speed_rr,
                state.si_drive_mode.label, state.surface_state.label,
            ],
        )

    def record_thermal(
        self, session_id: str, state: Any,
        brake_fl: float = 0, brake_fr: float = 0,
        brake_rl: float = 0, brake_rr: float = 0,
    ) -> None:
        """Record thermal state snapshot."""
        from model.vehicle_state import DiffState
        if not isinstance(state, DiffState):
            return

        self._conn.execute(
            "INSERT INTO thermal_state VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _now(), session_id,
                state.oil_temp_c, state.coolant_temp, state.iat_c,
                brake_fl, brake_fr, brake_rl, brake_rr,
            ],
        )

    # -------------------------------------------------------------------
    # Events and alerts
    # -------------------------------------------------------------------

    def record_event(
        self, session_id: str, event_type: str,
        value: float = 0.0, metadata: Optional[dict] = None,
    ) -> str:
        """Record a session event (mode change, keypad, voice command)."""
        eid = _new_id()
        import json
        self._conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            [eid, session_id, _now(), event_type, value,
             json.dumps(metadata) if metadata else None],
        )
        return eid

    def record_alert(
        self, session_id: str, alert_type: str, severity: str,
        message: str, value: Optional[float] = None,
    ) -> str:
        """Record an alert."""
        aid = _new_id()
        self._conn.execute(
            "INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)",
            [aid, session_id, _now(), alert_type, severity, message, value],
        )
        return aid

    # -------------------------------------------------------------------
    # Segments
    # -------------------------------------------------------------------

    def start_segment(self, session_id: str, name: str = "") -> str:
        """Mark a new segment (K2 keypad)."""
        seg_id = _new_id()
        self._conn.execute(
            "INSERT INTO segments (segment_id, session_id, start_time, name) VALUES (?, ?, ?, ?)",
            [seg_id, session_id, _now(), name],
        )
        log.info("Segment started: %s (%s)", seg_id[:8], name or "unnamed")
        return seg_id

    def end_segment(self, segment_id: str) -> None:
        """End a segment."""
        self._conn.execute(
            "UPDATE segments SET end_time = ? WHERE segment_id = ?",
            [_now(), segment_id],
        )

    # -------------------------------------------------------------------
    # Summaries
    # -------------------------------------------------------------------

    def save_summary(
        self, session_id: str, content: str, tier: str = "local",
    ) -> str:
        """Save an LLM-generated session summary."""
        sid = _new_id()
        self._conn.execute(
            "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, FALSE)",
            [sid, session_id, _now(), tier, content],
        )
        log.info("Summary saved: %s (tier=%s)", sid[:8], tier)
        return sid

    # -------------------------------------------------------------------
    # Sync support
    # -------------------------------------------------------------------

    def get_unsynced_sessions(self) -> list[dict]:
        """Get sessions that haven't been synced to cloud."""
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE synced = FALSE ORDER BY start_time"
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    def mark_synced(self, session_id: str) -> None:
        """Mark a session as synced."""
        self._conn.execute(
            "UPDATE sessions SET synced = TRUE WHERE session_id = ?",
            [session_id],
        )
        self._conn.execute(
            "UPDATE summaries SET synced = TRUE WHERE session_id = ?",
            [session_id],
        )

    def export_session_parquet(self, session_id: str, output_dir: Path) -> list[Path]:
        """Export a session's telemetry and metadata to Parquet files.

        Returns list of exported file paths (only files with data).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        files = []

        for table in ["telemetry", "thermal_state", "events", "alerts"]:
            # Check if there's data to export
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE session_id = ?", [session_id]
            ).fetchone()[0]
            if count == 0:
                continue

            path = output_dir / f"{session_id}_{table}.parquet"
            # Validate session_id is a UUID to prevent injection
            import uuid as _uuid
            _uuid.UUID(session_id)
            # DuckDB COPY doesn't support prepared params — use validated literal
            self._conn.execute(
                f"COPY (SELECT * FROM {table} WHERE session_id = '{session_id}') "
                f"TO '{path}' (FORMAT PARQUET)"
            )
            files.append(path)
            log.debug("Exported %s (%d rows) → %s", table, count, path)

        return files

    # -------------------------------------------------------------------
    # Storage management
    # -------------------------------------------------------------------

    def purge_synced(self, keep_days: int = 30) -> int:
        """Purge old synced data. NEVER deletes unsynced data.

        Returns number of sessions purged.
        """
        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Subtract days manually (avoid timedelta import)
        import datetime as dt_mod
        cutoff = cutoff - dt_mod.timedelta(days=keep_days)

        # Get sessions to purge
        rows = self._conn.execute(
            "SELECT session_id FROM sessions WHERE synced = TRUE AND end_time < ?",
            [cutoff],
        ).fetchall()

        if not rows:
            return 0

        sids = [r[0] for r in rows]
        count = len(sids)

        for sid in sids:
            for table in ["telemetry", "thermal_state", "events", "alerts", "segments", "summaries"]:
                self._conn.execute(f"DELETE FROM {table} WHERE session_id = ?", [sid])
            self._conn.execute("DELETE FROM sessions WHERE session_id = ?", [sid])

        log.info("Purged %d synced sessions older than %d days", count, keep_days)
        return count

    def db_stats(self) -> dict:
        """Get database statistics."""
        stats = {}
        for table in ["sessions", "telemetry", "thermal_state", "events", "alerts", "segments", "summaries"]:
            count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count

        unsynced = self._conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE synced = FALSE"
        ).fetchone()[0]
        stats["unsynced_sessions"] = unsynced

        return stats
