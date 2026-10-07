"""The transcription pipeline: choose the best available method automatically.

Order of attempts for a YouTube link:
    1. Existing YouTube captions      (instant, free)
    2. Download audio -> Groq Whisper (fast, needs GROQ_API_KEY + internet)
    3. Download audio -> local Whisper (slow on CPU, but always works offline)

Uploaded files skip step 1 and go straight to Whisper.
"""

import hashlib
import logging
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # only for type hints: the real import happens lazily
    from app.transcription.local_whisper import LocalWhisperTranscriber

from app.config import Settings, get_settings
from app.errors import RateLimitError, TranscriptionFailedError, UnsupportedFileError
from app.transcription.audio import SUPPORTED_EXTENSIONS, AudioPart, probe_duration, split_audio
from app.transcription.downloader import download_audio, fetch_metadata
from app.transcription.groq_whisper import GroqWhisperError, GroqWhisperTranscriber
from app.transcription.models import (
    Language,
    MediaInfo,
    ProgressCallback,
    Transcript,
    TranscriptionResult,
    TranscriptSegment,
    format_timestamp,
)
from app.transcription.youtube_captions import extract_video_id, fetch_captions

logger = logging.getLogger(__name__)

WhisperEngine = Literal["auto", "groq", "local"]

# The language hint we give Whisper. For Hinglish we let Whisper auto-detect,
# because forcing "hi" makes it write English words in Devanagari script.
_WHISPER_LANGUAGE: dict[str, str | None] = {"en": "en", "hi": "hi", "hinglish": None, "auto": None}


class _Reporter:
    """Wraps the progress callback and avoids flooding it with tiny updates."""

    def __init__(self, callback: ProgressCallback | None) -> None:
        self.callback = callback
        self._last: tuple[str, str, float | None] | None = None

    def __call__(self, stage: str, message: str, fraction: float | None = None) -> None:
        if self.callback is None:
            return
        if self._last and fraction is not None and self._last[1] == message:
            previous = self._last[2] or 0.0
            if fraction < 1.0 and fraction - previous < 0.05:
                return  # less than 5% progress since the last update
        self._last = (stage, message, fraction)
        self.callback(stage, message, fraction)


