"""A tiny, offline stand-in for the embedding model (for tests only)."""

import hashlib
import math
import re

_WORD = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {"the", "a", "an", "is", "are", "of", "to", "and", "in", "what", "how", "does", "do", "it", "this"}


class HashingEmbedder:
    """Bag-of-words vectors: texts sharing words get similar vectors.

    Real embedding models also understand synonyms and other languages, but
    this is enough to test retrieval logic deterministically and instantly.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for word in _WORD.findall(text.lower()):
                if word in _STOPWORDS:
                    continue
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
                vector[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors
