"""All database reads and writes in one place (the Repository pattern)."""

from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from app.db.models import FlashcardReview, Lecture, QuizAttempt, utcnow

ACTIVE_STATUSES = ("queued", "processing")


def get_lecture(session: Session, lecture_id: str) -> Lecture | None:
    return session.get(Lecture, lecture_id)


def find_cached(session: Session, source_id: str, notes_language: str) -> Lecture | None:
    """Find an existing (finished or in-progress) lecture for the same source and language."""
    statement = (
        select(Lecture)
        .where(Lecture.source_id == source_id)
        .where(Lecture.notes_language == notes_language)
        .where(col(Lecture.status).in_(("done", *ACTIVE_STATUSES)))
        .order_by(col(Lecture.created_at).desc())
    )
    return session.exec(statement).first()


def delete_failed_for_source(session: Session, source_id: str) -> None:
    """Remove old failed attempts for a source before retrying it."""
    for lecture in session.exec(
        select(Lecture).where(Lecture.source_id == source_id).where(Lecture.status == "failed")
    ):
        session.delete(lecture)
    session.commit()


def list_lectures(session: Session, search: str | None = None, limit: int = 200) -> list[Lecture]:
    statement = select(Lecture).order_by(col(Lecture.created_at).desc()).limit(limit)
    if search:
        statement = statement.where(col(Lecture.title).icontains(search.strip()))
    return list(session.exec(statement))


def create_lecture(session: Session, **fields: Any) -> Lecture:
    lecture = Lecture(**fields)
    session.add(lecture)
    session.commit()
    session.refresh(lecture)
    return lecture


def update_lecture(engine: Engine, lecture_id: str, **fields: Any) -> None:
    """Update columns of a lecture in its own short transaction (safe from worker threads)."""
    with Session(engine) as session:
        lecture = session.get(Lecture, lecture_id)
        if lecture is None:
            return  # deleted while processing
        for name, value in fields.items():
            setattr(lecture, name, value)
        lecture.updated_at = utcnow()
        session.add(lecture)
        session.commit()


def delete_lecture(session: Session, lecture: Lecture) -> None:
    session.exec(delete(QuizAttempt).where(QuizAttempt.lecture_id == lecture.id))  # type: ignore[call-overload]
    session.exec(delete(FlashcardReview).where(FlashcardReview.lecture_id == lecture.id))  # type: ignore[call-overload]
    session.delete(lecture)
    session.commit()


# ------------------------------------------------------------ flashcards


def get_reviews(session: Session, lecture_id: str) -> dict[str, FlashcardReview]:
    """Spaced-repetition rows for a lecture, keyed by card ID."""
    rows = session.exec(select(FlashcardReview).where(FlashcardReview.lecture_id == lecture_id))
    return {row.card_id: row for row in rows}


def save_review(session: Session, lecture_id: str, card_id: str, **fields: Any) -> FlashcardReview:
    """Insert or update one card's review state."""
    row = session.exec(
        select(FlashcardReview)
        .where(FlashcardReview.lecture_id == lecture_id)
        .where(FlashcardReview.card_id == card_id)
    ).first() or FlashcardReview(lecture_id=lecture_id, card_id=card_id)
    for name, value in fields.items():
        setattr(row, name, value)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def reset_reviews(session: Session, lecture_id: str) -> None:
    session.exec(delete(FlashcardReview).where(FlashcardReview.lecture_id == lecture_id))  # type: ignore[call-overload]
    session.commit()


def add_quiz_attempt(session: Session, attempt: QuizAttempt) -> QuizAttempt:
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def mark_interrupted(engine: Engine) -> int:
    """On startup, fail any job that was running when the server stopped."""
    with Session(engine) as session:
        stuck = list(session.exec(select(Lecture).where(col(Lecture.status).in_(ACTIVE_STATUSES))))
        for lecture in stuck:
            lecture.status = "failed"
            lecture.stage = "failed"
            lecture.error = "The server stopped while this lecture was being processed."
            lecture.error_hint = "Submit it again to restart processing."
            session.add(lecture)
        session.commit()
        return len(stuck)
