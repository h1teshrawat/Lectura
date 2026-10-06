"""FastAPI application entry point.

Run the development server from the backend/ folder:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for interactive API documentation.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import routes_lectures, routes_quiz
from app.api.errors import register_error_handlers
from app.api.schemas import HealthOut
from app.config import Settings, get_settings
from app.db import repository
from app.db.session import create_db_engine
from app.logging_config import setup_logging
from app.pipeline.jobs import JobManager, Pipeline
from app.pipeline.orchestrator import LecturePipeline
from app.pipeline.progress import ProgressStore

VERSION = "0.4.0"
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, pipeline: Pipeline | None = None) -> FastAPI:
    """Build the FastAPI app (the *app factory* pattern).

    Tests call this with temporary settings and a fake pipeline, so they
    never touch your real database or call real APIs.
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- startup ---
        setup_logging(settings.log_level)
        engine = create_db_engine(settings.data_path / "lecturelens.db")
        interrupted = repository.mark_interrupted(engine)
        if interrupted:
            logger.warning("Marked %d interrupted job(s) as failed.", interrupted)

        app.state.settings = settings
        app.state.engine = engine
        app.state.progress = ProgressStore()
        app.state.jobs = JobManager(
            engine, pipeline or LecturePipeline(settings), app.state.progress, settings.max_parallel_jobs
        )
        logger.info("LectureLens API ready. Docs at /docs")
        yield
        # --- shutdown ---
        app.state.jobs.shutdown()
        engine.dispose()

    app = FastAPI(
        title="LectureLens API",
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
        )

    return app


app = create_app()
