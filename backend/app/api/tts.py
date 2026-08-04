import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.db.storage import get_store
from app.services import tts as tts_svc

logger = logging.getLogger("ghostwriter.tts.api")

router = APIRouter(prefix="/projects", tags=["tts"])

def _tts():
    return tts_svc.get_tts()


def _project(project_id: str):
    try:
        return get_store().get_project(project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{project_id}/tts/status")
def tts_status(project_id: str):
    _project(project_id)
    tts = _tts()
    return {
        "available": tts.available(),
        "voice": "en_US-lessac-medium",
        "guardrail": tts.guardrail_text(),
        "guardrail_interval_seconds": tts.guardrail_interval_seconds(),
        "pacing_defaults": tts_svc.Pacing().as_dict(),
    }


def _pacing(
    paragraph_pause,
    scene_pause,
    chapter_pause,
    quote_pause,
    comma_pause,
    speech_rate,
) -> "tts_svc.Pacing":
    return tts_svc.Pacing(
        paragraph_pause=paragraph_pause,
        scene_pause=scene_pause,
        chapter_pause=chapter_pause,
        quote_pause=quote_pause,
        comma_pause=comma_pause,
        speech_rate=speech_rate,
    )


@router.post("/{project_id}/tts/preview")
def tts_preview(
    project_id: str,
    payload: dict | None = None,
    text: str = Query("", alias="text"),
    paragraph_pause: float = Query(None, alias="paragraph_pause"),
    scene_pause: float = Query(None, alias="scene_pause"),
    chapter_pause: float = Query(None, alias="chapter_pause"),
    quote_pause: float = Query(None, alias="quote_pause"),
    comma_pause: float = Query(None, alias="comma_pause"),
    speech_rate: float = Query(None, alias="speech_rate"),
):
    """Quick low-fidelity clip of a short selection (no guardrail)."""
    _project(project_id)
    text = (payload or {}).get("text", "") if payload else text
    if not (text or "").strip():
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Selection too long (max 5000 chars)")

    tts = _tts()
    if not tts.available():
        raise HTTPException(
            status_code=501,
            detail=(
                "TTS voice not downloaded yet. Run "
                "`python -m app.services.tts download` in the backend and retry."
            ),
        )
    try:
        pacing = _pacing(
            paragraph_pause, scene_pause, chapter_pause, quote_pause, comma_pause, speech_rate
        )
        wav = tts.preview_wav(text, pacing)
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="preview.wav"'},
    )


@router.get("/{project_id}/tts/export")
def tts_export(
    project_id: str,
    paragraph_pause: float = Query(None, alias="paragraph_pause"),
    scene_pause: float = Query(None, alias="scene_pause"),
    chapter_pause: float = Query(None, alias="chapter_pause"),
    quote_pause: float = Query(None, alias="quote_pause"),
    comma_pause: float = Query(None, alias="comma_pause"),
    speech_rate: float = Query(None, alias="speech_rate"),
):
    """Full-book audiobook example — WAV with guardrail disclaimers embedded."""
    project = _project(project_id)
    chapters = sorted(project.chapters, key=lambda c: c.order)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters to synthesize.")

    pacing = _pacing(
        paragraph_pause, scene_pause, chapter_pause, quote_pause, comma_pause, speech_rate
    )

    tts = _tts()
    if not tts.available():
        raise HTTPException(
            status_code=501,
            detail=(
                "TTS voice not downloaded yet. Run "
                "`python -m app.services.tts download` in the backend and retry."
            ),
        )

    tmp = Path(tempfile.mkstemp(suffix=".wav", prefix="ghostwriter-audio-")[1])
    try:
        try:
            meta = tts.export_book(chapters, tmp, pacing)
        except RuntimeError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e
        slug = (project.title or "manuscript").lower().replace(" ", "-")
        filename = f"{slug}-audiobook-example.wav"
        return Response(
            content=tmp.read_bytes(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Audio-Meta": (
                    f"duration={meta['duration_seconds']:.0f}s;"
                    f"chapters={meta['chapters']};"
                    f"disclaimers={meta['disclaimers']}"
                ),
            },
        )
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
