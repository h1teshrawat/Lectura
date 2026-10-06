"""Tests for MCQ / flashcard quality checks and quiz selection."""

from collections import Counter

import pytest

from app.generators.quiz import build_question_bank, select_questions
from app.generators.schemas import MCQDraft, QuizQuestion
from app.generators.validators import check_flashcard, check_mcq, clean_options, matching_options

OPTIONS = ["Sigmoid", "ReLU", "Tanh", "Softmax"]
QUESTION = "Which activation function is preferred in modern deep networks?"
EXPLANATION = "The lecture says ReLU is easier to train."


def test_valid_mcq_passes() -> None:
    problems, correct = check_mcq(QUESTION, OPTIONS, "ReLU", EXPLANATION)
    assert problems == []
    assert correct == 1


@pytest.mark.parametrize(
    ("options", "answer", "expected_problem"),
    [
        (["Sigmoid", "ReLU", "Tanh"], "ReLU", "instead of exactly 4"),
        (["Sigmoid", "ReLU", "Tanh", "Softmax", "Linear"], "ReLU", "instead of exactly 4"),
        (["Sigmoid", "ReLU", "relu", "Softmax"], "ReLU", "not all different"),
        (["Sigmoid", "ReLU", "Tanh", ""], "ReLU", "empty option"),
        (["Sigmoid", "ReLU", "Tanh", "All of the above"], "ReLU", "all/none of the above"),
        (["Sigmoid", "ReLU", "Tanh", "None of these"], "ReLU", "all/none of the above"),
        (OPTIONS, "Leaky ReLU", "does not match any option"),
    ],
)
def test_invalid_mcqs_are_rejected(options, answer, expected_problem) -> None:
    problems, correct = check_mcq(QUESTION, options, answer, EXPLANATION)
    assert any(expected_problem in p for p in problems), problems
    assert correct is None


def test_missing_explanation_and_short_question_are_rejected() -> None:
    problems, _ = check_mcq("Why?", OPTIONS, "ReLU", "")
    assert "question is too short" in problems
    assert "missing explanation" in problems


@pytest.mark.parametrize(("answer", "expected"), [("ReLU", [1]), ("relu.", [1]), ("B", [1]), ("(c)", [2]), ("B) ReLU", [1]), (3, [3]), (7, [])])
def test_answer_can_be_text_letter_or_index(answer, expected) -> None:
    assert matching_options(OPTIONS, answer) == expected


def test_clean_options_strips_labels_only_when_all_options_have_them() -> None:
    assert clean_options(["A) Sigmoid", "B) ReLU", "C) Tanh", "D) Softmax"]) == OPTIONS
    # "A. Turing" isn't a label pattern for every option -> left unchanged.
    assert clean_options([" A. Turing ", "Babbage", "Lovelace", "Hopper"])[0] == "A. Turing"


def _draft(question: str, answer: str = "ReLU", difficulty: str = "medium") -> MCQDraft:
    return MCQDraft(question=question, options=OPTIONS, answer=answer, explanation=EXPLANATION, difficulty=difficulty)


def test_question_bank_rejects_duplicates_and_counts_validity() -> None:
    bank = build_question_bank(
        [
            (_draft(QUESTION), 0.0),
            (_draft(QUESTION.lower() + " "), 10.0),  # duplicate
            (_draft("Which function squashes values into the range 0 to 1?", answer="Sigmoid"), 20.0),
            (_draft("Which option is wrong here, really?", answer="Swish"), 30.0),  # no matching option
        ]
    )
    assert len(bank.questions) == 2
    assert len(bank.rejected) == 2
    assert bank.validity_rate == 0.5
    assert bank.rejected[0].reasons == ["duplicate of an earlier question"]


def test_questions_differing_only_in_numbers_are_not_duplicates() -> None:
    bank = build_question_bank(
        [(_draft("What does hidden layer 1 detect in the network?"), 0.0),
         (_draft("What does hidden layer 2 detect in the network?"), 5.0)]
    )
    assert len(bank.questions) == 2


def test_shuffle_keeps_the_correct_answer_and_is_reproducible() -> None:
    items = [(_draft(f"Question number {i} about activation functions?"), float(i)) for i in range(40)]
    bank_a = build_question_bank(items)
    bank_b = build_question_bank(items)

    for question in bank_a.questions:
        assert question.options[question.correct_index] == "ReLU"
        assert sorted(question.options) == sorted(OPTIONS)
    assert [q.options for q in bank_a.questions] == [q.options for q in bank_b.questions]

    # The correct answer should not always sit in the same position.
    positions = Counter(q.correct_index for q in bank_a.questions)
    assert len(positions) == 4


def _bank_question(index: int, difficulty: str) -> QuizQuestion:
    return QuizQuestion(
        id=f"q{index}", question=f"Q{index}?", options=OPTIONS, correct_index=1,
        explanation="...", difficulty=difficulty, start_seconds=index * 60,
    )


BANK = [_bank_question(i, d) for i, d in enumerate(["easy", "medium", "hard"] * 8, start=1)]


def test_select_mixed_spreads_across_lecture() -> None:
    chosen = select_questions(BANK, count=6)
    assert len(chosen) == 6
    assert chosen[0].start_seconds < 300 and chosen[-1].start_seconds > 1000
    assert [q.start_seconds for q in chosen] == sorted(q.start_seconds for q in chosen)


def test_select_by_difficulty_fills_from_nearest_level() -> None:
    chosen = select_questions(BANK, count=10, difficulty="hard")
    difficulties = Counter(q.difficulty for q in chosen)
    assert difficulties["hard"] == 8      # all hard questions
    assert difficulties["medium"] == 2    # nearest level fills the gap
    assert difficulties["easy"] == 0


def test_select_only_ids_for_retry_wrong_answers() -> None:
    chosen = select_questions(BANK, count=10, only_ids={"q2", "q5"})
    assert [q.id for q in chosen] == ["q2", "q5"]


@pytest.mark.parametrize(
    ("question", "answer", "expected"),
    [
        ("What is a neuron in this lecture?", "A thing that holds a number between 0 and 1.", []),
        ("What?", "A number.", ["question is too short"]),
        ("What is gradient descent?", "word " * 70, ["answer is longer than 60 words"]),
        ("What is gradient descent?", "What is gradient descent", ["answer just repeats the question"]),
    ],
)
def test_check_flashcard(question, answer, expected) -> None:
    assert check_flashcard(question, answer) == expected
