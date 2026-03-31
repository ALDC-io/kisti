"""Tests for FrontierLLMEngine — WiFi-aware cloud LLM with DuckDB cache."""

import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from data.duckdb_store import DuckDBStore
from voice.frontier_engine import (
    FRONTIER_CACHE_DDL,
    FrontierLLMEngine,
)
from voice.llm_engine import LLMEngine, LLMResponse


@pytest.fixture
def db_conn(tmp_path):
    """Ephemeral DuckDB connection for cache tests."""
    import duckdb

    conn = duckdb.connect(str(tmp_path / "test_frontier.duckdb"))
    conn.execute(FRONTIER_CACHE_DDL)
    yield conn
    conn.close()


@pytest.fixture
def engine(db_conn):
    """FrontierLLMEngine with test API key and DB."""
    e = FrontierLLMEngine(
        api_key="test-key-123",
        db_conn=db_conn,
        model="claude-haiku-4-5-20251001",
    )
    return e


class TestFrontierEngineLifecycle:

    def test_start_creates_cache_table(self, tmp_path):
        import duckdb

        conn = duckdb.connect(str(tmp_path / "lifecycle.duckdb"))
        e = FrontierLLMEngine(api_key="k", db_conn=conn)
        with patch.object(e, "_wifi_checker"):
            e.start()
        # Table should exist
        count = conn.execute("SELECT COUNT(*) FROM frontier_cache").fetchone()[0]
        assert count == 0
        e.stop()
        conn.close()

    def test_start_stop_sets_running_flag(self, engine):
        with patch.object(engine, "_wifi_checker"):
            engine.start()
            assert engine.is_running is True
            engine.stop()
            assert engine.is_running is False

    def test_no_api_key_disables_engine(self, db_conn):
        e = FrontierLLMEngine(api_key="", db_conn=db_conn)
        e.start()
        result = e.query("test query")
        assert result is None
        e.stop()

    def test_wifi_check_thread_starts(self, engine):
        engine.start()
        assert engine._wifi_check_thread is not None
        assert engine._wifi_check_thread.is_alive()
        engine.stop()
        assert engine._wifi_check_thread is None


class TestQueryHash:

    def test_hash_deterministic(self, engine):
        h1 = engine._hash_query("What is boost?")
        h2 = engine._hash_query("What is boost?")
        assert h1 == h2

    def test_hash_case_insensitive(self, engine):
        h1 = engine._hash_query("What is boost?")
        h2 = engine._hash_query("WHAT IS BOOST?")
        assert h1 == h2

    def test_hash_strips_whitespace(self, engine):
        h1 = engine._hash_query("What is boost?")
        h2 = engine._hash_query("  What is boost?  ")
        assert h1 == h2

    def test_different_queries_different_hashes(self, engine):
        h1 = engine._hash_query("What is boost?")
        h2 = engine._hash_query("How does DCCD work?")
        assert h1 != h2


class TestCache:

    def test_cache_miss_returns_none(self, engine):
        result = engine._check_cache("nonexistent_hash")
        assert result is None

    def test_cache_store_and_retrieve(self, engine):
        qhash = engine._hash_query("test question")
        engine._cache_response(qhash, "test question", "test answer", "haiku")
        result = engine._check_cache(qhash)
        assert result == "test answer"

    def test_hit_count_incremented(self, engine, db_conn):
        qhash = engine._hash_query("hit counter test")
        engine._cache_response(qhash, "hit counter test", "answer", "haiku")

        # First hit
        engine._check_cache(qhash)
        row = db_conn.execute(
            "SELECT hit_count FROM frontier_cache WHERE query_hash = ?", [qhash]
        ).fetchone()
        assert row[0] == 1

        # Second hit
        engine._check_cache(qhash)
        row = db_conn.execute(
            "SELECT hit_count FROM frontier_cache WHERE query_hash = ?", [qhash]
        ).fetchone()
        assert row[0] == 2

    def test_cache_ttl_expiry(self, engine, db_conn):
        qhash = engine._hash_query("expired question")
        # Insert with a past creation date (31 days ago, TTL is 30)
        past = datetime.now(timezone.utc) - timedelta(days=31)
        db_conn.execute(
            "INSERT INTO frontier_cache "
            "(query_hash, query_text, response_text, model, "
            "created_at, hit_count, last_hit_at, ttl_days) "
            "VALUES (?, 'q', 'old answer', 'haiku', ?, 0, NULL, 30)",
            [qhash, past],
        )
        result = engine._check_cache(qhash)
        assert result is None  # Expired

    def test_cache_within_ttl_returns_response(self, engine, db_conn):
        qhash = engine._hash_query("fresh question")
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        db_conn.execute(
            "INSERT INTO frontier_cache "
            "(query_hash, query_text, response_text, model, "
            "created_at, hit_count, last_hit_at, ttl_days) "
            "VALUES (?, 'q', 'fresh answer', 'haiku', ?, 0, NULL, 30)",
            [qhash, recent],
        )
        result = engine._check_cache(qhash)
        assert result == "fresh answer"

    def test_cache_stats(self, engine):
        engine._cache_response(
            engine._hash_query("q1"), "q1", "a1", "haiku"
        )
        engine._cache_response(
            engine._hash_query("q2"), "q2", "a2", "haiku"
        )
        stats = engine.cache_stats()
        assert stats["total"] == 2
        assert stats["total_hits"] == 0


