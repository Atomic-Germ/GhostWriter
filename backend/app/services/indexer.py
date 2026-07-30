"""Background story-memory indexing — never blocks HTTP handlers."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("ghostwriter.indexer")


@dataclass(frozen=True)
class IndexJob:
    project_id: str
    chapter_id: Optional[str] = None


class IndexWorker:
    def __init__(self) -> None:
        self._q: queue.Queue[Optional[IndexJob]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._pending: set[tuple[str, Optional[str]]] = set()
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None
        self._running = False

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="ghostwriter-indexer",
            daemon=True,
        )
        self._thread.start()
        logger.info("Index worker started")

    def stop(self) -> None:
        self._running = False
        self._q.put(None)
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def schedule(self, project_id: str, chapter_id: Optional[str] = None) -> None:
        key = (project_id, chapter_id)
        with self._lock:
            if key in self._pending:
                return
            self._pending.add(key)
        self._q.put(IndexJob(project_id=project_id, chapter_id=chapter_id))

    def _loop(self) -> None:
        while self._running:
            job = self._q.get()
            if job is None:
                break
            try:
                self._run(job)
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                logger.exception("Index job failed: %s", exc)
            finally:
                with self._lock:
                    self._pending.discard((job.project_id, job.chapter_id))
                self._q.task_done()

    def _run(self, job: IndexJob) -> None:
        from app.db.storage import get_store
        from app.services.embeddings import is_embedding_ready, warm_embeddings
        from app.services.rag import get_memory

        if not is_embedding_ready():
            if not warm_embeddings():
                logger.warning("Skipping index — embeddings unavailable")
                return

        project = get_store().get_project(job.project_id)
        count = get_memory().index_project(project, chapter_id=job.chapter_id)
        logger.info(
            "Indexed project=%s chapter=%s chunks=%s",
            job.project_id,
            job.chapter_id,
            count,
        )
        self._last_error = None


_worker: Optional[IndexWorker] = None
_worker_lock = threading.Lock()


def get_indexer() -> IndexWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = IndexWorker()
        return _worker


def schedule_reindex(project_id: str, chapter_id: Optional[str] = None) -> None:
    worker = get_indexer()
    worker.start()
    worker.schedule(project_id, chapter_id)
