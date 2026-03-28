"""Tests for EdgeMemory — local-first semantic memory system."""

import os
import time
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from data.duckdb_store import DuckDBStore
from data.edge_memory import EdgeMemory, _now


@pytest.fixture
def store(tmp_path):
    """DuckDBStore with temporary database."""
    db_path = tmp_path / "test_memory.duckdb"
    s = DuckDBStore(db_path=db_path)
    s.open()
    yield s
    s.close()


@pytest.fixture
def memory(store):
    """EdgeMemory with no embedder (keyword search only)."""
    m = EdgeMemory(db_store=store, embedder=None)
    m.initialize()
    return m


class TestMemoryStore:

    def test_remember_returns_uuid(self, memory):
        mid = memory.remember("Oil change at 5000 km")
        assert len(mid) == 36  # UUID format

    def test_remember_stores_content(self, memory):
        mid = memory.remember("Brake pads replaced", memory_type="maintenance")
        m = memory.get_memory(mid)
        assert m is not None
        assert m["content"] == "Brake pads replaced"
        assert m["memory_type"] == "maintenance"
        assert m["source"] == "voice"

    def test_remember_with_session_id(self, memory):
        mid = memory.remember(
            "Hit 14 PSI boost on lap 3",
            memory_type="driving_insight",
            source="auto_summary",
            session_id="test-session-001",
            tags="boost,lap",
        )
        m = memory.get_memory(mid)
        assert m["session_id"] == "test-session-001"
        assert m["tags"] == "boost,lap"

    def test_remember_default_importance(self, memory):
        mid = memory.remember("Manual note", memory_type="manual")
        m = memory.get_memory(mid)
        assert m["importance"] == 0.8  # manual default

    def test_remember_custom_importance(self, memory):
        mid = memory.remember("Custom", importance=0.3)
        m = memory.get_memory(mid)
        assert m["importance"] == 0.3

    def test_get_nonexistent_memory(self, memory):
        assert memory.get_memory("nonexistent-id") is None

    def test_get_recent_ordered_by_time(self, memory):
        memory.remember("First")
        memory.remember("Second")
        memory.remember("Third")
        recent = memory.get_recent(limit=3)
        assert len(recent) == 3
        assert recent[0]["content"] == "Third"
        assert recent[2]["content"] == "First"

    def test_get_recent_filtered_by_type(self, memory):
        memory.remember("Manual note", memory_type="manual")
        memory.remember("Session summary", memory_type="session_summary")
        memory.remember("Another manual", memory_type="manual")

        manual = memory.get_recent(limit=10, memory_type="manual")
        assert len(manual) == 2
        assert all(m["memory_type"] == "manual" for m in manual)


class TestMemorySearch:

    def test_keyword_search_matches_content(self, memory):
        memory.remember("Oil change completed at 5000 km", tags="oil,maintenance")
        memory.remember("Brake pads look worn", tags="brakes")
        results = memory.search("oil change")
        assert len(results) >= 1
        assert "oil" in results[0]["content"].lower()

    def test_keyword_search_matches_tags(self, memory):
        memory.remember("Service note", tags="oil,filter")
        results = memory.search("filter")
        assert len(results) == 1

    def test_keyword_search_no_match(self, memory):
        memory.remember("Brake pads replaced")
        results = memory.search("turbo rebuild")
        assert len(results) == 0

    def test_search_respects_limit(self, memory):
        for i in range(10):
            memory.remember(f"Oil note {i}", tags="oil")
        results = memory.search("oil", limit=3)
        assert len(results) == 3

    def test_search_filtered_by_type(self, memory):
        memory.remember("Oil manual", memory_type="manual", tags="oil")
        memory.remember("Oil insight", memory_type="driving_insight", tags="oil")
        results = memory.search("oil", memory_type="manual")
        assert len(results) == 1
        assert results[0]["memory_type"] == "manual"


class TestSearchByTags:

    def test_single_tag(self, memory):
        memory.remember("Note 1", tags="oil,brake")
        memory.remember("Note 2", tags="turbo")
        results = memory.search_by_tags(["oil"])
        assert len(results) == 1

    def test_multiple_tags(self, memory):
        memory.remember("Note 1", tags="oil,brake")
        memory.remember("Note 2", tags="turbo")
        results = memory.search_by_tags(["oil", "turbo"])
        assert len(results) == 2

    def test_empty_tags(self, memory):
        assert memory.search_by_tags([]) == []


