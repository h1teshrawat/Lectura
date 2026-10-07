"""Text embeddings: turning text into vectors that capture its meaning.

An embedding model maps a sentence to a list of numbers (here 384 of them).
Sentences with similar *meaning* get vectors that point in similar
directions, even if they use different words, or different languages.
"What is a neuron?" and "न्यूरॉन क्या है?" end up close together.

We compare vectors with *cosine similarity* (the angle between them):
1.0 = same meaning, around 0 = unrelated.
"""

import logging
import math
import os
import threading
import time
from typing import Protocol

from app.errors import ConfigurationError, LecturaError

logger = logging.getLogger(__name__)

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class Embedder(Protocol):
    """Anything that can embed a list of texts (a local model, an API, or a test fake).

    `embed` is used for transcript pieces (documents). Embedders may also offer
    `embed_query` for questions; RAGService uses it when available.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Embeddings from a sentence-transformers model, loaded on first use."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _get_model(self):  # type: ignore[no-untyped-def]
        with self._lock:
            if self._model is None:
                # Imported here because loading PyTorch takes a few seconds.
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model %s (first time downloads it)...", self.model_name)
                self._model = SentenceTransformer(self.model_name, device="cpu")
                logger.info("Embedding model ready.")
            return self._model

    def warm_up(self) -> None:
        """Load the model now (called in the background at server start)."""
        try:
            self._get_model()
        except Exception:  # noqa: BLE001 - chat will retry and report the error
            logger.exception("Could not load the embedding model")

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        # normalize_embeddings=True makes every vector length 1, so the dot
        # product of two vectors equals their cosine similarity.
        vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)  # this model treats questions and documents the same way


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class GeminiEmbedder:
    """Embeddings from Google's Gemini API (`gemini-embedding-001`).

    No model runs on the server, so this fits small cloud machines (e.g. Render's
    free 512 MB plan) where PyTorch + a local model wouldn't. Gemini embeds
    documents and questions slightly differently (`task_type`), which improves
    retrieval. Vectors are shortened to 768 numbers (Matryoshka representation
    learning keeps most quality) and normalised to length 1.
    """

    _BATCH = 100  # texts per API request
    _RETRY_SECONDS = (5, 15, 30)

    def __init__(self, api_key: str, model_name: str = "gemini-embedding-001", dimensions: int = 768) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.dimensions = dimensions
        self._client = None

    def _get_client(self):  # type: ignore[no-untyped-def]
        if not self.api_key.strip():
            raise ConfigurationError(
                "GEMINI_API_KEY is not set, but EMBEDDING_PROVIDER=gemini.",
                hint="Add a free Gemini key (aistudio.google.com) or set EMBEDDING_PROVIDER=local.",
            )
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import errors as genai_errors

        client = self._get_client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._BATCH):
            batch = texts[start : start + self._BATCH]
            for attempt in range(len(self._RETRY_SECONDS) + 1):
                try:
                    response = client.models.embed_content(
                        model=self.model_name,
                        contents=batch,
                        config={"task_type": task_type, "output_dimensionality": self.dimensions},
                    )
                    break
                except genai_errors.APIError as exc:
                    if exc.code == 429 and attempt < len(self._RETRY_SECONDS):
                        logger.warning("Gemini embedding rate limit; retrying in %ss", self._RETRY_SECONDS[attempt])
                        time.sleep(self._RETRY_SECONDS[attempt])
                        continue
                    raise LecturaError(
                        f"The Gemini embedding service failed ({exc.code}).",
                        hint="Check GEMINI_API_KEY, or wait a minute if the free limit was reached.",
                    ) from exc
            vectors.extend(_normalise(list(e.values)) for e in response.embeddings)
        return vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_QUERY")
