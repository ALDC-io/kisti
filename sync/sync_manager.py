"""KiSTI - Cloud Sync Manager

Manages data sync from DuckDB → Parquet → Nextcloud → Zeus Memory.
Detects WiFi connectivity and syncs when online.

Sync flow:
  1. Export unsynced sessions to Parquet (telemetry) + JSON (metadata)
  2. Write to /data/sync_queue/
  3. Detect WiFi via NetworkManager (nmcli)
  4. Upload via rclone/Nextcloud WebDAV
  5. Mark sessions as synced in DuckDB
  6. Announce "Session upload complete." (Intelligent mode)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.sync")

SYNC_QUEUE_DIR = Path("/data/sync_queue")
NEXTCLOUD_REMOTE = "nextcloud"  # rclone remote name
NEXTCLOUD_PATH = "KiSTI/sessions"  # Remote path on Nextcloud
SYNC_CHECK_INTERVAL_S = 60  # Check for sync every 60 seconds


@dataclass
class SyncStatus:
    """Current sync status."""
    is_online: bool = False
    pending_sessions: int = 0
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None


class SyncManager(QObject):
    """Manages cloud sync via Nextcloud/rclone.

    Signals:
        sync_complete(int): Number of sessions synced
        sync_status_changed(SyncStatus): Status changed
    """

    sync_complete = Signal(int)
    sync_status_changed = Signal(object)  # SyncStatus

    def __init__(
        self,
        db_store: Optional[object] = None,  # DuckDBStore
        sync_dir: Path = SYNC_QUEUE_DIR,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._store = db_store
        self._sync_dir = sync_dir
        self._status = SyncStatus()

        self._timer = QTimer(self)
        self._timer.setInterval(SYNC_CHECK_INTERVAL_S * 1000)
        self._timer.timeout.connect(self._sync_tick)

    def start(self) -> None:
        """Start sync manager."""
        self._sync_dir.mkdir(parents=True, exist_ok=True)
        self._timer.start()
        log.info("Sync manager started (check every %ds)", SYNC_CHECK_INTERVAL_S)

    def stop(self) -> None:
        self._timer.stop()

    def _sync_tick(self) -> None:
        """Periodic sync check."""
        try:
            online = self._check_connectivity()
            self._status.is_online = online

            if self._store is None:
                return

            # Count pending
            unsynced = self._store.get_unsynced_sessions()
            self._status.pending_sessions = len(unsynced)
            self.sync_status_changed.emit(self._status)

            if not online or not unsynced:
                return

            # Export and sync
            synced_count = 0
            for session in unsynced:
                try:
                    sid = session["session_id"]
                    session_dir = self._sync_dir / sid[:8]
                    session_dir.mkdir(parents=True, exist_ok=True)

                    # Export telemetry to Parquet
                    self._store.export_session_parquet(sid, session_dir)

                    # Export session metadata to JSON
                    meta_path = session_dir / "session.json"
                    meta_path.write_text(json.dumps(session, default=str, indent=2))

                    # Upload via rclone
                    if self._upload_rclone(session_dir, f"{NEXTCLOUD_PATH}/{sid[:8]}"):
                        self._store.mark_synced(sid)
                        synced_count += 1
                        log.info("Session synced: %s", sid[:8])

                        # Clean up local queue
                        self._cleanup_dir(session_dir)

                except Exception as exc:
                    log.warning("Failed to sync session %s: %s", session.get("session_id", "?")[:8], exc)
                    self._status.last_error = str(exc)

            if synced_count > 0:
                self._status.last_sync = datetime.now(timezone.utc)
                self._status.pending_sessions -= synced_count
                self.sync_complete.emit(synced_count)
                self.sync_status_changed.emit(self._status)

        except Exception as exc:
            log.error("Sync tick error: %s", exc, exc_info=True)
            self._status.last_error = str(exc)

    @staticmethod
    def _check_connectivity() -> bool:
        """Check WiFi/network connectivity via nmcli."""
        try:
            result = subprocess.run(
                ["nmcli", "networking", "connectivity", "check"],
                capture_output=True, text=True, timeout=10,
            )
            connectivity = result.stdout.strip()
            return connectivity in ("full", "limited")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # nmcli not available — try pinging
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", "cloud.aldc.io"],
                    capture_output=True, timeout=5,
                )
                return result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

    @staticmethod
    def _upload_rclone(local_dir: Path, remote_path: str) -> bool:
        """Upload a directory to Nextcloud via rclone."""
        try:
            result = subprocess.run(
                [
                    "rclone", "copy",
                    str(local_dir),
                    f"{NEXTCLOUD_REMOTE}:{remote_path}",
                    "--transfers", "2",
                    "--retries", "3",
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return True
            log.warning("rclone upload failed: %s", result.stderr)
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            log.warning("rclone not available or timed out: %s", exc)
            return False

    @staticmethod
    def _cleanup_dir(path: Path) -> None:
        """Remove a sync queue directory after successful upload."""
        try:
            for f in path.iterdir():
                f.unlink()
            path.rmdir()
        except OSError as exc:
            log.debug("Cleanup failed for %s: %s", path, exc)

    @property
    def status(self) -> SyncStatus:
        return self._status

    def force_sync(self) -> None:
        """Force an immediate sync check."""
        self._sync_tick()
