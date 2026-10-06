"""Database tables (SQLModel = SQLAlchemy tables defined like Pydantic models).

Design choice: the generated content (transcript, notes, flashcards, quiz) is
stored as JSON text columns on the lecture row instead of many separate
tables. It is always read and written as a whole, so this keeps the schema
simple while Pydantic still validates it on the way in and out.
"""

from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)



class Lecture(SQLModel, table=True):
    id: str = Field(primary_key=True)

    # Where it came from
    source_type: str                        # "youtube" | "upload"
    source_id: str = Field(index=True)      # YouTube video ID or file SHA-256 (the cache key)
    url: str | None = None
    title: str
    channel: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    language: str = "auto"                  # lecture language hint
    notes_language: str = "english"         # language of the generated material

    # Processing state
    status: str = Field(default="queued", index=True)  # queued | processing | done | failed
    stage: str = "queued"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    error_hint: str | None = None
    warnings_json: str = "[]"
    processing_seconds: float | None = None

    # Results
    transcript_source: str | None = None
    detected_language: str | None = None
    llm_model: str | None = None
    transcript_json: str | None = None
    notes_json: str | None = None
    flashcards_json: str | None = None
    quiz_json: str | None = None
    flashcard_count: int = 0
    quiz_count: int = 0

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class QuizAttempt(SQLModel, table=True):
    """One completed quiz, used for scores and the stats dashboard."""

    id: int | None = Field(default=None, primary_key=True)
    lecture_id: str = Field(foreign_key="lecture.id", index=True)
    difficulty: str = "mixed"
    score: int
    total: int
    answers_json: str = "[]"
    time_taken_seconds: float | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class FlashcardReview(SQLModel, table=True):
    """Spaced-repetition progress of one flashcard (Leitner box and next due date)."""

    __table_args__ = (UniqueConstraint("lecture_id", "card_id"),)

    id: int | None = Field(default=None, primary_key=True)
    lecture_id: str = Field(foreign_key="lecture.id", index=True)
    card_id: str
    box: int = 1
    due_at: datetime = Field(default_factory=utcnow)
    reviews: int = 0
    correct_count: int = 0
    last_result: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)
