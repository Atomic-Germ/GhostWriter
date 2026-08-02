import asyncio
import json
import logging
import re

from fastapi import APIRouter, HTTPException

from app.db.storage import get_store
from app.models.schemas import ExtractRequest, ExtractResponse, ExtractedCharacter
from app.services.llm import MODE_SYSTEM_PROMPTS, get_llm

logger = logging.getLogger("ghostwriter.extract")

router = APIRouter(prefix="/projects", tags=["extract"])

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_extraction(raw: str) -> ExtractResponse:
    """Parse model output into a structured response; best-effort fallbacks."""
    text = (raw or "").strip()
    if not text:
        return ExtractResponse(raw=raw)

    # Strip markdown fences if present, otherwise use the raw text
    fence = _JSON_FENCE.search(text)
    candidate = fence.group(1).strip() if fence else text
    # Find the outermost JSON object
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ExtractResponse(raw=raw)

    try:
        data = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return ExtractResponse(raw=raw)

    characters: list[ExtractedCharacter] = []
    for item in data.get("characters") or []:
        if isinstance(item, dict) and item.get("name"):
            characters.append(
                ExtractedCharacter(
                    name=str(item.get("name", "")).strip()[:200],
                    role=str(item.get("role", "") or "").strip()[:200],
                    physical_traits=str(item.get("physical_traits", "") or "").strip()[:500],
                    personality=str(item.get("personality", "") or "").strip()[:1000],
                    motivations=str(item.get("motivations", "") or "").strip()[:1000],
                    speech_patterns=str(item.get("speech_patterns", "") or "").strip()[:500],
                    backstory=str(item.get("backstory", "") or "").strip()[:2000],
                    relationships=str(item.get("relationships", "") or "").strip()[:1000],
                    notes=str(item.get("notes", "") or "").strip()[:1000],
                )
            )

    world_facts = []
    for fact in data.get("world_facts") or []:
        if isinstance(fact, str) and fact.strip():
            world_facts.append(fact.strip()[:500])

    return ExtractResponse(
        characters=characters,
        world_facts=world_facts,
        raw=raw,
    )


@router.post("/{project_id}/extract", response_model=ExtractResponse)
async def extract_from_story(project_id: str, payload: ExtractRequest):
    """Read prose and return proposed characters + world facts (no plot)."""
    store = get_store()
    llm = get_llm()

    try:
        project = await asyncio.to_thread(store.get_project, project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    chapters = sorted(project.chapters, key=lambda c: c.order)
    if payload.chapter_id:
        chapters = [c for c in chapters if c.id == payload.chapter_id]
    if not chapters:
        return ExtractResponse(raw="No chapter content to extract from.")

    # Concatenate prose (chapter titles excluded — this is plot-ignorant but we
    # keep the raw text only; titles are fine to omit)
    prose_parts: list[str] = []
    budget = 60000
    used = 0
    for ch in chapters:
        body = (ch.content or "").strip()
        if not body:
            continue
        remaining = budget - used
        if remaining <= 0:
            break
        if len(body) > remaining:
            body = body[:remaining] + "…[truncated]"
        prose_parts.append(body)
        used += len(body)

    if not prose_parts:
        return ExtractResponse(raw="No chapter content to extract from.")

    user_message = (
        "Extract the cast and worldbuilding from this story prose (ignore plot):\n\n"
        + "\n\n".join(prose_parts)
    )

    available = await llm.check_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="No LLM connected — start llama.cpp to extract from the story.",
        )

    try:
        raw = await llm.complete(
            user_message=user_message,
            system_prompt=MODE_SYSTEM_PROMPTS["extract"],
            temperature=0.2,
            max_tokens=4000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Extract LLM call failed")
        raise HTTPException(status_code=502, detail=f"Extraction failed: {exc}") from exc

    result = _parse_extraction(raw)
    logger.info(
        "Extract done project=%s characters=%s facts=%s",
        project_id,
        len(result.characters),
        len(result.world_facts),
    )
    return result
