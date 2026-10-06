"""A fake LLM for tests: returns scripted replies, needs no internet or API key."""

from collections.abc import Callable, Iterator

from app.llm.base import ChatMessage, LLMProvider, LLMResponse

Reply = str | Callable[[list[ChatMessage]], str]


class FakeLLM(LLMProvider):
    """Replies with the given strings in order (the last one repeats).

    A reply can also be a function that receives the messages and returns text,
    so a test can answer differently depending on the prompt.
    """

    name = "fake"

    def __init__(self, replies: list[Reply]) -> None:
        super().__init__(model="fake-model")
        self.replies = replies
        self.calls: list[list[ChatMessage]] = []

    def _next_reply(self, messages: list[ChatMessage]) -> str:
        reply = self.replies[min(len(self.calls), len(self.replies) - 1)]
        self.calls.append(messages)
        return reply(messages) if callable(reply) else reply

    def _complete(self, messages, *, json_mode, temperature, max_tokens) -> LLMResponse:
        return LLMResponse(text=self._next_reply(messages), prompt_tokens=10, completion_tokens=5)

    def stream(self, messages, *, temperature=0.3, max_tokens=2048) -> Iterator[str]:
        yield from self._next_reply(messages).split(" ")
