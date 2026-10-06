"""Tests for the notes map-reduce pipeline (with a fake LLM)."""

import json

import pytest

from app.generators.notes import (
    NotesGenerator,
    build_glossary,
    dedupe_texts,
    merge_sections,
    parse_timestamp,
)
from app.generators.schemas import Definition, NoteSection
from app.llm.base import ChatMessage
from app.transcription.models import Transcript, TranscriptSegment


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2:05", 125), ("[12:30]", 750), ("1:02:05", 3725), (90, 90), ("abc", None), (None, None)],
)
def test_parse_timestamp(value, expected) -> None:
    assert parse_timestamp(value) == expected


def test_dedupe_texts_removes_near_duplicates() -> None:
    points = ["Gradient descent minimises loss.", "gradient descent minimises loss", "Learning rate sets step size."]
    assert dedupe_texts(points) == ["Gradient descent minimises loss.", "Learning rate sets step size."]


def _section(title: str, start: float, terms: list[str] | None = None) -> NoteSection:
    return NoteSection(
        title=title,
        start_seconds=start,
        summary=f"About {title}.",
        key_points=[f"Point about {title}"],
        definitions=[Definition(term=t, definition=f"{t} means...") for t in (terms or [])],
    )


def test_merge_sections_joins_same_topic_across_chunks() -> None:
    merged = merge_sections(
        [_section("Gradient Descent", 0), _section("Gradient descent", 300), _section("Backpropagation", 420)]
    )
    assert [s.title for s in merged] == ["Gradient Descent", "Backpropagation"]
    assert merged[0].start_seconds == 0


def test_merge_sections_keeps_numbered_topics_apart() -> None:
    merged = merge_sections([_section("Example 1", 0), _section("Example 2", 300)])
    assert len(merged) == 2


def test_build_glossary_dedupes_and_sorts() -> None:
    glossary = build_glossary([_section("A", 0, ["Neuron", "bias"]), _section("B", 60, ["neuron"])])
    assert [d.term for d in glossary] == ["bias", "Neuron"]


def _fake_reply(messages: list[ChatMessage]) -> str:
    """Answer map prompts with sections and reduce prompts with a summary."""
    prompt = messages[-1].content
    if '"sections"' in prompt:
        part = prompt.split("This is part ")[1].split(" ")[0]
        return json.dumps(
            {
                "sections": [
                    {
                        "title": f"Topic {part}",
                        "timestamp": "99:99",  # nonsense time -> must be clamped to the chunk
                        "summary": f"Summary of part {part}.",
                        "key_points": [f"Point {part}"],
                        "key_terms": ["term"],
                        "definitions": [{"term": "Neuron", "definition": "A unit that holds a number."}],
                    }
                ]
            }
        )
    return json.dumps(
        {"title": "Neural Networks 101", "overview": "An overview.", "key_takeaways": ["Takeaway one"]}
    )


def test_notes_generator_end_to_end_with_fake_llm() -> None:
    from tests.fakes import FakeLLM

    segments = [TranscriptSegment(start=t, end=t + 10, text="some lecture words") for t in range(0, 900, 10)]
    transcript = Transcript(source="youtube_captions", language="en", segments=segments)
    llm = FakeLLM([_fake_reply])

    notes = NotesGenerator(llm, chunk_seconds=300).generate(transcript, title_hint="NN lecture")

    assert notes.title == "Neural Networks 101"
    assert [s.title for s in notes.sections] == ["Topic 1", "Topic 2", "Topic 3"]
    # Invalid "99:99" timestamps fall back to each chunk's start time.
    assert [s.start_seconds for s in notes.sections] == [0, 300, 600]
    assert [d.term for d in notes.glossary] == ["Neuron"]
    assert len(llm.calls) == 4  # 3 map calls + 1 reduce call
