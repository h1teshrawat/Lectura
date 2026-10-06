"""Quality checks for generated flashcards and multiple-choice questions.

LLMs make predictable mistakes in MCQs: 3 or 5 options, two identical
options, an "answer" that matches no option (or two), lazy "All of the
above" options, or the same question twice. Pydantic only checks the *shape*
of the JSON; these functions check the *content* and explain each problem.
"""

import re

from app.generators.text_utils import normalise

# "A) text", "(b) text", "C. text", "d: text"
_OPTION_LABEL_RE = re.compile(r"^\s*\(?([A-Da-d])[).:\-]\s+")
_LETTER_ANSWER_RE = re.compile(r"^\s*\(?([A-Da-d])[).]?\s*$")
_BANNED_OPTIONS = (
    "all of the above",
    "none of the above",
    "all the above",
    "none of these",
    "all of these",
    "both a and b",
)

MIN_QUESTION_CHARS = 10
MAX_FLASHCARD_ANSWER_WORDS = 60


def clean_options(options: list[str]) -> list[str]:
    """Strip whitespace, and remove "A) ..." style labels if every option has one."""
    cleaned = [o.strip() for o in options if isinstance(o, str)]
    if cleaned and all(_OPTION_LABEL_RE.match(o) for o in cleaned):
        cleaned = [_OPTION_LABEL_RE.sub("", o, count=1).strip() for o in cleaned]
    return cleaned


def matching_options(options: list[str], answer: str | int) -> list[int]:
    """Return the indexes of the options that match the given answer.

    The answer may be the option text (preferred), a letter like "B", or an index.
    """
    if isinstance(answer, int):
        return [answer] if 0 <= answer < len(options) else []

    normalised_options = [normalise(o) for o in options]
    text_match = [i for i, o in enumerate(normalised_options) if o == normalise(answer)]
    if text_match:
        return text_match

    # "B" or "(b)" -> option index 1
    letter = _LETTER_ANSWER_RE.match(answer)
    if letter:
        index = ord(letter.group(1).upper()) - ord("A")
        return [index] if index < len(options) else []

    # "B) the option text"
    without_label = normalise(_OPTION_LABEL_RE.sub("", answer, count=1))
    return [i for i, o in enumerate(normalised_options) if o == without_label]


def check_mcq(
    question: str, options: list[str], answer: str | int, explanation: str
) -> tuple[list[str], int | None]:
    """Check one multiple-choice question.

    Args:
        options: Already cleaned with `clean_options`.

    Returns:
        (problems, correct_index). `problems` is empty for a valid question;
        `correct_index` is set only when exactly one option is correct.
    """
    problems: list[str] = []

    if len(question.strip()) < MIN_QUESTION_CHARS:
        problems.append("question is too short")
    if len(options) != 4:
        problems.append(f"has {len(options)} options instead of exactly 4")
    if any(not option for option in options):
        problems.append("has an empty option")

    normalised = [normalise(o) for o in options]
    if len(set(normalised)) < len(normalised):
        problems.append("options are not all different")
    if any(banned in option for option in normalised for banned in _BANNED_OPTIONS):
        problems.append("uses an 'all/none of the above' style option")

    matches = matching_options(options, answer)
    correct_index: int | None = None
    if not matches:
        problems.append("the answer does not match any option")
    elif len(matches) > 1:
        problems.append("more than one option matches the answer")
    else:
        correct_index = matches[0]

    if not explanation.strip():
        problems.append("missing explanation")

    return problems, correct_index if not problems else None


def check_flashcard(question: str, answer: str) -> list[str]:
    """Check one flashcard. Returns a list of problems (empty if valid)."""
    problems: list[str] = []
    if len(question.strip()) < MIN_QUESTION_CHARS:
        problems.append("question is too short")
    if not answer.strip():
        problems.append("answer is empty")
    if len(answer.split()) > MAX_FLASHCARD_ANSWER_WORDS:
        problems.append(f"answer is longer than {MAX_FLASHCARD_ANSWER_WORDS} words")
    if normalise(question) == normalise(answer):
        problems.append("answer just repeats the question")
    return problems
