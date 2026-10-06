"""Flashcard spaced-repetition endpoints."""

import json

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from app.api.deps import get_lecture_or_404
from app.api.errors import api_error
from app.api.schemas import CardProgress, FlashcardProgressOut, ReviewIn
from app.db import repository
from app.db.models import FlashcardReview, Lecture, utcnow
from app.db.session import get_session
from app.study.leitner import CardState, is_due, is_mastered, next_state

router = APIRouter(prefix="/api/lectures/{lecture_id}/flashcards", tags=["flashcards"])


def _card_ids(lecture: Lecture) -> list[str]:
    if lecture.status != "done" or not lecture.flashcards_json:
        raise api_error(409, "The flashcards aren't ready yet.", "Wait until processing finishes.")
    return [card["id"] for card in json.loads(lecture.flashcards_json)["cards"]]


def _state(row: FlashcardReview | None) -> CardState | None:
    if row is None:
        return None
    return CardState(
        box=row.box,
        due_at=row.due_at,
        reviews=row.reviews,
        correct_count=row.correct_count,
        last_result=row.last_result,  # type: ignore[arg-type]
    )


def _card_progress(card_id: str, row: FlashcardReview | None) -> CardProgress:
    state, now = _state(row), utcnow()
    return CardProgress(
        card_id=card_id,
        box=state.box if state else 0,
        due_at=state.due_at if state else None,
        is_due=is_due(state, now),
        is_mastered=is_mastered(state),
        reviews=state.reviews if state else 0,
        correct_count=state.correct_count if state else 0,
        last_result=state.last_result if state else None,
    )


@router.get("/progress", response_model=FlashcardProgressOut)
def get_progress(lecture: Lecture = Depends(get_lecture_or_404), session: Session = Depends(get_session)):
    """Leitner box and due status for every flashcard of the lecture."""
    rows = repository.get_reviews(session, lecture.id)
    cards = [_card_progress(card_id, rows.get(card_id)) for card_id in _card_ids(lecture)]
    return FlashcardProgressOut(
        total=len(cards),
        new=sum(c.box == 0 for c in cards),
        learning=sum(c.box > 0 and not c.is_mastered for c in cards),
        mastered=sum(c.is_mastered for c in cards),
        due_now=sum(c.is_due for c in cards),
        cards=cards,
    )


@router.post("/{card_id}/review", response_model=CardProgress)
def review_card(
    card_id: str,
    review: ReviewIn,
    lecture: Lecture = Depends(get_lecture_or_404),
    session: Session = Depends(get_session),
) -> CardProgress:
    """Record "Got it" or "Review again" for one card and schedule its next review."""
    if card_id not in _card_ids(lecture):
        raise api_error(404, f"Flashcard '{card_id}' not found in this lecture.")

    current = repository.get_reviews(session, lecture.id).get(card_id)
    new = next_state(_state(current), review.result, utcnow())
    row = repository.save_review(
        session,
        lecture.id,
        card_id,
        box=new.box,
        due_at=new.due_at,
        reviews=new.reviews,
        correct_count=new.correct_count,
        last_result=new.last_result,
    )
    return _card_progress(card_id, row)


@router.delete("/progress", status_code=204)
def reset_progress(lecture: Lecture = Depends(get_lecture_or_404), session: Session = Depends(get_session)) -> Response:
    """Forget all spaced-repetition progress for this lecture's flashcards."""
    repository.reset_reviews(session, lecture.id)
    return Response(status_code=204)
