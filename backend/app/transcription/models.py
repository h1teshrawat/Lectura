"""Data models for transcripts.

A transcript is a list of *segments*: short pieces of text, each with the time
(in seconds) where it starts and ends in the video. Keeping timestamps on every
segment is what later lets us make clickable timestamps in the notes and cite
times in the RAG chat.
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

# What language the lecture is in (chosen by the user on the home page).
Language = Literal["auto", "en", "hi", "hinglish"]

# Where the transcript came from.
TranscriptSource = Literal["youtube_captions", "groq_whisper", "local_whisper", "mixed_whisper"]

# Progress callback: (stage, message, fraction 0..1 or None).
# The CLI prints these; in Phase (d) the API forwards them to the browser with SSE.
ProgressCallback = Callable[[str, str, float | None], None]


class TranscriptSegment(BaseModel):
    """One timed piece of the transcript."""

    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")
    text: str


class Transcript(BaseModel):
    """A full transcript plus information about how it was produced."""

    source: TranscriptSource
    language: str | None = None
    segments: list[TranscriptSegment]

    @property
    def duration(self) -> float:
        """Length covered by the transcript, in seconds."""
        return self.segments[-1].end if self.segments else 0.0

    @property
    def full_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())


class MediaInfo(BaseModel):
    """Basic details about the lecture (a YouTube video or an uploaded file)."""

    source_type: Literal["youtube", "upload"]
    # The YouTube video ID, or a SHA-256 hash of an uploaded file. Used as the cache key.
    source_id: str
    title: str
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    channel: str | None = None
    url: str | None = None


class TranscriptionResult(BaseModel):
    """Everything the transcription step returns."""

    media: MediaInfo
    transcript: Transcript
    warnings: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0


def format_timestamp(seconds: float) -> str:
    """Format seconds as `m:ss` or `h:mm:ss` (like YouTube does).

    >>> format_timestamp(75)
    '1:15'
    >>> format_timestamp(3725)
    '1:02:05'
    """
    total = int(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fix_overlaps(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Trim segment end times so that no segment overlaps the next one.

    YouTube's auto-generated captions often overlap (a line is still on screen
    when the next one appears). Clean, non-overlapping times make chunking
    and timestamp citations accurate.
    """
    fixed: list[TranscriptSegment] = []
    for i, seg in enumerate(segments):
        end = seg.end
        if i + 1 < len(segments):
            next_start = segments[i + 1].start
            if seg.start < next_start < end:
                end = next_start
        fixed.append(TranscriptSegment(start=seg.start, end=max(end, seg.start), text=seg.text))
    return fixed
