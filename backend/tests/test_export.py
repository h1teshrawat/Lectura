"""Tests for exporting notes (PDF / Markdown) and flashcards (Anki CSV)."""

import csv
import io

from app.export.anki import anki_tag, flashcards_to_anki_csv
from app.export.pdf import notes_to_pdf
from app.generators.markdown import notes_to_markdown
from app.generators.schemas import Definition, Flashcard, LectureNotes, NoteSection

NOTES = LectureNotes(
    title="Neural Networks",
    overview="An overview with a non‑breaking hyphen.",
    key_takeaways=["Neurons hold numbers.", "Bias shifts the threshold."],
    sections=[
        NoteSection(
            title="Bias", start_seconds=680, summary="What bias does.", key_points=["Shifts the weighted sum"],
            definitions=[Definition(term="bias", definition="a constant added to the weighted sum")],
        )
    ],
    glossary=[Definition(term="न्यूरॉन", definition="एक इकाई जो संख्या रखती है")],
)
URL = "https://www.youtube.com/watch?v=aircAruvnKk"


def test_markdown_has_clickable_timestamps() -> None:
    markdown = notes_to_markdown(NOTES, video_url=URL)
    assert markdown.startswith("# Neural Networks")
    assert f"[11:20]({URL}&t=680s) Bias" in markdown
    assert "**bias**" in markdown and "न्यूरॉन" in markdown


def test_pdf_is_valid_and_handles_hindi() -> None:
    data = notes_to_pdf(NOTES, "Lecture title", video_url=URL, subtitle="3Blue1Brown · 19 min")
    assert data.startswith(b"%PDF-")
    assert len(data) > 1000


def test_anki_csv_format() -> None:
    cards = [
        Flashcard(id="c1", question='What is a "neuron"?', answer="A unit, holding a number <0..1>.", start_seconds=75),
        Flashcard(id="c2", question="What is bias?", answer="A shift.", start_seconds=680),
    ]
    text = flashcards_to_anki_csv(cards, "But what is a neural network?", URL)
    lines = text.splitlines()
    assert lines[:3] == ["#separator:comma", "#html:true", "#tags column:3"]

    rows = list(csv.reader(io.StringIO("\n".join(lines[3:]))))
    assert len(rows) == 2 and all(len(row) == 3 for row in rows)
    front, back, tag = rows[0]
    assert front == "What is a &quot;neuron&quot;?"          # quotes survive CSV + HTML
    assert "&lt;0..1&gt;" in back and "t=75s" in back       # HTML-escaped answer + timestamp link
    assert tag == "Lectura::but-what-is-a-neural-network"


def test_anki_tag_has_no_spaces() -> None:
    assert " " not in anki_tag("Lecture with   many spaces!")
    assert anki_tag("???") == "Lectura::lecture"
