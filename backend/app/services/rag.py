"""ChromaDB-backed story memory / RAG."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from typing import Optional

from app.config import get_settings
from app.models.schemas import Character, Project
from app.services.embeddings import (
    embed_query,
    embed_texts,
    get_status as embedding_status,
    is_embedding_ready,
)

logger = logging.getLogger("ghostwriter.rag")

# Chroma is not reliably multi-threaded — serialize all client use.
_chroma_lock = threading.RLock()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            if len(current) + len(para) + 1 <= chunk_size:
                current = f"{current}\n\n{para}".strip()
            else:
                flush()
                current = para
        else:
            flush()
            words = para.split()
            buf: list[str] = []
            size = 0
            for w in words:
                if size + len(w) + 1 > chunk_size and buf:
                    chunks.append(" ".join(buf))
                    overlap_words = []
                    osize = 0
                    for ow in reversed(buf):
                        if osize + len(ow) + 1 > overlap:
                            break
                        overlap_words.insert(0, ow)
                        osize += len(ow) + 1
                    buf = overlap_words + [w]
                    size = sum(len(x) + 1 for x in buf)
                else:
                    buf.append(w)
                    size += len(w) + 1
            if buf:
                chunks.append(" ".join(buf))
            current = ""
    flush()
    return chunks


def _stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class StoryMemory:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self._client = None
        self._client_error: Optional[str] = None

    @property
    def client(self):
        if self._client is not None:
            return self._client
        if self._client_error is not None:
            return None
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.PersistentClient(
                path=str(self.settings.chroma_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            return self._client
        except Exception as exc:  # noqa: BLE001
            self._client_error = str(exc)
            logger.warning("Chroma unavailable: %s", exc)
            return None

    def _collection(self, project_id: str):
        client = self.client
        if client is None:
            return None
        return client.get_or_create_collection(
            name=f"project_{project_id.replace('-', '_')}",
            metadata={"hnsw:space": "cosine"},
        )

    def index_project(self, project: Project, chapter_id: Optional[str] = None) -> int:
        if not is_embedding_ready():
            return 0

        with _chroma_lock:
            collection = self._collection(project.id)
            if collection is None:
                return 0

            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict] = []

            for char in project.characters:
                doc = self._character_doc(char)
                cid = _stable_id(project.id, "character", char.id)
                ids.append(cid)
                documents.append(doc)
                metadatas.append(
                    {
                        "type": "character",
                        "project_id": project.id,
                        "character_id": char.id,
                        "name": char.name,
                        "title": char.name,
                    }
                )

            if project.world_notes.strip():
                for i, chunk in enumerate(
                    _chunk_text(
                        project.world_notes,
                        self.settings.chunk_size,
                        self.settings.chunk_overlap,
                    )
                ):
                    cid = _stable_id(project.id, "world", str(i), chunk[:40])
                    ids.append(cid)
                    documents.append(chunk)
                    metadatas.append(
                        {
                            "type": "world",
                            "project_id": project.id,
                            "title": "World Notes",
                        }
                    )

            chapters = project.chapters
            if chapter_id:
                chapters = [c for c in chapters if c.id == chapter_id]

            for chapter in chapters:
                if not chapter.content.strip():
                    continue
                if chapter.summary.strip():
                    cid = _stable_id(project.id, "summary", chapter.id)
                    ids.append(cid)
                    documents.append(
                        f"Chapter summary — {chapter.title}: {chapter.summary}"
                    )
                    metadatas.append(
                        {
                            "type": "summary",
                            "project_id": project.id,
                            "chapter_id": chapter.id,
                            "title": chapter.title,
                        }
                    )
                for i, chunk in enumerate(
                    _chunk_text(
                        chapter.content,
                        self.settings.chunk_size,
                        self.settings.chunk_overlap,
                    )
                ):
                    cid = _stable_id(
                        project.id, "chapter", chapter.id, str(i), chunk[:40]
                    )
                    ids.append(cid)
                    documents.append(f"[{chapter.title}]\n{chunk}")
                    metadatas.append(
                        {
                            "type": "chapter",
                            "project_id": project.id,
                            "chapter_id": chapter.id,
                            "title": chapter.title,
                            "chunk_index": i,
                        }
                    )

            if not ids:
                return 0

            batch = 32
            total = 0
            for start in range(0, len(ids), batch):
                end = start + batch
                batch_docs = documents[start:end]
                batch_ids = ids[start:end]
                batch_meta = metadatas[start:end]
                embeddings = embed_texts(batch_docs)
                try:
                    collection.delete(ids=batch_ids)
                except Exception:  # noqa: BLE001
                    pass
                collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_meta,
                    embeddings=embeddings,
                )
                total += len(batch_ids)
            return total

    def _character_doc(self, char: Character) -> str:
        parts = [f"Character: {char.name}"]
        if char.role:
            parts.append(f"Role: {char.role}")
        if char.physical_traits:
            parts.append(f"Physical traits: {char.physical_traits}")
        if char.personality:
            parts.append(f"Personality: {char.personality}")
        if char.motivations:
            parts.append(f"Motivations: {char.motivations}")
        if char.speech_patterns:
            parts.append(f"Speech patterns: {char.speech_patterns}")
        if char.backstory:
            parts.append(f"Backstory: {char.backstory}")
        if char.relationships:
            parts.append(f"Relationships: {char.relationships}")
        if char.notes:
            parts.append(f"Notes: {char.notes}")
        return "\n".join(parts)

    def query(
        self,
        project_id: str,
        query_text: str,
        top_k: Optional[int] = None,
        filter_type: Optional[str] = None,
    ) -> list[dict]:
        # Never block assist on a cold/loading embedder
        if embedding_status() != "ready" or not query_text.strip():
            return []

        if not _chroma_lock.acquire(timeout=2.0):
            logger.warning("Skipping vector query — chroma busy")
            return []
        try:
            collection = self._collection(project_id)
            if collection is None or collection.count() == 0:
                return []

            k = top_k or self.settings.rag_top_k
            where = {"type": filter_type} if filter_type else None
            emb = embed_query(query_text)

            kwargs = {
                "query_embeddings": [emb],
                "n_results": min(k, collection.count()),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = collection.query(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector query failed: %s", exc)
            return []
        finally:
            _chroma_lock.release()

        out: list[dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            out.append(
                {
                    "text": doc,
                    "metadata": meta or {},
                    "score": 1.0 - float(dist) if dist is not None else 0.0,
                }
            )
        return out

    def build_context_block(
        self,
        project: Project,
        query_text: str,
        extra_text: str = "",
        use_vector: bool = True,
    ) -> tuple[str, list[str]]:
        """Build LLM context from project data (+ optional vector hits)."""
        sources: list[str] = []
        sections: list[str] = []

        meta_bits = [f"Title: {project.title}"]
        if project.genre:
            meta_bits.append(f"Genre: {project.genre}")
        if project.premise:
            meta_bits.append(f"Premise: {project.premise}")
        if project.description:
            meta_bits.append(f"Description: {project.description}")
        sections.append("## Project\n" + "\n".join(meta_bits))

        if project.characters:
            char_blocks = [self._character_doc(c) for c in project.characters]
            sections.append("## Characters\n" + "\n\n".join(char_blocks))
            sources.extend([f"Character: {c.name}" for c in project.characters])

        # Full world notes — primary source for lore questions
        if project.world_notes.strip():
            notes = project.world_notes.strip()
            if len(notes) > 12000:
                notes = notes[:12000] + "\n…[truncated]"
            sections.append(f"## World Notes\n{notes}")
            sources.append("World Notes")

        # Chapter bodies from disk (no vector DB required)
        chapters = sorted(project.chapters, key=lambda c: c.order)
        if chapters:
            ch_parts: list[str] = []
            budget = 8000
            for ch in chapters:
                body = (ch.content or "").strip()
                if not body and not ch.summary:
                    continue
                block = f"### {ch.title}\n"
                if ch.summary:
                    block += f"Summary: {ch.summary}\n"
                if body:
                    # Prefer head+tail if long
                    if len(body) > 2000:
                        block += body[:1000] + "\n…\n" + body[-1000:]
                    else:
                        block += body
                if len(block) > budget:
                    break
                ch_parts.append(block)
                budget -= len(block)
                sources.append(f"chapter: {ch.title}")
            if ch_parts:
                sections.append("## Manuscript\n" + "\n\n".join(ch_parts))

        if use_vector:
            search_q = " ".join(filter(None, [query_text, extra_text[:500]]))
            hits = self.query(project.id, search_q)
            if hits:
                hit_texts = []
                for h in hits:
                    title = (h.get("metadata") or {}).get("title", "story")
                    htype = (h.get("metadata") or {}).get("type", "chunk")
                    label = f"{htype}: {title}"
                    if label not in sources:
                        sources.append(label)
                    hit_texts.append(h["text"])
                sections.append(
                    "## Retrieved Story Memory\n" + "\n---\n".join(hit_texts)
                )

        return "\n\n".join(sections), sources

    def delete_project_collection(self, project_id: str) -> None:
        if not _chroma_lock.acquire(timeout=5.0):
            return
        try:
            client = self.client
            if client is None:
                return
            name = f"project_{project_id.replace('-', '_')}"
            try:
                client.delete_collection(name)
            except Exception:  # noqa: BLE001
                pass
        finally:
            _chroma_lock.release()


_memory: Optional[StoryMemory] = None


def get_memory() -> StoryMemory:
    global _memory
    if _memory is None:
        _memory = StoryMemory()
    return _memory
