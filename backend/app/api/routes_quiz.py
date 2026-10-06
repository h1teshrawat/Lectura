"""Quiz endpoints: get a quiz from the question bank, and submit answers."""

import json

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_lecture_or_404
from app.api.errors import api_error
from app.api.schemas import QuestionResult, QuizDifficulty, QuizOut, QuizResult, QuizSubmission
from app.db import repository
from app.db.models import Lecture, QuizAttempt
from app.db.session import get_session
from app.generators.quiz import select_questions
from app.generators.schemas import QuestionBank

router = APIRouter(prefix="/api/lectures/{lecture_id}/quiz", tags=["quiz"])


def _bank(lecture: Lecture) -> QuestionBank:
    if lecture.status != "done" or not lecture.quiz_json:
        raise api_error(409, "The quiz isn't ready yet.", "Wait until processing finishes.")
    return QuestionBank.model_validate_json(lecture.quiz_json)


@router.get("", response_model=QuizOut)
def get_quiz(
    lecture: Lecture = Depends(get_lecture_or_404),
    count: int = Query(10, ge=1, le=20, description="Number of questions (1-20)"),
    difficulty: QuizDifficulty = Query("mixed"),
    ids: str | None = Query(None, description="Comma-separated question IDs (for 'Retry wrong answers')"),
) -> QuizOut:
    """Pick questions for a new quiz attempt.

    Answers and explanations are included so the app can give instant feedback;
    the score is still calculated on the server when the quiz is submitted.
    """
    only_ids = {i.strip() for i in ids.split(",") if i.strip()} if ids else None
    questions = select_questions(_bank(lecture).questions, count=count, difficulty=difficulty, only_ids=only_ids)
    return QuizOut(difficulty=difficulty, questions=questions)


@router.post("/submit", response_model=QuizResult)
def submit_quiz(
    submission: QuizSubmission,
    lecture: Lecture = Depends(get_lecture_or_404),
    session: Session = Depends(get_session),
) -> QuizResult:
    """Score a finished quiz and save the attempt (used by the stats dashboard)."""
    questions = {q.id: q for q in _bank(lecture).questions}
    unknown = [a.question_id for a in submission.answers if a.question_id not in questions]
    if unknown:
        raise api_error(422, f"Unknown question IDs: {', '.join(unknown)}")

    results = []
    for answer in submission.answers:
        question = questions[answer.question_id]
        results.append(
            QuestionResult(
                question_id=question.id,
                selected_index=answer.selected_index,
                correct_index=question.correct_index,
                is_correct=answer.selected_index == question.correct_index,
                explanation=question.explanation,
                start_seconds=question.start_seconds,
            )
        )

    score = sum(r.is_correct for r in results)
    attempt = repository.add_quiz_attempt(
        session,
        QuizAttempt(
            lecture_id=lecture.id,
            difficulty=submission.difficulty,
            score=score,
            total=len(results),
            answers_json=json.dumps([a.model_dump() for a in submission.answers]),
            time_taken_seconds=submission.time_taken_seconds,
        ),
    )
    return QuizResult(
        attempt_id=attempt.id,  # type: ignore[arg-type]
        score=score,
        total=len(results),
        percent=round(100 * score / len(results), 1),
        results=results,
        wrong_question_ids=[r.question_id for r in results if not r.is_correct],
    )
