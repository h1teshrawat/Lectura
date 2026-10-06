"""Create the configured LLM provider."""

from app.config import Settings, get_settings
from app.errors import ConfigurationError
from app.llm.base import LLMProvider


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    settings: Settings | None = None,
) -> LLMProvider:
    """Build an LLM provider from settings (or explicit overrides).

    Args:
        provider: "groq" or "gemini". Defaults to LLM_PROVIDER from .env.
        model: Model name override. Defaults to GROQ_MODEL / GEMINI_MODEL.
    """
    settings = settings or get_settings()
    provider = (provider or settings.llm_provider).lower()

    if provider == "groq":
        if not settings.has_groq:
            raise ConfigurationError("GROQ_API_KEY is not set.")
        from app.llm.groq_provider import GroqProvider

        return GroqProvider(
            settings.groq_api_key,
            model or settings.groq_model,
            reasoning_effort=settings.groq_reasoning_effort,
        )

    if provider == "gemini":
        if not settings.has_gemini:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set.",
                hint="Get a free key at https://aistudio.google.com/apikey and add it to backend/.env.",
            )
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, model or settings.gemini_model)

    raise ConfigurationError(f"Unknown LLM provider '{provider}'.", hint="Use 'groq' or 'gemini'.")
