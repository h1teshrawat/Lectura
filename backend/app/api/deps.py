"""FastAPI dependencies: shared objects stored on the app at startup."""

from fastapi import Depends, Request
from sqlmodel import Session

from app.api.errors import api_error
from app.config import Settings
from app.db import repository
from app.db.models import Lecture
from app.db.session import get_session
from app.pipeline.jobs import JobManager
from app.pipeline.progress import ProgressStore


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def get_progress_store(request: Request) -> ProgressStore:
    return request.app.state.progress


def get_lecture_or_404(lecture_id: str, session: Session = Depends(get_session)) -> Lecture:
    lecture = repository.get_lecture(session, lecture_id)
    if lecture is None:
        raise api_error(404, "Lecture not found.", "It may have been deleted. Check your library.")
    return lecture
