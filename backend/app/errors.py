"""Custom exceptions with user-friendly messages.

Every error carries:
- `message`: what went wrong, in plain words (shown to the user);
- `hint`: what the user can do about it.

The API layer (Phase d) turns these into clean JSON error responses.
"""

UPLOAD_HINT = "Tip: download the lecture yourself and upload the audio/video file instead."


class LectureLensError(Exception):
    """Base class for all expected (user-facing) errors."""

    default_hint: str = ""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = self.default_hint if hint is None else hint

    def __str__(self) -> str:
        return f"{self.message} {self.hint}".strip()


class InvalidYouTubeURLError(LectureLensError):
    default_hint = "Paste a link like https://www.youtube.com/watch?v=... or https://youtu.be/..."


class VideoUnavailableError(LectureLensError):
    """The video is private, deleted, age-restricted or otherwise unplayable."""

    default_hint = UPLOAD_HINT


class DownloadFailedError(LectureLensError):
    """yt-dlp could not download the audio (network issue, YouTube bot check, ...)."""

    default_hint = UPLOAD_HINT


class UnsupportedFileError(LectureLensError):
    default_hint = "Supported formats: MP3, MP4, WAV, M4A, WEBM, OGG, FLAC, MKV, MOV."


class TranscriptionFailedError(LectureLensError):
    default_hint = "Check that the file has audible speech, or try a different file."


class DependencyMissingError(LectureLensError):
    """A required external program (like ffmpeg) is not installed."""


class RateLimitError(LectureLensError):
    default_hint = "The free API limit was reached. Wait a minute and try again."
