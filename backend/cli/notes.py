"""Phase (b) test tool: generate smart notes from a transcript.

Examples (run from backend/ with the venv active):
    # Use a transcript saved by `python -m cli.transcribe`
    python -m cli.notes data\\transcripts\\aircAruvnKk.json

    # Or give a YouTube link / file directly (it is transcribed first)
    python -m cli.notes https://www.youtube.com/watch?v=aircAruvnKk

    # Try another provider, model or notes language
    python -m cli.notes data\\transcripts\\aircAruvnKk.json --model openai/gpt-oss-20b
    python -m cli.notes data\\transcripts\\aircAruvnKk.json --provider gemini
    python -m cli.notes data\\transcripts\\aircAruvnKk.json --lang hinglish
"""

import argparse
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.errors import LectureLensError
from app.generators.markdown import notes_to_markdown
from app.generators.notes import NotesGenerator
from app.llm.factory import get_llm
from app.logging_config import setup_logging
from app.transcription.models import TranscriptionResult
from app.transcription.service import TranscriptionService


def _load_transcript(source: str) -> TranscriptionResult:
    """Load a saved transcript JSON, or transcribe a URL/file."""
    path = Path(source)
    if path.suffix.lower() == ".json" and path.is_file():
        return TranscriptionResult.model_validate_json(path.read_text(encoding="utf-8"))

    print("Transcribing first...")
    service = TranscriptionService()
    if path.is_file():
        return service.transcribe_file(path)
    return service.transcribe_youtube(source)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="LectureLens notes generation test")
    parser.add_argument("source", help="Transcript .json, YouTube URL or media file")
    parser.add_argument("--provider", choices=["groq", "gemini"], help="Override LLM_PROVIDER")
    parser.add_argument("--model", help="Override the model name")
    parser.add_argument("--lang", choices=["english", "hindi", "hinglish"], help="Notes language")
    parser.add_argument("--chunk-seconds", type=int, help="Chunk length (default from .env: 300)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logs")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging("INFO" if args.verbose else "WARNING")

    try:
        result = _load_transcript(args.source)
        llm = get_llm(args.provider, args.model)
        generator = NotesGenerator(
            llm,
            output_language=args.lang or settings.notes_language,
            chunk_seconds=args.chunk_seconds or settings.chunk_seconds,
            max_workers=settings.llm_max_concurrency,
            temperature=settings.llm_temperature,
        )

        transcript = result.transcript
        print("\nLectureLens - notes test")
        print(f"  Lecture:  {result.media.title}")
        print(f"  Words:    {transcript.word_count:,}")
        print(f"  Model:    {llm.label}\n")

        started = time.perf_counter()
        notes = generator.generate(
            transcript,
            title_hint=result.media.title,
            on_progress=lambda message, fraction: print(
                f"  [notes] {fraction * 100:5.1f}% {message}" if fraction is not None else f"  [notes] {message}",
                flush=True,
            ),
        )
        elapsed = time.perf_counter() - started
    except LectureLensError as exc:
        print(f"\nERROR: {exc.message}")
        if exc.hint:
            print(f"  {exc.hint}")
        return 1

    markdown = notes_to_markdown(notes, video_url=result.media.url)
    print("\n" + "=" * 70 + "\n" + markdown + "=" * 70)

    usage = llm.usage
    print(f"\nDone in {elapsed:.1f} s")
    print(f"  Sections: {len(notes.sections)}   Glossary terms: {len(notes.glossary)}")
    print(
        f"  LLM calls: {usage.calls}   Tokens: {usage.prompt_tokens:,} in + "
        f"{usage.completion_tokens:,} out = {usage.total_tokens:,}"
    )

    out_dir = settings.data_path / "notes"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.media.source_id[:16]
    (out_dir / f"{stem}.json").write_text(notes.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(markdown, encoding="utf-8")
    print(f"  Saved: {out_dir / (stem + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
