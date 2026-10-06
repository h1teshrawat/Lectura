"""Flashcard generation: per-chunk Q/A cards, quality-checked and de-duplicated."""

import logging

from app.generators.base import ChunkedGenerator, ProgressFn, resolve_timestamp
from app.generators.chunking import Chunk
from app.generators.prompts import FLASHCARDS_MAP_USER
from app.generators.schemas import ChunkFlashcardsDraft, Flashcard, FlashcardDeck, Rejection
from app.generators.text_utils import is_duplicate
from app.generators.validators import check_flashcard
from app.transcription.models import Transcript, format_timestamp

logger = logging.getLogger(__name__)

MAX_CARDS = 40


class FlashcardGenerator(ChunkedGenerator):
    """Creates a deck of flashcards for a lecture."""

    def generate(self, transcript: Transcript, on_progress: ProgressFn | None = None) -> FlashcardDeck:
        report = on_progress or (lambda message, fraction: None)
        chunks = self._chunks(transcript)
        # Fewer cards per chunk for long lectures, so the deck stays a useful size.
        per_chunk = (4, 8) if len(chunks) <= 4 else (3, 5)

        drafts = self._map(
            chunks,
            lambda chunk: self._map_chunk(chunk, len(chunks), per_chunk),
            report,
            label="Writing flashcards",
        )
        deck = build_deck(drafts)
        report(f"{len(deck.cards)} flashcards ready.", 1.0)
        return deck

    def _map_chunk(
        self, chunk: Chunk, total_chunks: int, per_chunk: tuple[int, int]
    ) -> list[tuple[str, str, float]]:
        draft = self._ask(
            FLASHCARDS_MAP_USER.format(
                part=chunk.index + 1,
                total_parts=total_chunks,
                start=format_timestamp(chunk.start),
                end=format_timestamp(chunk.end),
                min_cards=per_chunk[0],
                max_cards=per_chunk[1],
                transcript=chunk.to_prompt_text(),
            ),
            ChunkFlashcardsDraft,
        )
        return [
            (card.question.strip(), card.answer.strip(), resolve_timestamp(card.timestamp, chunk, chunk.start))
            for card in draft.flashcards
        ]


def build_deck(items: list[tuple[str, str, float]], max_cards: int = MAX_CARDS) -> FlashcardDeck:
    """Quality-check and de-duplicate raw (question, answer, seconds) items."""
    cards: list[Flashcard] = []
    rejected: list[Rejection] = []
    for question, answer, seconds in sorted(items, key=lambda item: item[2]):  # lecture order
        problems = check_flashcard(question, answer)
        if not problems and is_duplicate(question, [c.question for c in cards]):
            problems.append("duplicate of an earlier card")
        if problems:
            rejected.append(Rejection(item=question, reasons=problems))
            continue
        cards.append(
            Flashcard(id=f"c{len(cards) + 1}", question=question, answer=answer, start_seconds=round(seconds, 1))
        )

    if len(cards) > max_cards:
        logger.info("Keeping %d of %d flashcards.", max_cards, len(cards))
        cards = cards[:max_cards]
    return FlashcardDeck(cards=cards, rejected=rejected)
