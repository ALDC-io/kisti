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

# Ensure repo is in path for module imports (allows running from any directory)
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kisti.sync.cloud")

RCLONE_REMOTE = "kisti"
CLOUD_BASE = "Project KiSTI"
DB_PATH = Path("/data/duckdb/kisti.duckdb")
# Fallback for development (workstation)
DEV_DB_PATH = Path("/tmp/kisti_test.duckdb")
SYNC_QUEUE_DIR = Path("/data/sync_queue")


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


def sync_flir(db_path: Path) -> int:
    """Export FLIR thermal readings + surface transitions to Nextcloud."""
    try:
        import duckdb
    except ImportError:
        log.error("duckdb not installed")
        return 0

    if not db_path.exists():
        log.info("No DuckDB at %s — skipping FLIR sync", db_path)
        return 0

    conn = _open_db_readonly(db_path)

    try:
        # Check table exists
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()]
        if "flir_readings" not in tables:
            log.info("No flir_readings table — skipping")
            conn.close()
            return 0

        count = conn.execute("SELECT COUNT(*) FROM flir_readings").fetchone()[0]
        if count == 0:
            log.info("No FLIR data to sync")
            conn.close()
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            # Export FLIR readings
            out = Path(tmp) / "flir_readings.parquet"
            conn.execute(
                f"COPY (SELECT * FROM flir_readings ORDER BY timestamp) "
                f"TO '{out}' (FORMAT PARQUET)"
            )
            csv_out = Path(tmp) / "flir_readings.csv"
            conn.execute(
                f"COPY (SELECT * FROM flir_readings ORDER BY timestamp) "
                f"TO '{csv_out}' (FORMAT CSV, HEADER TRUE)"
            )
            _rclone_copy(out, f"{CLOUD_BASE}/flir/flir_readings.parquet")
            _rclone_copy(csv_out, f"{CLOUD_BASE}/flir/flir_readings.csv")

            # Export surface transitions if available
            if "surface_transitions" in tables:
                trans_count = conn.execute("SELECT COUNT(*) FROM surface_transitions").fetchone()[0]
                if trans_count > 0:
                    trans_out = Path(tmp) / "surface_transitions.parquet"
                    conn.execute(
                        f"COPY (SELECT * FROM surface_transitions ORDER BY timestamp) "
                        f"TO '{trans_out}' (FORMAT PARQUET)"
                    )
                    _rclone_copy(trans_out, f"{CLOUD_BASE}/flir/surface_transitions.parquet")

            # Summary stats
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_readings,
                    MIN(timestamp) as first_reading,
                    MAX(timestamp) as last_reading,
                    AVG(road_temp_center) as avg_center_c,
                    MIN(road_temp_center) as min_center_c,
                    MAX(road_temp_center) as max_center_c,
                    SUM(CASE WHEN warm_object_detected THEN 1 ELSE 0 END) as warm_detections,
                    COUNT(DISTINCT surface_state) as unique_states
                FROM flir_readings
            """).fetchone()

            summary = {
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "total_readings": stats[0],
                "first_reading": str(stats[1]),
                "last_reading": str(stats[2]),
                "avg_road_temp_center_c": round(stats[3], 1) if stats[3] else None,
                "min_road_temp_center_c": round(stats[4], 1) if stats[4] else None,
                "max_road_temp_center_c": round(stats[5], 1) if stats[5] else None,
                "warm_object_detections": stats[6],
                "unique_surface_states": stats[7],
            }
            summary_path = Path(tmp) / "flir_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2))
            _rclone_copy(summary_path, f"{CLOUD_BASE}/flir/flir_summary.json")

        log.info("FLIR sync complete: %d readings", count)
        return count
    finally:
        conn.close()


def sync_llm() -> bool:
    """Sync LLM configuration (system prompt, persona, token caps) to Nextcloud."""
    try:
        from voice.llm_engine import (
            KISTI_SYSTEM_PROMPT,
            MODE_TOKEN_CAPS,
            MODE_TEMPERATURE,
            PERSONA_RESPONSES,
            DEFAULT_MODEL,
        )
    except ImportError as exc:
        log.warning("Could not import LLM config: %s — skipping LLM sync", exc)
        return False

    with tempfile.TemporaryDirectory() as tmp:
        # Export current LLM config as reference

        config = {
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "model": DEFAULT_MODEL,
            "mode_token_caps": MODE_TOKEN_CAPS,
            "mode_temperature": MODE_TEMPERATURE,
            "system_prompt": KISTI_SYSTEM_PROMPT,
            "persona_responses_count": len(PERSONA_RESPONSES),
            "persona_keywords": [
                {"keywords": kws, "response_preview": resp[:80] + "...", "category": cat}
                for kws, resp, cat in PERSONA_RESPONSES
            ],
        }

        out = Path(tmp) / "llm_config.json"
        out.write_text(json.dumps(config, indent=2))
        _rclone_copy(out, f"{CLOUD_BASE}/llm/llm_config.json")

        # Export build record
        try:
            from data.build_record import build_summary, build_detail, BASELINES
        except ImportError:
            log.warning("Could not import build record — skipping")
            log.info("LLM config sync complete")
            return True

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


NAS_HOST = "192.168.22.220"
NAS_SHARE = "LL824"
NAS_BACKUP_PATH = "Backup/KiSTI"
NAS_CREDS_FILE = "/etc/kisti-nas.creds"
# Jetson network interfaces
WIFI_IFACE = "wlP1p1s0"
LAN_IFACE = "enP8p1s0"


def _nas_reachable(iface: str) -> bool:
    """Ping NAS using a specific network interface."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "-I", iface, NAS_HOST],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _nas_pick_iface() -> str | None:
    """Return the first reachable interface (WiFi preferred) or None."""
    for candidate in (WIFI_IFACE, LAN_IFACE):
        if _nas_reachable(candidate):
            log.info("NAS reachable via %s", candidate)
            return candidate
    log.warning("NAS %s unreachable on both interfaces", NAS_HOST)
    return None


