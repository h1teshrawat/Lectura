"""LLM abstraction layer: one interface, switchable providers (Groq, Gemini)."""

from app.llm.base import ChatMessage, LLMProvider, LLMResponse, LLMUsage
from app.llm.factory import get_llm
from app.llm.structured import extract_json, generate_structured

__all__ = [
    "ChatMessage",
    "LLMProvider",
    "LLMResponse",
    "LLMUsage",
    "extract_json",
    "generate_structured",
    "get_llm",
]
