"""Vector storage and similarity search with ChromaDB.

A vector database stores embeddings and can quickly find the ones closest to
a query vector. Chroma uses an HNSW index (Hierarchical Navigable Small
World graph): an approximate nearest-neighbour search that avoids comparing
the query with every stored vector, so search stays fast even for thousands
of lectures.

All lectures share one collection; each piece has a `lecture_id` metadata
field, and every search filters on it, so answers only come from the
lecture you're chatting with.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.rag.chunking import RetrievalChunk

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


@dataclass
class SearchHit:
    start: float
    end: float
    text: str
    similarity: float  # cosine similarity, 1.0 = identical meaning

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["similarity"] = round(self.similarity, 3)
        return data


class VectorStore(Protocol):
    def replace(self, lecture_id: str, chunks: list[RetrievalChunk], embeddings: list[list[float]]) -> None: ...
    def search(self, lecture_id: str, embedding: list[float], k: int) -> list[SearchHit]: ...
    def has(self, lecture_id: str) -> bool: ...
    def delete(self, lecture_id: str) -> None: ...


class ChromaVectorStore:
    """ChromaDB store on disk (or in memory when `path` is None, for tests)."""

    def __init__(self, path: Path | None, collection: str = "lecture_chunks") -> None:
        """
        Args:
            path: Folder for the database, or None for an in-memory store (tests).
            collection: Collection name. Vectors from different embedding models
                can't be compared, so each model gets its own collection.
        """
        chroma_settings = ChromaSettings(anonymized_telemetry=False)
        if path is None:
            self.client = chromadb.EphemeralClient(settings=chroma_settings)
            name = f"test_{uuid.uuid4().hex}"  # in-memory clients share state: keep tests separate
        else:
            path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(path), settings=chroma_settings)
            name = collection
        # Cosine distance = 1 - cosine similarity. We always pass our own embeddings.
        self.collection = self.client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def replace(self, lecture_id: str, chunks: list[RetrievalChunk], embeddings: list[list[float]]) -> None:
        self.delete(lecture_id)
        for start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[start : start + _BATCH_SIZE]
            self.collection.add(
                ids=[f"{lecture_id}-{chunk.index}" for chunk in batch],
                embeddings=embeddings[start : start + _BATCH_SIZE],
                documents=[chunk.text for chunk in batch],
                metadatas=[{"lecture_id": lecture_id, "start": chunk.start, "end": chunk.end} for chunk in batch],
            )

    def search(self, lecture_id: str, embedding: list[float], k: int) -> list[SearchHit]:
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where={"lecture_id": lecture_id},
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for text, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
            hits.append(SearchHit(start=float(meta["start"]), end=float(meta["end"]), text=text, similarity=1 - distance))
        return hits

    def has(self, lecture_id: str) -> bool:
        return bool(self.collection.get(where={"lecture_id": lecture_id}, limit=1, include=[])["ids"])

    def delete(self, lecture_id: str) -> None:
        self.collection.delete(where={"lecture_id": lecture_id})
