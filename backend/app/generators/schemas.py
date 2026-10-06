"""Pydantic models for generated notes.

There are two kinds of models here:
- *Draft* models describe exactly what we ask the LLM to return. They are
  validated strictly, so a malformed reply triggers a correction retry.
- *Final* models are what the app stores and shows, after we clean up,
  merge and attach real timestamps (in seconds).
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
Timestamp = str | float | int | None


def _strip_list(values: list[str]) -> list[str]:
    """Remove blank entries and surrounding whitespace."""
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


# A list of strings that is automatically cleaned after validation.
CleanList = Annotated[list[str], AfterValidator(_strip_list)]


class Definition(BaseModel):
    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)


# ----------------------------------------------------------------- LLM drafts


class SectionDraft(BaseModel):
    """One topic section, as returned by the LLM in the map step."""

    title: str = Field(min_length=1)
    # The model copies a "[m:ss]" marker from the transcript; we convert it later.
    timestamp: str | float | int
    summary: str = Field(min_length=1)
    key_points: CleanList = Field(min_length=1)
    key_terms: CleanList = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)


class ChunkNotesDraft(BaseModel):
    """The LLM's notes for one chunk."""

    sections: list[SectionDraft] = Field(min_length=1)


class SummaryDraft(BaseModel):
    """The LLM's whole-lecture summary (reduce step)."""

    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    key_takeaways: CleanList = Field(min_length=1)


class FlashcardDraft(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    timestamp: Timestamp = None


class ChunkFlashcardsDraft(BaseModel):
    flashcards: list[FlashcardDraft] = Field(min_length=1)


class MCQDraft(BaseModel):
    """A quiz question as returned by the LLM.

    Deliberately lenient (any number of options, any answer text): structural
    problems are caught by our own quality checks, so we can count and report
    them (the "MCQ validity rate") instead of silently retrying.
    """

    question: str = Field(min_length=1)
    options: list[str]
    answer: str | int
    explanation: str = ""
    difficulty: str = "medium"
    timestamp: Timestamp = None


class ChunkQuizDraft(BaseModel):
    questions: list[MCQDraft] = Field(min_length=1)


# ---------------------------------------------------------------- final notes


class NoteSection(BaseModel):
    title: str
    start_seconds: float
    summary: str
    key_points: list[str]
    key_terms: list[str] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)


class LectureNotes(BaseModel):
    """The complete smart notes for one lecture."""

    title: str
    overview: str
    key_takeaways: list[str]
    sections: list[NoteSection]
    glossary: list[Definition] = Field(default_factory=list)
    language: str = "english"


# ------------------------------------------------------- flashcards & quiz


class Rejection(BaseModel):
    """A generated item that failed a quality check, and why."""

    item: str
    reasons: list[str]


class Flashcard(BaseModel):
    id: str
    question: str
    answer: str
    start_seconds: float


class FlashcardDeck(BaseModel):
    cards: list[Flashcard]
    rejected: list[Rejection] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str
    difficulty: Difficulty
    start_seconds: float


class QuestionBank(BaseModel):
    """All valid questions for a lecture. Each quiz is picked from this bank."""

    questions: list[QuizQuestion]
    rejected: list[Rejection] = Field(default_factory=list)

    @property
    def generated_count(self) -> int:
        return len(self.questions) + len(self.rejected)

    @property
    def validity_rate(self) -> float:
        """Share of generated questions that passed every quality check (0..1)."""
        return len(self.questions) / self.generated_count if self.generated_count else 0.0
