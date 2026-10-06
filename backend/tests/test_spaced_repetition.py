"""Tests for the Leitner spaced-repetition rules."""

from datetime import datetime, timedelta

from app.study.leitner import MAX_BOX, CardState, is_due, is_mastered, next_state

NOW = datetime(2026, 10, 6, 12, 0)


def test_new_card_got_it_goes_to_box_2_due_tomorrow() -> None:
    state = next_state(None, "got_it", NOW)
    assert state.box == 2
    assert state.due_at == NOW + timedelta(days=1)
    assert (state.reviews, state.correct_count) == (1, 1)


def test_again_resets_to_box_1_due_now() -> None:
    state = next_state(CardState(box=4, due_at=NOW, reviews=5, correct_count=4), "again", NOW)
    assert state.box == 1
    assert state.due_at == NOW
    assert (state.reviews, state.correct_count) == (6, 4)


def test_got_it_moves_up_one_box_with_growing_intervals() -> None:
    state = next_state(None, "got_it", NOW)  # box 2
    intervals = []
    for _ in range(3):
        state = next_state(state, "got_it", NOW)
        intervals.append((state.box, (state.due_at - NOW).days))
    assert intervals == [(3, 3), (4, 7), (5, 14)]


def test_box_never_goes_above_max() -> None:
    state = CardState(box=MAX_BOX, due_at=NOW)
    assert next_state(state, "got_it", NOW).box == MAX_BOX


def test_due_and_mastered() -> None:
    assert is_due(None, NOW)  # new cards are due
    assert is_due(CardState(box=2, due_at=NOW - timedelta(minutes=1)), NOW)
    assert not is_due(CardState(box=2, due_at=NOW + timedelta(days=1)), NOW)
    assert not is_mastered(None)
    assert not is_mastered(CardState(box=3, due_at=NOW))
    assert is_mastered(CardState(box=4, due_at=NOW))
