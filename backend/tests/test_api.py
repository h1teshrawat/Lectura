"""API tests with a temporary database and a fake pipeline (no internet, no API keys)."""

import json
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import VideoUnavailableError
from app.generators.schemas import (
    Flashcard,
    FlashcardDeck,
    LectureNotes,
    NoteSection,
    QuestionBank,
    QuizQuestion,
)
from app.llm.base import LLMUsage
from app.main import create_app
from app.pipeline.orchestrator import JobRequest, PipelineResult
from app.rag.service import RAGService
from app.rag.vector_store import ChromaVectorStore
from app.transcription.models import MediaInfo, Transcript, TranscriptionResult, TranscriptSegment
from tests.fakes import FakeLLM
from tests.fakes_rag import HashingEmbedder

VIDEO_URL = "https://www.youtube.com/watch?v=aircAruvnKk"


class FakePipeline:
    """Pretends to process a lecture in a fraction of a second."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.runs: list[JobRequest] = []

    def run(self, job, report, on_transcribed=None) -> PipelineResult:
        self.runs.append(job)
        if self.fail_with:
            raise self.fail_with
        for stage in ("fetching", "transcribing", "notes", "flashcards", "quiz", "indexing"):
            report(stage, 0.5, f"Working on {stage}")
            time.sleep(0.02)

        is_youtube = job.source_type == "youtube"
        transcription = TranscriptionResult(
            media=MediaInfo(
                source_type=job.source_type,
                source_id="aircAruvnKk" if is_youtube else "hash",
                title="Neural networks" if is_youtube else (job.title or "upload"),
                duration_seconds=1120,
                thumbnail_url="https://i.ytimg.com/vi/aircAruvnKk/hqdefault.jpg" if is_youtube else None,
            ),
            transcript=Transcript(
                source="youtube_captions", language="en",
                segments=[TranscriptSegment(start=0, end=5, text="Hello and welcome.")],
            ),
            warnings=["Just a test warning."],
        )
        if on_transcribed:
            on_transcribed(transcription)

        questions = [
            QuizQuestion(
                id=f"q{i}", question=f"Question {i}?", options=["a", "b", "c", "d"], correct_index=i % 4,
                explanation="Because.", difficulty=("easy", "medium", "hard")[i % 3], start_seconds=i * 10,
            )
            for i in range(1, 13)
        ]
        return PipelineResult(
            transcription=transcription,
            notes=LectureNotes(
                title="Neural Networks", overview="Overview.", key_takeaways=["One"],
                sections=[NoteSection(title="Intro", start_seconds=0, summary="Hi.", key_points=["Point"])],
            ),
            flashcards=FlashcardDeck(cards=[Flashcard(id="c1", question="Q?", answer="A.", start_seconds=0)]),
            quiz=QuestionBank(questions=questions),
            llm_label="fake:model",
            llm_usage=LLMUsage(),
        )


CHAT_ANSWER = "The lecture says hello and welcome [0:00]."


def _make_client(tmp_path, pipeline) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, data_dir=tmp_path, groq_api_key="test-key", rag_warmup=False, rag_min_similarity=0.1
    )
    rag = RAGService(
        store=ChromaVectorStore(path=None),
        embedder=HashingEmbedder(),
        llm_factory=lambda: FakeLLM([CHAT_ANSWER]),
        settings=settings,
    )
    with TestClient(create_app(settings, pipeline=pipeline, rag=rag)) as client:
        yield client


@pytest.fixture
def pipeline() -> FakePipeline:
    return FakePipeline()


@pytest.fixture
def client(tmp_path, pipeline) -> Iterator[TestClient]:
    yield from _make_client(tmp_path, pipeline)


def _wait_until_finished(client: TestClient, lecture_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/lectures/{lecture_id}").json()
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def _create(client: TestClient, **form) -> dict:
    response = client.post("/api/lectures", data={"url": VIDEO_URL, **form})
    assert response.status_code in (200, 202), response.text
    return response.json()


# ------------------------------------------------------------------ tests


def test_health(client: TestClient) -> None:
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["groq_configured"] is True


def test_invalid_link_gives_clear_error(client: TestClient) -> None:
    response = client.post("/api/lectures", data={"url": "https://example.com/video"})
    assert response.status_code == 422
    assert "doesn't look like a YouTube video link" in response.json()["detail"]["message"]


def test_requires_exactly_one_of_url_or_file(client: TestClient) -> None:
    assert client.post("/api/lectures", data={}).status_code == 400


def test_full_youtube_flow_and_library(client: TestClient) -> None:
    created = _create(client)
    assert created["cached"] is False

    lecture = _wait_until_finished(client, created["id"])
    assert lecture["status"] == "done"
    assert lecture["title"] == "Neural networks"          # updated from video metadata
    assert lecture["video_id"] == "aircAruvnKk"
    assert lecture["notes"]["title"] == "Neural Networks"
    assert len(lecture["flashcards"]) == 1
    assert lecture["quiz_count"] == 12
    assert lecture["warnings"] == ["Just a test warning."]
    assert lecture["llm_model"] == "fake:model"

    library = client.get("/api/lectures").json()
    assert [item["id"] for item in library] == [created["id"]]
    assert client.get("/api/lectures", params={"q": "neural"}).json()[0]["id"] == created["id"]
    assert client.get("/api/lectures", params={"q": "chemistry"}).json() == []

    transcript = client.get(f"/api/lectures/{created['id']}/transcript").json()
    assert transcript["segments"][0]["text"] == "Hello and welcome."


def test_same_video_is_served_from_cache(client: TestClient, pipeline: FakePipeline) -> None:
    first = _create(client)
    _wait_until_finished(client, first["id"])

    response = client.post("/api/lectures", data={"url": "https://youtu.be/aircAruvnKk"})
    assert response.status_code == 200
    assert response.json() == {"id": first["id"], "status": "done", "cached": True}
    assert len(pipeline.runs) == 1  # not processed again

    # A different notes language is a different result -> processed again.
    other = _create(client, notes_language="hinglish")
    assert other["id"] != first["id"] and other["cached"] is False

    # force=true reprocesses.
    forced = _create(client, force="true")
    assert forced["id"] != first["id"]


def test_file_upload(client: TestClient) -> None:
    response = client.post("/api/lectures", files={"file": ("my lecture.mp3", b"fake audio bytes", "audio/mpeg")})
    assert response.status_code == 202
    lecture = _wait_until_finished(client, response.json()["id"])
    assert lecture["status"] == "done"
    assert lecture["source_type"] == "upload"
    assert lecture["title"] == "my lecture"


def test_unsupported_upload_is_rejected(client: TestClient) -> None:
    response = client.post("/api/lectures", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415
    assert "not supported" in response.json()["detail"]["message"]


def test_progress_stream_sends_events_until_done(client: TestClient) -> None:
    created = _create(client)
    with client.stream("GET", f"/api/lectures/{created['id']}/progress") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    events = [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]
    assert events[-1]["status"] == "done"
    assert events[-1]["progress"] == 1.0
    progresses = [e["progress"] for e in events]
    assert progresses == sorted(progresses)  # never goes backwards


def test_failed_job_reports_message_and_hint(tmp_path) -> None:
    pipeline = FakePipeline(fail_with=VideoUnavailableError("This video is private."))
    for client in _make_client(tmp_path, pipeline):
        lecture = _wait_until_finished(client, _create(client)["id"])
        assert lecture["status"] == "failed"
        assert lecture["error"] == "This video is private."
        assert "upload" in lecture["error_hint"]

        # Retrying a failed lecture processes it again instead of returning the failure.
        retry = _create(client)
        assert retry["cached"] is False


def test_quiz_get_and_submit(client: TestClient) -> None:
    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)

    quiz = client.get(f"/api/lectures/{lecture_id}/quiz", params={"count": 5, "difficulty": "hard"}).json()
    assert len(quiz["questions"]) == 5
    assert sum(q["difficulty"] == "hard" for q in quiz["questions"]) == 4  # only 4 hard ones exist

    answers = [
        {"question_id": q["id"], "selected_index": q["correct_index"] if i < 3 else (q["correct_index"] + 1) % 4}
        for i, q in enumerate(quiz["questions"])
    ]
    result = client.post(
        f"/api/lectures/{lecture_id}/quiz/submit", json={"answers": answers, "difficulty": "hard"}
    ).json()
    assert (result["score"], result["total"], result["percent"]) == (3, 5, 60.0)
    assert len(result["wrong_question_ids"]) == 2

    retry = client.get(
        f"/api/lectures/{lecture_id}/quiz", params={"ids": ",".join(result["wrong_question_ids"])}
    ).json()
    assert sorted(q["id"] for q in retry["questions"]) == sorted(result["wrong_question_ids"])

    bad = client.post(
        f"/api/lectures/{lecture_id}/quiz/submit", json={"answers": [{"question_id": "q999", "selected_index": 0}]}
    )
    assert bad.status_code == 422


def test_delete_lecture(client: TestClient) -> None:
    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)
    client.post(
        f"/api/lectures/{lecture_id}/quiz/submit",
        json={"answers": [{"question_id": "q1", "selected_index": 0}]},
    )
    assert client.delete(f"/api/lectures/{lecture_id}").status_code == 204
    assert client.get(f"/api/lectures/{lecture_id}").status_code == 404


def test_flashcard_spaced_repetition_flow(client: TestClient) -> None:
    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)
    base = f"/api/lectures/{lecture_id}/flashcards"

    progress = client.get(f"{base}/progress").json()
    assert (progress["total"], progress["new"], progress["due_now"], progress["mastered"]) == (1, 1, 1, 0)

    reviewed = client.post(f"{base}/c1/review", json={"result": "got_it"}).json()
    assert reviewed["box"] == 2 and reviewed["is_due"] is False

    progress = client.get(f"{base}/progress").json()
    assert (progress["new"], progress["learning"], progress["due_now"]) == (0, 1, 0)

    again = client.post(f"{base}/c1/review", json={"result": "again"}).json()
    assert again["box"] == 1 and again["is_due"] is True and again["reviews"] == 2

    assert client.post(f"{base}/c999/review", json={"result": "got_it"}).status_code == 404
    assert client.post(f"{base}/c1/review", json={"result": "maybe"}).status_code == 422

    assert client.delete(f"{base}/progress").status_code == 204
    assert client.get(f"{base}/progress").json()["new"] == 1

    # Deleting the lecture also removes its review rows (no foreign-key error).
    client.post(f"{base}/c1/review", json={"result": "got_it"})
    assert client.delete(f"/api/lectures/{lecture_id}").status_code == 204


def test_export_endpoints(client: TestClient) -> None:
    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)
    url = f"/api/lectures/{lecture_id}/export"

    pdf = client.get(url, params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="Neural-networks-notes.pdf"' in pdf.headers["content-disposition"]

    md = client.get(url, params={"format": "md"})
    assert md.status_code == 200 and "# Neural Networks" in md.text and "> Source: Neural networks" in md.text

    anki = client.get(url, params={"format": "csv"})
    assert anki.status_code == 200 and anki.text.startswith("#separator:comma")
    assert "flashcards.csv" in anki.headers["content-disposition"]

    assert client.get(url, params={"format": "docx"}).status_code == 422


def test_stats_dashboard(client: TestClient) -> None:
    empty = client.get("/api/stats").json()
    assert empty["totals"]["quizzes_taken"] == 0 and empty["totals"]["average_percent"] is None
    assert len(empty["activity"]) == 14

    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)
    for correct in (2, 1):  # two quizzes: 2/2 and 1/2
        answers = [{"question_id": f"q{i}", "selected_index": i % 4 if i <= correct else (i + 1) % 4} for i in (1, 2)]
        client.post(f"/api/lectures/{lecture_id}/quiz/submit", json={"answers": answers})
    client.post(f"/api/lectures/{lecture_id}/flashcards/c1/review", json={"result": "got_it"})

    stats = client.get("/api/stats", params={"tz_offset_minutes": 330}).json()
    totals = stats["totals"]
    assert (totals["lectures"], totals["quizzes_taken"], totals["questions_answered"]) == (1, 2, 4)
    assert totals["average_percent"] == 75.0 and totals["best_percent"] == 100.0
    assert totals["cards_reviewed"] == 1 and totals["flashcards_total"] == 1
    assert [p["percent"] for p in stats["score_history"]] == [100.0, 50.0]
    assert stats["activity"][-1]["questions_answered"] == 4 and stats["activity"][-1]["cards_reviewed"] == 1
    assert {b["label"]: b["count"] for b in stats["box_distribution"]}["Box 2"] == 1
    assert stats["lectures"][0]["quizzes"] == 2 and stats["lectures"][0]["last_percent"] == 50.0


def _chat(client: TestClient, lecture_id: str, message: str) -> list[tuple[str, dict]]:
    """Send a chat message and parse the Server-Sent Events into (event, data) pairs."""
    with client.stream("POST", f"/api/lectures/{lecture_id}/chat", json={"message": message}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_chat_streams_grounded_answer_and_saves_history(client: TestClient) -> None:
    lecture_id = _create(client)["id"]
    _wait_until_finished(client, lecture_id)

    events = _chat(client, lecture_id, "What does the speaker say when welcoming everyone?")
    names = [name for name, _ in events]
    assert names[0] in ("status", "sources") and "token" in names and names[-1] == "done"
    sources = next(data for name, data in events if name == "sources")["sources"]
    assert sources and sources[0]["text"] == "Hello and welcome."
    assert events[-1][1]["answer"] == CHAT_ANSWER

    history = client.get(f"/api/lectures/{lecture_id}/chat").json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["sources"][0]["start"] == 0

    assert client.delete(f"/api/lectures/{lecture_id}/chat").status_code == 204
    assert client.get(f"/api/lectures/{lecture_id}/chat").json() == []

    # Unrelated first question: "not covered", answered without calling the LLM.
    off_topic = _chat(client, lecture_id, "Who won the cricket world cup?")
    assert off_topic[-1][1]["answer"] == "This isn't covered in this lecture."

    # Validation: empty messages are rejected.
    assert client.post(f"/api/lectures/{lecture_id}/chat", json={"message": ""}).status_code == 422
