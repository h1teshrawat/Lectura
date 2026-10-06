"""Split a transcript into small, overlapping pieces for semantic search.

Why smaller than the 5-minute chunks used for notes? For retrieval we want
each piece to be about *one* idea, so its embedding is precise and the
citation points to the right moment. About 60 seconds (~150 words) works well.

Why overlap? If an explanation starts at the end of one piece and continues
in the next, overlapping by ~15 seconds means at least one piece contains
the whole thought.
"""

from dataclasses import dataclass

from app.transcription.models import TranscriptSegment


@dataclass
class RetrievalChunk:
    index: int
    start: float
    end: float
    text: str


def build_retrieval_chunks(
    segments: list[TranscriptSegment],
    window_seconds: float = 60.0,
    overlap_seconds: float = 15.0,
) -> list[RetrievalChunk]:
    """Group transcript segments into overlapping windows of about `window_seconds`."""
    chunks: list[RetrievalChunk] = []
    i, n = 0, len(segments)
    while i < n:
        window_start = segments[i].start
        j = i + 1  # every window has at least one segment
        while j < n and segments[j].end - window_start <= window_seconds:
            j += 1
        group = segments[i:j]
        chunks.append(
            RetrievalChunk(
                index=len(chunks),
                start=group[0].start,
                end=group[-1].end,
                text=" ".join(seg.text for seg in group),
            )
        )
        if j >= n:
            break
        # Start the next window `overlap_seconds` before this one ended
        # (but always move forward by at least one segment).
        next_i = j
        while next_i - 1 > i and segments[next_i - 1].start >= group[-1].end - overlap_seconds:
            next_i -= 1
        i = next_i
    return chunks
