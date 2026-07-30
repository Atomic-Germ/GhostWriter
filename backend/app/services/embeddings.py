"""Embedding model wrapper with thread-safe lazy load."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("ghostwriter.embeddings")

_model = None
_load_error: Optional[str] = None
_loading = False
_lock = threading.Lock()
_status = "cold"  # cold | loading | ready | error


def get_status() -> str:
    return _status


def get_load_error() -> Optional[str]:
    return _load_error


def get_embedding_model():
    """Return model, loading it once under a lock if needed."""
    global _model, _load_error, _loading, _status

    if _model is not None:
        return _model
    if _load_error is not None and _status == "error":
        return None

    with _lock:
        if _model is not None:
            return _model
        if _status == "error":
            return None

        _loading = True
        _status = "loading"
        try:
            logger.info("Loading embedding model…")
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            _model = SentenceTransformer(settings.embedding_model)
            _status = "ready"
            _load_error = None
            logger.info("Embedding model ready (%s)", settings.embedding_model)
            return _model
        except Exception as exc:  # noqa: BLE001
            _load_error = str(exc)
            _status = "error"
            _model = None
            logger.exception("Failed to load embedding model: %s", exc)
            return None
        finally:
            _loading = False


def warm_embeddings() -> bool:
    """Eagerly load the model (safe to call from a background thread)."""
    return get_embedding_model() is not None


def is_embedding_ready() -> bool:
    return _model is not None


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError(f"Embedding model unavailable: {_load_error}")
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
