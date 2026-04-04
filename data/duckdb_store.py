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
    session_name TEXT,
    route_tag TEXT,
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
    surface_state TEXT,
    gps_latitude DOUBLE,
    gps_longitude DOUBLE,
    gps_altitude_m DOUBLE,
    gps_speed_mps DOUBLE,
    gps_heading DOUBLE,
    gps_satellites INTEGER,
    imu_accel_x DOUBLE,
    imu_accel_y DOUBLE,
    imu_accel_z DOUBLE,
    imu_gyro_x DOUBLE,
    imu_gyro_y DOUBLE,
    imu_gyro_z DOUBLE,
    lap_number INTEGER,
    sector_index INTEGER,
    lap_distance_m DOUBLE
);

CREATE TABLE IF NOT EXISTS ambient_conditions (
    timestamp TIMESTAMP,
    temperature_c DOUBLE,
    humidity_pct DOUBLE,
    pressure_hpa DOUBLE,
    density_altitude_ft DOUBLE,
    dew_point_c DOUBLE,
    change_event TEXT,
    change_delta DOUBLE
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

-- Maintenance / service event history
CREATE TABLE IF NOT EXISTS service_events (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    event_type TEXT,
    odometer_km INTEGER,
    engine_km INTEGER,
    description TEXT NOT NULL,
    parts TEXT,
    cost DOUBLE,
    provider TEXT,
    notes TEXT,
    synced BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS voice_latency (
    timestamp TIMESTAMP,
    session_id TEXT,
    stt_ms INTEGER,
    llm_ms INTEGER,
    tts_ms INTEGER,
    total_ms INTEGER,
    source TEXT,
    query_text TEXT
);

-- Race analysis: track definitions
CREATE TABLE IF NOT EXISTS tracks (
    track_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    center_lat DOUBLE,
    center_lon DOUBLE,
    radius_m DOUBLE DEFAULT 2000.0,
    track_type TEXT DEFAULT 'circuit',
    start_lat1 DOUBLE,
    start_lon1 DOUBLE,
    start_lat2 DOUBLE,
    start_lon2 DOUBLE,
    country TEXT,
    region TEXT,
    length_m DOUBLE,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP
);

-- Race analysis: sector boundaries per track
CREATE TABLE IF NOT EXISTS track_sectors (
    sector_id TEXT PRIMARY KEY,
    track_id TEXT,
    sector_index INTEGER,
    line_lat1 DOUBLE,
    line_lon1 DOUBLE,
    line_lat2 DOUBLE,
    line_lon2 DOUBLE,
    name TEXT
);

-- Race analysis: lap timing records
CREATE TABLE IF NOT EXISTS lap_times (
    lap_id TEXT PRIMARY KEY,
    session_id TEXT,
    track_id TEXT,
    lap_number INTEGER,
    lap_time_s DOUBLE,
    sector_times JSON,
    delta_vs_best DOUBLE,
    theoretical_best_s DOUBLE,
    timestamp TIMESTAMP
);

-- Data collection: FLIR thermal readings at 3Hz
CREATE TABLE IF NOT EXISTS flir_readings (
    timestamp TIMESTAMP,
    session_id TEXT,
    road_temp_left DOUBLE,
    road_temp_center DOUBLE,
    road_temp_right DOUBLE,
    surface_state TEXT,
    warm_object_detected BOOLEAN DEFAULT FALSE
);

-- Data collection: surface state transitions
CREATE TABLE IF NOT EXISTS surface_transitions (
    transition_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    session_id TEXT,
    from_state TEXT,
    to_state TEXT,
    road_temp_c DOUBLE,
    dew_point_c DOUBLE,
    delta_c DOUBLE
);

-- Data collection: knock events for tune health tracking
CREATE TABLE IF NOT EXISTS knock_events (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    session_id TEXT,
    knock_count_delta INTEGER,
    rpm DOUBLE,
    boost_psi DOUBLE,
    gear INTEGER,
    iam DOUBLE
);

-- Data collection: pattern detection engine output
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    session_id TEXT,
    pattern_type TEXT,
    severity TEXT,
    value DOUBLE,
    context_json JSON
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
        session_name: str = "",
        route_tag: str = "",
    ) -> str:
        """Start a new recording session. Returns session_id."""
        sid = _new_id()
        self._conn.execute(
            "INSERT INTO sessions (session_id, driver_id, car_id, start_time, "
            "session_type, si_drive_mode, session_name, route_tag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [sid, driver_id, car_id, _now(), session_type, si_drive_mode,
             session_name or None, route_tag or None],
        )
        log.info("Session started: %s (%s) name=%s route=%s",
                 sid[:8], session_type, session_name or "-", route_tag or "-")
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
            "INSERT INTO telemetry VALUES ("
            + ", ".join(["?"] * 42) + ")",
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
                state.gps_latitude, state.gps_longitude,
                state.gps_altitude_m, state.gps_speed_mps,
                state.gps_heading, state.gps_satellites,
                state.imu_accel_x, state.imu_accel_y, state.imu_accel_z,
                state.imu_gyro_x, state.imu_gyro_y, state.imu_gyro_z,
                getattr(state, 'lap_count', None),
                getattr(state, 'current_sector', None),
                getattr(state, 'lap_distance_m', None),
            ],
        )

    def record_ambient(
        self,
        temperature_c: float,
        humidity_pct: float,
        pressure_hpa: float,
        density_altitude_ft: float,
        dew_point_c: float,
        change_event: Optional[str] = None,
        change_delta: Optional[float] = None,
    ) -> None:
        """Record an ambient conditions snapshot (independent of ECU session)."""
        self._conn.execute(
            "INSERT INTO ambient_conditions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _now(), temperature_c, humidity_pct, pressure_hpa,
                density_altitude_ft, dew_point_c,
                change_event, change_delta,
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
    # Data collection: FLIR, surface transitions, knock events, patterns
    # -------------------------------------------------------------------

    def record_flir_temps(
        self,
        session_id: str,
        road_temp_left: float,
        road_temp_center: float,
        road_temp_right: float,
        surface_state: str = "",
        warm_object_detected: bool = False,
    ) -> None:
        """Record FLIR thermal reading (called at 3Hz)."""
        self._conn.execute(
            "INSERT INTO flir_readings VALUES (?, ?, ?, ?, ?, ?, ?)",
            [_now(), session_id, road_temp_left, road_temp_center,
             road_temp_right, surface_state, warm_object_detected],
        )

    def record_surface_transition(
        self,
        session_id: str,
        from_state: str,
        to_state: str,
        road_temp_c: float = 0.0,
        dew_point_c: float = 0.0,
    ) -> str:
        """Record a surface state transition (DRY→WET, etc)."""
        tid = _new_id()
        delta = road_temp_c - dew_point_c if road_temp_c != 0.0 else 0.0
        self._conn.execute(
            "INSERT INTO surface_transitions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [tid, _now(), session_id, from_state, to_state,
             road_temp_c, dew_point_c, delta],
        )
        log.debug("Surface transition: %s → %s (delta=%.1f°C)", from_state, to_state, delta)
        return tid

    def record_knock_event(
        self,
        session_id: str,
        knock_count_delta: int,
        rpm: float = 0.0,
        boost_psi: float = 0.0,
        gear: int = 0,
        iam: float = 1.0,
    ) -> str:
        """Record a knock event for tune health tracking."""
        eid = _new_id()
        self._conn.execute(
            "INSERT INTO knock_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [eid, _now(), session_id, knock_count_delta, rpm, boost_psi, gear, iam],
        )
        log.info("Knock event: delta=%d rpm=%.0f boost=%.1f gear=%d IAM=%.3f",
                 knock_count_delta, rpm, boost_psi, gear, iam)
        return eid

    def record_pattern(
        self,
        session_id: str,
        pattern_type: str,
        severity: str = "info",
        value: float = 0.0,
        context: Optional[dict] = None,
    ) -> str:
        """Record a detected pattern from the pattern engine."""
        pid = _new_id()
        import json
        self._conn.execute(
            "INSERT INTO patterns VALUES (?, ?, ?, ?, ?, ?, ?)",
            [pid, _now(), session_id, pattern_type, severity, value,
             json.dumps(context) if context else None],
        )
        log.debug("Pattern detected: %s severity=%s value=%.2f", pattern_type, severity, value)
        return pid

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

        for table in ["telemetry", "thermal_state", "events", "alerts", "lap_times",
                      "flir_readings", "surface_transitions", "knock_events", "patterns"]:
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
            for table in ["telemetry", "thermal_state", "events", "alerts", "segments",
                          "summaries", "flir_readings", "surface_transitions",
                          "knock_events", "patterns"]:
                self._conn.execute(f"DELETE FROM {table} WHERE session_id = ?", [sid])
            self._conn.execute("DELETE FROM sessions WHERE session_id = ?", [sid])

        log.info("Purged %d synced sessions older than %d days", count, keep_days)
        return count

    def export_weather_parquet(self, output_dir: Path) -> Optional[Path]:
        """Export ambient_conditions to Parquet for cloud sync.

        Returns the Parquet path, or None if no data.
        """
        count = self._conn.execute(
            "SELECT COUNT(*) FROM ambient_conditions"
        ).fetchone()[0]
        if count == 0:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "ambient_conditions.parquet"
        self._conn.execute(
            f"COPY (SELECT * FROM ambient_conditions ORDER BY timestamp) "
            f"TO '{path}' (FORMAT PARQUET)"
        )

        # Also export CSV for easy viewing
        csv_path = output_dir / "ambient_conditions.csv"
        self._conn.execute(
            f"COPY (SELECT * FROM ambient_conditions ORDER BY timestamp) "
            f"TO '{csv_path}' (FORMAT CSV, HEADER TRUE)"
        )

        # Summary JSON
        stats = self._conn.execute("""
            SELECT
                COUNT(*) as total,
                MIN(timestamp) as first_ts,
                MAX(timestamp) as last_ts,
                AVG(temperature_c) as avg_temp,
                MIN(temperature_c) as min_temp,
                MAX(temperature_c) as max_temp,
                AVG(humidity_pct) as avg_humidity,
                AVG(pressure_hpa) as avg_pressure,
                COUNT(change_event) as changes
            FROM ambient_conditions
        """).fetchone()

        import json
        summary = {
            "exported_at": _now().isoformat(),
            "total_readings": stats[0],
            "first_reading": str(stats[1]),
            "last_reading": str(stats[2]),
            "avg_temp_c": round(stats[3], 1) if stats[3] else None,
            "min_temp_c": round(stats[4], 1) if stats[4] else None,
            "max_temp_c": round(stats[5], 1) if stats[5] else None,
            "avg_humidity_pct": round(stats[6], 1) if stats[6] else None,
            "avg_pressure_hpa": round(stats[7], 1) if stats[7] else None,
            "change_events": stats[8],
        }
        summary_path = output_dir / "weather_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))

        log.info("Weather export: %d readings → %s", count, output_dir)
        return path

    def db_stats(self) -> dict:
        """Get database statistics."""
        stats = {}
        for table in ["sessions", "telemetry", "thermal_state", "events", "alerts",
                       "segments", "summaries", "ambient_conditions", "service_events",
                       "voice_latency", "tracks", "lap_times",
                       "flir_readings", "surface_transitions", "knock_events", "patterns"]:
            count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count

        unsynced = self._conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE synced = FALSE"
        ).fetchone()[0]
        stats["unsynced_sessions"] = unsynced

        return stats

    # -------------------------------------------------------------------
    # Voice pipeline latency recording
    # -------------------------------------------------------------------

    def record_voice_latency(
        self,
        session_id: str,
        stt_ms: int,
        llm_ms: int,
        tts_ms: int,
        total_ms: int,
        source: str = "",
        query_text: str = "",
    ) -> None:
        """Record voice pipeline latency trace."""
        self._conn.execute(
            "INSERT INTO voice_latency VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [_now(), session_id, stt_ms, llm_ms, tts_ms, total_ms, source, query_text],
        )

    # -------------------------------------------------------------------
    # Service event logging (maintenance history)
    # -------------------------------------------------------------------

    def record_service_event(
        self,
        event_type: str,
        description: str,
        odometer_km: int = 0,
        engine_km: int = 0,
        parts: Optional[str] = None,
        cost: Optional[float] = None,
        provider: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Record a maintenance/service event. Returns event_id.

        event_type: 'oil_change', 'brake_service', 'part_install',
                    'tire_rotation', 'inspection', 'repair', 'tune', etc.
        """
        event_id = _new_id()
        self._conn.execute(
            """INSERT INTO service_events (
                event_id, timestamp, event_type, odometer_km, engine_km,
                description, parts, cost, provider, notes, synced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)""",
            [event_id, _now(), event_type, odometer_km, engine_km,
             description, parts, cost, provider, notes],
        )
        log.info("Service event recorded: %s [%s] %s", event_id[:8], event_type, description[:50])
        return event_id

    def get_service_events(self, limit: int = 20) -> list[dict]:
        """Get recent service events, newest first."""
        rows = self._conn.execute(
            "SELECT event_id, timestamp, event_type, odometer_km, engine_km, "
            "description, parts, cost, provider, notes, synced "
            "FROM service_events ORDER BY timestamp DESC LIMIT ?",
            [limit],
        ).fetchall()
        return [
            {
                "event_id": r[0], "timestamp": r[1], "event_type": r[2],
                "odometer_km": r[3], "engine_km": r[4], "description": r[5],
                "parts": r[6], "cost": r[7], "provider": r[8],
                "notes": r[9], "synced": r[10],
            }
            for r in rows
        ]

    # -------------------------------------------------------------------
    # Lap timing
    # -------------------------------------------------------------------

    def record_lap_time(
        self,
        session_id: str,
        track_id: str,
        lap_number: int,
        lap_time_s: float,
        sector_times: Optional[list[float]] = None,
        delta_vs_best: Optional[float] = None,
        theoretical_best_s: Optional[float] = None,
    ) -> str:
        """Record a completed lap time with optional sector splits."""
        import json
        lap_id = _new_id()
        self._conn.execute(
            "INSERT INTO lap_times VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                lap_id, session_id, track_id, lap_number, lap_time_s,
                json.dumps(sector_times) if sector_times else None,
                delta_vs_best, theoretical_best_s, _now(),
            ],
        )
        log.info(
            "Lap %d recorded: %.3fs (delta: %s)",
            lap_number, lap_time_s,
            f"{delta_vs_best:+.3f}s" if delta_vs_best is not None else "N/A",
        )
        return lap_id

    def get_session_laps(self, session_id: str) -> list[dict]:
        """Get all lap times for a session, ordered by lap number."""
        import json
        rows = self._conn.execute(
            "SELECT * FROM lap_times WHERE session_id = ? ORDER BY lap_number",
            [session_id],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        laps = []
        for row in rows:
            lap = dict(zip(cols, row))
            if lap.get("sector_times") and isinstance(lap["sector_times"], str):
                lap["sector_times"] = json.loads(lap["sector_times"])
            laps.append(lap)
        return laps

    def get_track_best_laps(self, track_id: str, limit: int = 10) -> list[dict]:
        """Get best lap times for a track across all sessions."""
        import json
        rows = self._conn.execute(
            "SELECT * FROM lap_times WHERE track_id = ? ORDER BY lap_time_s ASC LIMIT ?",
            [track_id, limit],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        laps = []
        for row in rows:
            lap = dict(zip(cols, row))
            if lap.get("sector_times") and isinstance(lap["sector_times"], str):
                lap["sector_times"] = json.loads(lap["sector_times"])
            laps.append(lap)
        return laps

    def get_service_history_context(self, max_events: int = 5) -> str:
        """Build service history string for LLM context."""
        events = self.get_service_events(limit=max_events)
        if not events:
            return ""
        lines = []
        for e in events:
            date_str = e["timestamp"].strftime("%Y-%m-%d") if hasattr(e["timestamp"], "strftime") else str(e["timestamp"])[:10]
            parts_str = f" Parts: {e['parts']}" if e.get("parts") else ""
            lines.append(f"- {date_str} [{e['event_type']}] {e['description']}{parts_str}")
        return "\n".join(lines)
