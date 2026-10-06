"""Learning statistics for the dashboard."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db.session import get_session
from app.study.stats import StatsOut, compute_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(
    tz_offset_minutes: int = Query(0, ge=-720, le=840, description="Viewer's UTC offset, e.g. 330 for India"),
    session: Session = Depends(get_session),
) -> StatsOut:
    """Quizzes taken, scores over time, daily activity and flashcard mastery."""
    return compute_stats(session, tz_offset_minutes)
