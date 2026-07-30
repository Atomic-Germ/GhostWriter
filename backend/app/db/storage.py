"""JSON file-based project storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.models.schemas import (
    Chapter,
    ChapterCreate,
    ChapterUpdate,
    Character,
    CharacterCreate,
    CharacterUpdate,
    Project,
    ProjectCreate,
    ProjectSummary,
    ProjectUpdate,
    new_id,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


class ProjectStore:
    def __init__(self, base_dir: Optional[Path] = None):
        settings = get_settings()
        self.base_dir = base_dir or settings.projects_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self.base_dir / f"{project_id}.json"

    def _load(self, project_id: str) -> Project:
        path = self._path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"Project {project_id} not found")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Project.model_validate(data)

    def _save(self, project: Project) -> Project:
        project.updated_at = _now()
        path = self._path(project.id)
        path.write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return project

    # ── Projects ────────────────────────────────────────────

    def list_projects(self) -> list[ProjectSummary]:
        summaries: list[ProjectSummary] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                chapters = data.get("chapters", [])
                characters = data.get("characters", [])
                word_count = sum(_word_count(c.get("content", "")) for c in chapters)
                summaries.append(
                    ProjectSummary(
                        id=data["id"],
                        title=data.get("title", "Untitled"),
                        description=data.get("description", ""),
                        genre=data.get("genre", ""),
                        chapter_count=len(chapters),
                        character_count=len(characters),
                        word_count=word_count,
                        updated_at=data.get("updated_at", ""),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue
        summaries.sort(key=lambda s: s.updated_at, reverse=True)
        return summaries

    def get_project(self, project_id: str) -> Project:
        return self._load(project_id)

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(
            id=new_id(),
            title=payload.title,
            description=payload.description,
            genre=payload.genre,
            premise=payload.premise,
            characters=[],
            chapters=[],
            world_notes="",
            created_at=_now(),
            updated_at=_now(),
        )
        return self._save(project)

    def update_project(self, project_id: str, payload: ProjectUpdate) -> Project:
        project = self._load(project_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(project, key, value)
        return self._save(project)

    def delete_project(self, project_id: str) -> None:
        path = self._path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"Project {project_id} not found")
        path.unlink()

    def update_world_notes(self, project_id: str, notes: str) -> Project:
        project = self._load(project_id)
        project.world_notes = notes
        return self._save(project)

    # ── Characters ──────────────────────────────────────────

    def list_characters(self, project_id: str) -> list[Character]:
        return self._load(project_id).characters

    def get_character(self, project_id: str, character_id: str) -> Character:
        project = self._load(project_id)
        for c in project.characters:
            if c.id == character_id:
                return c
        raise FileNotFoundError(f"Character {character_id} not found")

    def add_character(self, project_id: str, payload: CharacterCreate) -> Character:
        project = self._load(project_id)
        character = Character(
            id=new_id(),
            **payload.model_dump(),
            created_at=_now(),
            updated_at=_now(),
        )
        project.characters.append(character)
        self._save(project)
        return character

    def update_character(
        self, project_id: str, character_id: str, payload: CharacterUpdate
    ) -> Character:
        project = self._load(project_id)
        for i, c in enumerate(project.characters):
            if c.id == character_id:
                data = c.model_dump()
                data.update(payload.model_dump(exclude_unset=True))
                data["updated_at"] = _now()
                updated = Character.model_validate(data)
                project.characters[i] = updated
                self._save(project)
                return updated
        raise FileNotFoundError(f"Character {character_id} not found")

    def delete_character(self, project_id: str, character_id: str) -> None:
        project = self._load(project_id)
        before = len(project.characters)
        project.characters = [c for c in project.characters if c.id != character_id]
        if len(project.characters) == before:
            raise FileNotFoundError(f"Character {character_id} not found")
        self._save(project)

    # ── Chapters ────────────────────────────────────────────

    def list_chapters(self, project_id: str) -> list[Chapter]:
        chapters = self._load(project_id).chapters
        return sorted(chapters, key=lambda c: c.order)

    def get_chapter(self, project_id: str, chapter_id: str) -> Chapter:
        project = self._load(project_id)
        for c in project.chapters:
            if c.id == chapter_id:
                return c
        raise FileNotFoundError(f"Chapter {chapter_id} not found")

    def add_chapter(self, project_id: str, payload: ChapterCreate) -> Chapter:
        project = self._load(project_id)
        order = payload.order if payload.order else len(project.chapters)
        chapter = Chapter(
            id=new_id(),
            title=payload.title,
            content=payload.content,
            order=order,
            summary=payload.summary,
            word_count=_word_count(payload.content),
            created_at=_now(),
            updated_at=_now(),
        )
        project.chapters.append(chapter)
        self._save(project)
        return chapter

    def update_chapter(
        self, project_id: str, chapter_id: str, payload: ChapterUpdate
    ) -> Chapter:
        project = self._load(project_id)
        for i, c in enumerate(project.chapters):
            if c.id == chapter_id:
                data = c.model_dump()
                updates = payload.model_dump(exclude_unset=True)
                data.update(updates)
                if "content" in updates:
                    data["word_count"] = _word_count(data["content"])
                data["updated_at"] = _now()
                updated = Chapter.model_validate(data)
                project.chapters[i] = updated
                self._save(project)
                return updated
        raise FileNotFoundError(f"Chapter {chapter_id} not found")

    def delete_chapter(self, project_id: str, chapter_id: str) -> None:
        project = self._load(project_id)
        before = len(project.chapters)
        project.chapters = [c for c in project.chapters if c.id != chapter_id]
        if len(project.chapters) == before:
            raise FileNotFoundError(f"Chapter {chapter_id} not found")
        self._save(project)


_store: Optional[ProjectStore] = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
