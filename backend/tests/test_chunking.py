"""Tests for transcript chunking."""

from app.generators.chunking import chunk_transcript
from app.transcription.models import TranscriptSegment


def make_segments(total_seconds: int, step: int = 10, words_per_segment: int = 5) -> list[TranscriptSegment]:
    """Fake transcript: one segment every `step` seconds."""
    return [
        TranscriptSegment(start=t, end=t + step, text=" ".join(["word"] * words_per_segment))
        for t in range(0, total_seconds, step)
    ]


def test_empty_transcript_gives_no_chunks() -> None:
    assert chunk_transcript([]) == []


def test_short_transcript_is_one_chunk() -> None:
    chunks = chunk_transcript(make_segments(120))
    assert len(chunks) == 1
    assert (chunks[0].start, chunks[0].end) == (0, 120)


def test_chunks_are_about_target_length() -> None:
    chunks = chunk_transcript(make_segments(1500), target_seconds=300)  # 25 minutes
    assert len(chunks) == 5
    for chunk in chunks:
        assert chunk.end - chunk.start <= 300


def test_no_segment_is_lost_or_duplicated() -> None:
    segments = make_segments(1234)
    chunks = chunk_transcript(segments, target_seconds=300)
    assert [s for c in chunks for s in c.segments] == segments
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_tiny_last_chunk_is_merged_into_previous() -> None:
    # 10 minutes + 30 seconds: the 30 s tail should not become its own chunk.
    chunks = chunk_transcript(make_segments(630), target_seconds=300)
    assert len(chunks) == 2
    assert chunks[-1].end == 630


def test_max_words_starts_a_new_chunk_early() -> None:
    # Very fast speech: 100 words every 10 s.
    chunks = chunk_transcript(make_segments(300, words_per_segment=100), max_words=1000)
    assert all(c.word_count <= 1000 for c in chunks)
    assert len(chunks) == 3


def test_prompt_text_has_timestamp_markers() -> None:
    chunk = chunk_transcript(make_segments(120), target_seconds=300)[0]
    lines = chunk.to_prompt_text(line_seconds=20).splitlines()
    assert lines[0].startswith("[0:00] ")
    assert lines[1].startswith("[0:20] ")
    assert len(lines) == 6
