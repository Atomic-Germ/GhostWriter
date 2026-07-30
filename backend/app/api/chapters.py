from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db.storage import get_store
from app.models.schemas import Chapter, ChapterCreate, ChapterUpdate
from app.services.indexer import schedule_reindex

router = APIRouter(
    prefix="/projects/{project_id}/chapters",
    tags=["chapters"],
)


def _maybe_index(project_id: str, chapter_id: str | None = None) -> None:
    if get_settings().auto_index:
        schedule_reindex(project_id, chapter_id)


@router.get("", response_model=list[Chapter])
def list_chapters(project_id: str):
    try:
        return get_store().list_chapters(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("", response_model=Chapter, status_code=201)
def create_chapter(project_id: str, payload: ChapterCreate):
    try:
        chapter = get_store().add_chapter(project_id, payload)
        if chapter.content.strip():
            _maybe_index(project_id, chapter.id)
        return chapter
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{chapter_id}", response_model=Chapter)
def get_chapter(project_id: str, chapter_id: str):
    try:
        return get_store().get_chapter(project_id, chapter_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{chapter_id}", response_model=Chapter)
def update_chapter(project_id: str, chapter_id: str, payload: ChapterUpdate):
    """Save only — must stay fast. Indexing is background + optional."""
    try:
        chapter = get_store().update_chapter(project_id, chapter_id, payload)
        if payload.content is not None or payload.summary is not None:
            _maybe_index(project_id, chapter.id)
        return chapter
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{chapter_id}", status_code=204)
def delete_chapter(project_id: str, chapter_id: str):
    try:
        get_store().delete_chapter(project_id, chapter_id)
        _maybe_index(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
