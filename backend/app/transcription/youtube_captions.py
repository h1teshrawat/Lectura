"""YouTube link parsing and caption fetching (the fastest transcription path).

Many YouTube videos already have captions: either uploaded by the creator
("manual") or made by YouTube's own speech recognition ("auto-generated").
If they exist, we can skip downloading audio and running Whisper entirely.
"""

import html
import logging
import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApi,
)

from app.errors import InvalidYouTubeURLError, VideoUnavailableError
from app.transcription.models import Language, Transcript, TranscriptSegment, fix_overlaps

logger = logging.getLogger(__name__)

# A YouTube video ID is always exactly 11 characters: letters, digits, '-' or '_'.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Caption languages to try, in order of preference, for each lecture language.
_CAPTION_LANGUAGES: dict[str, list[str]] = {
    "en": ["en", "en-IN", "en-US", "en-GB"],
    "hi": ["hi", "en", "en-IN"],
    "hinglish": ["hi", "en-IN", "en"],
    "auto": ["en", "en-IN", "en-US", "en-GB", "hi"],
}

# Caption tags such as [Music] or [Applause] that are not speech.
_TAG_RE = re.compile(r"\[[^\]]{1,40}\]")


def extract_video_id(url_or_id: str) -> str:
    """Pull the 11-character video ID out of any common YouTube link format.

    Supports youtube.com/watch?v=, youtu.be/, /shorts/, /embed/, /live/,
    mobile (m.youtube.com) links and a bare video ID.

    Raises:
        InvalidYouTubeURLError: if no valid video ID is found.
    """
    text = url_or_id.strip()
    if _VIDEO_ID_RE.match(text):
        return text

    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m."):
        host = host.removeprefix(prefix)

    candidate: str | None = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
                candidate = parts[1]

    if candidate and _VIDEO_ID_RE.match(candidate):
        return candidate
    raise InvalidYouTubeURLError(f"'{url_or_id}' doesn't look like a YouTube video link.")


def video_url(video_id: str) -> str:
    """Canonical watch URL for a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


def _clean_caption_text(text: str) -> str:
    """Remove HTML entities, line breaks and [Music]-style tags."""
    text = html.unescape(text).replace("\n", " ")
    text = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_captions(video_id: str, language: Language = "auto") -> Transcript | None:
    """Fetch existing YouTube captions for a video.

    Preference order: manual captions in a preferred language, then
    auto-generated captions in a preferred language, then any captions at all.

    Returns:
        The transcript, or None if the video has no usable captions (or YouTube
        blocked the request). In that case the caller falls back to Whisper.

    Raises:
        VideoUnavailableError: the video is private, deleted or age-restricted.
    """
    preferred = _CAPTION_LANGUAGES.get(language, _CAPTION_LANGUAGES["auto"])
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        logger.info("Video %s has no captions.", video_id)
        return None
    except (VideoUnavailable, InvalidVideoId) as exc:
        raise VideoUnavailableError(
            "This video is unavailable. It may be private, deleted, or the link may be wrong."
        ) from exc
    except AgeRestricted as exc:
        raise VideoUnavailableError(
            "This video is age-restricted, so LectureLens can't access it."
        ) from exc
    except VideoUnplayable as exc:
        raise VideoUnavailableError(
            "YouTube says this video can't be played (it may be private or region-locked)."
        ) from exc
    except (RequestBlocked, IpBlocked):
        logger.warning("YouTube blocked the caption request (common on cloud servers).")
        return None
    except CouldNotRetrieveTranscript as exc:
        logger.warning("Could not retrieve captions: %s", type(exc).__name__)
        return None

    try:
        chosen = transcript_list.find_manually_created_transcript(preferred)
    except NoTranscriptFound:
        try:
            chosen = transcript_list.find_generated_transcript(preferred)
        except NoTranscriptFound:
            chosen = next(iter(transcript_list), None)
    if chosen is None:
        return None

    logger.info(
        "Using %s captions in '%s'.",
        "auto-generated" if chosen.is_generated else "manual",
        chosen.language_code,
    )
    try:
        fetched = chosen.fetch()
    except CouldNotRetrieveTranscript as exc:
        logger.warning("Captions were listed but could not be downloaded: %s", type(exc).__name__)
        return None

    segments = []
    for snippet in fetched:
        text = _clean_caption_text(snippet.text)
        if text:
            segments.append(
                TranscriptSegment(
                    start=snippet.start, end=snippet.start + snippet.duration, text=text
                )
            )
    if not segments:
        return None

    return Transcript(
        source="youtube_captions",
        language=chosen.language_code,
        segments=fix_overlaps(segments),
    )
