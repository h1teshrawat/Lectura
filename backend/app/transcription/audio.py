"""Audio helpers built on ffmpeg / ffprobe.

Why we re-encode audio before sending it to Whisper:
- Whisper only needs 16 kHz mono audio; that's what the model was trained on.
- A 32 kbps mono MP3 is ~14 MB per hour, versus ~100+ MB for the original.
- Groq accepts files up to about 25 MB, so we also split long audio into
  ~10-minute parts and remember each part's *offset* (where it starts in the
  full lecture), so the timestamps stay correct after we join the parts back.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.errors import DependencyMissingError, TranscriptionFailedError

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".mkv", ".mov", ".aac", ".opus",
}


@dataclass
class AudioPart:
    """One piece of a split audio file."""

    path: Path
    offset: float  # seconds from the start of the full lecture
    duration: float


def ensure_ffmpeg() -> None:
    """Make sure ffmpeg and ffprobe are on PATH, with install help if not."""
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise DependencyMissingError(
            f"{' and '.join(missing)} not found.",
            hint="Install it with:  winget install Gyan.FFmpeg  and then open a NEW terminal.",
        )


def probe_duration(path: Path) -> float:
    """Return the length of an audio/video file in seconds, using ffprobe."""
    ensure_ffmpeg()
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise TranscriptionFailedError(
            f"Could not read '{path.name}'. The file may be damaged or not an audio/video file."
        ) from exc


def split_audio(source: Path, out_dir: Path, segment_seconds: int = 600) -> list[AudioPart]:
    """Convert any audio/video file into 16 kHz mono MP3 parts.

    Args:
        source: Input audio or video file.
        out_dir: Folder for the parts (created if missing).
        segment_seconds: Target length of each part.

    Returns:
        The parts in order, each with its offset in the original file.
    """
    ensure_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "part_%03d.mp3"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-vn",                      # drop any video stream
        "-ac", "1",                 # mono
        "-ar", "16000",             # 16 kHz sample rate
        "-c:a", "libmp3lame", "-b:a", "32k",
        "-f", "segment",
        "-segment_time", str(segment_seconds),
        "-reset_timestamps", "1",
        str(pattern),
    ]
    logger.info("Converting and splitting audio with ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg failed: %s", result.stderr.strip()[-500:])
        raise TranscriptionFailedError(
            f"ffmpeg could not process '{source.name}'. It may not contain an audio track."
        )

    parts: list[AudioPart] = []
    offset = 0.0
    for path in sorted(out_dir.glob("part_*.mp3")):
        duration = probe_duration(path)
        parts.append(AudioPart(path=path, offset=offset, duration=duration))
        offset += duration

    if not parts:
        raise TranscriptionFailedError(f"No audio found in '{source.name}'.")
    logger.info("Audio split into %d part(s), total %.0f s.", len(parts), offset)
    return parts
