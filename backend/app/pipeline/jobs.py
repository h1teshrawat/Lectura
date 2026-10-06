"""Background job manager.

Processing a lecture takes minutes, but an HTTP request should answer in
milliseconds. So the API only *queues* the job and returns an ID; a worker
thread does the actual work and reports progress, which the browser follows
through Server-Sent Events.

We use a small thread pool (default: 1 worker) as a queue. With one worker,
lectures are processed one after another, which keeps us under the free API
rate limits.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine

from app.db import repository
from app.errors import LectureLensError
from app.pipeline.orchestrator import JobRequest, PipelineResult, ReportFn
from app.pipeline.progress import ProgressStore, overall_progress
from app.transcription.models import TranscriptionResult

logger = logging.getLogger(__name__)

# Save progress to the database at most this often (seconds).
_DB_SAVE_INTERVAL = 1.0


class Pipeline(Protocol):
    """Anything with this `run` method can be used (the real pipeline or a test fake)."""

    def run(self, job: JobRequest, report: ReportFn, on_transcribed=None) -> PipelineResult: ...


class JobManager:
    def __init__(self, engine: Engine, pipeline: Pipeline, store: ProgressStore, max_workers: int = 1) -> None:
        self.engine = engine
        self.pipeline = pipeline
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="lecture-job")

    def submit(self, job: JobRequest) -> None:
        """Queue a job and return immediately."""
        self.store.update(
            job.lecture_id, status="queued", stage="queued", progress=0.0,
            message="Waiting to start...", started_at=time.time(),
        )
        self.executor.submit(self._run, job)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ worker

    def _run(self, job: JobRequest) -> None:
        lecture_id = job.lecture_id
        started = time.time()
        self.store.update(lecture_id, status="processing", started_at=started)
        repository.update_lecture(self.engine, lecture_id, status="processing")

        try:
            result = self.pipeline.run(
                job,
                self._make_reporter(lecture_id),
                on_transcribed=lambda transcription: self._save_transcript(lecture_id, transcription),
            )
            self._save_result(lecture_id, result, time.time() - started)
        except LectureLensError as exc:
            logger.warning("Lecture %s failed: %s", lecture_id, exc)
            self._fail(lecture_id, exc.message, exc.hint)
        except Exception:  # noqa: BLE001 - any bug must still end the job cleanly
            logger.exception("Unexpected error while processing lecture %s", lecture_id)
            self._fail(
                lecture_id,
                "Something unexpected went wrong while processing this lecture.",
                "Check the backend terminal for details, then try again.",
            )
        finally:
            if job.source_type == "upload":
                Path(job.source).unlink(missing_ok=True)  # the transcript is saved; the file isn't needed

    def _make_reporter(self, lecture_id: str) -> ReportFn:
        """Create the progress callback for one job."""
        last_saved = {"time": 0.0, "stage": ""}

        def report(stage: str, fraction: float | None, message: str) -> None:
            current = self.store.get(lecture_id)
            previous_progress = current.progress if current else 0.0
            if fraction is None:
                # No new number: keep the bar where it is (but never before this stage's start).
                progress = max(previous_progress, overall_progress(stage, 0.0))
            else:
                progress = max(previous_progress, overall_progress(stage, fraction))  # never goes backwards
            self.store.update(lecture_id, stage=stage, progress=progress, message=message)

            now = time.time()
            if stage != last_saved["stage"] or now - last_saved["time"] >= _DB_SAVE_INTERVAL:
                repository.update_lecture(self.engine, lecture_id, stage=stage, progress=progress, message=message)
                last_saved.update(time=now, stage=stage)

        return report

    def _save_transcript(self, lecture_id: str, transcription: TranscriptionResult) -> None:
        """Save title/thumbnail/transcript as soon as transcription finishes."""
        media = transcription.media
        self.store.update(lecture_id, warnings=list(transcription.warnings))
        fields = {
            "channel": media.channel,
            "duration_seconds": media.duration_seconds,
            "transcript_json": transcription.transcript.model_dump_json(),
            "transcript_source": transcription.transcript.source,
            "detected_language": transcription.transcript.language,
            "warnings_json": json.dumps(transcription.warnings),
        }
        if media.source_type == "youtube":
            fields["title"] = media.title
            fields["thumbnail_url"] = media.thumbnail_url
        repository.update_lecture(self.engine, lecture_id, **fields)

    def _save_result(self, lecture_id: str, result: PipelineResult, seconds: float) -> None:
        repository.update_lecture(
            self.engine,
            lecture_id,
            status="done",
            stage="done",
            progress=1.0,
            message="Ready!",
            notes_json=result.notes.model_dump_json(),
            flashcards_json=result.flashcards.model_dump_json(),
            quiz_json=result.quiz.model_dump_json(),
            flashcard_count=len(result.flashcards.cards),
            quiz_count=len(result.quiz.questions),
            llm_model=result.llm_label,
            processing_seconds=round(seconds, 1),
        )
        self.store.update(lecture_id, status="done", stage="done", progress=1.0, message="Ready!")
        logger.info("Lecture %s done in %.0fs", lecture_id, seconds)

    def _fail(self, lecture_id: str, message: str, hint: str | None) -> None:
        self.store.update(lecture_id, status="failed", stage="failed", message=message, error=message, hint=hint)
        repository.update_lecture(
            self.engine, lecture_id, status="failed", stage="failed", message=message, error=message, error_hint=hint
        )
