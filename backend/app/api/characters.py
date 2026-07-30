from fastapi import APIRouter, HTTPException

from app.db.storage import get_store
from app.models.schemas import Character, CharacterCreate, CharacterUpdate
from app.services.indexer import schedule_reindex

router = APIRouter(
    prefix="/projects/{project_id}/characters",
    tags=["characters"],
)


@router.get("", response_model=list[Character])
def list_characters(project_id: str):
    try:
        return get_store().list_characters(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("", response_model=Character, status_code=201)
def create_character(project_id: str, payload: CharacterCreate):
    try:
        character = get_store().add_character(project_id, payload)
        schedule_reindex(project_id)
        return character
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{character_id}", response_model=Character)
def get_character(project_id: str, character_id: str):
    try:
        return get_store().get_character(project_id, character_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{character_id}", response_model=Character)
def update_character(project_id: str, character_id: str, payload: CharacterUpdate):
    try:
        character = get_store().update_character(project_id, character_id, payload)
        schedule_reindex(project_id)
        return character
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{character_id}", status_code=204)
def delete_character(project_id: str, character_id: str):
    try:
        get_store().delete_character(project_id, character_id)
        schedule_reindex(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
