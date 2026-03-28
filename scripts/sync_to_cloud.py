#!/usr/bin/env python3
"""KiSTI - Sync local data to Nextcloud KiSTI share.

Exports weather data, memory DB, LLM config, and session summaries
to the KiSTI Nextcloud account at cloud.aldc.io.

Usage:
    python3 scripts/sync_to_cloud.py              # Sync all
    python3 scripts/sync_to_cloud.py --weather     # Weather data only
    python3 scripts/sync_to_cloud.py --database    # Memory DB only
    python3 scripts/sync_to_cloud.py --llm         # LLM config only

Requires: rclone configured with 'kisti' remote.
"""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kisti.sync.cloud")

RCLONE_REMOTE = "kisti"
CLOUD_BASE = "Project KiSTI"
DB_PATH = Path("/data/duckdb/kisti.duckdb")
# Fallback for development (workstation)
DEV_DB_PATH = Path("/tmp/kisti_test.duckdb")


def _open_db_readonly(db_path: Path):
    """Open DuckDB read-only, copying if locked by another process."""
    import duckdb
    try:
        return duckdb.connect(str(db_path), read_only=True)
    except Exception:
        # KiSTI likely holds the lock — copy the file and read from copy
        import shutil
        copy_path = Path(tempfile.mkdtemp()) / "kisti_copy.duckdb"
        shutil.copy2(db_path, copy_path)
        log.info("DB locked, reading from copy: %s", copy_path)
        return duckdb.connect(str(copy_path), read_only=True)