class TestQuery:

    def test_returns_none_when_not_running(self, engine):
        result = engine.query("test")
        assert result is None

    def test_cache_hit_returns_llm_response(self, engine):
        engine._running = True
        qhash = engine._hash_query("cached query")
        engine._cache_response(qhash, "cached query", "cached answer", "haiku")

        result = engine.query("cached query")
        assert result is not None
        assert result.text == "cached answer"
        assert result.tier == "frontier_cache"
        assert "cached" in result.model

    def test_returns_none_when_offline_no_cache(self, engine):
        engine._running = True
        engine._wifi_available = False
        result = engine.query("unknown question")
        assert result is None

    def test_live_api_call_when_online(self, engine):
        engine._running = True
        engine._wifi_available = True

        def mock_urlopen(req, timeout=10):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "content": [{"type": "text", "text": "Claude says hello"}],
                "model": "claude-haiku-4-5-20251001",
                "usage": {"input_tokens": 50, "output_tokens": 10},
            }).encode()
            return resp

        with patch("voice.frontier_engine.urllib.request.urlopen", side_effect=mock_urlopen):
            result = engine.query("What causes turbo lag?")

        assert result is not None
        assert result.text == "Claude says hello"
        assert result.tier == "frontier_live"

    def test_api_response_gets_cached(self, engine, db_conn):
        engine._running = True
        engine._wifi_available = True

        def mock_urlopen(req, timeout=10):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "content": [{"type": "text", "text": "Turbo lag is compressor spool time."}],
            }).encode()
            return resp

        with patch("voice.frontier_engine.urllib.request.urlopen", side_effect=mock_urlopen):
            engine.query("What causes turbo lag?")

        # Verify it was cached
        qhash = engine._hash_query("What causes turbo lag?")
        cached = engine._check_cache(qhash)
        assert cached == "Turbo lag is compressor spool time."

    def test_api_timeout_returns_none(self, engine):
        engine._running = True
        engine._wifi_available = True

        import urllib.error

        with patch(
            "voice.frontier_engine.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            result = engine.query("test timeout")

        assert result is None

    def test_api_http_error_returns_none(self, engine):
        engine._running = True
        engine._wifi_available = True

        import urllib.error

        with patch(
            "voice.frontier_engine.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="", code=429, msg="Rate limited", hdrs={}, fp=None
            ),
        ):
            result = engine.query("test rate limit")

        assert result is None


class TestLLMEngineIntegration:

    def test_llm_engine_uses_frontier_on_persona_miss(self):
        """When persona misses, LLMEngine should try frontier."""
        mock_frontier = MagicMock()
        mock_frontier.query.return_value = LLMResponse(
            text="Frontier answer",
            model="claude-haiku-4-5",
            tier="frontier_live",
            latency_s=0.3,
            tokens=5,
        )

        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        # Query that won't match any persona keyword
        response = engine.query("what is the capital of Mongolia")
        assert response.text == "Frontier answer"
        assert response.tier == "frontier_live"
        mock_frontier.query.assert_called_once()

    def test_llm_engine_skips_frontier_when_none(self):
        """Without frontier, falls back to FALLBACK_RESPONSE."""
        engine = LLMEngine(frontier=None)
        engine._running = True

        response = engine.query("what is the capital of Mongolia")
        assert response.tier == "fallback"

    def test_safety_fast_path_bypasses_frontier(self):
        """Safety queries (brakes, oil, overheating) bypass frontier entirely."""
        mock_frontier = MagicMock()
        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        response = engine.query("How are my brakes?")
        assert response.tier == "persona_match"
        assert response.model == "persona_safety"
        mock_frontier.query.assert_not_called()

    def test_frontier_takes_priority_over_persona_for_tech(self):
        """Tech queries that match persona keywords still go to frontier first."""
        mock_frontier = MagicMock()
        mock_frontier.query.return_value = LLMResponse(
            text="Frontier piston answer",
            model="claude-haiku-4-5",
            tier="frontier_live",
            latency_s=0.4,
            tokens=4,
        )

        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        response = engine.query("Tell me about the pistons")
        assert response.tier == "frontier_live"
        assert response.text == "Frontier piston answer"
        mock_frontier.query.assert_called_once()

    def test_llm_engine_fallback_when_frontier_returns_none(self):
        """If frontier returns None, should fall through to fallback."""
        mock_frontier = MagicMock()
        mock_frontier.query.return_value = None

        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        response = engine.query("what is the capital of Mongolia")
        assert response.tier == "fallback"

    def test_llm_engine_fallback_when_frontier_raises(self):
        """If frontier raises on non-persona query, should hit hard fallback."""
        mock_frontier = MagicMock()
        mock_frontier.query.side_effect = RuntimeError("API crashed")

        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        response = engine.query("what is the capital of Mongolia")
        assert response.tier == "fallback"

    def test_persona_fallback_when_frontier_fails(self):
        """If frontier raises on a persona-matching query, persona catches it."""
        mock_frontier = MagicMock()
        mock_frontier.query.side_effect = RuntimeError("Network unreachable")

        engine = LLMEngine(frontier=mock_frontier)
        engine._running = True

        # "your boost" has self-ref + keyword match → persona fallback catches it
        response = engine.query("How's your boost?")
        assert response.tier == "persona_match"
        assert response.model == "persona_keywords"
