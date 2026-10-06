"""Phase (c) test tool: generate flashcards and a quiz, and play the quiz in the terminal.

Examples (run from backend/ with the venv active):
    python -m cli.study data\\transcripts\\aircAruvnKk.json
    python -m cli.study data\\transcripts\\aircAruvnKk.json --play
    python -m cli.study data\\transcripts\\aircAruvnKk.json --play --difficulty hard --count 5

Results are saved in data/study/, so `--play` reuses them instead of calling
the LLM again (add --regenerate to force new ones).
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.errors import LecturaError
from app.generators.flashcards import FlashcardGenerator
from app.generators.quiz import QuizGenerator, select_questions
from app.generators.schemas import FlashcardDeck, QuestionBank, QuizQuestion
from app.llm.factory import get_llm
from app.logging_config import setup_logging
from app.transcription.models import TranscriptionResult, format_timestamp

LETTERS = "ABCD"


def _progress(message: str, fraction: float | None) -> None:
    percent = f"{fraction * 100:5.1f}% " if fraction is not None else ""
    print(f"  [study] {percent}{message}", flush=True)


def _print_flashcards(deck: FlashcardDeck, limit: int = 8) -> None:
    print(f"\nFLASHCARDS ({len(deck.cards)} cards, {len(deck.rejected)} rejected by quality checks)")
    for card in deck.cards[:limit]:
        print(f"\n  [{format_timestamp(card.start_seconds)}] Q: {card.question}")
        print(f"          A: {card.answer}")
    if len(deck.cards) > limit:
        print(f"\n  ... and {len(deck.cards) - limit} more (see the saved JSON file)")


def _print_bank(bank: QuestionBank, limit: int = 3) -> None:
    print("\nQUIZ QUESTION BANK")
    print(f"  Generated: {bank.generated_count}   Valid: {len(bank.questions)}   "
          f"Rejected: {len(bank.rejected)}   Validity rate: {bank.validity_rate:.0%}")
    levels = Counter(q.difficulty for q in bank.questions)
    print(f"  Difficulty: easy={levels['easy']}  medium={levels['medium']}  hard={levels['hard']}")
    positions = Counter(LETTERS[q.correct_index] for q in bank.questions)
    print("  Correct answer positions after shuffling: "
          + "  ".join(f"{letter}={positions[letter]}" for letter in LETTERS))
    for rejection in bank.rejected:
        print(f"  REJECTED: {rejection.item[:70]!r} -> {', '.join(rejection.reasons)}")

    for question in bank.questions[:limit]:
        print(f"\n  ({question.difficulty}) [{format_timestamp(question.start_seconds)}] {question.question}")
        for i, option in enumerate(question.options):
            marker = "*" if i == question.correct_index else " "
            print(f"     {marker} {LETTERS[i]}) {option}")
        print(f"       Why: {question.explanation}")


def _play(questions: list[QuizQuestion]) -> None:
    """A simple interactive quiz in the terminal."""
    print("\n" + "=" * 70)
    print(f"QUIZ TIME: {len(questions)} questions. Type A, B, C or D and press Enter (Q to quit).")
    print("=" * 70)
    score, wrong = 0, []
    for number, question in enumerate(questions, start=1):
        print(f"\nQ{number} ({question.difficulty}): {question.question}")
        for i, option in enumerate(question.options):
            print(f"   {LETTERS[i]}) {option}")
        while True:
            reply = input("Your answer: ").strip().lstrip("﻿").upper()
            if reply in {"A", "B", "C", "D", "Q"}:
                break
            print("   Please type A, B, C or D.")
        if reply == "Q":
            break
        correct_letter = LETTERS[question.correct_index]
        if reply == correct_letter:
            score += 1
            print("   Correct!")
        else:
            wrong.append(question)
            print(f"   Wrong. The answer is {correct_letter}) {question.options[question.correct_index]}")
        print(f"   {question.explanation}  (see {format_timestamp(question.start_seconds)} in the video)")

    answered = score + len(wrong)
    if answered:
        print(f"\nSCORE: {score}/{answered} ({score / answered:.0%})")
    if wrong:
        print("Review these parts of the lecture: "
              + ", ".join(format_timestamp(q.start_seconds) for q in wrong))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Lectura flashcards + quiz test")
    parser.add_argument("transcript", help="Transcript .json saved by `python -m cli.transcribe`")
    parser.add_argument("--provider", choices=["groq", "gemini"], help="Override LLM_PROVIDER")
    parser.add_argument("--model", help="Override the model name")
    parser.add_argument("--lang", choices=["english", "hindi", "hinglish"], help="Output language")
    parser.add_argument("--play", action="store_true", help="Take the quiz in the terminal")
    parser.add_argument("--count", type=int, default=10, help="Questions per quiz (default 10)")
    parser.add_argument("--difficulty", choices=["mixed", "easy", "medium", "hard"], default="mixed")
    parser.add_argument("--regenerate", action="store_true", help="Ignore saved results and call the LLM again")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logs")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging("INFO" if args.verbose else "WARNING")

    path = Path(args.transcript)
    if not path.is_file():
        print(f"ERROR: transcript file not found: {path}")
        print("  Create one first with: python -m cli.transcribe <youtube-link>")
        return 1
    result = TranscriptionResult.model_validate_json(path.read_text(encoding="utf-8"))

    out_dir = settings.data_path / "study"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.media.source_id[:16]
    deck_file, bank_file = out_dir / f"{stem}_flashcards.json", out_dir / f"{stem}_quiz.json"

    print(f"\nLectura - flashcards & quiz test\n  Lecture: {result.media.title}")

    if deck_file.exists() and bank_file.exists() and not args.regenerate:
        print("  Using saved results (add --regenerate to create new ones)")
        deck = FlashcardDeck.model_validate_json(deck_file.read_text(encoding="utf-8"))
        bank = QuestionBank.model_validate_json(bank_file.read_text(encoding="utf-8"))
    else:
        try:
            llm = get_llm(args.provider, args.model)
            options = {
                "output_language": args.lang or settings.notes_language,
                "chunk_seconds": settings.chunk_seconds,
                "max_workers": settings.llm_max_concurrency,
                "temperature": settings.llm_temperature,
            }
            print(f"  Model:   {llm.label}\n")
            started = time.perf_counter()
            deck = FlashcardGenerator(llm, **options).generate(result.transcript, on_progress=_progress)
            bank = QuizGenerator(llm, **options).generate(result.transcript, on_progress=_progress)
            elapsed = time.perf_counter() - started
        except LecturaError as exc:
            print(f"\nERROR: {exc.message}")
            if exc.hint:
                print(f"  {exc.hint}")
            return 1

        deck_file.write_text(deck.model_dump_json(indent=2), encoding="utf-8")
        bank_file.write_text(bank.model_dump_json(indent=2), encoding="utf-8")
        usage = llm.usage
        print(f"\nGenerated in {elapsed:.1f} s with {usage.calls} LLM calls "
              f"({usage.total_tokens:,} tokens). Saved to {out_dir}")

    _print_flashcards(deck)
    _print_bank(bank)

    if args.play:
        questions = select_questions(bank.questions, count=args.count, difficulty=args.difficulty)
        _play(questions)
    else:
        print("\nTip: add --play to take the quiz in the terminal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
