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

        async def complete(self, **kwargs):
            return '{"characters": [], "world_facts": []}'

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


def test_series_flow(client):
    # Two books in one series, one standalone
    r = client.post(
        "/api/projects",
        json={"title": "Book One", "series": "Twin Suns", "series_position": 1},
    )
    assert r.status_code == 201
    book1 = r.json()

    r = client.post(
        "/api/projects",
        json={"title": "Book Two", "series": "Twin Suns", "series_position": 2},
    )
    assert r.status_code == 201
    book2 = r.json()

    r = client.post("/api/projects", json={"title": "Standalone"})
    assert r.status_code == 201
    solo = r.json()

    # Series bible save + fetch
    r = client.put(
        "/api/series/Twin Suns/bible",
        json={
            "world_notes": "Two suns rise over a tonal-magic world.",
            "characters": [
                {"name": "Mira", "role": "Protagonist", "relationships": "Sister of Ona"}
            ],
        },
    )
    assert r.status_code == 200
    bible = r.json()
    assert bible["name"] == "Twin Suns"
    assert bible["characters"][0]["name"] == "Mira"

    r = client.get("/api/series/Twin Suns/bible")
    assert r.status_code == 200
    assert r.json()["world_notes"] == "Two suns rise over a tonal-magic world."

    # Listing groups books under the series
    r = client.get("/api/series")
    assert r.status_code == 200
    series_list = r.json()
    twin = next(s for s in series_list if s["name"] == "Twin Suns")
    assert len(twin["books"]) == 2
    assert twin["character_count"] == 1

    # Project summaries expose series
    r = client.get("/api/projects")
    summaries = r.json()
    summary = next(s for s in summaries if s["id"] == book1["id"])
    assert summary["series"] == "Twin Suns"

    # Assist in series mode works offline and reaches context builder
    r = client.post(
        "/api/assist",
        json={
            "project_id": book1["id"],
            "mode": "series",
            "prompt": "What do we know about Mira?",
        },
    )
    assert r.status_code == 200
    assert "response" in r.json()
    body = r.json()
    assert any("Twin Suns" in s for s in body.get("sources", []))

    # Canon mode includes this book's draft + the universe (bible/books)
    r = client.post(
        f"/api/projects/{book1['id']}/chapters",
        json={"title": "Chapter 1", "content": "Mira speaks with Ona."},
    )
    assert r.status_code == 201
    r = client.post(
        "/api/assist",
        json={
            "project_id": book1["id"],
            "mode": "canon",
            "prompt": "Does this fit the canon?",
        },
    )
    assert r.status_code == 200
    body = r.json()
    joined = " ".join(body.get("sources", []))
    assert "Twin Suns" in joined
    assert "This Book's Draft" in joined

    for pid in (book1["id"], book2["id"], solo["id"]):
        r = client.delete(f"/api/projects/{pid}")
        assert r.status_code == 204


def test_extract_requires_llm(client):
    r = client.post("/api/projects", json={"title": "Extractable"})
    assert r.status_code == 201
    pid = r.json()["id"]
    client.post(
        f"/api/projects/{pid}/chapters",
        json={
            "title": "Chapter 1",
            "content": "Mira walked under two suns. Her sister Ona waited.",
            "order": 0,
        },
    )

    # No LLM connected in the test fixture → 503
    r = client.post(
        f"/api/projects/{pid}/extract",
        json={"project_id": pid},
    )
    assert r.status_code == 503

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204


def test_extract_with_llm(client, monkeypatch):
    r = client.post("/api/projects", json={"title": "Extractable"})
    assert r.status_code == 201
    pid = r.json()["id"]
    client.post(
        f"/api/projects/{pid}/chapters",
        json={
            "title": "Chapter 1",
            "content": "Mira walked under two suns. Her sister Ona waited.",
            "order": 0,
        },
    )

    from app.api import extract as extract_mod

    class _ExtractLLM:
        async def check_available(self, force: bool = False):
            return True

        async def complete(self, **kwargs):
            return (
                '{"characters": [{"name": "Mira", "role": "Protagonist", '
                '"relationships": "Sister of Ona"}, {"name": "Ona", "role": "Sibling"}], '
                '"locations": [{"name": "Vell Mar", "type": "city", '
                '"description": "Mira\'s home"}, {"name": "The Bell Tower", '
                '"type": "landmark"}], '
                '"world_facts": ["The world has two suns.", "Magic is tonal."]}'
            )

    monkeypatch.setattr(extract_mod, "get_llm", lambda: _ExtractLLM())

    r = client.post(
        f"/api/projects/{pid}/extract",
        json={"project_id": pid},
    )
    assert r.status_code == 200
    body = r.json()
    names = [c["name"] for c in body["characters"]]
    assert names == ["Mira", "Ona"]
    loc_names = [l["name"] for l in body["locations"]]
    assert loc_names == ["Vell Mar", "The Bell Tower"]
    assert body["locations"][0]["type"] == "city"
    assert body["world_facts"] == ["The world has two suns.", "Magic is tonal."]

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204


