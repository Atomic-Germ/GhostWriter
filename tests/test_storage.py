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
