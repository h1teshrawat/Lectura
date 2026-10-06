"""Split a timestamped transcript into ~5-minute chunks.

Why chunk at all?
- LLMs have a limited context window, and long inputs make them slower,
  costlier and more likely to skip details in the middle ("lost in the middle").
- Free API tiers limit tokens per minute, so smaller requests are safer.
- Each chunk covers a known time range, so notes made from it get accurate
  timestamps.

We cut only *between* transcript segments (never mid-sentence) and keep
every segment's timestamps.
"""

from dataclasses import dataclass, field

from app.transcription.models import TranscriptSegment, format_timestamp


@dataclass
class Chunk:
    """A continuous slice of the transcript."""

    index: int
    start: float
    end: float
    segments: list[TranscriptSegment] = field(repr=False)

    @property
    def text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_prompt_text(self, line_seconds: float = 20.0) -> str:
        """Format the chunk for an LLM prompt, with a [m:ss] marker every ~20 s.

        Example:
            [4:00] So today we'll talk about gradient descent...
            [4:21] The idea is to move downhill on the loss surface...

        One marker per ~20 seconds (instead of per caption line) gives the model
        enough timestamps to cite while keeping the prompt short.
        """
        lines: list[str] = []
        current: list[str] = []
        line_start = self.segments[0].start if self.segments else self.start
        for seg in self.segments:
            if current and seg.start - line_start >= line_seconds:
                lines.append(f"[{format_timestamp(line_start)}] {' '.join(current)}")
                current, line_start = [], seg.start
            current.append(seg.text)
        if current:
            lines.append(f"[{format_timestamp(line_start)}] {' '.join(current)}")
        return "\n".join(lines)


def chunk_transcript(
    segments: list[TranscriptSegment],
    target_seconds: float = 300,
    max_words: int = 1500,
    min_last_fraction: float = 0.4,
) -> list[Chunk]:
    """Group transcript segments into chunks of about `target_seconds` each.

    Args:
        segments: Transcript segments in time order.
        target_seconds: Desired chunk length (default 5 minutes).
        max_words: Start a new chunk early if this many words is reached
            (protects against very fast speakers).
        min_last_fraction: If the final chunk is shorter than this fraction of
            the target, merge it into the previous chunk instead of leaving a
            tiny chunk at the end.

    Returns:
        Chunks in order. Empty list if there are no segments.
    """
    groups: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    current_words = 0

    for seg in segments:
        seg_words = len(seg.text.split())
        too_long = current and seg.end - current[0].start > target_seconds
        too_many_words = current and current_words + seg_words > max_words
        if too_long or too_many_words:
            groups.append(current)
            current, current_words = [], 0
        current.append(seg)
        current_words += seg_words

    if current:
        last_duration = current[-1].end - current[0].start
        if groups and last_duration < target_seconds * min_last_fraction:
            previous_words = sum(len(s.text.split()) for s in groups[-1])
            if previous_words + current_words <= max_words * 1.5:
                groups[-1].extend(current)
                current = []
        if current:
            groups.append(current)

    return [
        Chunk(index=i, start=group[0].start, end=group[-1].end, segments=group)
        for i, group in enumerate(groups)
    ]
