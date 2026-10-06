"""Tests for JSON extraction and the validate-and-retry loop."""

import pytest
from pydantic import BaseModel, Field

from app.errors import StructuredOutputError
from app.llm.base import ChatMessage
from app.llm.structured import extract_json, generate_structured
from tests.fakes import FakeLLM


class Card(BaseModel):
    question: str
    answer: str
    tags: list[str] = Field(min_length=1)


GOOD = '{"question": "What is RAG?", "answer": "Retrieval-augmented generation", "tags": ["nlp"]}'


@pytest.mark.parametrize(
    "reply",
    [
        GOOD,
        f"```json\n{GOOD}\n```",
        f"Sure! Here is the JSON you asked for:\n{GOOD}\nHope this helps.",
        f"<think>The user wants a card...</think>{GOOD}",
    ],
)
def test_extract_json_handles_common_formats(reply: str) -> None:
    assert extract_json(reply)["question"] == "What is RAG?"


def test_extract_json_handles_arrays() -> None:
    assert extract_json("Result: [1, 2, 3]") == [1, 2, 3]


@pytest.mark.parametrize("reply", ["", "no json here", "{broken: json"])
def test_extract_json_raises_when_no_json(reply: str) -> None:
    with pytest.raises(ValueError):
        extract_json(reply)


def test_generate_structured_returns_validated_model() -> None:
    llm = FakeLLM([GOOD])
    card = generate_structured(llm, [ChatMessage("user", "make a card")], Card)
    assert card == Card(question="What is RAG?", answer="Retrieval-augmented generation", tags=["nlp"])
    assert len(llm.calls) == 1


def test_generate_structured_retries_with_correction_prompt() -> None:
    # First reply is missing "tags" -> validation error -> model is asked to fix it.
    bad = '{"question": "What is RAG?", "answer": "Retrieval-augmented generation"}'
    llm = FakeLLM([bad, GOOD])
    card = generate_structured(llm, [ChatMessage("user", "make a card")], Card)

    assert card.tags == ["nlp"]
    assert len(llm.calls) == 2
    retry_messages = llm.calls[1]
    assert retry_messages[-2].role == "assistant" and retry_messages[-2].content == bad
    assert "tags" in retry_messages[-1].content  # the error is explained to the model


def test_generate_structured_gives_up_after_max_retries() -> None:
    llm = FakeLLM(["not json at all"])
    with pytest.raises(StructuredOutputError):
        generate_structured(llm, [ChatMessage("user", "make a card")], Card, max_retries=2)
    assert len(llm.calls) == 3
