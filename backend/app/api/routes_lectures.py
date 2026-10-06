"""Lecture endpoints: create, list, details, transcript, live progress, delete."""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session

from app.api.deps import get_app_settings, get_jobs, get_lecture_or_404, get_progress_store
from app.api.errors import api_error
from app.api.schemas import (
    Language,
    LectureCreated,
    LectureDetail,
    LectureSummary,
    NotesLanguage,
    TranscriptOut,
)
from app.config import Settings
from app.db import repository
from app.db.models import Lecture
from app.db.session import get_session
from app.errors import UnsupportedFileError
from app.pipeline.jobs import JobManager
from app.pipeline.orchestrator import JobRequest
from app.transcription.audio import SUPPORTED_EXTENSIONS
from app.transcription.models import Transcript
from app.transcription.youtube_captions import extract_video_id, video_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lectures", tags=["lectures"])

_SSE_POLL_SECONDS = 0.5
_SSE_HEARTBEAT_SECONDS = 2.0


def _save_upload(upload: UploadFile, settings: Settings) -> tuple[Path, str]:
    """Stream an uploaded file to disk, computing its SHA-256 hash and enforcing the size limit."""
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(f"'{suffix or 'unknown'}' files are not supported.")

    upload_dir = settings.data_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    limit = settings.max_upload_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0

    with open(path, "wb") as out:
        while block := upload.file.read(1024 * 1024):
            size += len(block)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise UnsupportedFileError(
                    f"The file is larger than {settings.max_upload_mb} MB.",
                    hint="Compress it to an MP3 first, or split the lecture into parts.",
                )
            digest.update(block)
            out.write(block)

    if size == 0:
        path.unlink(missing_ok=True)
        raise UnsupportedFileError("The uploaded file is empty.")
    return path, digest.hexdigest()


@router.post("", response_model=LectureCreated, status_code=202)
def create_lecture(
    response: Response,
    url: str | None = Form(None, description="YouTube link (or send `file` instead)"),
    file: UploadFile | None = File(None, description="Audio/video file (MP3, MP4, WAV...)"),
    language: Language = Form("auto"),
    notes_language: NotesLanguage = Form("english"),
    force: bool = Form(False, description="Reprocess even if this lecture was processed before"),
    session: Session = Depends(get_session),
    jobs: JobManager = Depends(get_jobs),
    settings: Settings = Depends(get_app_settings),
) -> LectureCreated:
    """Start processing a YouTube link or an uploaded file.

    Returns immediately with the lecture ID. Follow `/progress` for live updates.
    If the same lecture was already processed, returns it instantly (`cached: true`).
    """
    has_url, has_file = bool(url and url.strip()), file is not None and bool(file.filename)
    if has_url == has_file:
        raise api_error(400, "Send either a YouTube link or a file (exactly one of them).")

    if has_url:
        video_id = extract_video_id(url)  # raises a 422 error for bad links
        source_type, source_id, source, title = "youtube", video_id, video_url(video_id), None
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        upload_path = None
    else:
        upload_path, source_id = _save_upload(file, settings)  # type: ignore[arg-type]
        source_type, source, title = "upload", str(upload_path), Path(file.filename).stem  # type: ignore[union-attr]
        thumbnail = None

    # Caching: reuse finished (or still running) results for the same source + language.
    if not force:
        existing = repository.find_cached(session, source_id, notes_language)
        if existing:
            if upload_path:
                upload_path.unlink(missing_ok=True)
            response.status_code = 200 if existing.status == "done" else 202
            logger.info("Cache hit for %s (%s)", source_id[:16], existing.status)
            return LectureCreated(id=existing.id, status=existing.status, cached=existing.status == "done")

    repository.delete_failed_for_source(session, source_id)
    lecture = repository.create_lecture(
        session,
        id=uuid.uuid4().hex[:12],
        source_type=source_type,
        source_id=source_id,
        url=source if source_type == "youtube" else None,
        title=title or "Fetching video details...",
        thumbnail_url=thumbnail,
        language=language,
        notes_language=notes_language,
    )
    jobs.submit(
        JobRequest(
            lecture_id=lecture.id,
            source_type=source_type,
            source=source,
            language=language,
            notes_language=notes_language,
            title=title,
        )
    )
    return LectureCreated(id=lecture.id, status="queued", cached=False)