def _nas_put(local_path: Path, remote_subpath: str, timeout: int = 300) -> bool:
    """Upload a single file to NAS at Backup/KiSTI/<remote_subpath>/<filename>.

    Creates the remote subdirectory if needed.  Returns True on success.
    """
    remote_dir = f"{NAS_BACKUP_PATH}/{remote_subpath}"
    remote_dest = f"{remote_dir}/{local_path.name}"
    smb_cmds = f'mkdir "{remote_dir}"; put "{local_path}" "{remote_dest}"'
    try:
        cmd = [
            "smbclient",
            f"//{NAS_HOST}/{NAS_SHARE}",
            "-A", NAS_CREDS_FILE,
            "-c", smb_cmds,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            log.info("NAS upload OK: %s → //%s/%s/%s", local_path.name, NAS_HOST, NAS_SHARE, remote_dest)
            return True
        log.warning("NAS upload failed (%s): %s", local_path.name,
                    result.stderr.strip() or result.stdout.strip())
        return False
    except Exception as exc:
        log.warning("NAS upload error (%s): %s", local_path.name, exc)
        return False


def sync_nas(db_path: Path) -> bool:
    """Copy DuckDB snapshot to UNAS-Pro-8 NAS via SMB. WiFi-first, LAN fallback. Best-effort."""
    if not db_path.exists():
        log.info("No DuckDB at %s — skipping NAS sync", db_path)
        return False

    iface = _nas_pick_iface()
    if iface is None:
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    remote_filename = f"kisti_{timestamp}.duckdb"

    try:
        remote_dest = f"{NAS_BACKUP_PATH}/{remote_filename}"
        cmd = [
            "smbclient",
            f"//{NAS_HOST}/{NAS_SHARE}",
            "-A", NAS_CREDS_FILE,
            "-c", f'put "{db_path}" "{remote_dest}"',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            log.info("NAS sync complete: %s → //%s/%s/%s",
                     db_path.name, NAS_HOST, NAS_SHARE, remote_dest)
            return True
        log.warning("NAS sync failed: %s", result.stderr.strip() or result.stdout.strip())
        return False
    except Exception as exc:
        log.warning("NAS sync error: %s", exc)
        return False


def sync_nas_sessions(sync_queue: Path = SYNC_QUEUE_DIR) -> bool:
    """Tar the session/sensor Parquet export queue and upload to NAS Backup/KiSTI/sessions/.

    Best-effort — skips silently if NAS unreachable or queue is empty.
    """
    if not sync_queue.exists() or not any(sync_queue.iterdir()):
        log.info("sync_queue empty or absent — skipping NAS sessions backup")
        return False

    iface = _nas_pick_iface()
    if iface is None:
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"sessions_{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / archive_name
        try:
            result = subprocess.run(
                ["tar", "-czf", str(archive_path), "-C", str(sync_queue.parent), sync_queue.name],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                log.warning("tar sessions failed: %s", result.stderr.strip())
                return False
            size_mb = archive_path.stat().st_size / 1024 / 1024
            log.info("sessions archive: %.1f MB", size_mb)
            return _nas_put(archive_path, "sessions")
        except Exception as exc:
            log.warning("NAS sessions backup error: %s", exc)
            return False


def sync_nas_image() -> bool:
    """Weekly system image backup: tar repos/kisti + tracks + .env → NAS Backup/KiSTI/images/.

    Best-effort — skips silently if NAS unreachable.
    """
    iface = _nas_pick_iface()
    if iface is None:
        return False

    home = Path("/home/aldc")
    targets = [
        home / "repos" / "kisti",
        home / "tracks",
        home / ".env",
    ]
    # Only include paths that actually exist
    existing = [str(t) for t in targets if t.exists()]
    if not existing:
        log.info("No image backup targets found — skipping")
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"kisti_image_{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / archive_name
        try:
            result = subprocess.run(
                ["tar", "-czf", str(archive_path), "--exclude=__pycache__",
                 "--exclude=*.pyc", "--exclude=.git"] + existing,
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                log.warning("tar image failed: %s", result.stderr.strip())
                return False
            size_mb = archive_path.stat().st_size / 1024 / 1024
            log.info("image archive: %.1f MB", size_mb)
            return _nas_put(archive_path, "images", timeout=600)
        except Exception as exc:
            log.warning("NAS image backup error: %s", exc)
            return False


def main():
    parser = argparse.ArgumentParser(description="KiSTI — Sync data to Nextcloud")
    parser.add_argument("--weather", action="store_true", help="Sync weather data only")
    parser.add_argument("--database", action="store_true", help="Sync DuckDB only")
    parser.add_argument("--memories", action="store_true", help="Sync memories only")
    parser.add_argument("--llm", action="store_true", help="Sync LLM config only")
    parser.add_argument("--flir", action="store_true", help="Sync FLIR thermal data only")
    parser.add_argument("--nas", action="store_true", help="Sync DuckDB to NAS only")
    parser.add_argument("--nas-sessions", action="store_true",
                        help="Sync session/sensor Parquet queue to NAS only")
    parser.add_argument("--nas-image", action="store_true",
                        help="Weekly system image backup to NAS only")
    parser.add_argument("--db-path", type=str, default=None,
                        help="Override DuckDB path")
    args = parser.parse_args()

    # Find DB
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    if not db_path.exists():
        db_path = DEV_DB_PATH

    sync_all = not (args.weather or args.database or args.memories or args.llm
                    or args.flir or args.nas or args.nas_sessions or args.nas_image)

    if sync_all or args.weather:
        sync_weather(db_path)

    if sync_all or args.flir:
        sync_flir(db_path)

    if sync_all or args.database:
        sync_database(db_path)

    if sync_all or args.memories:
        sync_memories(db_path)

    if sync_all or args.llm:
        sync_llm()

    if sync_all or args.nas:
        sync_nas(db_path)

    if sync_all or args.nas_sessions:
        sync_nas_sessions()

    if args.nas_image:
        sync_nas_image()

    log.info("All syncs complete")


if __name__ == "__main__":
    main()
