"""Lightweight embeddings — no torch on the request path.

Uses a stable hashing embedder by default (fast, pure Python/numpy).
Optional sentence-transformers if GW_EMBEDDING_BACKEND=st.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from typing import Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger("ghostwriter.embeddings")

_model = None
_load_error: Optional[str] = None
_lock = threading.Lock()
_status = "cold"  # cold | loading | ready | error
_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9']+", re.I)


def get_status() -> str:
    return _status


def get_load_error() -> Optional[str]:
    return _load_error


class HashingEmbedder:
    """Deterministic bag-of-words hashing vectorizer (no neural net)."""

    def __init__(self, dim: int = _DIM):
        self.dim = dim

    def encode(self, texts, show_progress_bar=False, convert_to_numpy=True):
        if isinstance(texts, str):
            texts = [texts]
        vectors = np.vstack([self._one(t) for t in texts])
        return vectors

    def _one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = _TOKEN_RE.findall((text or "").lower())
        if not tokens:
            return vec
        for tok in tokens:
            h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


def get_embedding_model():
    global _model, _load_error, _status

    if _model is not None:
        return _model
    if _status == "error":
        return None

    with _lock:
        if _model is not None:
            return _model
        if _status == "error":
            return None

        _status = "loading"
        settings = get_settings()
        backend = (getattr(settings, "embedding_backend", None) or "hash").lower()

        try:
            if backend in ("st", "sentence-transformers", "torch"):
                logger.info("Loading sentence-transformers model…")
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(settings.embedding_model)
                logger.info("sentence-transformers ready")
            else:
                _model = HashingEmbedder(_DIM)
                logger.info("Hashing embedder ready (dim=%s)", _DIM)

            _status = "ready"
            _load_error = None
            return _model
        except Exception as exc:  # noqa: BLE001
            # Fall back to hashing if ST fails
            logger.warning("Primary embedder failed (%s); using hashing fallback", exc)
            try:
                _model = HashingEmbedder(_DIM)
                _status = "ready"
                _load_error = None
                return _model
            except Exception as exc2:  # noqa: BLE001
                _load_error = str(exc2)
                _status = "error"
                _model = None
                logger.exception("Embedding init failed")
                return None


def warm_embeddings() -> bool:
    return get_embedding_model() is not None


def is_embedding_ready() -> bool:
    if _model is not None:
        return True
    # Hash backend is instant — mark ready on first check without heavy work
    settings = get_settings()
    backend = (getattr(settings, "embedding_backend", None) or "hash").lower()
    if backend not in ("st", "sentence-transformers", "torch"):
        return get_embedding_model() is not None
    return False


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError(f"Embedding model unavailable: {_load_error}")
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [np.asarray(v, dtype=np.float32).tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
