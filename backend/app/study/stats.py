"""Learning statistics for the dashboard."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.db.models import FlashcardReview, Lecture, QuizAttempt, ReviewLog
from app.study.leitner import MASTERED_BOX

ACTIVITY_DAYS = 14
HISTORY_LIMIT = 30


class Totals(BaseModel):
    lectures: int
    quizzes_taken: int
    questions_answered: int
    average_percent: float | None
    best_percent: float | None
    flashcards_total: int
    flashcards_mastered: int
    cards_reviewed: int


class ScorePoint(BaseModel):
    attempt_id: int
    taken_at: datetime
    percent: float
    score: int
    total: int
    difficulty: str
    lecture_id: str
    lecture_title: str


class ActivityDay(BaseModel):
    date: str  # YYYY-MM-DD in the viewer's timezone
    questions_answered: int
    cards_reviewed: int


class BoxCount(BaseModel):
    label: str
    box: int  # 0 = new
    count: int


class LectureProgress(BaseModel):
    lecture_id: str
    title: str
    thumbnail_url: str | None
    quizzes: int
    average_percent: float | None
    last_percent: float | None
    flashcards_total: int
    flashcards_mastered: int


class StatsOut(BaseModel):
    totals: Totals
    score_history: list[ScorePoint]
    activity: list[ActivityDay]
    box_distribution: list[BoxCount]
    lectures: list[LectureProgress]


def _percent(attempt: QuizAttempt) -> float:
    return round(100 * attempt.score / attempt.total, 1) if attempt.total else 0.0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def compute_stats(session: Session, tz_offset_minutes: int = 0, now: datetime | None = None) -> StatsOut:
    """Gather all dashboard numbers.

    Args:
        tz_offset_minutes: The viewer's offset from UTC (India = +330), so that
            "today" in the activity chart means the viewer's today.
    """
    now = now or datetime.now(timezone.utc)
    offset = timedelta(minutes=tz_offset_minutes)

    lectures = list(session.exec(select(Lecture).where(Lecture.status == "done")))
    titles = {lecture.id: lecture.title for lecture in lectures}
    attempts = list(session.exec(select(QuizAttempt).order_by(col(QuizAttempt.created_at))))
    reviews = list(session.exec(select(FlashcardReview)))
    since = now - timedelta(days=ACTIVITY_DAYS)
    logs = list(session.exec(select(ReviewLog).where(col(ReviewLog.created_at) >= since)))
    total_logs = len(list(session.exec(select(ReviewLog.id))))

    percents = [_percent(a) for a in attempts]
    flashcards_total = sum(lecture.flashcard_count for lecture in lectures)
    mastered_by_lecture = Counter(r.lecture_id for r in reviews if r.box >= MASTERED_BOX)

    totals = Totals(
        lectures=len(lectures),
        quizzes_taken=len(attempts),
        questions_answered=sum(a.total for a in attempts),
        average_percent=_mean(percents),
        best_percent=max(percents) if percents else None,
        flashcards_total=flashcards_total,
        flashcards_mastered=sum(mastered_by_lecture.values()),
        cards_reviewed=total_logs,
    )

    history = [
        ScorePoint(
            attempt_id=a.id,  # type: ignore[arg-type]
            taken_at=a.created_at,
            percent=_percent(a),
            score=a.score,
            total=a.total,
            difficulty=a.difficulty,
            lecture_id=a.lecture_id,
            lecture_title=titles.get(a.lecture_id, "Deleted lecture"),
        )
        for a in attempts[-HISTORY_LIMIT:]
    ]

    # Daily activity in the viewer's local time, including days with no activity.
    def local_day(moment: datetime) -> str:
        return (moment + offset).date().isoformat()

    questions_per_day: Counter[str] = Counter()
    for a in attempts:
        if a.created_at >= since:
            questions_per_day[local_day(a.created_at)] += a.total
    cards_per_day = Counter(local_day(log.created_at) for log in logs)
    today = (now + offset).date()
    activity = [
        ActivityDay(
            date=(day := (today - timedelta(days=i)).isoformat()),
            questions_answered=questions_per_day[day],
            cards_reviewed=cards_per_day[day],
        )
        for i in reversed(range(ACTIVITY_DAYS))
    ]

    # Leitner boxes across all cards of finished lectures (unreviewed cards are "New").
    live_ids = set(titles)
    box_counts = Counter(r.box for r in reviews if r.lecture_id in live_ids)
    reviewed = sum(box_counts.values())
    boxes = [BoxCount(label="New", box=0, count=max(flashcards_total - reviewed, 0))]
    boxes += [BoxCount(label=f"Box {b}", box=b, count=box_counts[b]) for b in range(1, 6)]

    per_lecture: dict[str, list[float]] = defaultdict(list)
    for a in attempts:
        per_lecture[a.lecture_id].append(_percent(a))
    progress = [
        LectureProgress(
            lecture_id=lecture.id,
            title=lecture.title,
            thumbnail_url=lecture.thumbnail_url,
            quizzes=len(per_lecture[lecture.id]),
            average_percent=_mean(per_lecture[lecture.id]),
            last_percent=per_lecture[lecture.id][-1] if per_lecture[lecture.id] else None,
            flashcards_total=lecture.flashcard_count,
            flashcards_mastered=mastered_by_lecture[lecture.id],
        )
        for lecture in sorted(lectures, key=lambda l: l.created_at, reverse=True)
    ]

    return StatsOut(
        totals=totals, score_history=history, activity=activity, box_distribution=boxes, lectures=progress
    )
