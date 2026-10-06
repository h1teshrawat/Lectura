"""Speech-to-text with Whisper large-v3, hosted on Groq's free API."""

import logging
from pathlib import Path
from typing import Any

import groq

from app.transcription.models import TranscriptSegment

logger = logging.getLogger(__name__)

# Whisper sometimes "hallucinates" text during silence or music (e.g.
# "Thanks for watching!"). It also reports how likely a segment is to contain
# no speech, so we drop segments that look like silence.
_NO_SPEECH_THRESHOLD = 0.8
_LOW_CONFIDENCE_LOGPROB = -1.0


class GroqWhisperError(Exception):
    """Groq transcription failed. `reason` is a short human-readable explanation."""

    def __init__(self, reason: str, rate_limited: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.rate_limited = rate_limited


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(obj)


class GroqWhisperTranscriber:
    """Transcribes one audio file at a time through the Groq API."""

    def __init__(self, api_key: str, model: str = "whisper-large-v3") -> None:
        # max_retries: the SDK automatically waits and retries on rate limits (HTTP 429).
        self.client = groq.Groq(api_key=api_key, max_retries=3, timeout=300)
        self.model = model

    def transcribe(
        self, path: Path, language: str | None = None
    ) -> tuple[list[TranscriptSegment], str | None]:
        """Transcribe an audio file.

        Args:
            path: Audio file (must be under Groq's upload size limit).
            language: ISO code like "en" or "hi", or None to auto-detect.

        Returns:
            (segments with times relative to this file, detected language)

        Raises:
            GroqWhisperError: on any API problem (bad key, rate limit, no internet...).
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",  # includes per-segment timestamps
            "temperature": 0.0,
        }
        if language:
            kwargs["language"] = language

        try:
            with open(path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    file=(path.name, f.read()), **kwargs
                )
        except groq.AuthenticationError as exc:
            raise GroqWhisperError("Groq API key is invalid") from exc
        except groq.RateLimitError as exc:
            raise GroqWhisperError("Groq rate limit reached", rate_limited=True) from exc
        except groq.APIConnectionError as exc:
            raise GroqWhisperError("could not connect to Groq (no internet?)") from exc
        except groq.APIStatusError as exc:
            raise GroqWhisperError(f"Groq API error {exc.status_code}") from exc

        data = _as_dict(response)
        segments: list[TranscriptSegment] = []
        for raw in data.get("segments") or []:
            seg = _as_dict(raw)
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            if (
                seg.get("no_speech_prob", 0) > _NO_SPEECH_THRESHOLD
                and seg.get("avg_logprob", 0) < _LOW_CONFIDENCE_LOGPROB
            ):
                logger.debug("Dropping likely-silence segment: %r", text)
                continue
            segments.append(
                TranscriptSegment(start=float(seg["start"]), end=float(seg["end"]), text=text)
            )

        # Fallback: some responses may contain only the plain text.
        if not segments and data.get("text", "").strip():
            segments.append(TranscriptSegment(start=0.0, end=0.0, text=data["text"].strip()))

        language_out = data.get("language")
        return segments, language_out.lower() if isinstance(language_out, str) else None
