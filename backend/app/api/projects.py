from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.storage import get_store
from app.models.schemas import (
    Project,
    ProjectCreate,
    ProjectSummary,
    ProjectUpdate,
)
from app.services.indexer import schedule_reindex
from app.services.rag import get_memory

router = APIRouter(prefix="/projects", tags=["projects"])


class WorldNotesUpdate(BaseModel):
    world_notes: str


class ForkRequest(BaseModel):
    title: str | None = None


@router.get("", response_model=list[ProjectSummary])
def list_projects():
    return get_store().list_projects()


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate):
    return get_store().create_project(payload)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    try:
        return get_store().get_project(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate):
    try:
        return get_store().update_project(project_id, payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    try:
        get_store().delete_project(project_id)
        get_memory().delete_project_collection(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{project_id}/world-notes", response_model=Project)
def update_world_notes(project_id: str, payload: WorldNotesUpdate):
    try:
        project = get_store().update_world_notes(project_id, payload.world_notes)
        schedule_reindex(project_id)
        return project
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{project_id}/fork", response_model=Project, status_code=201)
def fork_project(project_id: str, payload: ForkRequest | None = None):
    try:
        title = payload.title if payload else None
        return get_store().fork_project(project_id, title_override=title)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