def test_extract_retries_when_model_rambles(client, monkeypatch):
    """A thinking model that only emits reasoning should trigger the strict retry."""
    r = client.post("/api/projects", json={"title": "Rambler"})
    assert r.status_code == 201
    pid = r.json()["id"]
    client.post(
        f"/api/projects/{pid}/chapters",
        json={
            "title": "Chapter 1",
            "content": "Dukkat waited for the tube car. Eloise called him Ducky.",
            "order": 0,
        },
    )

    from app.api import extract as extract_mod

    calls = []

    class _RamblingLLM:
        async def check_available(self, force: bool = False):
            return True

        async def complete(self, **kwargs):
            calls.append(kwargs.get("system_prompt", ""))
            if len(calls) == 1:
                # Reasoning-only first pass: no JSON, just thinking aloud.
                return (
                    "I should identify the characters. Dukkat is the main one here, "
                    "nicknamed Ducky by his wife Eloise. I'll write the JSON now."
                )
            return (
                '{"characters": [{"name": "Dukkat", "role": "Bureaucrat", '
                '"relationships": "Husband of Eloise"}, '
                '{"name": "Eloise", "role": "Teacher"}], '
                '"locations": [{"name": "Synergy Cab HQ", "type": "building"}], '
                '"world_facts": ["Synergy Cab is the nationalized transit service."]}'
            )

    monkeypatch.setattr(extract_mod, "get_llm", lambda: _RamblingLLM())

    r = client.post(
        f"/api/projects/{pid}/extract",
        json={"project_id": pid},
    )
    assert r.status_code == 200
    body = r.json()
    names = [c["name"] for c in body["characters"]]
    assert names == ["Dukkat", "Eloise"]
    assert [l["name"] for l in body["locations"]] == ["Synergy Cab HQ"]
    assert len(calls) == 2

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204


def test_extract_parser_fallbacks():
    from app.api.extract import _parse_extraction
    # plain JSON
    r = _parse_extraction(
        '{"characters": [{"name": "Mira"}], "world_facts": ["One moon."]}'
    )
    assert [c.name for c in r.characters] == ["Mira"]
    assert r.world_facts == ["One moon."]

    # plain JSON with locations
    r = _parse_extraction(
        '{"characters": [{"name": "Mira"}], '
        '"locations": [{"name": "Vell Mar", "type": "city", '
        '"description": "Mira\'s home"}], '
        '"world_facts": ["One moon."]}'
    )
    assert [c.name for c in r.characters] == ["Mira"]
    assert [l.name for l in r.locations] == ["Vell Mar"]
    assert r.locations[0].type == "city"
    assert r.locations[0].description == "Mira's home"
    assert r.world_facts == ["One moon."]

    # fenced + trailing prose
    r = _parse_extraction(
        "Here:\n```json\n{\"characters\":[{\"name\":\"Zed\"}],\"world_facts\":[]}\n```\nDone."
    )
    assert [c.name for c in r.characters] == ["Zed"]

    # garbage → raw preserved, empty lists
    r = _parse_extraction("definitely not json")
    assert r.characters == []
    assert r.raw == "definitely not json"

    # malformed array: objects dangling outside the characters list
    r = _parse_extraction(
        '{"characters": [{"name": "Mira"}], {"name": "Zed"}], '
        '"world_facts": ["One moon.", "Two suns."]}'
    )
    assert [c.name for c in r.characters] == ["Mira", "Zed"]
    assert r.world_facts == ["One moon.", "Two suns."]

    # malformed array for locations too (dangling object rescued by repair)
    r = _parse_extraction(
        '{"characters": [{"name": "Mira"}], "locations": [{"name": "Vell Mar"}], '
        '{"name": "The Bell Tower"}], "world_facts": ["One moon."]}'
    )
    assert [l.name for l in r.locations] == ["Vell Mar", "The Bell Tower"]

    # keys out of order: locations before characters — repair slices per key
    r = _parse_extraction(
        '{"locations": [{"name": "Vell Mar", "type": "city"}], '
        '"characters": [{"name": "Mira"}], '
        '"world_facts": ["One moon."]}'
    )
    assert [l.name for l in r.locations] == ["Vell Mar"]
    assert [c.name for c in r.characters] == ["Mira"]
    assert r.world_facts == ["One moon."]

    # junk facts: single words and repeats are dropped
    r = _parse_extraction(
        '{"characters": [], "world_facts": ["watch", "watch", "opinion", '
        '"Districts go dark.", "districts go dark.", "gr"]}'
    )
    assert r.world_facts == ["Districts go dark."]
