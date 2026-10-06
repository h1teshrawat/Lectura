"""Smart-notes generation with map-reduce summarisation.

MAP:    each ~5-minute chunk -> LLM -> 1-3 topic sections (title, timestamp,
        summary, key points, key terms, definitions). Chunks are independent,
        so they could run in parallel.
MERGE:  join sections in time order; merge neighbouring sections that are the
        same topic split across a chunk boundary; remove duplicate points.
REDUCE: send just the section titles + summaries (much shorter than the
        transcript) to the LLM to write the overall title, overview and key
        takeaways. Very long lectures are reduced in batches first
        (hierarchical / recursive reduce).
"""

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

from app.errors import StructuredOutputError
from app.generators.chunking import Chunk, chunk_transcript
from app.generators.prompts import (
    LANGUAGE_INSTRUCTIONS,
    NOTES_MAP_USER,
    NOTES_REDUCE_PARTIAL_USER,
    NOTES_REDUCE_USER,
    NOTES_SYSTEM,
)
from app.generators.schemas import (
    ChunkNotesDraft,
    Definition,
    LectureNotes,
    NoteSection,
    SummaryDraft,
)
from app.llm.base import ChatMessage, LLMProvider
from app.llm.structured import generate_structured
from app.transcription.models import Transcript, format_timestamp

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, float | None], None]  # (message, fraction 0..1)

# Reduce input above this many words is summarised in batches first.
_REDUCE_MAX_WORDS = 2500
# Titles at least this similar are treated as the same topic.
_SAME_TOPIC_SIMILARITY = 0.75
# Bullet points at least this similar are treated as duplicates.
_DUPLICATE_POINT_SIMILARITY = 0.85


# ------------------------------------------------------------------ helpers


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


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.casefold()).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


def _same_topic(title_a: str, title_b: str) -> bool:
    """True if two section titles describe the same topic.

    Titles with different numbers ("Example 1" vs "Example 2") are never the
    same topic, even though the strings are very similar.
    """
    if re.findall(r"\d+", title_a) != re.findall(r"\d+", title_b):
        return False
    return _similar(title_a, title_b) >= _SAME_TOPIC_SIMILARITY


def dedupe_texts(items: list[str], threshold: float = _DUPLICATE_POINT_SIMILARITY) -> list[str]:
    """Remove items that are (nearly) identical to an earlier item."""
    kept: list[str] = []
    for item in items:
        if not any(_similar(item, existing) >= threshold for existing in kept):
            kept.append(item)
    return kept


def dedupe_definitions(definitions: list[Definition]) -> list[Definition]:
    """Keep the first definition of each term (case/punctuation-insensitive)."""
    seen: set[str] = set()
    kept: list[Definition] = []
    for definition in definitions:
        key = _normalise(definition.term)
        if key and key not in seen:
            seen.add(key)
            kept.append(definition)
    return kept


def merge_sections(sections: list[NoteSection]) -> list[NoteSection]:
    """Merge neighbouring sections about the same topic.

    A topic often continues across a 5-minute chunk boundary, giving two
    sections with almost the same title. We join them, keeping the earlier
    timestamp, and remove duplicate points.
    """
    merged: list[NoteSection] = []
    for section in sections:
        previous = merged[-1] if merged else None
        if previous and _same_topic(previous.title, section.title):
            merged[-1] = NoteSection(
                title=previous.title,
                start_seconds=previous.start_seconds,
                summary=f"{previous.summary} {section.summary}",
                key_points=dedupe_texts(previous.key_points + section.key_points),
                key_terms=dedupe_texts(previous.key_terms + section.key_terms, threshold=0.95),
                definitions=dedupe_definitions(previous.definitions + section.definitions),
            )
        else:
            merged.append(section)
    return merged


def build_glossary(sections: list[NoteSection]) -> list[Definition]:
    """Collect every definition from all sections, without duplicates, A-Z."""
    all_definitions = [d for s in sections for d in s.definitions]
    return sorted(dedupe_definitions(all_definitions), key=lambda d: d.term.casefold())


# ---------------------------------------------------------------- generator


