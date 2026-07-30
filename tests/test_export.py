"""Export format smoke tests."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.schemas import Chapter, Character, Project
from app.services.export import export_project, filename_for


@pytest.fixture
def sample_project():
    return Project(
        id="p1",
        title="Superposition",
        premise="Immortality is the ultimate goal… right?",
        genre="Science Fiction",
        characters=[
            Character(id="c1", name="Eddie Rapton", role="Protagonist"),
        ],
        chapters=[
            Chapter(
                id="ch1",
                title="Chapter 1",
                order=0,
                content='Eddie thought "Free speech my ass."\n\nThe guards advanced.',
                word_count=10,
            ),
            Chapter(
                id="ch2",
                title="Chapter 2",
                order=1,
                content="Later, the mountain was quiet.",
                word_count=5,
            ),
        ],
        world_notes="Quantum immortality rules apply.",
    )


def test_markdown_export(sample_project):
    raw = export_project(sample_project, "markdown").decode("utf-8")
    assert "# Superposition" in raw
    assert "## Chapter 1" in raw
    assert "Eddie thought" in raw
    assert "Dramatis Personae" in raw
    assert filename_for(sample_project, "markdown") == "superposition.md"


def test_html_export(sample_project):
    raw = export_project(sample_project, "html").decode("utf-8")
    assert "<!DOCTYPE html>" in raw
    assert "Superposition" in raw
    assert "chapter" in raw


def test_txt_export(sample_project):
    raw = export_project(sample_project, "txt").decode("utf-8")
    assert "Superposition" in raw
    assert "Chapter 1" in raw


def test_epub_is_zip(sample_project):
    data = export_project(sample_project, "epub")
    assert data[:2] == b"PK"
    assert b"mimetype" in data
    assert b"application/epub+zip" in data


def test_json_backup(sample_project):
    raw = export_project(sample_project, "json").decode("utf-8")
    assert '"title": "Superposition"' in raw
    assert "Eddie Rapton" in raw