class TestMemorySync:

    def test_new_memory_is_unsynced(self, memory):
        mid = memory.remember("Test")
        m = memory.get_memory(mid)
        assert m["synced"] is False
        assert m["zeus_memory_id"] is None

    def test_get_unsynced_memories(self, memory):
        memory.remember("Unsynced 1")
        memory.remember("Unsynced 2")
        unsynced = memory.get_unsynced_memories()
        assert len(unsynced) == 2

    def test_mark_synced(self, memory):
        mid = memory.remember("To sync")
        memory.mark_synced(mid, zeus_memory_id="zeus-abc-123")
        m = memory.get_memory(mid)
        assert m["synced"] is True
        assert m["zeus_memory_id"] == "zeus-abc-123"

    def test_mark_synced_removes_from_unsynced(self, memory):
        mid = memory.remember("To sync")
        memory.mark_synced(mid, zeus_memory_id="zeus-id")
        unsynced = memory.get_unsynced_memories()
        assert len(unsynced) == 0

    def test_apply_zeus_enrichment(self, memory):
        mid = memory.remember("Raw note")
        memory.apply_zeus_enrichment(
            mid,
            content="Enriched note with context",
            tags="enriched,zeus",
            importance=0.9,
            zeus_version=2,
        )
        m = memory.get_memory(mid)
        assert m["content"] == "Enriched note with context"
        assert m["tags"] == "enriched,zeus"
        assert m["importance"] == 0.9
        assert m["zeus_version"] == 2
        assert m["zeus_enriched"] is True

    def test_apply_enrichment_partial(self, memory):
        mid = memory.remember("Original content", tags="original")
        memory.apply_zeus_enrichment(mid, importance=0.95, zeus_version=1)
        m = memory.get_memory(mid)
        assert m["content"] == "Original content"  # unchanged
        assert m["tags"] == "original"  # unchanged
        assert m["importance"] == 0.95
        assert m["zeus_enriched"] is True


class TestMemoryPurge:

    def test_purge_never_deletes_unsynced(self, memory):
        memory.remember("Unsynced memory")
        count = memory.purge_synced(keep_days=0)
        assert count == 0
        assert len(memory.get_recent()) == 1

    def test_purge_deletes_old_synced(self, memory):
        mid = memory.remember("Old synced")
        memory.mark_synced(mid, "zeus-id")
        # Backdate the created_at to 100 days ago
        old_date = _now() - timedelta(days=100)
        memory._conn.execute(
            "UPDATE memories SET created_at = ? WHERE memory_id = ?",
            [old_date, mid],
        )
        count = memory.purge_synced(keep_days=90)
        assert count == 1

    def test_purge_respects_keep_days(self, memory):
        mid = memory.remember("Recent synced")
        memory.mark_synced(mid, "zeus-id")
        # Created just now — should NOT be purged
        count = memory.purge_synced(keep_days=90)
        assert count == 0


class TestMemoryStats:

    def test_stats_empty(self, memory):
        s = memory.stats()
        assert s["total"] == 0
        assert s["unsynced"] == 0
        assert s["embedded"] == 0
        assert s["by_type"] == {}

    def test_stats_after_inserts(self, memory):
        memory.remember("Manual 1", memory_type="manual")
        memory.remember("Manual 2", memory_type="manual")
        memory.remember("Summary 1", memory_type="session_summary")
        s = memory.stats()
        assert s["total"] == 3
        assert s["unsynced"] == 3
        assert s["embedded"] == 0  # no embedder
        assert s["by_type"]["manual"] == 2
        assert s["by_type"]["session_summary"] == 1


class TestMemoryContext:

    def test_build_context_empty(self, memory):
        ctx = memory.build_memory_context("anything")
        assert ctx == ""

    def test_build_context_with_memories(self, memory):
        memory.remember("Oil changed at 5000 km", tags="oil")
        ctx = memory.build_memory_context("oil")
        assert "Oil changed at 5000 km" in ctx
        assert ctx.startswith("- ")

    def test_build_context_respects_limit(self, memory):
        for i in range(10):
            memory.remember(f"Oil note {i}", tags="oil")
        ctx = memory.build_memory_context("oil", max_memories=2)
        lines = [l for l in ctx.split("\n") if l.strip()]
        assert len(lines) == 2

    def test_build_context_truncates_long_content(self, memory):
        long_text = "A" * 200
        memory.remember(long_text, tags="test")
        ctx = memory.build_memory_context("test")
        # Each line should be truncated to ~120 chars + tag + prefix
        assert "..." in ctx
