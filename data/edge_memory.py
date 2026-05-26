"""KiSTI - Edge Memory System

Local-first semantic memory with lightweight ONNX embeddings.
Stores memories in DuckDB with optional HNSW vector search via VSS extension.
Syncs to Zeus cloud when WiFi available.

Memory types:
  - manual: Voice commands ("remember oil change at 5000km")
  - session_summary: Auto-generated session summaries
  - alert_pattern: Recurring alert patterns detected
  - driving_insight: Driving behavior insights
  - maintenance: Service/build events
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("kisti.data.memory")

MEMORIES_DDL = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    session_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    memory_type TEXT,
    source TEXT,
    content TEXT NOT NULL,
    tags TEXT,
    importance DOUBLE DEFAULT 0.5,
    visibility TEXT DEFAULT 'private',
    embedding FLOAT[384],
    zeus_memory_id TEXT,
    zeus_version INTEGER DEFAULT 0,
    synced BOOLEAN DEFAULT FALSE,
    zeus_enriched BOOLEAN DEFAULT FALSE
);
"""

SETTINGS_DDL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP
);
"""

# Visibility levels for access control:
#   private  - owner only (default). Never exported to shared folders
#   team     - visible to KiSTI share members (tuner, mechanic)
#   public   - visible to anyone with the link
VISIBILITY_LEVELS = ("private", "team", "public")

# Importance defaults by memory type
IMPORTANCE_DEFAULTS = {
    "manual": 0.8,
    "maintenance": 0.8,
    "alert_pattern": 0.6,
    "session_summary": 0.5,
    "driving_insight": 0.5,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EdgeMemory:
    """Local-first semantic memory backed by DuckDB.

    Args:
        db_store: Existing DuckDBStore (shares its DuckDB connection).
        embedder: Optional EdgeEmbedder for vector search. Falls back
                  to keyword search when None or unavailable.
    """

    def __init__(self, db_store: object, embedder: object = None) -> None:
        self._store = db_store
        self._embedder = embedder
        self._vss_available = False

    @property
    def _conn(self):
        return self._store._conn

    def initialize(self) -> None:
        """Create memories and settings tables, optionally install VSS index."""
        self._conn.execute(MEMORIES_DDL)
        self._conn.execute(SETTINGS_DDL)

        # Try to load DuckDB VSS extension for HNSW index
        try:
            self._conn.execute("INSTALL vss; LOAD vss;")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_embedding "
                "ON memories USING HNSW (embedding) "
                "WITH (metric = 'cosine')"
            )
            self._vss_available = True
            log.info("DuckDB VSS extension loaded — HNSW vector search enabled")
        except Exception as exc:
            log.info("DuckDB VSS unavailable (%s) — using keyword/brute-force search", exc)
            self._vss_available = False

    # ---- Store ----

    def remember(
        self,
        content: str,
        memory_type: str = "manual",
        source: str = "voice",
        session_id: Optional[str] = None,
        tags: Optional[str] = None,
        importance: Optional[float] = None,
        visibility: str = "private",
    ) -> str:
        """Store a new memory. Returns memory_id (UUID).

        visibility: 'private' (owner only), 'team' (share members), 'public'.
        """
        memory_id = str(uuid.uuid4())
        now = _now()

        if importance is None:
            importance = IMPORTANCE_DEFAULTS.get(memory_type, 0.5)

        # Generate embedding if embedder is available
        embedding = None
        if self._embedder and hasattr(self._embedder, "embed"):
            embedding = self._embedder.embed(content)

        self._conn.execute(
            """INSERT INTO memories (
                memory_id, session_id, created_at, updated_at,
                memory_type, source, content, tags, importance, visibility,
                embedding, zeus_memory_id, zeus_version, synced, zeus_enriched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, FALSE, FALSE)""",
            [memory_id, session_id, now, now,
             memory_type, source, content, tags, importance, visibility,
             embedding],
        )

        log.info("Memory stored: %s [%s/%s] %s", memory_id[:8], memory_type, source, content[:50])
        return memory_id

    # ---- Read ----

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Get a single memory by ID."""
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE memory_id = ?", [memory_id],
        ).fetchall()
        if not rows:
            return None
        return self._row_to_dict(rows[0])

    def get_recent(
        self,
        limit: int = 10,
        memory_type: Optional[str] = None,
    ) -> list[dict]:
        """Get most recent memories, optionally filtered by type."""
        if memory_type:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE memory_type = ? "
                "ORDER BY created_at DESC LIMIT ?",
                [memory_type, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                [limit],
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ---- Search ----

    def search(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> list[dict]:
        """Semantic search. Uses vector similarity if available, else keyword."""
        # Try vector search first
        if self._embedder and hasattr(self._embedder, "embed"):
            query_embedding = self._embedder.embed(query)
            if query_embedding is not None:
                return self._vector_search(query_embedding, limit, memory_type)

        # Keyword fallback
        return self._keyword_search(query, limit, memory_type)

    def search_by_tags(self, tags: list[str], limit: int = 10) -> list[dict]:
        """Filter memories by tag substring match."""
        if not tags:
            return []
        conditions = " OR ".join(["tags LIKE ?" for _ in tags])
        params = [f"%{t}%" for t in tags]
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM memories WHERE ({conditions}) "
            f"ORDER BY importance DESC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _vector_search(
        self,
        query_embedding: list[float],
        limit: int,
        memory_type: Optional[str] = None,
    ) -> list[dict]:
        """Brute-force cosine similarity over FLOAT[384] column.

        Uses DuckDB's array_cosine_similarity function. Works with or
        without the VSS extension (HNSW just makes it faster).
        """
        if memory_type:
            rows = self._conn.execute(
                "SELECT *, list_cosine_similarity(embedding, ?::FLOAT[384]) AS score "
                "FROM memories WHERE embedding IS NOT NULL AND memory_type = ? "
                "ORDER BY score DESC LIMIT ?",
                [query_embedding, memory_type, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT *, list_cosine_similarity(embedding, ?::FLOAT[384]) AS score "
                "FROM memories WHERE embedding IS NOT NULL "
                "ORDER BY score DESC LIMIT ?",
                [query_embedding, limit],
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _keyword_search(
        self,
        query: str,
        limit: int,
        memory_type: Optional[str] = None,
    ) -> list[dict]:
        """Keyword fallback: LIKE match on content and tags."""
        pattern = f"%{query}%"
        if memory_type:
            rows = self._conn.execute(
                "SELECT * FROM memories "
                "WHERE (content ILIKE ? OR tags ILIKE ?) AND memory_type = ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                [pattern, pattern, memory_type, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE content ILIKE ? OR tags ILIKE ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                [pattern, pattern, limit],
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ---- Sync support ----

    def get_unsynced_memories(self) -> list[dict]:
        """Get memories not yet pushed to Zeus."""
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE synced = FALSE "
            "ORDER BY created_at ASC",
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def mark_synced(self, memory_id: str, zeus_memory_id: str) -> None:
        """Mark a memory as synced to Zeus, store Zeus-side ID."""
        self._conn.execute(
            "UPDATE memories SET synced = TRUE, zeus_memory_id = ?, "
            "updated_at = ? WHERE memory_id = ?",
            [zeus_memory_id, _now(), memory_id],
        )

    def apply_zeus_enrichment(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[str] = None,
        importance: Optional[float] = None,
        zeus_version: int = 1,
    ) -> None:
        """Apply enriched data from Zeus back to local memory."""
        updates = ["zeus_enriched = TRUE", "zeus_version = ?", "updated_at = ?"]
        params: list = [zeus_version, _now()]

        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)

        params.append(memory_id)
        self._conn.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE memory_id = ?",
            params,
        )

    # ---- Maintenance ----

    def purge_synced(self, keep_days: int = 90) -> int:
        """Purge old synced memories. NEVER deletes unsynced."""
        cutoff = _now() - timedelta(days=keep_days)
        result = self._conn.execute(
            "DELETE FROM memories WHERE synced = TRUE AND created_at < ? "
            "RETURNING memory_id",
            [cutoff],
        ).fetchall()
        count = len(result)
        if count:
            log.info("Purged %d synced memories older than %d days", count, keep_days)
        return count

    def stats(self) -> dict:
        """Memory stats: total, unsynced, by type, embedded count."""
        total = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        unsynced = self._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE synced = FALSE",
        ).fetchone()[0]
        embedded = self._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL",
        ).fetchone()[0]

        type_counts = {}
        rows = self._conn.execute(
            "SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type",
        ).fetchall()
        for row in rows:
            type_counts[row[0]] = row[1]

        return {
            "total": total,
            "unsynced": unsynced,
            "embedded": embedded,
            "by_type": type_counts,
            "vss_available": self._vss_available,
        }

    # ---- LLM Context ----

    def build_memory_context(self, query: str, max_memories: int = 3) -> str:
        """Build memory context string for LLM system prompt injection.

        Returns formatted text of relevant memories, or empty string.
        Budget: ~200 tokens max to keep LLM prompt tight.
        """
        memories = self.search(query, limit=max_memories)
        if not memories:
            return ""

        lines = []
        for m in memories:
            content = m["content"]
            if len(content) > 120:
                content = content[:117] + "..."
            tag_str = f" [{m['tags']}]" if m.get("tags") else ""
            lines.append(f"- {content}{tag_str}")

        return "\n".join(lines)

    # ---- Settings ----

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a setting value by key."""
        rows = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            [key],
        ).fetchall()
        if rows:
            return rows[0][0]
        return default

    def set_setting(self, key: str, value: str) -> None:
        """Store or update a setting."""
        self._conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
            "updated_at = EXCLUDED.updated_at",
            [key, value, _now()],
        )
        log.debug("Setting stored: %s = %s", key, value)

    def get_setting_bool(self, key: str, default: bool = False) -> bool:
        """Retrieve a boolean setting."""
        value = self.get_setting(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "enabled")

    def set_setting_bool(self, key: str, value: bool) -> None:
        """Store a boolean setting."""
        self.set_setting(key, "true" if value else "false")

    # ---- Internal ----

    def _row_to_dict(self, row) -> dict:
        """Convert a DuckDB row tuple to dict."""
        columns = [
            "memory_id", "session_id", "created_at", "updated_at",
            "memory_type", "source", "content", "tags", "importance",
            "visibility", "embedding", "zeus_memory_id", "zeus_version",
            "synced", "zeus_enriched",
        ]
        d = {}
        for i, col in enumerate(columns):
            if i < len(row):
                d[col] = row[i]
        return d
