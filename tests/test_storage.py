"""Unit tests for project storage (no embeddings/LLM required)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.storage import ProjectStore
from app.models.schemas import (
    ChapterCreate,
    ChapterUpdate,
    CharacterCreate,
    CharacterUpdate,
    ProjectCreate,
    ProjectUpdate,
)


@pytest.fixture
def store(tmp_path):
    return ProjectStore(base_dir=tmp_path)


def test_project_crud(store):
    p = store.create_project(
        ProjectCreate(title="Test Book", genre="Sci-fi", premise="A ship AI dreams")
    )
    assert p.id
    assert p.title == "Test Book"

    listed = store.list_projects()
    assert len(listed) == 1
    assert listed[0].title == "Test Book"

    updated = store.update_project(p.id, ProjectUpdate(title="Renamed"))
    assert updated.title == "Renamed"

    store.delete_project(p.id)
    assert store.list_projects() == []


def test_character_and_chapter(store):
    p = store.create_project(ProjectCreate(title="Cast Test"))

    c = store.add_character(
        p.id,
        CharacterCreate(name="Ava", role="Protagonist", personality="Wry"),
    )
    assert c.name == "Ava"
    assert len(store.list_characters(p.id)) == 1

    c2 = store.update_character(
        p.id, c.id, CharacterUpdate(motivations="Find home")
    )
    assert c2.motivations == "Find home"

    ch = store.add_chapter(
        p.id,
        ChapterCreate(title="Arrival", content="The rain tasted like copper."),
    )
    assert ch.word_count == 5

    ch2 = store.update_chapter(
        p.id, ch.id, ChapterUpdate(content="One two three four five six")
    )
    assert ch2.word_count == 6

    store.delete_character(p.id, c.id)
    store.delete_chapter(p.id, ch.id)
    p2 = store.get_project(p.id)
    assert p2.characters == []
    assert p2.chapters == []


def test_world_notes(store):
    p = store.create_project(ProjectCreate(title="World"))
    p2 = store.update_world_notes(p.id, "Magic costs memory.")
    assert p2.world_notes == "Magic costs memory."


def test_chapter_orders_renumbered_after_delete(store):
    p = store.create_project(ProjectCreate(title="Orders"))
    ids = []
    for i in range(5):
        ch = store.add_chapter(
            p.id, ChapterCreate(title=f"Chapter {i + 1}", content="x", order=i)
        )
        ids.append(ch.id)

    # Delete the middle chapter — remaining orders must stay contiguous.
    store.delete_chapter(p.id, ids[2])
    p2 = store.get_project(p.id)
    assert [c.order for c in p2.chapters] == [0, 1, 2, 3]

    # Adding a chapter must land at the end (order = len), not collide.
    new = store.add_chapter(
        p.id, ChapterCreate(title="Last", content="y", order=99)
    )
    assert new.order == 4
    p3 = store.get_project(p.id)
    assert [c.order for c in p3.chapters] == [0, 1, 2, 3, 4]
    assert p3.chapters[-1].title == "Last"


def test_chapter_orders_repaired_on_load(store, tmp_path):
    p = store.create_project(ProjectCreate(title="Repair"))
    for i in range(4):
        store.add_chapter(
            p.id, ChapterCreate(title=f"Chapter {i + 1}", content="x", order=i)
        )

    # Corrupt orders on disk directly (simulates the old stale-order bug).
    path = tmp_path / f"{p.id}.json"
    import json as _json

    data = _json.loads(path.read_text(encoding="utf-8"))
    data["chapters"] = sorted(data["chapters"], key=lambda c: c["order"])
    data["chapters"][3]["order"] = 2  # duplicate/out-of-place order
    path.write_text(_json.dumps(data), encoding="utf-8")

    # Loading the project must repair orders to 0..n-1.
    p2 = store.get_project(p.id)
    assert [c.order for c in p2.chapters] == [0, 1, 2, 3]

    # And the fix must persist to disk.
    data2 = _json.loads(path.read_text(encoding="utf-8"))
    assert [c["order"] for c in data2["chapters"]] == [0, 1, 2, 3]
