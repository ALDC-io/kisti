"""Tests for EdgeEmbedder — graceful degradation without model files."""

import pytest
from pathlib import Path

from data.edge_embedder import EdgeEmbedder, EMBEDDING_DIM


@pytest.fixture
def embedder(tmp_path):
    """Embedder pointed at empty dir — model not present."""
    return EdgeEmbedder(model_dir=tmp_path / "no_model")


class TestEdgeEmbedder:

    def test_dimension_is_384(self, embedder):
        assert embedder.dimension == EMBEDDING_DIM
        assert embedder.dimension == 384

    def test_unavailable_without_model(self, embedder):
        assert not embedder.is_available

    def test_start_returns_false_without_model(self, embedder):
        result = embedder.start()
        assert result is False
        assert not embedder.is_available

    def test_embed_returns_none_when_unavailable(self, embedder):
        assert embedder.embed("test text") is None

    def test_embed_batch_returns_nones_when_unavailable(self, embedder):
        results = embedder.embed_batch(["hello", "world"])
        assert results == [None, None]

    def test_stop_is_safe_when_not_started(self, embedder):
        embedder.stop()
        assert not embedder.is_available

    def test_embed_empty_string_returns_none(self, embedder):
        embedder._available = True  # force available to test empty guard
        assert embedder.embed("") is None
        assert embedder.embed("   ") is None