@router.get("", response_model=list[LectureSummary])
def list_lectures(
    q: str | None = Query(None, description="Search in titles"),
    session: Session = Depends(get_session),
) -> list[LectureSummary]:
    """All lectures, newest first (the library)."""
    return [LectureSummary.from_db(lecture) for lecture in repository.list_lectures(session, q)]


@router.get("/{lecture_id}", response_model=LectureDetail)
def get_lecture(lecture: Lecture = Depends(get_lecture_or_404)) -> LectureDetail:
    """Status and all generated material for one lecture."""
    return LectureDetail.from_db(lecture)


@router.get("/{lecture_id}/transcript", response_model=TranscriptOut)
def get_transcript(lecture: Lecture = Depends(get_lecture_or_404)) -> TranscriptOut:
    if not lecture.transcript_json:
        raise api_error(409, "The transcript isn't ready yet.")
    transcript = Transcript.model_validate_json(lecture.transcript_json)
    return TranscriptOut(source=transcript.source, language=transcript.language, segments=transcript.segments)


@router.delete("/{lecture_id}", status_code=204)
def delete_lecture(
    request: Request,
    lecture: Lecture = Depends(get_lecture_or_404),
    session: Session = Depends(get_session),
) -> Response:
    if lecture.status in repository.ACTIVE_STATUSES:
        raise api_error(409, "This lecture is still being processed.", "Wait until it finishes, then delete it.")
    request.app.state.rag.delete(lecture.id)  # remove its chat search index too
    # FastAPI reuses one session per request, so `lecture` belongs to `session`.
    repository.delete_lecture(session, lecture)
    return Response(status_code=204)


# ----------------------------------------------------------- live progress


def _state_from_db(engine: Engine, lecture_id: str) -> dict | None:
    """Progress from the database (used after a server restart or for finished jobs)."""
    with Session(engine) as session:
        lecture = repository.get_lecture(session, lecture_id)
        if lecture is None:
            return None
        return {
            "status": lecture.status,
            "stage": lecture.stage,
            "progress": lecture.progress,
            "message": lecture.message,
            "warnings": json.loads(lecture.warnings_json or "[]"),
            "error": lecture.error,
            "hint": lecture.error_hint,
            "elapsed_seconds": None,
            "eta_seconds": None,
        }


@router.get("/{lecture_id}/progress", response_class=StreamingResponse)
async def stream_progress(lecture_id: str, request: Request, _lecture: Lecture = Depends(get_lecture_or_404)):
    """Live processing progress as Server-Sent Events (`text/event-stream`).

    Each event looks like:  `event: progress` / `data: {"status": ..., "stage": ..., "progress": 0.42, ...}`
    The stream ends after a `done` or `failed` event.
    """
    store = get_progress_store(request)
    engine: Engine = request.app.state.engine

    async def events() -> AsyncIterator[str]:
        last_key, last_sent = None, 0.0
        loop = asyncio.get_running_loop()
        while not await request.is_disconnected():
            state = store.get(lecture_id)
            data = state.to_dict() if state else await run_in_threadpool(_state_from_db, engine, lecture_id)
            if data is None:
                data = {"status": "failed", "stage": "failed", "error": "Lecture was deleted.", "hint": None}

            # Send when something changed, or every couple of seconds (to refresh the ETA).
            key = (data.get("status"), data.get("stage"), data.get("progress"), data.get("message"),
                   len(data.get("warnings") or []))
            now = loop.time()
            if key != last_key or now - last_sent >= _SSE_HEARTBEAT_SECONDS:
                yield f"event: progress\ndata: {json.dumps(data)}\n\n"
                last_key, last_sent = key, now

            if data.get("status") in ("done", "failed"):
                break
            await asyncio.sleep(_SSE_POLL_SECONDS)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
