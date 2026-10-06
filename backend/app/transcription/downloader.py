"""Video metadata and audio download from YouTube, using yt-dlp."""

import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.errors import DownloadFailedError, VideoUnavailableError
from app.transcription.models import MediaInfo
from app.transcription.youtube_captions import video_url

logger = logging.getLogger(__name__)


class _YtDlpLogger:
    """Send yt-dlp's own messages to our log instead of printing them raw."""

    def debug(self, msg: str) -> None:
        logger.debug(msg)

    def info(self, msg: str) -> None:
        logger.debug(msg)

    def warning(self, msg: str) -> None:
        logger.debug(msg)

    def error(self, msg: str) -> None:
        logger.debug(msg)  # we raise our own friendly error instead


# Recent YouTube versions require solving a JavaScript challenge to download.
# yt-dlp does this with a JS runtime: Deno if installed, otherwise Node.js.
_BASE_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "noplaylist": True,
    "logger": _YtDlpLogger(),
    "js_runtimes": {"deno": {}, "node": {}},
}


def _friendly_error(exc: Exception) -> Exception:
    """Translate a raw yt-dlp error into one of our user-friendly errors."""
    text = str(exc).lower()
    if "not a bot" in text or "429" in text or "too many requests" in text:
        return DownloadFailedError(
            "YouTube blocked the download (bot check / too many requests). "
            "This often happens on cloud servers or after many downloads."
        )
    if "service unavailable" in text or "timed out" in text or "getaddrinfo" in text:
        return DownloadFailedError("Network problem while contacting YouTube. Check your internet.")
    if "private video" in text:
        return VideoUnavailableError("This video is private, so it can't be downloaded.")
    if "confirm your age" in text or "age-restricted" in text:
        return VideoUnavailableError("This video is age-restricted, so LectureLens can't access it.")
    if "unavailable" in text or "has been removed" in text or "not available" in text:
        return VideoUnavailableError("This video is unavailable (deleted, private or region-locked).")
    if "live event" in text or "premieres" in text:
        return VideoUnavailableError("This is an upcoming live stream or premiere with no recording yet.")
    return DownloadFailedError(f"Could not download audio from YouTube ({str(exc)[:200]}).")


def _fetch_oembed(video_id: str) -> dict[str, Any] | None:
    """Lightweight fallback for title/channel when yt-dlp metadata fails."""
    query = urllib.parse.urlencode({"url": video_url(video_id), "format": "json"})
    try:
        with urllib.request.urlopen(f"https://www.youtube.com/oembed?{query}", timeout=10) as resp:
            return json.load(resp)
    except Exception:  # noqa: BLE001 - any failure just means "no metadata"
        return None


def fetch_metadata(video_id: str) -> MediaInfo:
    """Get the title, duration, channel and thumbnail of a YouTube video.

    Tries yt-dlp first (it gives us the duration), then YouTube's oEmbed endpoint.

    Raises:
        VideoUnavailableError: the video is private/deleted/age-restricted.
    """
    try:
        with YoutubeDL(_BASE_OPTS) as ydl:
            info = ydl.extract_info(video_url(video_id), download=False, process=False)
        return MediaInfo(
            source_type="youtube",
            source_id=video_id,
            title=info.get("title") or f"YouTube video {video_id}",
            duration_seconds=info.get("duration"),
            thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            channel=info.get("channel") or info.get("uploader"),
            url=video_url(video_id),
        )
    except DownloadError as exc:
        friendly = _friendly_error(exc)
        if isinstance(friendly, VideoUnavailableError):
            raise friendly from exc
        logger.warning("yt-dlp metadata failed (%s); trying oEmbed.", type(friendly).__name__)

    oembed = _fetch_oembed(video_id) or {}
    return MediaInfo(
        source_type="youtube",
        source_id=video_id,
        title=oembed.get("title") or f"YouTube video {video_id}",
        duration_seconds=None,
        thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        channel=oembed.get("author_name"),
        url=video_url(video_id),
    )


def download_audio(
    video_id: str,
    out_dir: Path,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Download the best available audio-only stream of a video.

    Args:
        video_id: YouTube video ID.
        out_dir: Folder to save the file in.
        on_progress: Optional callback receiving download progress (0..1).

    Returns:
        Path to the downloaded audio file (usually .webm or .m4a).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(status: dict[str, Any]) -> None:
        if on_progress and status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if total:
                on_progress(min(status.get("downloaded_bytes", 0) / total, 1.0))

    opts = {
        **_BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{video_id}.%(ext)s"),
        "progress_hooks": [hook],
    }
    logger.info("Downloading audio for %s with yt-dlp...", video_id)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url(video_id), download=True)
            path = Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        raise _friendly_error(exc) from exc

    if not path.exists():
        raise DownloadFailedError("yt-dlp finished but the audio file was not found.")
    logger.info("Downloaded %s (%.1f MB).", path.name, path.stat().st_size / 1e6)
    return path
