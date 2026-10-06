"""Text embeddings: turning text into vectors that capture its meaning.

An embedding model maps a sentence to a list of numbers (here 384 of them).
Sentences with similar *meaning* get vectors that point in similar
directions, even if they use different words, or different languages.
"What is a neuron?" and "न्यूरॉन क्या है?" end up close together.

We compare vectors with *cosine similarity* (the angle between them):
1.0 = same meaning, around 0 = unrelated.
"""

import logging
import os
import threading
from typing import Protocol

logger = logging.getLogger(__name__)

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class Embedder(Protocol):
    """Anything that can embed a list of texts (the real model or a test fake)."""

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
