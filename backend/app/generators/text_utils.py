"""Small text helpers shared by all generators (normalising, similarity, dedupe)."""

import re
from difflib import SequenceMatcher

# Bullet points / questions at least this similar are treated as duplicates.
DUPLICATE_SIMILARITY = 0.85


def normalise(text: str) -> str:
    """Lowercase, drop punctuation and squeeze spaces (works for Hindi too)."""
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    """How alike two strings are, from 0.0 (different) to 1.0 (identical)."""
    return SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def same_numbers(a: str, b: str) -> bool:
    """True if both texts mention the same numbers ("layer 1" vs "layer 2" -> False)."""
    return re.findall(r"\d+", a) == re.findall(r"\d+", b)


def is_duplicate(text: str, existing: list[str], threshold: float = DUPLICATE_SIMILARITY) -> bool:
    """True if `text` is nearly identical to any item in `existing`.

    Texts that differ in their numbers are never duplicates: "What does layer 1
    detect?" and "What does layer 2 detect?" are different questions.
    """
    return any(same_numbers(text, other) and similarity(text, other) >= threshold for other in existing)


def dedupe_texts(items: list[str], threshold: float = DUPLICATE_SIMILARITY) -> list[str]:
    """Remove items that are (nearly) identical to an earlier item."""
    kept: list[str] = []
    for item in items:
        if not is_duplicate(item, kept, threshold):
            kept.append(item)
    return kept
