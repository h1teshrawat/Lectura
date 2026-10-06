"""Phase (a) test tool: transcribe a YouTube link or a local file from the terminal.

Examples (run from the backend/ folder with the venv active):
    python -m cli.transcribe https://www.youtube.com/watch?v=aircAruvnKk
    python -m cli.transcribe https://youtu.be/aircAruvnKk --skip-captions --engine local
    python -m cli.transcribe C:\\path\\to\\lecture.mp3 --lang hi

The full transcript is saved as JSON in data/transcripts/ so later phases can
reuse it without fetching or transcribing again.
"""

import argparse
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.errors import LecturaError
from app.logging_config import setup_logging
from app.transcription.models import format_timestamp
from app.transcription.service import TranscriptionService


def _print_progress(stage: str, message: str, fraction: float | None) -> None:
    percent = f" {fraction * 100:5.1f}%" if fraction is not None else ""
    print(f"  [{stage:<12}]{percent} {message}", flush=True)


def main() -> int:
    # Make sure Hindi (Devanagari) text prints correctly in the Windows terminal.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Lectura transcription test")
    parser.add_argument("source", help="YouTube URL/video ID, or path to an audio/video file")
    parser.add_argument("--lang", choices=["auto", "en", "hi", "hinglish"], default="auto",
                        help="Lecture language (default: auto)")
    parser.add_argument("--engine", choices=["auto", "groq", "local"], default="auto",
                        help="Whisper engine when captions aren't used (default: auto)")
    parser.add_argument("--skip-captions", action="store_true",
                        help="Ignore YouTube captions and force Whisper (to test the fallback)")
    parser.add_argument("--show", type=int, default=10,
                        help="How many transcript lines to print (default: 10)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logs")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging("DEBUG" if args.verbose else "WARNING")

    print("\nLectura - transcription test")
    print(f"  Input:    {args.source}")
    print(f"  Groq key: {'found' if settings.has_groq else 'not set (local Whisper will be used)'}\n")

    service = TranscriptionService(settings)
    is_file = Path(args.source).exists()
    started = time.perf_counter()
    try:
        if is_file:
            result = service.transcribe_file(
                args.source, language=args.lang, engine=args.engine, on_progress=_print_progress
            )
        else:
            result = service.transcribe_youtube(
                args.source,
                language=args.lang,
                engine=args.engine,
                skip_captions=args.skip_captions,
                on_progress=_print_progress,
            )
    except LecturaError as exc:
        print(f"\nERROR: {exc.message}")
        if exc.hint:
            print(f"  {exc.hint}")
        return 1

    t = result.transcript
    print(f"\nDone in {time.perf_counter() - started:.1f} s")
    print(f"  Title:     {result.media.title}")
    print(f"  Source:    {t.source}")
    print(f"  Language:  {t.language}")
    print(f"  Duration:  {format_timestamp(result.media.duration_seconds or t.duration)}")
    print(f"  Segments:  {len(t.segments)}   Words: {t.word_count:,}")
    for warning in result.warnings:
        print(f"  WARNING:   {warning}")

    print(f"\nFirst {min(args.show, len(t.segments))} lines:")
    for seg in t.segments[: args.show]:
        print(f"  [{format_timestamp(seg.start):>7}] {seg.text}")

    out_dir = settings.data_path / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{result.media.source_id[:16]}.json"
    out_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved full transcript to {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
