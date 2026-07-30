import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assist, chapters, characters, projects
from app.config import get_settings
from app.models.schemas import HealthResponse
from app.services.embeddings import get_status as embedding_status, is_embedding_ready
from app.services.indexer import get_indexer
from app.services.llm import get_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ghostwriter")


def _warmup_background() -> None:
    try:
        from app.services.embeddings import warm_embeddings

        ok = warm_embeddings()
        logger.info("Embedding warmup %s", "succeeded" if ok else "failed")
    except Exception:  # noqa: BLE001
        logger.exception("Embedding warmup crashed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import os

    get_settings().ensure_dirs()
    get_indexer().start()
    # Load embeddings off the request path so Memory can go green without hangs
    if os.environ.get("GW_SKIP_EMBED_WARMUP", "").lower() not in ("1", "true", "yes"):
        threading.Thread(
            target=_warmup_background,
            name="ghostwriter-embed-warmup",
            daemon=True,
        ).start()
    yield
    get_indexer().stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Intelligent writing companion with story-aware RAG",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router, prefix="/api")
    app.include_router(characters.router, prefix="/api")
    app.include_router(chapters.router, prefix="/api")
    app.include_router(assist.router, prefix="/api")

    @app.get("/api/health", response_model=HealthResponse)
    async def health():
        llm_ok = await get_llm().check_available()
        return HealthResponse(
            status="ok",
            llm_available=llm_ok,
            embedding_ready=is_embedding_ready(),
        )

    @app.get("/api/health/detail")
    async def health_detail():
        llm_ok = await get_llm().check_available()
        from app.services import embeddings as emb
        from app.services.indexer import get_indexer

        return {
            "status": "ok",
            "llm_available": llm_ok,
            "embedding_ready": is_embedding_ready(),
            "embedding_status": embedding_status(),
            "embedding_error": emb.get_load_error(),
            "index_error": get_indexer().last_error,
        }

    @app.get("/")
    def root():
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
