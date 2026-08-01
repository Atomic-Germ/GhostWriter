"""API smoke tests with temp data dir."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GW_SKIP_EMBED_WARMUP", "1")

    from app.config import get_settings
    from app.db import storage as storage_mod
    from app.services import embeddings as emb_mod
    from app.services import indexer as indexer_mod
    from app.services import llm as llm_mod
    from app.services import rag as rag_mod

    get_settings.cache_clear()
    storage_mod._store = None
    llm_mod._llm = None
    rag_mod._memory = None
    indexer_mod._worker = None
    emb_mod._model = None
    emb_mod._load_error = "skipped in tests"
    emb_mod._status = "error"
    monkeypatch.setattr(emb_mod, "is_embedding_ready", lambda: False)
    monkeypatch.setattr(emb_mod, "get_status", lambda: "error")
    monkeypatch.setattr(emb_mod, "warm_embeddings", lambda: False)

    class _FakeLLM:
        async def check_available(self, force: bool = False):
            return False

        async def assist(self, **kwargs):
            return ("offline test reply", False)

    monkeypatch.setattr(llm_mod, "get_llm", lambda: _FakeLLM())

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    storage_mod._store = None
    llm_mod._llm = None
    rag_mod._memory = None
    if indexer_mod._worker:
        indexer_mod._worker.stop()
    indexer_mod._worker = None


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_project_flow(client):
    r = client.post(
        "/api/projects",
        json={
            "title": "Moon Harbor",
            "genre": "Mystery",
            "premise": "Fog hides a secret",
        },
    )
    assert r.status_code == 201
    project = r.json()
    pid = project["id"]

    r = client.get("/api/projects")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    r = client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "Mara", "role": "Detective", "personality": "Patient"},
    )
    assert r.status_code == 201

    r = client.post(
        f"/api/projects/{pid}/chapters",
        json={
            "title": "Chapter 1",
            "content": "The harbor lights flickered twice.",
        },
    )
    assert r.status_code == 201
    chapter = r.json()

    r = client.patch(
        f"/api/projects/{pid}/chapters/{chapter['id']}",
        json={
            "content": "The harbor lights flickered twice. Mara closed her notebook."
        },
    )
    assert r.status_code == 200
    assert r.json()["word_count"] > 5

    r = client.post(
        "/api/assist",
        json={
            "project_id": pid,
            "chapter_id": chapter["id"],
            "mode": "brainstorm",
            "prompt": "What should happen next? Keep your answer limited to one paragraph",
            "context_text": "The harbor lights flickered twice.",
        },
    )
    assert r.status_code == 200
    assert "response" in r.json()

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204


def test_fork_project(client):
    r = client.post(
        "/api/projects",
        json={"title": "Original", "genre": "Sci-Fi", "premise": "A forkable draft"},
    )
    assert r.status_code == 201
    original = r.json()
    pid = original["id"]

    r = client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "Chapter 1", "content": "The original text.", "order": 0},
    )
    assert r.status_code == 201

    r = client.post(f"/api/projects/{pid}/fork", json={"title": "Fork One"})
    assert r.status_code == 201
    fork = r.json()
    assert fork["title"] == "Fork One"
    assert fork["fork_of"] == pid
    assert len(fork["chapters"]) == 1
    assert fork["chapters"][0]["content"] == "The original text."
    assert fork["id"] != pid

    r = client.get("/api/projects")
    all_projects = r.json()
    assert any(p["id"] == fork["id"] for p in all_projects)
    summary = next(p for p in all_projects if p["id"] == fork["id"])
    assert summary["fork_of"] == pid

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204
    r = client.delete(f"/api/projects/{fork['id']}")
    assert r.status_code == 204


def test_fork_project_default_title(client):
    r = client.post(
        "/api/projects",
        json={"title": "Base", "genre": "Fantasy"},
    )
    assert r.status_code == 201
    original = r.json()
    pid = original["id"]

    r = client.post(f"/api/projects/{pid}/fork")
    assert r.status_code == 201
    fork = r.json()
    assert fork["title"] == "Base (fork)"
    assert fork["fork_of"] == pid

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204
    r = client.delete(f"/api/projects/{fork['id']}")
    assert r.status_code == 204
