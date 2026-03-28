"""Tests for ZeusMemorySyncWorker — mocked HTTP, no real network."""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from data.duckdb_store import DuckDBStore
from data.edge_memory import EdgeMemory
from sync.zeus_memory_sync import (
    ZeusMemorySyncWorker,
    ZeusSyncStatus,
    DEVICE_ID,
)


@pytest.fixture
def memory(tmp_path):
    """EdgeMemory with DuckDB store."""
    db_path = tmp_path / "test_sync.duckdb"
    store = DuckDBStore(db_path=db_path)
    store.open()
    mem = EdgeMemory(db_store=store, embedder=None)
    mem.initialize()
    yield mem
    store.close()


@pytest.fixture
def worker(memory):
    """ZeusMemorySyncWorker with mocked connectivity."""
    w = ZeusMemorySyncWorker(
        edge_memory=memory,
        api_key="test-api-key",
        api_base="http://mock-zeus.local/api",
    )
    return w


class TestZeusSyncWorker:

    def test_init(self, worker):
        assert worker._api_key == "test-api-key"
        assert worker.status.is_online is False
        assert worker.status.pending_push == 0

    def test_push_payload_format(self, worker, memory):
        """Verify the JSON payload sent to Zeus has correct structure."""
        memory.remember("Test memory", memory_type="manual", tags="test")

        captured_body = {}

        def mock_urlopen(req, timeout=30):
            body = json.loads(req.data)
            captured_body.update(body)
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "accepted": [{
                    "edge_memory_id": body["memories"][0]["edge_memory_id"],
                    "zeus_memory_id": "zeus-123",
                }],
            }).encode()
            return resp

        with patch("sync.zeus_memory_sync.urllib.request.urlopen", side_effect=mock_urlopen):
            count = worker._push_memories()

        assert count == 1
        assert captured_body["source"] == "kisti-edge"
        assert captured_body["device_id"] == DEVICE_ID
        assert len(captured_body["memories"]) == 1

        mem = captured_body["memories"][0]
        assert "edge_memory_id" in mem
        assert mem["content"] == "Test memory"
        assert mem["memory_type"] == "manual"
        assert mem["tags"] == "test"

    def test_push_marks_synced(self, worker, memory):
        """After successful push, memories should be marked synced."""
        mid = memory.remember("To sync")

        def mock_urlopen(req, timeout=30):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "accepted": [{
                    "edge_memory_id": mid,
                    "zeus_memory_id": "zeus-456",
                }],
            }).encode()
            return resp

        with patch("sync.zeus_memory_sync.urllib.request.urlopen", side_effect=mock_urlopen):
            worker._push_memories()

        m = memory.get_memory(mid)
        assert m["synced"] is True
        assert m["zeus_memory_id"] == "zeus-456"

    def test_pull_enrichment_applies(self, worker, memory):
        """Mock enrichment response should update local memory."""
        mid = memory.remember("Raw note")
        memory.mark_synced(mid, "zeus-789")

        def mock_urlopen(req, timeout=30):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "enrichments": [{
                    "edge_memory_id": mid,
                    "content": "Enriched note",
                    "tags": "enriched",
                    "importance": 0.9,
                    "zeus_version": 2,
                }],
            }).encode()
            return resp

        with patch("sync.zeus_memory_sync.urllib.request.urlopen", side_effect=mock_urlopen):
            count = worker._pull_enrichments()

        assert count == 1
        m = memory.get_memory(mid)
        assert m["content"] == "Enriched note"
        assert m["zeus_enriched"] is True
        assert m["zeus_version"] == 2

    def test_no_sync_when_offline(self, worker, memory):
        """Sync tick should skip when connectivity check fails."""
        memory.remember("Offline memory")

        with patch.object(worker, "_check_connectivity", return_value=False):
            worker._sync_tick()

        assert worker.status.is_online is False
        # Memory should still be unsynced
        unsynced = memory.get_unsynced_memories()
        assert len(unsynced) == 1

    def test_push_returns_zero_when_nothing_to_sync(self, worker):
        assert worker._push_memories() == 0
