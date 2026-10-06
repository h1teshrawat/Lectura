"""MCQ quiz generation.

We generate a *question bank* (about 24 questions of mixed difficulty) once
per lecture. Each time the user starts a quiz, `select_questions` picks 10-20
questions from the bank at the requested difficulty, so retakes can differ and
no extra LLM calls are needed.
"""

import logging
import math
import random

from app.generators.base import ChunkedGenerator, ProgressFn, resolve_timestamp
from app.generators.chunking import Chunk
from app.generators.prompts import QUIZ_MAP_USER
from app.generators.schemas import (
    ChunkQuizDraft,
    Difficulty,
    MCQDraft,
    QuestionBank,
    QuizQuestion,
    Rejection,
)
from app.generators.text_utils import is_duplicate
from app.generators.validators import check_mcq, clean_options
from app.transcription.models import Transcript, format_timestamp

logger = logging.getLogger(__name__)

DEFAULT_BANK_SIZE = 24
_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")


class QuizGenerator(ChunkedGenerator):
    """Creates a validated MCQ question bank for a lecture."""

    def __init__(self, *args, bank_size: int = DEFAULT_BANK_SIZE, seed: int = 42, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.bank_size = bank_size
        self.seed = seed

    def generate(self, transcript: Transcript, on_progress: ProgressFn | None = None) -> QuestionBank:
        report = on_progress or (lambda message, fraction: None)
        chunks = self._chunks(transcript)
        # Spread the bank over all chunks: 3 to 8 questions per chunk.
        per_chunk = min(8, max(3, math.ceil(self.bank_size / len(chunks))))

        drafts = self._map(
            chunks,
            lambda chunk: self._map_chunk(chunk, len(chunks), per_chunk),
            report,
            label="Writing quiz questions",
        )
        bank = build_question_bank(drafts, seed=self.seed)
        logger.info(
            "Quiz: %d valid of %d generated (validity %.0f%%)",
            len(bank.questions), bank.generated_count, bank.validity_rate * 100,
        )
        report(f"{len(bank.questions)} quiz questions ready.", 1.0)
        return bank

    def _map_chunk(self, chunk: Chunk, total_chunks: int, count: int) -> list[tuple[MCQDraft, float]]:
        draft = self._ask(
            QUIZ_MAP_USER.format(
                part=chunk.index + 1,
                total_parts=total_chunks,
                start=format_timestamp(chunk.start),
                end=format_timestamp(chunk.end),
                count=count,
                transcript=chunk.to_prompt_text(),
            ),
            ChunkQuizDraft,
            max_tokens=6000,
        )
        return [(q, resolve_timestamp(q.timestamp, chunk, chunk.start)) for q in draft.questions]


def _normalise_difficulty(value: str) -> Difficulty:
    value = value.strip().lower()
    return value if value in _DIFFICULTIES else "medium"  # type: ignore[return-value]


def build_question_bank(items: list[tuple[MCQDraft, float]], seed: int = 42) -> QuestionBank:
    """Validate raw questions, drop bad/duplicate ones and shuffle the options.

    Why shuffle? LLMs show *position bias*: they put the correct answer in
    option A or B far more often than chance. Shuffling (with a fixed seed, so
    results are reproducible) spreads correct answers evenly over A-D.
    """
    questions: list[QuizQuestion] = []
    rejected: list[Rejection] = []

    for draft, seconds in items:
        options = clean_options(draft.options)
        problems, correct_index = check_mcq(draft.question, options, draft.answer, draft.explanation)
        if not problems and is_duplicate(draft.question, [q.question for q in questions]):
            problems = ["duplicate of an earlier question"]
        if problems or correct_index is None:
            rejected.append(Rejection(item=draft.question, reasons=problems))
            continue

        rng = random.Random(f"{seed}:{draft.question}")  # same question -> same shuffle
        order = list(range(4))
        rng.shuffle(order)
        questions.append(
            QuizQuestion(
                id=f"q{len(questions) + 1}",
                question=draft.question.strip(),
                options=[options[i] for i in order],
                correct_index=order.index(correct_index),
                explanation=draft.explanation.strip(),
                difficulty=_normalise_difficulty(draft.difficulty),
                start_seconds=round(seconds, 1),
            )
        )
    return QuestionBank(questions=questions, rejected=rejected)


def select_questions(
    questions: list[QuizQuestion],
    count: int = 10,
    difficulty: Difficulty | str = "mixed",
    only_ids: set[str] | None = None,
) -> list[QuizQuestion]:
    """Pick questions for one quiz attempt.

    Args:
        questions: The lecture's question bank.
        count: How many questions to return (fewer if the bank is smaller).
        difficulty: "easy", "medium", "hard" or "mixed". If there aren't enough
            questions at that level, the nearest level fills the gap.
        only_ids: Restrict to these question IDs (used for "Retry wrong answers").

    Returns:
        Questions in lecture order, spread evenly across the whole lecture.
    """
    pool = [q for q in questions if only_ids is None or q.id in only_ids]
    pool.sort(key=lambda q: q.start_seconds)

    if difficulty in _DIFFICULTIES:
        target = _DIFFICULTIES.index(difficulty)  # type: ignore[arg-type]
        # Exact level first, then levels one step away, then two (stable sort keeps time order).
        pool.sort(key=lambda q: abs(_DIFFICULTIES.index(q.difficulty) - target))
        chosen = pool[:count]
    elif len(pool) <= count:
        chosen = pool
    else:
        # Evenly spaced picks, so the quiz covers the whole lecture, not just the start.
        step = len(pool) / count
        chosen = [pool[int(i * step)] for i in range(count)]

    return sorted(chosen, key=lambda q: q.start_seconds)
