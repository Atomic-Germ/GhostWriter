from fastapi import APIRouter

from app.db.storage import get_store
from app.models.schemas import SeriesBible, SeriesBibleUpdate, SeriesInfo

router = APIRouter(prefix="/series", tags=["series"])


@router.get("", response_model=list[SeriesInfo])
def list_series():
    return get_store().list_series()


@router.get("/{name}/bible", response_model=SeriesBible)
def get_series_bible(name: str):
    return get_store().get_series_bible(name)


@router.put("/{name}/bible", response_model=SeriesBible)
def update_series_bible(name: str, payload: SeriesBibleUpdate):
    return get_store().update_series_bible(name, payload)
