"""The full lecture-processing pipeline, from link/file to study material.

    fetching -> transcribing -> notes -> flashcards -> quiz -> indexing

Each stage reports progress through a callback, so the same pipeline can be
driven by the API (with live SSE updates) or by tests (with a fake reporter).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.config import Settings
from app.generators.flashcards import FlashcardGenerator
from app.generators.notes import NotesGenerator
from app.generators.quiz import QuizGenerator
from app.generators.schemas import FlashcardDeck, LectureNotes, QuestionBank
from app.llm.base import LLMProvider, LLMUsage
from app.llm.factory import get_llm
from app.transcription.models import Transcript, TranscriptionResult
from app.transcription.service import TranscriptionService

logger = logging.getLogger(__name__)

# report(stage, fraction within the stage or None, message)
ReportFn = Callable[[str, float | None, str], None]


@dataclass
class JobRequest:
    """Everything needed to process one lecture."""

    lecture_id: str
    source_type: str          # "youtube" | "upload"
    source: str               # YouTube URL or path of the uploaded file
    language: str = "auto"
    notes_language: str = "english"
    title: str | None = None  # original filename for uploads


@dataclass
class PipelineResult:
    transcription: TranscriptionResult
    notes: LectureNotes
    flashcards: FlashcardDeck
    quiz: QuestionBank
    llm_label: str
    llm_usage: LLMUsage


class LecturePipeline:
    """Runs all processing stages for one lecture."""

    def __init__(
        self,
        settings: Settings,
        transcriber: TranscriptionService | None = None,
        llm_factory: Callable[[], LLMProvider] | None = None,
        indexer: Callable[[str, Transcript], int] | None = None,
    ) -> None:
        self.settings = settings
        self.transcriber = transcriber or TranscriptionService(settings)
        self.llm_factory = llm_factory or (lambda: get_llm(settings=settings))
        self.indexer = indexer  # builds the chat search index (RAGService.index_transcript)

    def run(
        self,
        job: JobRequest,
        report: ReportFn,
        on_transcribed: Callable[[TranscriptionResult], None] | None = None,
    ) -> PipelineResult:
        """Process a lecture. Raises LecturaError subclasses on expected failures."""
        # Create the LLM first: if the API key is missing we fail in a second,
        # not after minutes of transcription.
        llm = self.llm_factory()

        # 1-2. Fetching + transcribing
        report("fetching", 0.0, "Starting...")
        def transcription_progress(stage: str, message: str, fraction: float | None) -> None:
            report(stage, fraction, message)

        if job.source_type == "youtube":
            transcription = self.transcriber.transcribe_youtube(
                job.source, language=job.language, on_progress=transcription_progress  # type: ignore[arg-type]
            )
        else:
            transcription = self.transcriber.transcribe_file(
                job.source, language=job.language, title=job.title, on_progress=transcription_progress  # type: ignore[arg-type]
            )
        if on_transcribed:
            on_transcribed(transcription)

        transcript = transcription.transcript
        options = {
            "output_language": job.notes_language,
            "chunk_seconds": self.settings.chunk_seconds,
            "max_workers": self.settings.llm_max_concurrency,
            "temperature": self.settings.llm_temperature,
        }

        # 3. Notes (map-reduce)
        report("notes", 0.0, "Generating smart notes...")
        notes = NotesGenerator(llm, **options).generate(
            transcript,
            title_hint=transcription.media.title,
            on_progress=lambda message, fraction: report("notes", fraction, message),
        )

        # 4. Flashcards
        report("flashcards", 0.0, "Writing flashcards...")
        flashcards = FlashcardGenerator(llm, **options).generate(
            transcript, on_progress=lambda message, fraction: report("flashcards", fraction, message)
        )

        # 5. Quiz
        report("quiz", 0.0, "Writing quiz questions...")
        quiz = QuizGenerator(llm, **options).generate(
            transcript, on_progress=lambda message, fraction: report("quiz", fraction, message)
        )

        # 6. Indexing for "chat with the lecture" (RAG)
        report("indexing", 0.0, "Indexing the transcript for chat...")
        if self.indexer:
            try:
                pieces = self.indexer(job.lecture_id, transcript)
                report("indexing", 1.0, f"Indexed {pieces} transcript pieces for chat.")
            except Exception:  # noqa: BLE001 - notes/quiz are ready; chat retries indexing on first use
                logger.exception("Indexing for chat failed for lecture %s", job.lecture_id)
                report("indexing", 1.0, "Chat index will be built when you first open the chat.")

        logger.info(
            "Lecture %s processed with %s: %d LLM calls, %d tokens",
            job.lecture_id, llm.label, llm.usage.calls, llm.usage.total_tokens,
        )
        return PipelineResult(
            transcription=transcription,
            notes=notes,
            flashcards=flashcards,
            quiz=quiz,
            llm_label=llm.label,
            llm_usage=llm.usage,
        )