def _rclone_copy(local_path: Path, remote_path: str) -> bool:
    """Upload a file or directory to Nextcloud via rclone."""
    try:
        cmd = [
            "rclone", "copy" if local_path.is_dir() else "copyto",
            str(local_path),
            f"{RCLONE_REMOTE}:{remote_path}",
            "--transfers", "2",
            "--retries", "3",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            log.info("Uploaded: %s → %s", local_path.name, remote_path)
            return True
        log.warning("rclone failed: %s", result.stderr.strip())
        return False
    except Exception as exc:
        log.warning("Upload failed: %s", exc)
        return False


def sync_weather(db_path: Path) -> int:
    """Export ambient conditions from DuckDB to Parquet, upload to Nextcloud."""
    try:
        import duckdb
    except ImportError:
        log.error("duckdb not installed")
        return 0

    if not db_path.exists():
        log.info("No DuckDB at %s — skipping weather sync", db_path)
        return 0

    conn = _open_db_readonly(db_path)

    try:
        count = conn.execute("SELECT COUNT(*) FROM ambient_conditions").fetchone()[0]
        if count == 0:
            log.info("No weather data to sync")
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ambient_conditions.parquet"
            conn.execute(
                f"COPY (SELECT * FROM ambient_conditions ORDER BY timestamp) "
                f"TO '{out}' (FORMAT PARQUET)"
            )

            csv_out = Path(tmp) / "ambient_conditions.csv"
            conn.execute(
                f"COPY (SELECT * FROM ambient_conditions ORDER BY timestamp) "
                f"TO '{csv_out}' (FORMAT CSV, HEADER TRUE)"
            )

            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_readings,
                    MIN(timestamp) as first_reading,
                    MAX(timestamp) as last_reading,
                    AVG(temperature_c) as avg_temp_c,
                    MIN(temperature_c) as min_temp_c,
                    MAX(temperature_c) as max_temp_c,
                    AVG(humidity_pct) as avg_humidity,
                    AVG(pressure_hpa) as avg_pressure_hpa,
                    COUNT(change_event) as change_events
                FROM ambient_conditions
            """).fetchone()

            _rclone_copy(out, f"{CLOUD_BASE}/weather/ambient_conditions.parquet")
            _rclone_copy(csv_out, f"{CLOUD_BASE}/weather/ambient_conditions.csv")

            summary = {
                "synced_at": datetime.now(timezone.utc).isoformat(),
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
            summary_path = Path(tmp) / "weather_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2))
            _rclone_copy(summary_path, f"{CLOUD_BASE}/weather/weather_summary.json")

        log.info("Weather sync complete: %d readings", count)
        return count
    finally:
        conn.close()


def sync_database(db_path: Path) -> bool:
    """Copy DuckDB file to Nextcloud for backup."""
    if not db_path.exists():
        log.info("No DuckDB at %s — skipping database sync", db_path)
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    remote_name = f"{CLOUD_BASE}/database/kisti_{timestamp}.duckdb"
    _rclone_copy(db_path, remote_name)

    # Also copy as 'latest'
    _rclone_copy(db_path, f"{CLOUD_BASE}/database/kisti_latest.duckdb")
    log.info("Database sync complete")
    return True


def sync_memories(db_path: Path) -> int:
    """Export edge memories from DuckDB to JSON, upload to Nextcloud."""
    try:
        import duckdb
    except ImportError:
        log.error("duckdb not installed")
        return 0

    if not db_path.exists():
        log.info("No DuckDB at %s — skipping memory sync", db_path)
        return 0

    conn = _open_db_readonly(db_path)

    # Check if memories table exists
    tables = [r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()]
    if "memories" not in tables:
        log.info("No memories table — skipping")
        conn.close()
        return 0

    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    if count == 0:
        log.info("No memories to sync")
        conn.close()
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # Export only team/public memories to the shared folder (RLS)
        # Private memories stay local and sync to Zeus only
        rows = conn.execute(
            "SELECT memory_id, session_id, created_at, updated_at, "
            "memory_type, source, content, tags, importance, visibility, "
            "zeus_memory_id, zeus_version, synced, zeus_enriched "
            "FROM memories "
            "WHERE visibility IN ('team', 'public') "
            "ORDER BY created_at DESC"
        ).fetchall()
        conn.close()

        memories = []
        for r in rows:
            memories.append({
                "memory_id": r[0],
                "session_id": r[1],
                "created_at": str(r[2]),
                "updated_at": str(r[3]),
                "memory_type": r[4],
                "source": r[5],
                "content": r[6],
                "tags": r[7],
                "importance": r[8],
                "visibility": r[9],
                "zeus_memory_id": r[10],
                "zeus_version": r[11],
                "synced": r[12],
                "zeus_enriched": r[13],
            })

        out = Path(tmp) / "memories.json"
        out.write_text(json.dumps(memories, indent=2, default=str))
        _rclone_copy(out, f"{CLOUD_BASE}/memories/memories.json")

    log.info("Memory sync complete: %d memories", count)
    return count


def sync_llm() -> bool:
    """Sync LLM configuration (system prompt, persona, token caps) to Nextcloud."""
    with tempfile.TemporaryDirectory() as tmp:
        # Export current LLM config as reference
        from voice.llm_engine import (
            KISTI_SYSTEM_PROMPT,
            MODE_TOKEN_CAPS,
            MODE_TEMPERATURE,
            PERSONA_RESPONSES,
            DEFAULT_MODEL,
        )

        config = {
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "model": DEFAULT_MODEL,
            "mode_token_caps": MODE_TOKEN_CAPS,
            "mode_temperature": MODE_TEMPERATURE,
            "system_prompt": KISTI_SYSTEM_PROMPT,
            "persona_responses_count": len(PERSONA_RESPONSES),
            "persona_keywords": [
                {"keywords": kws, "response_preview": resp[:80] + "..."}
                for kws, resp in PERSONA_RESPONSES
            ],
        }

        out = Path(tmp) / "llm_config.json"
        out.write_text(json.dumps(config, indent=2))
        _rclone_copy(out, f"{CLOUD_BASE}/llm/llm_config.json")

        # Export build record
        from data.build_record import build_summary, build_detail, BASELINES

        build = {
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "summary": build_summary(),
            "detail": build_detail(),
            "baseline_targets": {
                "oil_idle_warm_low_psi": BASELINES.oil_idle_warm_low,
                "oil_idle_warm_high_psi": BASELINES.oil_idle_warm_high,
                "oil_per_1000_rpm_psi": BASELINES.oil_per_1000_rpm,
                "oil_high_rpm_low_psi": BASELINES.oil_high_rpm_low,
                "oil_high_rpm_high_psi": BASELINES.oil_high_rpm_high,
                "coolant_normal_low_c": BASELINES.coolant_normal_low,
                "coolant_normal_high_c": BASELINES.coolant_normal_high,
                "coolant_alert_c": BASELINES.coolant_alert,
                "iat_above_ambient_normal_c": BASELINES.iat_above_ambient_normal,
                "iat_heat_soak_alert_c": BASELINES.iat_heat_soak_alert,
                "fuel_base_psi": BASELINES.fuel_base_psi,
                "fuel_boost_ratio": BASELINES.fuel_boost_ratio,
                "afr_cruise": BASELINES.afr_cruise,
                "afr_boost_gas_low": BASELINES.afr_boost_gas_low,
                "afr_boost_gas_high": BASELINES.afr_boost_gas_high,
            },
        }

        build_out = Path(tmp) / "build_record.json"
        build_out.write_text(json.dumps(build, indent=2))
        _rclone_copy(build_out, f"{CLOUD_BASE}/llm/build_record.json")

    log.info("LLM config sync complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="KiSTI — Sync data to Nextcloud")
    parser.add_argument("--weather", action="store_true", help="Sync weather data only")
    parser.add_argument("--database", action="store_true", help="Sync DuckDB only")
    parser.add_argument("--memories", action="store_true", help="Sync memories only")
    parser.add_argument("--llm", action="store_true", help="Sync LLM config only")
    parser.add_argument("--db-path", type=str, default=None,
                        help="Override DuckDB path")
    args = parser.parse_args()

    # Find DB
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    if not db_path.exists():
        db_path = DEV_DB_PATH

    sync_all = not (args.weather or args.database or args.memories or args.llm)

    if sync_all or args.weather:
        sync_weather(db_path)

    if sync_all or args.database:
        sync_database(db_path)

    if sync_all or args.memories:
        sync_memories(db_path)

    if sync_all or args.llm:
        sync_llm()

    log.info("All syncs complete")


if __name__ == "__main__":
    main()
