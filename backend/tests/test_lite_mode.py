"""Tests for the cloud 'lite' mode: Gemini embeddings and disabled local Whisper."""

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from app.config import Settings
from app.errors import ConfigurationError, RateLimitError, TranscriptionFailedError
from app.rag import embedder as embedder_module
from app.rag.embedder import GeminiEmbedder
from app.transcription import service as service_module
from app.transcription.audio import AudioPart
from app.transcription.groq_whisper import GroqWhisperError
from app.transcription.service import TranscriptionService


class FakeGeminiModels:
    """Records embed_content calls and returns simple vectors (optionally failing first)."""

    def __init__(self, fail_first_with: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.fail_first_with = fail_first_with

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "count": len(contents), **config})
        if self.fail_first_with is not None:
            error, self.fail_first_with = self.fail_first_with, None
            raise error
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents])


def _gemini(models: FakeGeminiModels) -> GeminiEmbedder:
    embedder = GeminiEmbedder("test-key")
    embedder._client = SimpleNamespace(models=models)
    return embedder


def test_gemini_embedder_batches_and_normalises() -> None:
    models = FakeGeminiModels()
    vectors = _gemini(models).embed([f"text {i}" for i in range(250)])

    assert [c["count"] for c in models.calls] == [100, 100, 50]  # API batch limit
    assert all(c["task_type"] == "RETRIEVAL_DOCUMENT" and c["output_dimensionality"] == 768 for c in models.calls)
    assert len(vectors) == 250
    assert math.isclose(math.hypot(*vectors[0]), 1.0)  # length 1, so dot product = cosine similarity


def test_gemini_embedder_uses_query_task_for_questions() -> None:
    models = FakeGeminiModels()
    _gemini(models).embed_query(["What is a neuron?"])
    assert models.calls[0]["task_type"] == "RETRIEVAL_QUERY"


def test_gemini_embedder_retries_rate_limits(monkeypatch) -> None:
    monkeypatch.setattr(embedder_module.time, "sleep", lambda seconds: None)
    models = FakeGeminiModels(fail_first_with=genai_errors.ClientError(429, {"error": {"message": "slow down"}}))
    assert len(_gemini(models).embed(["a", "b"])) == 2
    assert len(models.calls) == 2


def test_gemini_embedder_without_key_explains_what_to_do() -> None:
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        GeminiEmbedder("").embed(["text"])


# ------------------------------------------------- local Whisper disabled


def _service(monkeypatch, **settings) -> TranscriptionService:
    # Pretend ffmpeg split the audio into one 10-second part.
    part = AudioPart(path=Path("part_000.mp3"), offset=0.0, duration=10.0)
    monkeypatch.setattr(service_module, "split_audio", lambda *args, **kwargs: [part])
    return TranscriptionService(Settings(_env_file=None, local_whisper_enabled=False, **settings))


def _transcribe(service: TranscriptionService) -> None:
    service._transcribe_audio(Path("lecture.mp3"), Path("."), "en", "auto", lambda *a, **k: None, [])


def test_local_whisper_property_refuses_when_disabled() -> None:
    service = TranscriptionService(Settings(_env_file=None, local_whisper_enabled=False))
    with pytest.raises(TranscriptionFailedError, match="disabled"):
        _ = service.local_whisper


def test_no_engine_available_gives_clear_error(monkeypatch) -> None:
    with pytest.raises(TranscriptionFailedError, match="No speech-to-text engine"):
        _transcribe(_service(monkeypatch, groq_api_key=""))


def test_groq_failure_without_fallback_reports_the_groq_problem(monkeypatch) -> None:
    class RateLimitedGroq:
        def __init__(self, *args) -> None: ...

        def transcribe(self, *args):
            raise GroqWhisperError("Groq rate limit reached", rate_limited=True)

    monkeypatch.setattr(service_module, "GroqWhisperTranscriber", RateLimitedGroq)
    with pytest.raises(RateLimitError, match="Groq transcription failed"):
        _transcribe(_service(monkeypatch, groq_api_key="test-key"))
