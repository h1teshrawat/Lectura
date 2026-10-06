"""Getting reliable, validated JSON out of an LLM.

LLMs produce text, but our app needs structured data (lists of sections,
flashcards, questions...). The approach:

1. Ask for JSON in the prompt and turn on the provider's JSON mode.
2. Parse the reply, tolerating common mistakes (```json fences, extra prose).
3. Validate it against a Pydantic model: right fields, right types, sensible values.
4. If parsing or validation fails, send the error back to the model and ask it
   to fix its answer (a "self-correction" retry).
"""

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import StructuredOutputError
from app.llm.base import ChatMessage, LLMInvalidJSONError, LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array found in an LLM reply.

    Handles: plain JSON, JSON inside ```json fences, and JSON surrounded by
    extra sentences ("Sure! Here is the JSON: {...}").

    Raises:
        ValueError: if no valid JSON can be found.
    """
    text = _THINK_RE.sub("", text).strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first '{' or '[' and decode from there, ignoring anything after.
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char in "{[":
            try:
                value, _ = decoder.raw_decode(text[index:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("No valid JSON found in the model's reply.")


def describe_error(exc: Exception) -> str:
    """A short, model-readable description of what was wrong."""
    if isinstance(exc, ValidationError):
        problems = []
        for err in exc.errors()[:6]:
            location = ".".join(str(part) for part in err["loc"]) or "(root)"
            problems.append(f"- {location}: {err['msg']}")
        return "The JSON did not match the required format:\n" + "\n".join(problems)
    return f"The reply was not valid JSON ({exc})."


def generate_structured(
    llm: LLMProvider,
    messages: list[ChatMessage],
    schema: type[T],
    *,
    max_retries: int = 2,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> T:
    """Ask the LLM for JSON and return it as a validated Pydantic object.

    Args:
        llm: The provider to call.
        messages: The prompt (should describe the exact JSON format wanted).
        schema: Pydantic model the reply must match.
        max_retries: How many correction attempts after the first try.

    Raises:
        StructuredOutputError: still invalid after all retries.
    """
    conversation = list(messages)
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            raw = llm.complete(
                conversation, json_mode=True, temperature=temperature, max_tokens=max_tokens
            ).text
        except LLMInvalidJSONError as exc:
            raw = exc.failed_output

        try:
            return schema.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Invalid %s from %s (attempt %d/%d): %s",
                schema.__name__, llm.label, attempt + 1, max_retries + 1, str(exc)[:200],
            )
            # Show the model its own answer and what was wrong with it.
            conversation = [
                *messages,
                ChatMessage("assistant", raw[:6000] or "(empty reply)"),
                ChatMessage(
                    "user",
                    f"{describe_error(exc)}\n\nReply again with ONLY the corrected JSON object "
                    "in exactly the requested format. No markdown, no explanations.",
                ),
            ]

    raise StructuredOutputError(
        f"The AI model returned invalid {schema.__name__} data {max_retries + 1} times in a row."
    ) from last_error
