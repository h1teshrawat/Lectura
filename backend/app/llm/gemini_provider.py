"""LLM provider for Google Gemini, using the official `google-genai` SDK."""

import re
import time
from collections.abc import Iterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.llm.base import (
    ChatMessage,
    LLMAuthError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
)

# Gemini puts the suggested wait in the error details, e.g. "retryDelay": "34s".
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


def _convert_error(exc: genai_errors.APIError) -> LLMError:
    if exc.code == 429:
        match = _RETRY_DELAY_RE.search(str(exc))
        return LLMRateLimitError(str(exc), retry_after=float(match.group(1)) if match else None)
    if exc.code in (401, 403) or (exc.code == 400 and "API key" in str(exc)):
        return LLMAuthError("Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env.")
    return LLMError(f"Gemini API error {exc.code}: {exc}")


class GeminiProvider(LLMProvider):
    """Google Gemini models (free tier available via Google AI Studio)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.client = genai.Client(api_key=api_key)

    @staticmethod
    def _split(messages: list[ChatMessage]) -> tuple[str | None, list[types.Content]]:
        """Gemini takes the system prompt separately and calls the assistant 'model'."""
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part.from_text(text=m.content)],
            )
            for m in messages
            if m.role != "system"
        ]
        return system, contents

    def _config(
        self, system: str | None, *, json_mode: bool, temperature: float, max_tokens: int
    ) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
        )

    def _complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        system, contents = self._split(messages)
        started = time.perf_counter()
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._config(
                    system, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
                ),
            )
        except genai_errors.APIError as exc:
            raise _convert_error(exc) from exc
        except Exception as exc:  # network errors etc.
            raise LLMError(f"Could not reach Gemini: {exc}") from exc

        usage = response.usage_metadata
        return LLMResponse(
            text=(response.text or "").strip(),
            prompt_tokens=(usage.prompt_token_count or 0) if usage else 0,
            completion_tokens=(usage.candidates_token_count or 0) if usage else 0,
            seconds=time.perf_counter() - started,
        )

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        system, contents = self._split(messages)
        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=self._config(
                    system, json_mode=False, temperature=temperature, max_tokens=max_tokens
                ),
            ):
                if chunk.text:
                    yield chunk.text
        except genai_errors.APIError as exc:
            raise _convert_error(exc) from exc
