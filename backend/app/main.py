"""FastAPI application entry point.

Run the development server from the backend/ folder:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for interactive API documentation.
"""

import logging
import re
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import routes_chat, routes_export, routes_flashcards, routes_lectures, routes_quiz, routes_stats
from app.api.errors import register_error_handlers
from app.api.schemas import HealthOut
from app.config import Settings, get_settings
from app.db import repository
from app.db.session import create_db_engine, resolve_db_path
from app.llm.factory import get_llm
from app.logging_config import setup_logging
from app.pipeline.jobs import JobManager, Pipeline
from app.pipeline.orchestrator import LecturePipeline
from app.pipeline.progress import ProgressStore
from app.rag.embedder import GeminiEmbedder, SentenceTransformerEmbedder
from app.rag.service import RAGService
from app.rag.vector_store import ChromaVectorStore

VERSION = "0.5.0"
logger = logging.getLogger(__name__)


def build_rag(settings: Settings) -> RAGService:
    """The real RAG service: embeddings (local model or Gemini API) + ChromaDB on disk + the LLM."""
    if settings.embedding_provider == "gemini":
        embedder = GeminiEmbedder(settings.gemini_api_key, settings.gemini_embedding_model)
        # Different models give incompatible vectors: keep them in separate collections.
        collection = "lecture_chunks_" + re.sub(r"[^a-z0-9]+", "_", settings.gemini_embedding_model.lower())
    else:
        embedder = SentenceTransformerEmbedder(settings.embedding_model)
        collection = "lecture_chunks"
    return RAGService(
        store=ChromaVectorStore(settings.data_path / "chroma", collection=collection),
        embedder=embedder,
        llm_factory=lambda: get_llm(settings=settings),
        settings=settings,
    )


def create_app(
    settings: Settings | None = None,
    pipeline: Pipeline | None = None,
    rag: RAGService | None = None,
) -> FastAPI:
    """Build the FastAPI app (the *app factory* pattern).

    Tests call this with temporary settings, a fake pipeline and a fake RAG
    service, so they never touch your real database or call real APIs.
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- startup ---
        setup_logging(settings.log_level)
        engine = create_db_engine(resolve_db_path(settings.data_path))
        interrupted = repository.mark_interrupted(engine)
        if interrupted:
            logger.warning("Marked %d interrupted job(s) as failed.", interrupted)

        app.state.settings = settings
        app.state.engine = engine
        app.state.progress = ProgressStore()
        app.state.rag = rag or build_rag(settings)
        app.state.jobs = JobManager(
            engine,
            pipeline or LecturePipeline(settings, indexer=app.state.rag.index_transcript),
            app.state.progress,
            settings.max_parallel_jobs,
        )
        # Load the embedding model in the background, so the first chat question is fast.
        embedder = app.state.rag.embedder
        if settings.rag_warmup and hasattr(embedder, "warm_up"):
            threading.Thread(target=embedder.warm_up, name="embedding-warmup", daemon=True).start()
        logger.info("Lectura API ready. Docs at /docs")
        yield
        # --- shutdown ---
        app.state.jobs.shutdown()
        engine.dispose()

    app = FastAPI(
        title="Lectura API",
        description="AI lecture summariser: notes, flashcards, quizzes and chat from YouTube or uploaded lectures.",
        version=VERSION,
        lifespan=lifespan,
    )
    # CORS: allow the React dev server (a different "origin") to call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(routes_lectures.router)
    app.include_router(routes_quiz.router)
    app.include_router(routes_flashcards.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_export.router)
    app.include_router(routes_stats.router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Opening the bare server address shows the API docs."""
        return RedirectResponse("/docs")

    @app.get("/api/health", response_model=HealthOut, tags=["system"])
    def health() -> HealthOut:
        """Check that the server is running and which AI provider is configured."""
        model = settings.groq_model if settings.llm_provider == "groq" else settings.gemini_model
        return HealthOut(
            status="ok",
            version=VERSION,
            llm_provider=settings.llm_provider,
            llm_model=model,
            groq_configured=settings.has_groq,
            gemini_configured=settings.has_gemini,
            embedding_provider=settings.embedding_provider,
            local_whisper_enabled=settings.local_whisper_enabled,
        )

    return app


app = create_app()
