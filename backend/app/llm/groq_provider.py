"""LLM provider for Groq (OpenAI-compatible chat completions API)."""

import re
import time
from collections.abc import Iterator
from typing import Any

import groq

from app.llm.base import (
    ChatMessage,
    LLMAuthError,
    LLMError,
    LLMInvalidJSONError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
)

# Some reasoning models wrap their "thinking" in <think> tags; we only want the answer.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _retry_after(exc: groq.APIStatusError) -> float | None:
    try:
        return float(exc.response.headers.get("retry-after"))
    except (TypeError, ValueError, AttributeError):
        return None


class GroqProvider(LLMProvider):
    """Chat models hosted on Groq (e.g. openai/gpt-oss-120b)."""

    name = "groq"

    def __init__(self, api_key: str, model: str, reasoning_effort: str = "low") -> None:
        super().__init__(model)
        # The SDK retries short rate limits itself; our base class handles longer ones.
        self.client = groq.Groq(api_key=api_key, max_retries=2, timeout=120)
        self.reasoning_effort = reasoning_effort

    def _extra_params(self) -> dict[str, Any]:
        # gpt-oss models are "reasoning" models: they think before answering.
        # Low effort is faster and uses fewer tokens, which matters on the free tier.
        if self.model.startswith("openai/gpt-oss"):
            return {"reasoning_effort": self.reasoning_effort}
        return {}

    @staticmethod
    def _to_api(messages: list[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_api(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            **self._extra_params(),
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            completion = self.client.chat.completions.create(**params)
        except groq.RateLimitError as exc:
            raise LLMRateLimitError(str(exc), retry_after=_retry_after(exc)) from exc
        except groq.AuthenticationError as exc:
            raise LLMAuthError("Groq rejected the API key. Check GROQ_API_KEY in backend/.env.") from exc
        except groq.BadRequestError as exc:
            # In JSON mode Groq returns HTTP 400 "json_validate_failed" if the
            # model's output isn't valid JSON, and includes what it generated.
            body = exc.body if isinstance(exc.body, dict) else {}
            error = body.get("error", body) if isinstance(body, dict) else {}
            if isinstance(error, dict) and error.get("code") == "json_validate_failed":
                raise LLMInvalidJSONError(
                    "Model output was not valid JSON", error.get("failed_generation") or ""
                ) from exc
            raise LLMError(f"Groq rejected the request: {exc}") from exc
        except groq.APIConnectionError as exc:
            raise LLMError("Could not connect to Groq. Check your internet connection.") from exc
        except groq.APIStatusError as exc:
            raise LLMError(f"Groq API error {exc.status_code}: {exc}") from exc

        text = _THINK_RE.sub("", completion.choices[0].message.content or "").strip()
        usage = completion.usage
        return LLMResponse(
            text=text,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            seconds=time.perf_counter() - started,
        )

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        try:
            chunks = self.client.chat.completions.create(
                model=self.model,
                messages=self._to_api(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **self._extra_params(),
            )
            for chunk in chunks:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except groq.RateLimitError as exc:
            raise LLMRateLimitError(str(exc), retry_after=_retry_after(exc)) from exc
        except groq.AuthenticationError as exc:
            raise LLMAuthError("Groq rejected the API key.") from exc
        except groq.APIError as exc:
            raise LLMError(f"Groq streaming failed: {exc}") from exc
