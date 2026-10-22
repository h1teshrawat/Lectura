"""Tests for the bundled demo lectures (exported locally, loaded on the cloud server)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.db.demo import DEMO_DIR, export_lecture, seed_demo_lectures
from app.db.models import Lecture
from app.db.session import create_db_engine
from app.main import create_app
from app.rag.service import RAGService
from app.rag.vector_store import ChromaVectorStore
from tests.fakes import FakeLLM
from tests.fakes_rag import HashingEmbedder
from tests.test_api import FakePipeline


def _finished_lecture(**fields) -> Lecture:
    return Lecture(
        id="abc123", source_type="youtube", source_id="aircAruvnKk", title="Neural networks",
        status="done", stage="done", progress=1.0, transcript_json='{"source": "x"}',
        notes_json='{"title": "Notes"}', flashcard_count=3, **fields,
    )


def test_export_then_seed_round_trip(tmp_path: Path) -> None:
    path = export_lecture(_finished_lecture(), tmp_path / "demo")
    assert path.name == "aircAruvnKk.json"

    engine = create_db_engine(tmp_path / "fresh.db")
    assert seed_demo_lectures(engine, tmp_path / "demo") == 1
    assert seed_demo_lectures(engine, tmp_path / "demo") == 0  # already there: not added twice

    with Session(engine) as session:
        lecture = session.get(Lecture, "abc123")
        assert lecture is not None
        assert lecture.status == "done"
        assert lecture.notes_json == '{"title": "Notes"}'
        assert lecture.flashcard_count == 3
        assert lecture.created_at is not None


def test_unfinished_lecture_is_not_exported(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_lecture(_finished_lecture().model_copy(update={"status": "failed"}), tmp_path)


@pytest.mark.skipif(not list(DEMO_DIR.glob("*.json")), reason="no demo lectures bundled")
def test_bundled_demo_lectures_are_served_from_cache(tmp_path: Path) -> None:
    """The committed demo files load, and submitting their YouTube link opens them instantly."""
    settings = Settings(_env_file=None, data_dir=tmp_path, groq_api_key="test-key", rag_warmup=False, seed_demo_lectures=True)
    rag = RAGService(ChromaVectorStore(path=None), HashingEmbedder(), lambda: FakeLLM(["ok"]), settings)
    pipeline = FakePipeline()
    with TestClient(create_app(settings, pipeline=pipeline, rag=rag)) as client:
        library = client.get("/api/lectures").json()
        assert len(library) == len(list(DEMO_DIR.glob("*.json")))

        for path in DEMO_DIR.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            response = client.post("/api/lectures", data={"url": data["url"]})
            assert response.status_code == 200, response.text
            assert response.json() == {"id": data["id"], "status": "done", "cached": True}

            detail = client.get(f"/api/lectures/{data['id']}").json()
            assert detail["notes"]["sections"]
            assert detail["flashcards"]
            assert client.get(f"/api/lectures/{data['id']}/quiz?count=5&difficulty=mixed").json()["questions"]
            assert client.get(f"/api/lectures/{data['id']}/transcript").json()["segments"]
    assert pipeline.runs == []  # nothing was reprocessed
