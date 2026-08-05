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
    return ProjectStore(base_dir=tmp_path, series_dir=tmp_path / "series")


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


def test_series_bible_and_grouping(store, tmp_path):
    from app.models.schemas import Character, Location, ProjectSummary, SeriesBibleUpdate

    a = store.create_project(
        ProjectCreate(title="Book One", series="Twin Suns", series_position=1)
    )
    b = store.create_project(
        ProjectCreate(title="Book Two", series="Twin Suns", series_position=2)
    )
    store.create_project(ProjectCreate(title="Solo"))

    # Bible starts empty
    bible = store.get_series_bible("Twin Suns")
    assert bible.world_notes == ""
    assert bible.characters == []
    assert bible.locations == []

    # Save world notes + cast + locations
    bible = store.update_series_bible(
        "Twin Suns",
        SeriesBibleUpdate(
            world_notes="Two suns, tonal magic.",
            characters=[
                Character(name="Mira", role="Protagonist", relationships="Sister of Ona")
            ],
            locations=[
                Location(name="Vell Mar", type="city", description="Mira's home")
            ],
        ),
    )
    assert bible.world_notes == "Two suns, tonal magic."
    assert bible.characters[0].name == "Mira"
    assert bible.locations[0].name == "Vell Mar"

    # Re-read from disk
    bible2 = store.get_series_bible("Twin Suns")
    assert bible2.world_notes == "Two suns, tonal magic."
    assert bible2.characters[0].name == "Mira"
    assert bible2.locations[0].name == "Vell Mar"
    assert bible2.locations[0].type == "city"

    # Summaries expose series + grouping works
    summaries = store.list_projects()
    series_map = {s.series: s for s in summaries}
    assert series_map["Twin Suns"].id in (a.id, b.id)

    info = store.list_series()
    twin = next(s for s in info if s.name == "Twin Suns")
    assert len(twin.books) == 2
    assert twin.character_count == 1
    assert twin.world_notes == "Two suns, tonal magic."

    # Cross-book lookup
    books = store.projects_in_series("Twin Suns")
    assert {p.id for p in books} == {a.id, b.id}
    assert books[0].series_position == 1

    # Bible file lives under tmp_path (not the real data dir)
    series_dir = tmp_path / "series"
    assert series_dir.exists()
    assert any(series_dir.glob("*.json"))
