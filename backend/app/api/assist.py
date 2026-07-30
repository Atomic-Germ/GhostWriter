import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.db.storage import get_store
from app.models.schemas import (
    AssistRequest,
    AssistResponse,
    IndexRequest,
    IndexResponse,
)
from app.services.embeddings import is_embedding_ready
from app.services.indexer import schedule_reindex
from app.services.llm import get_llm
from app.services.rag import get_memory

logger = logging.getLogger("ghostwriter.assist")

router = APIRouter(tags=["assist"])


@router.post("/assist", response_model=AssistResponse)
async def assist(payload: AssistRequest):
    logger.info(
        "Assist request mode=%s project=%s prompt_chars=%s",
        payload.mode,
        payload.project_id,
        len(payload.prompt or ""),
    )

    store = get_store()
    memory = get_memory()
    llm = get_llm()

    try:
        project = await asyncio.to_thread(store.get_project, payload.project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    context_text = payload.context_text
    if not context_text and payload.chapter_id:
        try:
            chapter = await asyncio.to_thread(
                store.get_chapter, payload.project_id, payload.chapter_id
            )
            context_text = chapter.content[-1500:] if chapter.content else ""
        except FileNotFoundError:
            pass

    # Structured context is enough for lore; vector search is optional bonus
    # and must never block the LLM call.
    try:
        context, sources = await asyncio.wait_for(
            asyncio.to_thread(
                memory.build_context_block,
                project,
                payload.prompt,
                context_text or "",
                True,
            ),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Context build timed out — using structured context only")
        context, sources = await asyncio.to_thread(
            memory.build_context_block,
            project,
            payload.prompt,
            context_text or "",
            False,  # skip vector
        )
    except Exception:  # noqa: BLE001
        logger.exception("Context build failed — minimal context")
        context = f"Title: {project.title}\n\n## World Notes\n{project.world_notes}"
        sources = ["World Notes"] if project.world_notes else []

    logger.info(
        "Context ready sources=%s chars=%s → calling LLM",
        len(sources),
        len(context),
    )

    response_text, available = await llm.assist(
        mode=payload.mode,
        prompt=payload.prompt,
        context=context,
        context_text=context_text or "",
    )

    logger.info("Assist done llm_available=%s response_chars=%s", available, len(response_text))

    return AssistResponse(
        response=response_text,
        sources=sources,
        mode=payload.mode,
        llm_available=available,
    )


@router.post("/index", response_model=IndexResponse)
def index_project(payload: IndexRequest):
    try:
        get_store().get_project(payload.project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    schedule_reindex(payload.project_id, payload.chapter_id)
    ready = is_embedding_ready()
    return IndexResponse(
        indexed_chunks=0,
        message=(
            "Story memory re-index queued."
            if ready
            else "Re-index queued (embeddings still loading)."
        ),
    )
