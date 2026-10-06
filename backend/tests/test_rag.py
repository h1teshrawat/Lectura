"""Tests for RAG: retrieval chunking, search, grounding and streaming (offline)."""

from app.config import Settings
from app.rag.chunking import build_retrieval_chunks
from app.rag.prompts import NOT_COVERED_EN, NOT_COVERED_HI
from app.rag.service import ChatTurn, RAGService, build_messages, not_covered_message
from app.rag.vector_store import ChromaVectorStore, SearchHit
from app.transcription.models import Transcript, TranscriptSegment
from tests.fakes import FakeLLM
from tests.fakes_rag import HashingEmbedder

LECTURE = [
    (0, "Welcome everyone, today we study neural networks for digit recognition."),
    (20, "A neuron holds a number between zero and one called its activation."),
    (40, "The input layer has 784 neurons, one for each pixel of the image."),
    (70, "Weights connect neurons, and the weighted sum is passed through a sigmoid function."),
    (95, "The bias shifts the weighted sum so a neuron only activates above a threshold."),
    (130, "Modern networks prefer the ReLU activation because it trains more easily."),
]


def _transcript() -> Transcript:
    segments = [
        TranscriptSegment(start=start, end=start + 18, text=text) for start, text in LECTURE
    ]
    return Transcript(source="youtube_captions", language="en", segments=segments)


def _service(llm: FakeLLM | None = None, **overrides) -> RAGService:
    settings = Settings(_env_file=None, rag_chunk_seconds=30, rag_chunk_overlap_seconds=10, rag_top_k=2, **overrides)
    return RAGService(
        store=ChromaVectorStore(path=None),
        embedder=HashingEmbedder(),
        llm_factory=lambda: llm or FakeLLM(["unused"]),
        settings=settings,
    )


# ------------------------------------------------------------- chunking


def test_retrieval_chunks_cover_everything_with_overlap() -> None:
    segments = [TranscriptSegment(start=t, end=t + 10, text=f"s{t}") for t in range(0, 300, 10)]
    chunks = build_retrieval_chunks(segments, window_seconds=60, overlap_seconds=15)

    assert chunks[0].start == 0 and chunks[-1].end == 300
    assert all(c.end - c.start <= 60 for c in chunks)
    # Consecutive chunks overlap (the next one starts before the previous ends).
    assert all(b.start < a.end for a, b in zip(chunks, chunks[1:]))
    # Every segment appears in at least one chunk.
    covered = {word for c in chunks for word in c.text.split()}
    assert covered == {seg.text for seg in segments}


def test_retrieval_chunks_handle_long_single_segment_and_empty_input() -> None:
    assert build_retrieval_chunks([]) == []
    long = [TranscriptSegment(start=0, end=500, text="one very long segment")]
    assert len(build_retrieval_chunks(long, window_seconds=60)) == 1


# --------------------------------------------------------- index + search


def test_index_and_retrieve_finds_the_right_moment() -> None:
    rag = _service()
    assert rag.index_transcript("lec1", _transcript()) > 0

    hits = rag.retrieve("lec1", "What does the bias do to the weighted sum?")
    assert hits[0].start <= 95 <= hits[0].end  # the bias explanation
    assert hits[0].similarity > hits[-1].similarity or len(hits) == 1


def test_search_is_isolated_per_lecture_and_delete_works() -> None:
    rag = _service()
    rag.index_transcript("lec1", _transcript())
    assert rag.store.has("lec1") and not rag.store.has("lec2")
    assert rag.retrieve("lec2", "neuron") == []
    rag.delete("lec1")
    assert not rag.store.has("lec1")


# --------------------------------------------------------------- answers


def _events(rag: RAGService, question: str, history=None):
    return list(rag.stream_answer("lec1", question, history or [], load_transcript=_transcript, title="NN"))


def test_answer_streams_sources_tokens_and_done() -> None:
    llm = FakeLLM(["The bias shifts the weighted sum so the neuron activates above a threshold [1:35]."])
    rag = _service(llm)
    events = _events(rag, "What does the bias do?")
    types = [e.type for e in events]

    assert types[0] == "status"  # first use: lecture gets indexed automatically
    assert types[1] == "sources" and events[1].data["sources"]
    assert "token" in types and types[-1] == "done"
    assert "[1:35]" in events[-1].data["answer"]
    # The LLM saw the rules and the retrieved excerpts.
    system_prompt = llm.calls[0][0].content
    assert "ONLY" in system_prompt and "bias shifts the weighted sum" in system_prompt


def test_unrelated_question_is_not_covered_without_calling_the_llm() -> None:
    llm = FakeLLM(["should not be used"])
    rag = _service(llm)
    events = _events(rag, "Who won the cricket world cup in 2011?")

    assert events[-1].type == "done"
    assert events[-1].data["answer"] == NOT_COVERED_EN
    assert llm.calls == []  # saved an API call


def test_not_covered_message_matches_question_language() -> None:
    assert not_covered_message("What is RAG?") == NOT_COVERED_EN
    assert not_covered_message("न्यूरॉन क्या है?") == NOT_COVERED_HI


def test_follow_up_question_uses_previous_question_for_search() -> None:
    llm = FakeLLM(["It uses ReLU [2:10]."])
    rag = _service(llm)
    history = [ChatTurn("user", "Which activation do modern networks prefer, ReLU?"), ChatTurn("assistant", "ReLU [2:10].")]
    events = _events(rag, "Why is that?", history)
    sources = events[1].data["sources"] if events[0].type == "status" else events[0].data["sources"]
    assert any(s["start"] <= 130 <= s["end"] for s in sources)
    # History is passed to the model as real conversation turns.
    assert [m.role for m in llm.calls[0]] == ["system", "user", "assistant", "user"]


def test_new_topic_after_unrelated_question_still_finds_its_excerpts() -> None:
    # Regression test: combining the previous (off-topic) question with a new,
    # on-topic one used to drag the search away and wrongly answer "not covered".
    llm = FakeLLM(["Modern networks prefer ReLU [2:10]."])
    rag = _service(llm)
    history = [
        ChatTurn("user", "Who won the cricket world cup in 2011 at Wankhede stadium Mumbai?"),
        ChatTurn("assistant", NOT_COVERED_EN),
    ]
    events = _events(rag, "Why do modern networks prefer ReLU activation?", history)
    sources = next(e.data["sources"] for e in events if e.type == "sources")
    assert any(s["start"] <= 130 <= s["end"] for s in sources)
    assert events[-1].data["answer"] != NOT_COVERED_EN


def test_build_messages_lists_excerpts_in_time_order() -> None:
    hits = [SearchHit(95, 113, "bias text", 0.9), SearchHit(20, 38, "neuron text", 0.5)]
    system = build_messages("NN", hits, [], "q")[0].content
    assert system.index("[0:20 - 0:38]") < system.index("[1:35 - 1:53]")


def test_llm_errors_become_error_events() -> None:
    from app.llm.base import LLMRateLimitError

    class RateLimitedLLM(FakeLLM):
        def stream(self, messages, *, temperature=0.3, max_tokens=2048):
            raise LLMRateLimitError("429")
            yield ""  # pragma: no cover

    rag = _service(RateLimitedLLM(["x"]))
    events = _events(rag, "What does the bias do?")
    assert events[-1].type == "error"
    assert "rate limit" in events[-1].data["message"]
