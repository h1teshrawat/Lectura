"""Application settings, loaded from environment variables and the `.env` file.

`pydantic-settings` reads each field from an environment variable with the same
name (case-insensitive), so `groq_api_key` comes from `GROQ_API_KEY`. Keys are
never hard-coded in the source.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend/ folder. Using it as the base means paths work no matter which
# directory you start Python from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configurable values for the app."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys (empty string means "not configured")
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Transcription
    groq_whisper_model: str = "whisper-large-v3"
    local_whisper_model: str = "small"
    local_whisper_compute_type: str = "int8"
    local_whisper_device: str = "cpu"
    audio_segment_seconds: int = 600
    # Set to false on small cloud servers: local Whisper needs ~1 GB of RAM.
    local_whisper_enabled: bool = True

    # LLM
    llm_provider: Literal["groq", "gemini"] = "groq"
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    gemini_model: str = "gemini-flash-latest"
    llm_temperature: float = 0.3
    llm_max_concurrency: int = 1

    # Notes generation
    chunk_seconds: int = 300
    notes_language: str = "english"

    # RAG chat
    # "local" = sentence-transformers on this machine (needs PyTorch, ~1 GB RAM);
    # "gemini" = Google's embedding API (tiny memory use; for small cloud servers).
    embedding_provider: Literal["local", "gemini"] = "local"
    # Multilingual model (50+ languages) so Hindi/Hinglish questions work too.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    gemini_embedding_model: str = "gemini-embedding-001"
    rag_chunk_seconds: float = 60.0
    rag_chunk_overlap_seconds: float = 15.0
    rag_top_k: int = 5
    # Below this similarity (0..1) nothing in the lecture is related to the question.
    # Measured on a real lecture: on-topic questions scored 0.45-0.80, off-topic 0.03-0.13.
    rag_min_similarity: float = 0.20
    rag_history_messages: int = 6
    # Load the embedding model in the background when the server starts.
    rag_warmup: bool = True

    # Limits
    long_video_warning_hours: float = 3.0
    max_upload_mb: int = 500

    # Web server
    # How many lectures to process at the same time (1 is safest on free API tiers)
    max_parallel_jobs: int = 1
    # Websites allowed to call the API (the Vite dev server by default)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # General
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @property
    def data_path(self) -> Path:
        """Absolute path to the data directory (created if missing)."""
        path = self.data_dir if self.data_dir.is_absolute() else BACKEND_DIR / self.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def tmp_path(self) -> Path:
        """Folder for temporary audio files."""
        path = self.data_path / "tmp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object (read from .env only once)."""
    return Settings()
