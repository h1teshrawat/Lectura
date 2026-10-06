"""End-to-end tests of the flashcard and quiz generators with a fake LLM."""

import json

from app.generators.flashcards import FlashcardGenerator
from app.generators.quiz import QuizGenerator
from app.llm.base import ChatMessage
from app.transcription.models import Transcript, TranscriptSegment
from tests.fakes import FakeLLM


def _transcript(seconds: int = 600) -> Transcript:
    segments = [TranscriptSegment(start=t, end=t + 10, text="lecture words here") for t in range(0, seconds, 10)]
    return Transcript(source="youtube_captions", language="en", segments=segments)


def _part(messages: list[ChatMessage]) -> str:
    return messages[-1].content.split("This is part ")[1].split(" ")[0]


def _flashcard_reply(messages: list[ChatMessage]) -> str:
    part = _part(messages)
    return json.dumps(
        {
            "flashcards": [
                {"question": f"What is concept {part}A in the lecture?", "answer": "An idea.", "timestamp": "0:30"},
                {"question": f"Why does concept {part}B matter so much?", "answer": "It helps.", "timestamp": "bad"},
                {"question": "What?", "answer": "Too short question."},
            ]
        }
    )


def test_flashcard_generator_builds_clean_deck() -> None:
    deck = FlashcardGenerator(FakeLLM([_flashcard_reply]), chunk_seconds=300).generate(_transcript())

    assert len(deck.cards) == 4  # 2 valid cards x 2 chunks
    assert [c.id for c in deck.cards] == ["c1", "c2", "c3", "c4"]
    assert len(deck.rejected) == 2  # the "What?" card from each chunk
    # Part 2 starts at 300 s: "0:30" is outside that chunk, so it falls back to 300.
    assert deck.cards[2].start_seconds == 300


def _quiz_reply(messages: list[ChatMessage]) -> str:
    part = _part(messages)
    good = {
        "question": f"Which statement about topic {part} is correct?",
        "options": ["Alpha", "Beta", "Gamma", "Delta"],
        "answer": "Gamma",
        "explanation": "The lecture says so.",
        "difficulty": "Hard",
        "timestamp": "5:10" if part == "2" else "1:00",
    }
    bad = {**good, "question": f"Broken question for part {part}?", "options": ["Alpha", "Beta", "Gamma"]}
    return json.dumps({"questions": [good, bad]})


def test_quiz_generator_validates_and_reports_rate() -> None:
    bank = QuizGenerator(FakeLLM([_quiz_reply]), chunk_seconds=300).generate(_transcript())

    assert len(bank.questions) == 2
    assert bank.generated_count == 4
    assert bank.validity_rate == 0.5
    assert all(q.difficulty == "hard" for q in bank.questions)  # "Hard" normalised
    assert all(q.options[q.correct_index] == "Gamma" for q in bank.questions)
    assert [q.start_seconds for q in bank.questions] == [60, 310]
