"""KiSTI - Edge Embedding Service (ONNX)

Lightweight sentence embeddings using all-MiniLM-L6-v2 INT8.
23 MB disk, ~80 MB RAM, 384-dim, pure CPU, 5-15ms/sentence on ARM.

DO NOT use Ollama embedding models — 10-30s model swap latency
and memory leak risk on Jetson (GitHub #12528). ONNX is deterministic.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisti.data.embedder")

ONNX_MODEL_DIR = Path("/data/models/all-MiniLM-L6-v2-int8")
EMBEDDING_DIM = 384
MAX_SEQ_LENGTH = 128  # tokens — longer text gets truncated


class EdgeEmbedder:
    """CPU-only ONNX sentence embedder for edge vector search.

    Gracefully degrades: returns None if model files are missing
    or onnxruntime is not installed. Zero GPU memory usage.
    """

    def __init__(self, model_dir: Path = ONNX_MODEL_DIR) -> None:
        self._model_dir = model_dir
        self._session = None  # ort.InferenceSession
        self._tokenizer = None  # tokenizers.Tokenizer
        self._available = False

    def start(self) -> bool:
        """Load ONNX model + tokenizer. Returns True if successful."""
        model_path = self._model_dir / "model_quantized.onnx"
        tokenizer_path = self._model_dir / "tokenizer.json"

        if not model_path.exists():
            log.info("ONNX model not found at %s — embedder disabled", model_path)
            return False
        if not tokenizer_path.exists():
            log.info("Tokenizer not found at %s — embedder disabled", tokenizer_path)
            return False

        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            from tokenizers import Tokenizer  # type: ignore[import-untyped]

            # CPU-only — never touch GPU memory
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                str(model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
            self._tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)
            self._tokenizer.enable_padding(length=MAX_SEQ_LENGTH)
            self._available = True

            log.info("ONNX embedder ready: %s (%d-dim)", model_path.name, EMBEDDING_DIM)
            return True

        except ImportError as exc:
            log.info("ONNX dependencies not installed (%s) — embedder disabled", exc)
            return False
        except Exception as exc:
            log.warning("ONNX embedder failed to load: %s", exc)
            return False

    def stop(self) -> None:
        """Release ONNX session."""
        self._session = None
        self._tokenizer = None
        self._available = False

    def embed(self, text: str) -> Optional[list[float]]:
        """Embed a single text string. Returns 384-dim float list or None."""
        if not self._available or not text.strip():
            return None

        try:
            result = self.embed_batch([text])
            return result[0]
        except Exception as exc:
            log.warning("Embedding failed: %s", exc)
            return None

    def embed_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Embed multiple texts. Returns list of 384-dim float lists."""
        if not self._available:
            return [None] * len(texts)

        try:
            import numpy as np  # type: ignore[import-untyped]

            encodings = self._tokenizer.encode_batch(texts)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array(
                [e.attention_mask for e in encodings], dtype=np.int64,
            )
            token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

            outputs = self._session.run(
                None,
                {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "token_type_ids": token_type_ids,
                },
            )

            # Mean pooling over token embeddings (masked by attention)
            token_embeddings = outputs[0]  # (batch, seq_len, hidden_dim)
            mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
            summed = (token_embeddings * mask_expanded).sum(axis=1)
            counts = mask_expanded.sum(axis=1).clip(min=1e-9)
            pooled = summed / counts

            # L2 normalize
            norms = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
            normalized = pooled / norms

            return [row.tolist() for row in normalized]

        except Exception as exc:
            log.warning("Batch embedding failed: %s", exc)
            return [None] * len(texts)

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM
