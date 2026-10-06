"""The provider-independent LLM interface.

Every provider (Groq, Gemini, or a fake one in tests) implements the same small
interface, so the rest of the app never needs to know which one is in use.
This is the *Strategy* / *Adapter* design pattern: swap the provider in
`.env` and nothing else changes.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from app.errors import RateLimitError

logger = logging.getLogger(__name__)

Role = Literal["system", "user", "assistant"]

# How long to wait between rate-limit retries if the API doesn't tell us (seconds).
_BACKOFF_SECONDS = [5, 15, 30, 60]
# If the API asks us to wait longer than this, it's probably a daily limit: give up.
_MAX_WAIT_SECONDS = 90


@dataclass
class ChatMessage:
    """One message in a conversation with the model."""

    role: Role
    content: str


@dataclass
class LLMResponse:
    """The model's reply plus token counts (used for evaluation and cost tracking)."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


@dataclass
class LLMUsage:
    """Running totals of all calls made through one provider object."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, response: LLMResponse) -> None:
        with self._lock:
            self.calls += 1
            self.prompt_tokens += response.prompt_tokens
            self.completion_tokens += response.completion_tokens
            self.seconds += response.seconds

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMError(Exception):
    """A provider call failed for a reason other than the ones below."""


class LLMRateLimitError(LLMError):
    """The provider said 'too many requests'. `retry_after` is in seconds, if known."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMAuthError(LLMError):
    """The API key is missing, wrong or revoked."""


class LLMInvalidJSONError(LLMError):
    """JSON mode was on but the model produced invalid JSON.

    `failed_output` holds what the model wrote, so we can show it the mistake.
    """

    def __init__(self, message: str, failed_output: str = "") -> None:
        super().__init__(message)
        self.failed_output = failed_output


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    name: str = "base"

    def __init__(self, model: str) -> None:
        self.model = model
        self.usage = LLMUsage()

    @property
    def label(self) -> str:
        """Human-readable name like 'groq:openai/gpt-oss-120b'."""
        return f"{self.name}:{self.model}"

    # --- Methods each provider implements -----------------------------------

    @abstractmethod
    def _complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Make one API call. Raise the LLM*Error classes above on failure."""

    @abstractmethod
    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Yield the reply piece by piece as it is generated (used by chat)."""

    # --- Shared logic --------------------------------------------------------

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Call the model, automatically waiting and retrying on rate limits.

        Raises:
            RateLimitError: still rate-limited after several retries (user-facing).
            LLMAuthError / LLMError: other failures.
        """
        for attempt in range(len(_BACKOFF_SECONDS) + 1):
            try:
                response = self._complete(
                    messages, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
                )
                self.usage.record(response)
                return response
            except LLMRateLimitError as exc:
                wait = exc.retry_after or _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                out_of_retries = attempt >= len(_BACKOFF_SECONDS)
                if out_of_retries or wait > _MAX_WAIT_SECONDS:
                    raise RateLimitError(
                        f"{self.label} rate limit reached (asked to wait {wait:.0f}s).",
                        hint=(
                            "You may have hit the free daily limit. Wait a while, switch to a "
                            "smaller model, or set LLM_PROVIDER=gemini in backend/.env."
                        ),
                    ) from exc
                logger.warning("Rate limited by %s; waiting %.0fs before retrying...", self.label, wait)
                time.sleep(wait)
        raise AssertionError("unreachable")  # pragma: no cover
