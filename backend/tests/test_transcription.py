"""Unit tests for the transcription helpers (no internet or API keys needed)."""

import pytest

from app.errors import DownloadFailedError, InvalidYouTubeURLError, VideoUnavailableError
from app.transcription.audio import AudioPart
from app.transcription.downloader import _friendly_error
from app.transcription.models import TranscriptSegment, fix_overlaps, format_timestamp
from app.transcription.service import _shift
from app.transcription.youtube_captions import _clean_caption_text, extract_video_id

VIDEO_ID = "aircAruvnKk"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://www.youtube.com/watch?v={VIDEO_ID}&t=42s&list=PLxyz",
        f"https://youtu.be/{VIDEO_ID}?si=abc123",
        f"https://m.youtube.com/watch?v={VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}",
        f"youtube.com/watch?v={VIDEO_ID}",
        f"  {VIDEO_ID}  ",
    ],
)
def test_extract_video_id_accepts_common_formats(url: str) -> None:
    assert extract_video_id(url) == VIDEO_ID


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/watch?v=aircAruvnKk",
        "https://www.youtube.com/playlist?list=PLxyz",
        "https://www.youtube.com/watch?v=short",
        "not a link",
        "",
    ],
)
def test_extract_video_id_rejects_invalid_links(url: str) -> None:
    with pytest.raises(InvalidYouTubeURLError):
        extract_video_id(url)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0:00"), (5.9, "0:05"), (75, "1:15"), (600, "10:00"), (3725, "1:02:05")],
)
def test_format_timestamp(seconds: float, expected: str) -> None:
    assert format_timestamp(seconds) == expected


def test_clean_caption_text_removes_tags_and_entities() -> None:
    assert _clean_caption_text("[Music]  hello &amp;\nwelcome [Applause]") == "hello & welcome"


def test_fix_overlaps_trims_end_times() -> None:
    segments = [
        TranscriptSegment(start=0, end=5, text="a"),
        TranscriptSegment(start=3, end=8, text="b"),
        TranscriptSegment(start=8, end=10, text="c"),
    ]
    fixed = fix_overlaps(segments)
    assert [s.end for s in fixed] == [3, 8, 10]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", VideoUnavailableError),
        ("ERROR: [youtube] abc: This video is unavailable", VideoUnavailableError),
        ("ERROR: [youtube] abc: Sign in to confirm your age", VideoUnavailableError),
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", DownloadFailedError),
        ("ERROR: HTTP Error 503: Service Unavailable", DownloadFailedError),
        ("ERROR: HTTP Error 429: Too Many Requests", DownloadFailedError),
        ("ERROR: something unexpected", DownloadFailedError),
    ],
)
def test_friendly_error_mapping(raw: str, expected: type) -> None:
    assert isinstance(_friendly_error(Exception(raw)), expected)


def test_shift_adds_part_offset() -> None:
    part = AudioPart(path=None, offset=600.0, duration=600.0)  # type: ignore[arg-type]
    shifted = _shift([TranscriptSegment(start=1.5, end=4.0, text="hi")], part)
    assert (shifted[0].start, shifted[0].end) == (601.5, 604.0)
