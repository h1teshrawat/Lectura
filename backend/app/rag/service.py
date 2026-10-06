"""The RAG pipeline: index -> retrieve -> generate (streamed).

    Indexing (once per lecture):
        transcript -> ~60 s overlapping pieces -> embeddings -> ChromaDB

    Answering (every question):
        question -> embedding -> top-k most similar pieces (semantic search)
                 -> prompt = rules + excerpts + recent chat + question
                 -> LLM streams an answer with [m:ss] citations
"""

import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Settings
from app.errors import LecturaError
from app.llm.base import ChatMessage, LLMAuthError, LLMError, LLMProvider, LLMRateLimitError
from app.rag.chunking import build_retrieval_chunks
from app.rag.embedder import Embedder
from app.rag.prompts import CHAT_SYSTEM, NOT_COVERED_EN, NOT_COVERED_HI
from app.rag.vector_store import SearchHit, VectorStore
from app.transcription.models import Transcript, format_timestamp

logger = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@dataclass
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class ChatEvent:
    """One server-sent event of a streamed answer."""

    type: Literal["status", "sources", "token", "done", "error"]
    data: dict[str, Any] = field(default_factory=dict)


def not_covered_message(question: str) -> str:
    """The fixed "not in this lecture" reply, in Hindi if the question is in Devanagari."""
    return NOT_COVERED_HI if _DEVANAGARI.search(question) else NOT_COVERED_EN


def format_excerpts(hits: list[SearchHit]) -> str:
    """Excerpts in time order, each labelled with its time range."""
    ordered = sorted(hits, key=lambda h: h.start)
    return "\n\n".join(
        f"[{format_timestamp(h.start)} - {format_timestamp(h.end)}]\n{h.text}" for h in ordered
    )


def build_messages(title: str | None, hits: list[SearchHit], history: list[ChatTurn], question: str) -> list[ChatMessage]:
    system = CHAT_SYSTEM.format(
        title_part=f' titled "{title}"' if title else "",
        not_covered=not_covered_message(question),
        excerpts=format_excerpts(hits),
    )
    messages = [ChatMessage("system", system)]
    messages += [ChatMessage(turn.role, turn.content) for turn in history]
    messages.append(ChatMessage("user", question))
    return messages


class RAGService:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        llm_factory: Callable[[], LLMProvider],
        settings: Settings,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.llm_factory = llm_factory
        self.settings = settings

    # ------------------------------------------------------------- indexing

    def index_transcript(self, lecture_id: str, transcript: Transcript) -> int:
        """Embed a lecture's transcript and store it. Returns the number of pieces."""
        chunks = build_retrieval_chunks(
            transcript.segments,
            window_seconds=self.settings.rag_chunk_seconds,
            overlap_seconds=self.settings.rag_chunk_overlap_seconds,
        )
        if not chunks:
            return 0
        embeddings = self.embedder.embed([chunk.text for chunk in chunks])
        self.store.replace(lecture_id, chunks, embeddings)
        logger.info("Indexed lecture %s: %d pieces", lecture_id, len(chunks))
        return len(chunks)

    def delete(self, lecture_id: str) -> None:
        self.store.delete(lecture_id)

    # ------------------------------------------------------------ retrieval

    def retrieve(self, lecture_id: str, query: str, *extra_queries: str) -> list[SearchHit]:
        """The `rag_top_k` transcript pieces most similar in meaning to any of the queries.

        Results from several queries are merged, keeping each piece's best score.
        """
        queries = [query, *extra_queries]
        best: dict[float, SearchHit] = {}
        for vector in self.embedder.embed(queries):
            for hit in self.store.search(lecture_id, vector, self.settings.rag_top_k):
                if hit.start not in best or hit.similarity > best[hit.start].similarity:
                    best[hit.start] = hit
        ranked = sorted(best.values(), key=lambda h: h.similarity, reverse=True)
        return ranked[: self.settings.rag_top_k]

    # ------------------------------------------------------------ answering

    def stream_answer(
        self,
        lecture_id: str,
        question: str,
        history: list[ChatTurn],
        load_transcript: Callable[[], Transcript],
        title: str | None = None,
    ) -> Iterator[ChatEvent]:
        """Answer a question about a lecture, yielding events as the answer is generated."""
        try:
            if not self.store.has(lecture_id):
                # Lectures processed before chat existed get indexed on first use.
                yield ChatEvent("status", {"message": "Preparing this lecture for chat (first time only)..."})
                self.index_transcript(lecture_id, load_transcript())

            # Search with the question on its own AND combined with the previous
            # question: short follow-ups ("why is that?") need the context, but a
            # brand-new topic must not be dragged towards the old one.
            previous = next((t.content for t in reversed(history) if t.role == "user"), "")
            extra = [f"{previous}\n{question}"] if previous else []
            hits = self.retrieve(lecture_id, question, *extra)
            relevant = [h for h in hits if h.similarity >= self.settings.rag_min_similarity]
            yield ChatEvent("sources", {"sources": [h.to_dict() for h in relevant]})

            if not relevant:
                # Nothing in the lecture is even remotely related: answer without calling the LLM.
                # (If only the combined follow-up query finds something, the LLM gets
                # the excerpts and applies the "not covered" rule itself.)
                answer = not_covered_message(question)
                yield ChatEvent("token", {"text": answer})
                yield ChatEvent("done", {"answer": answer})
                return

            llm = self.llm_factory()
            parts: list[str] = []
            for piece in llm.stream(build_messages(title, relevant, history, question), temperature=0.2, max_tokens=1500):
                parts.append(piece)
                yield ChatEvent("token", {"text": piece})

            answer = "".join(parts).strip() or not_covered_message(question)
            yield ChatEvent("done", {"answer": answer})

        except LLMRateLimitError:
            yield ChatEvent("error", {
                "message": "The AI provider's free rate limit was reached.",
                "hint": "Wait a minute and ask again.",
            })
        except LLMAuthError as exc:
            yield ChatEvent("error", {"message": str(exc), "hint": "Check your API key in backend/.env."})
        except LecturaError as exc:
            yield ChatEvent("error", {"message": exc.message, "hint": exc.hint})
        except LLMError as exc:
            yield ChatEvent("error", {"message": f"The AI model failed to answer: {exc}", "hint": "Try again."})
        except Exception:  # noqa: BLE001 - always end the stream cleanly
            logger.exception("Chat failed for lecture %s", lecture_id)
            yield ChatEvent("error", {"message": "Something went wrong while answering.", "hint": "Try again."})
