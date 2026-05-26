"""Tests for scripts/prewarm_frontier_cache.py"""

from __future__ import annotations

from scripts.prewarm_frontier_cache import PREWARM_QUERIES, collect_queries


class TestPrewarmFrontierCache:
    """Tests for the frontier cache prewarm script."""

    def test_collect_queries_returns_list(self):
        """collect_queries() returns a non-empty list of tuples."""
        queries = collect_queries()
        assert isinstance(queries, list)
        assert len(queries) > 0

    def test_queries_are_category_text_tuples(self):
        """Each query is a (category, text) tuple with non-empty strings."""
        for item in PREWARM_QUERIES:
            assert isinstance(item, tuple)
            assert len(item) == 2
            cat, query = item
            assert isinstance(cat, str) and cat
            assert isinstance(query, str) and query

    def test_queries_cover_multiple_categories(self):
        """Queries span at least 4 categories."""
        categories = {cat for cat, _ in PREWARM_QUERIES}
        assert len(categories) >= 4

    def test_no_duplicate_queries(self):
        """No duplicate query texts."""
        texts = [q for _, q in PREWARM_QUERIES]
        assert len(texts) == len(set(texts))

    def test_minimum_query_count(self):
        """At least 30 queries for meaningful cache coverage."""
        assert len(PREWARM_QUERIES) >= 30

    def test_dry_run_does_not_call_api(self, capsys):
        """Dry run prints queries without needing API key or DB."""
        from scripts.prewarm_frontier_cache import prewarm
        from pathlib import Path

        prewarm(db_path=Path("/tmp/nonexistent.db"), dry_run=True)
        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "no API calls" in captured.out

    def test_main_entry_point_exists(self):
        """Module has main() callable."""
        from scripts.prewarm_frontier_cache import main
        assert callable(main)
