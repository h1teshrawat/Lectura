"""Spaced repetition with the Leitner system.

Imagine 5 boxes of flashcards:

    Box 1 -> review again today       ("I keep forgetting this")
    Box 2 -> review in 1 day
    Box 3 -> review in 3 days
    Box 4 -> review in 7 days         (counts as "mastered")
    Box 5 -> review in 14 days

- "Got it": the card moves UP one box, so you see it less often.
- "Review again": the card goes back to box 1, so you see it again soon.

Cards you know well stop wasting your time; cards you struggle with keep
coming back. This uses the *spacing effect*: memories last longer when
reviews are spread out and timed just before you would forget.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

ReviewResult = Literal["got_it", "again"]

MAX_BOX = 5
MASTERED_BOX = 4
# Days until the next review for each box.
BOX_INTERVAL_DAYS: dict[int, int] = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}


@dataclass
class CardState:
    box: int
    due_at: datetime
    reviews: int = 0
    correct_count: int = 0
    last_result: ReviewResult | None = None


def next_state(current: CardState | None, result: ReviewResult, now: datetime) -> CardState:
    """Return the card's new state after one review.

    Args:
        current: The card's state, or None if it has never been reviewed.
        result: What the learner pressed.
        now: The current time (passed in so tests can control it).
    """
    reviews = (current.reviews if current else 0) + 1
    correct = (current.correct_count if current else 0) + (result == "got_it")

    if result == "again":
        box = 1
    elif current is None:
        box = 2  # a new card answered correctly skips straight to box 2
    else:
        box = min(current.box + 1, MAX_BOX)

    return CardState(
        box=box,
        due_at=now + timedelta(days=BOX_INTERVAL_DAYS[box]),
        reviews=reviews,
        correct_count=correct,
        last_result=result,
    )


def is_due(state: CardState | None, now: datetime) -> bool:
    """New cards and cards whose review date has arrived are due."""
    return state is None or state.due_at <= now


def is_mastered(state: CardState | None) -> bool:
    return state is not None and state.box >= MASTERED_BOX