def file_sha256(path: Path) -> str:
    """Hash a file's contents. Identical files get identical IDs (used for caching)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class TranscriptionService:
    """Turns a YouTube link or a media file into a timestamped transcript."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._local_whisper: "LocalWhisperTranscriber | None" = None

    @property
    def local_whisper(self) -> "LocalWhisperTranscriber":
        """The offline Whisper model, imported and created only when first needed.

        Importing faster-whisper alone costs memory, so small cloud servers that
        disable it (LOCAL_WHISPER_ENABLED=false) never load it at all.
        """
        if not self.settings.local_whisper_enabled:
            raise TranscriptionFailedError(
                "Local Whisper is disabled on this server.",
                hint="Set LOCAL_WHISPER_ENABLED=true, or make sure GROQ_API_KEY is set.",
            )
        if self._local_whisper is None:
            from app.transcription.local_whisper import LocalWhisperTranscriber

            self._local_whisper = LocalWhisperTranscriber(
                model_size=self.settings.local_whisper_model,
                device=self.settings.local_whisper_device,
                compute_type=self.settings.local_whisper_compute_type,
            )
        return self._local_whisper

    # ------------------------------------------------------------------ public

    def transcribe_youtube(
        self,
        url: str,
        language: Language = "auto",
        engine: WhisperEngine = "auto",
        skip_captions: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        """Transcribe a YouTube video.

        Args:
            url: Any YouTube link (or a bare video ID).
            language: Lecture language hint.
            engine: Which Whisper to use if there are no captions.
            skip_captions: Ignore existing captions and always use Whisper (for testing).
            on_progress: Optional progress callback.
        """
        started = time.perf_counter()
        report = _Reporter(on_progress)

        video_id = extract_video_id(url)
        report("fetching", "Reading video details...")
        media = fetch_metadata(video_id)
        warnings = self._length_warnings(media.duration_seconds)

        transcript: Transcript | None = None
        if not skip_captions:
            report("fetching", "Looking for existing YouTube captions...")
            transcript = fetch_captions(video_id, language)
            if transcript:
                report("fetching", f"Found YouTube captions ({transcript.language}).", 1.0)
            else:
                report("fetching", "No captions found. Transcribing the audio with Whisper.")

        if transcript is None:
            with self._workdir() as workdir:
                audio = download_audio(
                    video_id,
                    workdir,
                    on_progress=lambda f: report("fetching", "Downloading audio...", f),
                )
                transcript = self._transcribe_audio(audio, workdir, language, engine, report, warnings)

        if media.duration_seconds is None:
            media.duration_seconds = transcript.duration
            warnings += self._length_warnings(media.duration_seconds)

        report("transcribing", "Transcript ready.", 1.0)
        return TranscriptionResult(
            media=media,
            transcript=transcript,
            warnings=warnings,
            elapsed_seconds=round(time.perf_counter() - started, 2),
        )

    def transcribe_file(
        self,
        path: str | Path,
        language: Language = "auto",
        engine: WhisperEngine = "auto",
        title: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        """Transcribe a local audio/video file (MP3, MP4, WAV, ...)."""
        started = time.perf_counter()
        report = _Reporter(on_progress)
        path = Path(path)

        if not path.is_file():
            raise UnsupportedFileError(f"File not found: {path}", hint="Check the path and try again.")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileError(f"'{path.suffix}' files are not supported.")

        report("fetching", "Reading file...")
        duration = probe_duration(path)
        media = MediaInfo(
            source_type="upload",
            source_id=file_sha256(path),
            title=title or path.stem,
            duration_seconds=duration,
        )
        warnings = self._length_warnings(duration)

        with self._workdir() as workdir:
            transcript = self._transcribe_audio(path, workdir, language, engine, report, warnings)

        report("transcribing", "Transcript ready.", 1.0)
        return TranscriptionResult(
            media=media,
            transcript=transcript,
            warnings=warnings,
            elapsed_seconds=round(time.perf_counter() - started, 2),
        )

    # ----------------------------------------------------------------- helpers

    @contextmanager
    def _workdir(self) -> Iterator[Path]:
        """A temporary folder that is deleted afterwards (even if an error happens)."""
        with tempfile.TemporaryDirectory(
            dir=self.settings.tmp_path, ignore_cleanup_errors=True
        ) as tmp:
            yield Path(tmp)

    def _length_warnings(self, seconds: float | None) -> list[str]:
        limit_hours = self.settings.long_video_warning_hours
        if seconds and seconds > limit_hours * 3600:
            return [
                f"This lecture is {format_timestamp(seconds)} long (over {limit_hours:g} hours). "
                "Processing will take a while and may use up your free API quota."
            ]
        return []

    def _transcribe_audio(
        self,
        audio: Path,
        workdir: Path,
        language: Language,
        engine: WhisperEngine,
        report: _Reporter,
        warnings: list[str],
    ) -> Transcript:
        """Split audio into parts and run Whisper on each, adjusting timestamps."""
        report("transcribing", "Preparing audio with ffmpeg...")
        parts = split_audio(audio, workdir / "parts", self.settings.audio_segment_seconds)
        total = sum(p.duration for p in parts) or 1.0
        whisper_language = _WHISPER_LANGUAGE.get(language)

        groq_client: GroqWhisperTranscriber | None = None
        if engine in ("auto", "groq"):
            if self.settings.has_groq:
                groq_client = GroqWhisperTranscriber(
                    self.settings.groq_api_key, self.settings.groq_whisper_model
                )
            elif engine == "groq":
                raise TranscriptionFailedError(
                    "You chose the Groq engine but GROQ_API_KEY is not set.",
                    hint="Add your key to backend/.env, or use the local engine.",
                )
            elif not self.settings.local_whisper_enabled:
                raise TranscriptionFailedError(
                    "No speech-to-text engine is available: GROQ_API_KEY is not set and local Whisper is disabled.",
                    hint="Add GROQ_API_KEY to the server settings.",
                )
            else:
                logger.info("No GROQ_API_KEY set, so using local Whisper (slower on CPU).")

        all_segments: list[TranscriptSegment] = []
        engines_used: set[str] = set()
        detected_language: str | None = None

        for index, part in enumerate(parts, start=1):
            label = f"part {index}/{len(parts)}"
            segments: list[TranscriptSegment] | None = None

            if groq_client is not None:
                report("transcribing", f"Groq Whisper: {label}", part.offset / total)
                try:
                    segments, lang = groq_client.transcribe(part.path, whisper_language)
                    engines_used.add("groq")
                except GroqWhisperError as exc:
                    if engine == "groq" or not self.settings.local_whisper_enabled:
                        # No fallback available: report the Groq problem itself.
                        error_cls = RateLimitError if exc.rate_limited else TranscriptionFailedError
                        raise error_cls(f"Groq transcription failed: {exc.reason}.") from exc
                    logger.warning("Groq failed on %s (%s). Falling back to local Whisper.", label, exc.reason)
                    warnings.append(f"Groq Whisper failed ({exc.reason}), so local Whisper was used instead.")
                    groq_client = None  # don't try Groq again for the remaining parts

            if segments is None:
                message = f"Local Whisper: {label} (slower on CPU)"
                report("transcribing", message, part.offset / total)
                segments, lang = self.local_whisper.transcribe(
                    part.path,
                    whisper_language,
                    on_progress=lambda f, p=part, m=message: report(
                        "transcribing", m, (p.offset + f * p.duration) / total
                    ),
                )
                engines_used.add("local")

            detected_language = detected_language or lang
            all_segments.extend(_shift(segments, part))

        if not all_segments:
            raise TranscriptionFailedError("Whisper didn't detect any speech in this audio.")

        if engines_used == {"groq"}:
            source = "groq_whisper"
        elif engines_used == {"local"}:
            source = "local_whisper"
        else:
            source = "mixed_whisper"
        return Transcript(source=source, language=detected_language, segments=all_segments)


def _shift(segments: list[TranscriptSegment], part: AudioPart) -> list[TranscriptSegment]:
    """Convert times relative to an audio part into times in the full lecture."""
    shifted = []
    for seg in segments:
        end = seg.end if seg.end > seg.start else part.duration
        shifted.append(
            TranscriptSegment(start=seg.start + part.offset, end=end + part.offset, text=seg.text)
        )
    return shifted
