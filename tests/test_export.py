"""Export format smoke tests."""

import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.schemas import Chapter, Character, Project
from app.services.export import export_project, filename_for, media_type_for


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


def test_docx_export_includes_chapter_content(sample_project):
    data = export_project(sample_project, "docx")
    assert data[:2] == b"PK"
    zf = zipfile.ZipFile(BytesIO(data))
    xml = zf.read("word/document.xml").decode("utf-8")
    texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
    body = "".join(texts)
    assert "Chapter 1" in texts
    assert "Eddie thought" in body
    assert "the guards advanced" in body.lower()
    assert "(empty)" not in body
    assert filename_for(sample_project, "docx") == "superposition.docx"


def test_epub_is_zip(sample_project):
    data = export_project(sample_project, "epub")
    assert data[:2] == b"PK"
    assert b"mimetype" in data
    assert b"application/epub+zip" in data


def test_epub_has_amazon_metadata(sample_project):
    sample_project.author = "Jane Doe"
    sample_project.publisher = "Self-Published"
    sample_project.isbn = "9781234567890"
    sample_project.series = "Superposition Series"
    sample_project.series_position = 3
    sample_project.copyright = "Copyright © 2026 Jane Doe"
    data = export_project(sample_project, "epub")
    zf = zipfile.ZipFile(BytesIO(data))
    opf = zf.read("OEBPS/content.opf").decode("utf-8")

    assert "<dc:creator" in opf and "Jane Doe" in opf
    assert "<dc:language>" in opf and "en" in opf
    assert "<dc:publisher" in opf and "Self-Published" in opf
    assert "<dc:rights" in opf and "Copyright" in opf
    assert "urn:isbn:9781234567890" in opf
    assert "belongs-to-collection" in opf
    assert "group-position" in opf and ">3<" in opf
    assert '<reference type="copyright-page"' in opf

    copy = zf.read("OEBPS/copyright.xhtml").decode("utf-8")
    assert "Jane Doe" in copy
    assert "9781234567890" in copy
    assert "All rights reserved" in copy

    title = zf.read("OEBPS/title.xhtml").decode("utf-8")
    assert "Jane Doe" in title


def test_json_backup(sample_project):
    raw = export_project(sample_project, "json").decode("utf-8")
    assert '"title": "Superposition"' in raw
    assert "Eddie Rapton" in raw


def test_manuscript_docx_prose_only(sample_project):
    data = export_project(sample_project, "manuscript-docx")
    assert data[:2] == b"PK"
    zf = zipfile.ZipFile(BytesIO(data))
    xml = zf.read("word/document.xml").decode("utf-8")
    texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
    body = "".join(texts)
    assert "Eddie thought" in body
    assert "the guards advanced" in body.lower()
    assert "Later, the mountain was quiet." in body
    assert "* * *" in texts
    assert "Chapter 1" not in texts
    assert "Chapter 2" not in texts
    assert "Superposition" not in body
    assert "(empty)" not in body
    assert filename_for(sample_project, "manuscript-docx") == "superposition-manuscript.docx"


def test_manuscript_epub_prose_only(sample_project):
    data = export_project(sample_project, "manuscript-epub")
    assert data[:2] == b"PK"
    zf = zipfile.ZipFile(BytesIO(data))
    names = zf.namelist()
    assert "mimetype" in names
    assert "OEBPS/manuscript.xhtml" in names
    assert "OEBPS/nav.xhtml" in names

    xhtml = zf.read("OEBPS/manuscript.xhtml").decode("utf-8")
    body = xhtml.split("<body", 1)[1].split("</body>", 1)[0]
    assert "Eddie thought" in body
    assert "Later, the mountain was quiet." in body
    assert '<p class="chapnum first">1</p>' in body
    assert '<p class="chapnum">2</p>' in body
    assert "page-break-before" in zf.read("OEBPS/style.css").decode("utf-8")
    assert "Chapter 1" not in body
    assert "Dramatis Personae" not in body
    assert "Superposition" not in body

    assert "OEBPS/title.xhtml" not in names
    assert "OEBPS/copyright.xhtml" not in names
    assert "cover" not in " ".join(names)
    assert filename_for(sample_project, "manuscript-epub") == "superposition-manuscript.epub"


def test_cover_jpg(sample_project):
    data = export_project(sample_project, "cover-jpg")
    assert data[:2] == b"\xff\xd8"  # JPEG SOI marker
    assert data.rstrip()[-2:] == b"\xff\xd9"  # JPEG EOI marker
    assert filename_for(sample_project, "cover-jpg") == "superposition-cover.jpg"
    assert media_type_for("cover-jpg") == "image/jpeg"


def test_cover_tiff(sample_project):
    data = export_project(sample_project, "cover-tiff")
    assert data[:4] in (b"II*\x00", b"MM\x00*")  # TIFF little/big endian magic
    assert filename_for(sample_project, "cover-tiff") == "superposition-cover.tiff"
    assert media_type_for("cover-tiff") == "image/tiff"