class NotesGenerator:
    """Generates `LectureNotes` from a transcript using map-reduce."""

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
        self.system_prompt = NOTES_SYSTEM.format(
            language_instruction=LANGUAGE_INSTRUCTIONS[self.output_language]
        )

    def generate(
        self,
        transcript: Transcript,
        title_hint: str | None = None,
        on_progress: ProgressFn | None = None,
    ) -> LectureNotes:
        """Run the full map -> merge -> reduce pipeline.

        Args:
            transcript: The timestamped transcript.
            title_hint: The video/file title, to help the model name the lecture.
            on_progress: Optional callback (message, fraction).
        """
        report = on_progress or (lambda message, fraction: None)
        chunks = chunk_transcript(transcript.segments, target_seconds=self.chunk_seconds)
        if not chunks:
            raise StructuredOutputError("The transcript is empty, so there is nothing to summarise.")
        logger.info("Notes: %d chunk(s) of ~%ds with %s", len(chunks), self.chunk_seconds, self.llm.label)

        # MAP
        sections = self._map(chunks, report)
        # MERGE
        sections = merge_sections(sections)
        # REDUCE
        report("Writing the overall summary...", 0.9)
        summary = self._reduce(sections, title_hint)
        report("Notes ready.", 1.0)

        return LectureNotes(
            title=summary.title,
            overview=summary.overview,
            key_takeaways=dedupe_texts(summary.key_takeaways),
            sections=sections,
            glossary=build_glossary(sections),
            language=self.output_language,
        )

    # -- map ------------------------------------------------------------------

    def _map(self, chunks: list[Chunk], report: ProgressFn) -> list[NoteSection]:
        results: dict[int, list[NoteSection]] = {}
        failures = 0
        report(f"Summarising part 1 of {len(chunks)}...", 0.0)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._map_chunk, chunk, len(chunks)): chunk for chunk in chunks}
            for done, future in enumerate(as_completed(futures), start=1):
                chunk = futures[future]
                try:
                    results[chunk.index] = future.result()
                except StructuredOutputError as exc:
                    # One bad chunk shouldn't ruin the whole lecture.
                    failures += 1
                    logger.error("Skipping part %d: %s", chunk.index + 1, exc)
                report(f"Summarised part {done} of {len(chunks)}", 0.9 * done / len(chunks))

        if failures > len(chunks) // 2:
            raise StructuredOutputError(
                f"Notes generation failed for {failures} of {len(chunks)} parts of the lecture."
            )
        return [section for index in sorted(results) for section in results[index]]

    def _map_chunk(self, chunk: Chunk, total_chunks: int) -> list[NoteSection]:
        max_sections = 3 if chunk.end - chunk.start > 120 else 2
        prompt = NOTES_MAP_USER.format(
            part=chunk.index + 1,
            total_parts=total_chunks,
            start=format_timestamp(chunk.start),
            end=format_timestamp(chunk.end),
            max_sections=max_sections,
            transcript=chunk.to_prompt_text(),
        )
        draft = generate_structured(
            self.llm,
            [ChatMessage("system", self.system_prompt), ChatMessage("user", prompt)],
            ChunkNotesDraft,
            temperature=self.temperature,
        )

        sections: list[NoteSection] = []
        previous_start = chunk.start
        for item in draft.sections[:max_sections]:
            # Keep timestamps inside this chunk and in increasing order, even if
            # the model copied a wrong or made-up time.
            seconds = parse_timestamp(item.timestamp)
            if seconds is None or not chunk.start - 1 <= seconds <= chunk.end + 1:
                seconds = previous_start
            seconds = max(seconds, previous_start)
            previous_start = seconds

            sections.append(
                NoteSection(
                    title=item.title.strip(),
                    start_seconds=round(seconds, 1),
                    summary=item.summary.strip(),
                    key_points=dedupe_texts(item.key_points),
                    key_terms=dedupe_texts(item.key_terms, threshold=0.95),
                    definitions=dedupe_definitions(item.definitions),
                )
            )
        return sections

    # -- reduce ---------------------------------------------------------------

    def _reduce(self, sections: list[NoteSection], title_hint: str | None) -> SummaryDraft:
        lines = [
            f"[{format_timestamp(s.start_seconds)}] {s.title}: {s.summary}" for s in sections
        ]
        hint = f' titled "{title_hint}"' if title_hint else ""
        return self._reduce_lines(lines, hint)

    def _reduce_lines(self, lines: list[str], title_hint: str) -> SummaryDraft:
        """Summarise lines; if they're too long, summarise batches first (recursively)."""
        total_words = sum(len(line.split()) for line in lines)
        if total_words <= _REDUCE_MAX_WORDS or len(lines) <= 2:
            return self._call_reduce(NOTES_REDUCE_USER, lines, title_hint)

        # Hierarchical reduce: summarise groups of sections, then summarise the summaries.
        batches: list[list[str]] = [[]]
        batch_words = 0
        for line in lines:
            words = len(line.split())
            if batches[-1] and batch_words + words > _REDUCE_MAX_WORDS:
                batches.append([])
                batch_words = 0
            batches[-1].append(line)
            batch_words += words
        logger.info("Long lecture: reducing %d batches first.", len(batches))

        partial_lines = []
        for batch in batches:
            partial = self._call_reduce(NOTES_REDUCE_PARTIAL_USER, batch, title_hint)
            partial_lines.append(f"{partial.title}: {partial.overview}")
        return self._reduce_lines(partial_lines, title_hint)

    def _call_reduce(self, template: str, lines: list[str], title_hint: str) -> SummaryDraft:
        prompt = template.format(title_hint=title_hint, sections="\n".join(lines))
        return generate_structured(
            self.llm,
            [ChatMessage("system", self.system_prompt), ChatMessage("user", prompt)],
            SummaryDraft,
            temperature=self.temperature,
        )
