import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


async def _prepare_context(payload: AssistRequest) -> tuple[str, list[str], str, bool]:
    """Returns context, sources, context_text, llm_available_hint."""
    store = get_store()
    memory = get_memory()
    llm = get_llm()

    try:
        project = await asyncio.to_thread(store.get_project, payload.project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    context_text = payload.context_text or ""
    if not context_text and payload.chapter_id:
        try:
            chapter = await asyncio.to_thread(
                store.get_chapter, payload.project_id, payload.chapter_id
            )
            context_text = chapter.content[-1500:] if chapter.content else ""
        except FileNotFoundError:
            pass

    if payload.mode == "series" and project.series.strip():
        # Cross-book universe context — worldbuilding + cast, no plot
        context, sources = await asyncio.to_thread(
            memory.build_series_context,
            project,
            payload.prompt,
        )
    else:
        context, sources = await asyncio.to_thread(
            memory.build_context_block,
            project,
            payload.prompt,
            context_text,
            False,
        )
    available = await llm.check_available()
    return context, sources, context_text, available


@router.post("/assist", response_model=AssistResponse)
async def assist(payload: AssistRequest):
    """Non-streaming assist (kept for tests / simple clients)."""
    logger.info("Assist START mode=%s project=%s", payload.mode, payload.project_id)
    context, sources, context_text, _ = await _prepare_context(payload)
    response_text, available = await get_llm().assist(
        mode=payload.mode,
        prompt=payload.prompt,
        context=context,
        context_text=context_text,
    )
    logger.info("Assist DONE available=%s chars=%s", available, len(response_text or ""))
    return AssistResponse(
        response=response_text,
        sources=sources,
        mode=payload.mode,
        llm_available=available,
    )


@router.post("/assist/stream")
async def assist_stream(payload: AssistRequest):
    """SSE stream: meta → token* → done | error."""
    logger.info(
        "Assist STREAM start mode=%s project=%s",
        payload.mode,
        payload.project_id,
    )
    context, sources, context_text, available = await _prepare_context(payload)
    llm = get_llm()

    async def event_gen():
        def sse(obj: dict) -> str:
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        yield sse(
            {
                "type": "meta",
                "mode": payload.mode,
                "sources": sources,
                "llm_available": available,
                "model": llm._model_name() if available else None,
            }
        )

        try:
            async for kind, data in llm.assist_stream(
                mode=payload.mode,
                prompt=payload.prompt,
                context=context,
                context_text=context_text,
            ):
                if kind == "token":
                    yield sse({"type": "token", "text": data})
                elif kind == "thinking":
                    yield sse({"type": "thinking", "text": data})
                elif kind == "promote_thinking":
                    yield sse({"type": "promote_thinking"})
                elif kind == "error":
                    yield sse({"type": "error", "message": data})
                elif kind == "done":
                    yield sse({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Assist stream crashed")
            yield sse({"type": "error", "message": str(exc)})

        logger.info("Assist STREAM end")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/index", response_model=IndexResponse)
def index_project(payload: IndexRequest):
    try:
        get_store().get_project(payload.project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    schedule_reindex(payload.project_id, payload.chapter_id)
    return IndexResponse(
        indexed_chunks=0,
        message="Story memory re-index queued."
        if is_embedding_ready()
        else "Re-index queued.",
    )
