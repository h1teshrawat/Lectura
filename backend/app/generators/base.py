"""Shared machinery for generators that work chunk-by-chunk (the "map" step)."""

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

from pydantic import BaseModel

from app.errors import StructuredOutputError
from app.generators.chunking import Chunk, chunk_transcript
from app.generators.prompts import LANGUAGE_INSTRUCTIONS, SYSTEM_PROMPT
from app.llm.base import ChatMessage, LLMProvider
from app.llm.structured import generate_structured
from app.transcription.models import Transcript

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, float | None], None]  # (message, fraction 0..1)
T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


def parse_timestamp(value: str | float | int | None) -> float | None:
    """Convert '12:30', '[1:02:05]' or 750 into seconds. Returns None if unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    match = re.search(r"(\d+(?::\d{1,2}){0,2})", str(value))
    if not match:
        return None
    seconds = 0.0
    for part in match.group(1).split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def resolve_timestamp(value: str | float | int | None, chunk: Chunk, fallback: float) -> float:
    """Turn the model's timestamp into seconds that are guaranteed to lie inside the chunk.

    Models occasionally copy a wrong time or invent one; in that case we use
    `fallback` (usually the chunk start or the previous item's time).
    """
    seconds = parse_timestamp(value)
    if seconds is None or not chunk.start - 1 <= seconds <= chunk.end + 1:
        return fallback
    return seconds


class ChunkedGenerator:
    """Base class: split a transcript into chunks and run an LLM task on each."""

    def __init__(
        self,
        llm: LLMProvider,
        output_language: str = "english",
        chunk_seconds: int = 300,
        max_workers: int = 1,
        temperature: float = 0.3,
    ) -> None:
        self.llm = llm
        self.output_language = output_language if output_language in LANGUAGE_INSTRUCTIONS else "english"
        self.chunk_seconds = chunk_seconds
        self.max_workers = max(1, max_workers)
        self.temperature = temperature
        self.system_prompt = SYSTEM_PROMPT.format(
            language_instruction=LANGUAGE_INSTRUCTIONS[self.output_language]
        )

    def _chunks(self, transcript: Transcript) -> list[Chunk]:
        chunks = chunk_transcript(transcript.segments, target_seconds=self.chunk_seconds)
        if not chunks:
            raise StructuredOutputError("The transcript is empty, so there is nothing to work with.")
        return chunks

    def _ask(self, prompt: str, schema: type[M], max_tokens: int = 4096) -> M:
        """Send one prompt and get back a validated Pydantic object."""
        return generate_structured(
            self.llm,
            [ChatMessage("system", self.system_prompt), ChatMessage("user", prompt)],
            schema,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

    def _map(
        self,
        chunks: list[Chunk],
        task: Callable[[Chunk], list[T]],
        report: ProgressFn,
        label: str,
        progress_share: float = 1.0,
    ) -> list[T]:
        """Run `task` on every chunk (possibly in parallel) and join results in order.

        A chunk that keeps failing is skipped, but if more than half fail we stop.
        """
        results: dict[int, list[T]] = {}
        failures = 0
        report(f"{label}: part 1 of {len(chunks)}...", 0.0)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(task, chunk): chunk for chunk in chunks}
            for done, future in enumerate(as_completed(futures), start=1):
                chunk = futures[future]
                try:
                    results[chunk.index] = future.result()
                except StructuredOutputError as exc:
                    failures += 1
                    logger.error("%s: skipping part %d: %s", label, chunk.index + 1, exc)
                report(f"{label}: finished part {done} of {len(chunks)}", progress_share * done / len(chunks))

        if failures > len(chunks) // 2:
            raise StructuredOutputError(f"{label} failed for {failures} of {len(chunks)} parts of the lecture.")
        return [item for index in sorted(results) for item in results[index]]
