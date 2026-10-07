"""Request and response models for the HTTP API.

These are separate from the database models on purpose: the API decides
exactly what the frontend sees (e.g. it never sends raw JSON strings or the
full question bank with every lecture).
"""

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import Lecture
from app.generators.schemas import Flashcard, LectureNotes, QuizQuestion
from app.transcription.models import TranscriptSegment

Language = Literal["auto", "en", "hi", "hinglish"]
NotesLanguage = Literal["english", "hindi", "hinglish"]
QuizDifficulty = Literal["mixed", "easy", "medium", "hard"]


class LectureCreated(BaseModel):
    id: str
    status: str
    cached: bool = Field(description="True if the results were already available (no reprocessing).")


class LectureSummary(BaseModel):
    """A lecture card in the library."""

    id: str
    title: str
    source_type: str
    video_id: str | None
    url: str | None
    thumbnail_url: str | None
    channel: str | None
    duration_seconds: float | None
    status: str
    notes_language: str
    flashcard_count: int
    quiz_count: int
    created_at: datetime

    @classmethod
    def from_db(cls, lecture: Lecture) -> "LectureSummary":
        return cls(
            id=lecture.id,
            title=lecture.title,
            source_type=lecture.source_type,
            video_id=lecture.source_id if lecture.source_type == "youtube" else None,
            url=lecture.url,
            thumbnail_url=lecture.thumbnail_url,
            channel=lecture.channel,
            duration_seconds=lecture.duration_seconds,
            status=lecture.status,
            notes_language=lecture.notes_language,
            flashcard_count=lecture.flashcard_count,
            quiz_count=lecture.quiz_count,
            created_at=lecture.created_at,
        )


class LectureDetail(LectureSummary):
    """Everything the lecture workspace needs."""

    language: str
    stage: str
    progress: float
    message: str
    error: str | None
    error_hint: str | None
    warnings: list[str]
    transcript_source: str | None
    detected_language: str | None
    llm_model: str | None
    processing_seconds: float | None
    notes: LectureNotes | None
    flashcards: list[Flashcard]

    @classmethod
    def from_db(cls, lecture: Lecture) -> "LectureDetail":
        flashcards = json.loads(lecture.flashcards_json)["cards"] if lecture.flashcards_json else []
        return cls(
            **LectureSummary.from_db(lecture).model_dump(),
            language=lecture.language,
            stage=lecture.stage,
            progress=lecture.progress,
            message=lecture.message,
            error=lecture.error,
            error_hint=lecture.error_hint,
            warnings=json.loads(lecture.warnings_json or "[]"),
            transcript_source=lecture.transcript_source,
            detected_language=lecture.detected_language,
            llm_model=lecture.llm_model,
            processing_seconds=lecture.processing_seconds,
            notes=LectureNotes.model_validate_json(lecture.notes_json) if lecture.notes_json else None,
            flashcards=[Flashcard.model_validate(card) for card in flashcards],
        )


class TranscriptOut(BaseModel):
    source: str | None
    language: str | None
    segments: list[TranscriptSegment]


class QuizOut(BaseModel):
    difficulty: QuizDifficulty
    questions: list[QuizQuestion]


class QuizAnswer(BaseModel):
    question_id: str
    selected_index: int | None = Field(None, ge=0, le=3, description="None if the question was skipped")


class QuizSubmission(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1)
    difficulty: QuizDifficulty = "mixed"
    time_taken_seconds: float | None = Field(None, ge=0)


class QuestionResult(BaseModel):
    question_id: str
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str
    start_seconds: float


class QuizResult(BaseModel):
    attempt_id: int
    score: int
    total: int
    percent: float
    results: list[QuestionResult]
    wrong_question_ids: list[str]


class CardProgress(BaseModel):
    """Spaced-repetition state of one flashcard."""

    card_id: str
    box: int = Field(description="Leitner box 1-5 (0 = never reviewed)")
    due_at: datetime | None
    is_due: bool
    is_mastered: bool
    reviews: int
    correct_count: int
    last_result: Literal["got_it", "again"] | None


class FlashcardProgressOut(BaseModel):
    total: int
    new: int
    learning: int
    mastered: int
    due_now: int
    cards: list[CardProgress]


class ReviewIn(BaseModel):
    result: Literal["got_it", "again"]


class SourceOut(BaseModel):
    """A transcript excerpt used to answer a chat question."""

    start: float
    end: float
    text: str
    similarity: float


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceOut]
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    version: str
    llm_provider: str
    llm_model: str
    groq_configured: bool
    gemini_configured: bool
    embedding_provider: str
    local_whisper_enabled: bool
