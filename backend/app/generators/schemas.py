"""Pydantic models for generated notes.

There are two kinds of models here:
- *Draft* models describe exactly what we ask the LLM to return. They are
  validated strictly, so a malformed reply triggers a correction retry.
- *Final* models are what the app stores and shows, after we clean up,
  merge and attach real timestamps (in seconds).
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


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
