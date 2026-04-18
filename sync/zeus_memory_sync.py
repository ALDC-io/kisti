"""KiSTI - Zeus Memory Sync Worker

Pushes local memories to Zeus cloud API when WiFi available.
Pulls enriched data back from Zeus to update local memories.

Zeus API:
  POST   https://zeus.aldc.io/api/memory      — push new memories
  GET    https://zeus.aldc.io/api/memory/edge  — pull enriched memories
  Header: X-API-Key: <api_key>

Independent of SyncManager (Nextcloud/Parquet sessions).
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.sync.zeus")

ZEUS_API_BASE = "https://zeus.aldc.io/api"
ZEUS_SYNC_INTERVAL_S = 120  # 2 minutes
DEVICE_ID = "kisti-sti-001"
CONNECTIVITY_TIMEOUT_S = 10


@dataclass
class ZeusSyncStatus:
    """Immutable sync status snapshot."""
    is_online: bool = False
    pending_push: int = 0
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None


class ZeusMemorySyncWorker(QObject):
    """Periodic sync between edge memories and Zeus cloud.

    Push flow: local unsynced memories → POST to Zeus → mark synced.
    Pull flow: GET enriched memories from Zeus → apply locally.
    """

    sync_complete = Signal(int)         # memories pushed
    enrichment_received = Signal(int)   # memories enriched from Zeus
    sync_status_changed = Signal(object)  # ZeusSyncStatus

    def __init__(
        self,
        edge_memory: object,
        api_key: str,
        api_base: str = ZEUS_API_BASE,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._memory = edge_memory
        self._api_key = api_key
        self._api_base = api_base
        self._timer: Optional[QTimer] = None
        self._status = ZeusSyncStatus()
        self._last_pull_ts: Optional[str] = None  # ISO timestamp of last pull

    def start(self) -> None:
        """Begin periodic sync."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sync_tick)
        self._timer.start(ZEUS_SYNC_INTERVAL_S * 1000)
        log.info("Zeus memory sync started (every %ds)", ZEUS_SYNC_INTERVAL_S)

    def stop(self) -> None:
        """Stop periodic sync."""
        if self._timer:
            self._timer.stop()
            self._timer = None
        log.info("Zeus memory sync stopped")

    def force_sync(self) -> None:
        """Trigger immediate sync."""
        self._sync_tick()

    @property
    def status(self) -> ZeusSyncStatus:
        return self._status

    def _sync_tick(self) -> None:
        """One sync cycle: check connectivity → push → pull."""
        try:
            if not self._check_connectivity():
                self._update_status(is_online=False)
                return

            self._update_status(is_online=True)

            pushed = self._push_memories()
            if pushed > 0:
                self.sync_complete.emit(pushed)

            enriched = self._pull_enrichments()
            if enriched > 0:
                self.enrichment_received.emit(enriched)

            self._update_status(
                last_sync=datetime.now(timezone.utc),
                last_error=None,
            )

        except Exception as exc:
            log.warning("Zeus sync tick failed: %s", exc)
            self._update_status(last_error=str(exc))

    def _push_memories(self) -> int:
        """POST unsynced memories to Zeus. Returns count pushed.

        The Zeus API accepts one memory per POST (flat payload). Each request
        returns ``{"status": "ok", "success": true, "memory_id": "<uuid>",
        "tenant_id": "<uuid>", "content_summary": "..."}``. We iterate over
        unsynced rows, marking each synced as soon as its POST succeeds so a
        mid-batch network failure doesn't re-push already-accepted entries.
        """
        unsynced = self._memory.get_unsynced_memories()
        if not unsynced:
            return 0

        count = 0
        for m in unsynced:
            created_at = m["created_at"]
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            else:
                created_at = str(created_at)

            payload = {
                "source": "kisti-edge",
                "device_id": DEVICE_ID,
                "edge_memory_id": m["memory_id"],
                "content": m["content"],
                "memory_type": m.get("memory_type", "manual"),
                "tags": m.get("tags", ""),
                "importance": m.get("importance", 0.5),
                "session_id": m.get("session_id"),
                "created_at": created_at,
            }

            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self._api_base}/memory",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self._api_key,
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())

                zeus_id = data.get("memory_id")
                if data.get("success") and zeus_id:
                    self._memory.mark_synced(m["memory_id"], zeus_id)
                    count += 1
                else:
                    log.warning("Zeus push rejected for %s: %s", m["memory_id"], data)

            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                log.warning("Zeus push failed for %s: %s", m["memory_id"], exc)
                # Stop on first hard failure — connectivity likely gone.
                break

        if count:
            log.info("Pushed %d memories to Zeus", count)
        return count

    def _pull_enrichments(self) -> int:
        """GET enriched memories from Zeus. Returns count updated."""
        try:
            url = f"{self._api_base}/memory/edge?device_id={DEVICE_ID}"
            if self._last_pull_ts:
                url += f"&since={self._last_pull_ts}"

            req = urllib.request.Request(
                url,
                headers={"X-API-Key": self._api_key},
                method="GET",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            enrichments = data.get("enrichments", [])
            count = 0
            for item in enrichments:
                edge_id = item.get("edge_memory_id")
                if not edge_id:
                    continue
                self._memory.apply_zeus_enrichment(
                    memory_id=edge_id,
                    content=item.get("content"),
                    tags=item.get("tags"),
                    importance=item.get("importance"),
                    zeus_version=item.get("zeus_version", 1),
                )
                count += 1

            if count:
                log.info("Applied %d enrichments from Zeus", count)
                self._last_pull_ts = datetime.now(timezone.utc).isoformat()

            return count

        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            log.debug("Zeus pull skipped: %s", exc)
            return 0

    def _check_connectivity(self) -> bool:
        """Check WiFi connectivity. Reuses SyncManager's approach."""
        try:
            result = subprocess.run(
                ["nmcli", "networking", "connectivity", "check"],
                capture_output=True, text=True,
                timeout=CONNECTIVITY_TIMEOUT_S,
            )
            status = result.stdout.strip().lower()
            return status in ("full", "limited")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: ping
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "5", "zeus.aldc.io"],
                capture_output=True,
                timeout=CONNECTIVITY_TIMEOUT_S,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return False

    def _update_status(self, **kwargs) -> None:
        """Update status and emit signal."""
        pending = len(self._memory.get_unsynced_memories())
        self._status = ZeusSyncStatus(
            is_online=kwargs.get("is_online", self._status.is_online),
            pending_push=pending,
            last_sync=kwargs.get("last_sync", self._status.last_sync),
            last_error=kwargs.get("last_error", self._status.last_error),
        )
        self.sync_status_changed.emit(self._status)
