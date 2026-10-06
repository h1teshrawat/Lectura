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

    # Limits
    long_video_warning_hours: float = 3.0

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
