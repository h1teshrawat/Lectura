"""Lectura evaluation: summary quality (ROUGE), LLM comparison and transcription WER.

Run from the project root with the backend's virtual environment:

    backend\\.venv\\Scripts\\python evaluation\\run_eval.py          # everything
    backend\\.venv\\Scripts\\python evaluation\\run_eval.py llm      # LLM comparison + ROUGE
    backend\\.venv\\Scripts\\python evaluation\\run_eval.py wer      # transcription accuracy
    backend\\.venv\\Scripts\\python evaluation\\run_eval.py --fresh  # ignore cached runs

Expensive steps (LLM generations, transcriptions) are cached in results/runs/,
so after writing a new reference summary you can re-run instantly.
Everything is configured in evaluation/config.json.
"""

import argparse
import csv
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
RESULTS = EVAL_DIR / "results"  # can be changed with --out
RUNS = RESULTS / "runs"
sys.path.insert(0, str(BACKEND_DIR))  # so we can reuse the app's own code

from app.config import get_settings  # noqa: E402
from app.db.session import DB_FILENAME  # noqa: E402
from app.errors import LecturaError  # noqa: E402
from app.generators.notes import NotesGenerator  # noqa: E402
from app.generators.quiz import QuizGenerator  # noqa: E402
from app.llm.factory import get_llm  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.transcription.downloader import download_audio  # noqa: E402
from app.transcription.groq_whisper import GroqWhisperError, GroqWhisperTranscriber  # noqa: E402
from app.transcription.local_whisper import LocalWhisperTranscriber  # noqa: E402
from app.transcription.models import Transcript  # noqa: E402
from app.transcription.youtube_captions import extract_video_id  # noqa: E402

import charts  # noqa: E402
from metrics import ROUGE_TYPES, lead_baseline, mean_std, rouge, transcription_score  # noqa: E402

ROUGE_LABELS = {"rouge1": "ROUGE-1", "rouge2": "ROUGE-2", "rougeL": "ROUGE-L"}
PLACEHOLDER = "TODO: write your summary here"


# ---------------------------------------------------------------- helpers


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_json(path: Path) -> Any:
    # utf-8-sig also accepts files saved by Windows Notepad with a byte-order mark.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # -sig: Excel reads Hindi correctly
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No data._"
    headers = list(rows[0])
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(row[h]) for h in headers) + " |" for row in rows]
    return "\n".join(lines)


def load_lecture(lecture_id: str) -> tuple[str, Transcript] | None:
    """Title and transcript of a processed lecture, read straight from the app's database."""
    db = BACKEND_DIR / "data" / DB_FILENAME
    if not db.exists():
        return None
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute("SELECT title, transcript_json FROM lecture WHERE id = ?", (lecture_id,)).fetchone()
    finally:
        connection.close()
    if not row or not row[1]:
        return None
    return row[0], Transcript.model_validate_json(row[1])


def read_reference(path: Path) -> str | None:
    """A reference summary, without Markdown headings, quotes and HTML comments."""
    if not path.exists():
        return None
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("#", ">")))
    if PLACEHOLDER.lower() in text.lower() or len(text.split()) < 30:
        return None  # not written yet
    return text.strip()


# ------------------------------------------------------ LLM comparison


def run_system(system: dict, lecture_name: str, title: str, transcript: Transcript, fresh: bool) -> dict:
    """Generate notes + quiz with one LLM for one lecture (cached in results/runs/)."""
    cache = RUNS / "llm" / slug(system["name"]) / f"{slug(lecture_name)}.json"
    if cache.exists() and not fresh:
        return load_json(cache)

    settings = get_settings()
    print(f"  > {system['name']} on '{lecture_name}' ...", flush=True)
    try:
        llm = get_llm(system["provider"], system["model"], settings)
        options = {"chunk_seconds": settings.chunk_seconds, "temperature": settings.llm_temperature}
        started = time.perf_counter()
        notes = NotesGenerator(llm, **options).generate(transcript, title_hint=title)
        notes_done = time.perf_counter()
        bank = QuizGenerator(llm, **options).generate(transcript)
        finished = time.perf_counter()
    except LecturaError as exc:
        print(f"    skipped: {exc.message}")
        return {"skipped": exc.message}  # not cached: retried next time (e.g. after adding a key)

    reasons = Counter(reason for r in bank.rejected for reason in r.reasons)
    record = {
        "system": system["name"],
        "model": llm.label,
        "lecture": lecture_name,
        "wall_seconds": round(finished - started, 1),  # includes waiting for rate limits
        "notes_seconds": round(notes_done - started, 1),
        "quiz_seconds": round(finished - notes_done, 1),
        "api_seconds": round(llm.usage.seconds, 1),  # time actually spent in API calls
        "llm_calls": llm.usage.calls,
        "prompt_tokens": llm.usage.prompt_tokens,
        "completion_tokens": llm.usage.completion_tokens,
        "mcq_generated": bank.generated_count,
        "mcq_valid": len(bank.questions),
        "mcq_rejection_reasons": dict(reasons),
        "sections": len(notes.sections),
        "summary": notes.overview + "\n" + "\n".join(notes.key_takeaways),
        "notes": notes.model_dump(),
    }
    save_json(cache, record)
    print(f"    done in {record['wall_seconds']}s, {record['mcq_valid']}/{record['mcq_generated']} valid MCQs")
    return record


def evaluate_llms(config: dict, fresh: bool) -> str:
    print("\n== LLM comparison and summary quality ==")
    run_rows, rouge_rows = [], []
    per_system: dict[str, list[dict]] = {s["name"]: [] for s in config["systems"]}
    rouge_by_system: dict[str, dict[str, list[float]]] = {}
    lectures_with_reference = 0
    notes_md: list[str] = []

    for lecture in config["lectures"]:
        loaded = load_lecture(lecture["lecture_id"])
        if not loaded:
            print(f"  ! lecture {lecture['lecture_id']} not found in the database; skipping")
            continue
        title, transcript = loaded
        reference = read_reference(EVAL_DIR / lecture["reference_summary"])
        if reference:
            lectures_with_reference += 1
        else:
            notes_md.append(f"- No reference summary yet for **{lecture['name']}** "
                            f"(`{lecture['reference_summary']}`), so it has no ROUGE scores.")

        candidates: dict[str, tuple[str, bool]] = {}
        if reference:
            n_words = len(reference.split())
            candidates[f"Lead-{n_words} baseline"] = (lead_baseline(transcript.full_text, n_words), True)

        for system in config["systems"]:
            record = run_system(system, lecture["name"], title, transcript, fresh)
            if "skipped" in record:
                notes_md.append(f"- **{system['name']}** skipped on {lecture['name']}: {record['skipped']}")
                continue
            per_system[system["name"]].append(record)
            run_rows.append({k: record[k] for k in (
                "system", "lecture", "wall_seconds", "api_seconds", "llm_calls", "prompt_tokens",
                "completion_tokens", "sections", "mcq_generated", "mcq_valid")})
            candidates[system["name"]] = (record["summary"], False)

        if reference:
            for name, (text, is_baseline) in candidates.items():
                scores = rouge(reference, text)
                key = "Lead baseline" if is_baseline else name
                for rouge_type in ROUGE_TYPES:
                    rouge_by_system.setdefault(key, {}).setdefault(rouge_type, []).append(scores[rouge_type]["f1"])
                rouge_rows.append({
                    "lecture": lecture["name"],
                    "system": name,
                    **{f"{ROUGE_LABELS[t]} P": round(scores[t]["precision"], 3) for t in ROUGE_TYPES},
                    **{f"{ROUGE_LABELS[t]} R": round(scores[t]["recall"], 3) for t in ROUGE_TYPES},
                    **{f"{ROUGE_LABELS[t]} F1": round(scores[t]["f1"], 3) for t in ROUGE_TYPES},
                })

    # Aggregate per system.
    comparison = []
    for name, records in per_system.items():
        if not records:
            continue
        generated = sum(r["mcq_generated"] for r in records)
        valid = sum(r["mcq_valid"] for r in records)
        row = {
            "System": name,
            "Lectures": len(records),
            "Avg API time (s)": round(mean_std([r["api_seconds"] for r in records])[0], 1),
            "Avg wall time (s)": round(mean_std([r["wall_seconds"] for r in records])[0], 1),
            "Avg tokens": round(mean_std([r["prompt_tokens"] + r["completion_tokens"] for r in records])[0]),
            "MCQs valid / generated": f"{valid}/{generated}",
            "MCQ validity (%)": round(100 * valid / generated, 1) if generated else "-",
        }
        for rouge_type in ROUGE_TYPES:
            values = rouge_by_system.get(name, {}).get(rouge_type, [])
            mean, std = mean_std(values)
            row[f"{ROUGE_LABELS[rouge_type]} F1"] = f"{mean:.3f} ± {std:.3f}" if values else "-"
        comparison.append(row)

    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "llm_runs.csv", run_rows)
    write_csv(RESULTS / "llm_comparison.csv", comparison)
    write_csv(RESULTS / "rouge_scores.csv", rouge_rows)

    # Charts
    if rouge_by_system:
        names = list(rouge_by_system)
        charts.grouped_bars(
            RESULTS / "rouge_f1.png",
            f"Summary quality vs human reference (ROUGE F1, {lectures_with_reference} lecture(s))",
            [ROUGE_LABELS[t] for t in ROUGE_TYPES],
            [(n, [mean_std(rouge_by_system[n][t])[0] for t in ROUGE_TYPES], n == "Lead baseline") for n in names],
            ylabel="F1 score (higher is better)",
            ymax=1.0,
        )
    if comparison:
        charts.simple_bars(RESULTS / "api_time.png", "Generation time per lecture (notes + quiz)",
                           [r["System"] for r in comparison], [r["Avg API time (s)"] for r in comparison],
                           ylabel="Seconds in API calls (lower is better)", fmt="{:.0f}s")
        charts.simple_bars(RESULTS / "mcq_validity.png", "MCQs passing all quality checks",
                           [r["System"] for r in comparison],
                           [r["MCQ validity (%)"] if r["MCQ validity (%)"] != "-" else 0 for r in comparison],
                           ylabel="Valid questions (%)", fmt="{:.0f}%", ymax=105)

    print(markdown_table(comparison))
    return "\n\n".join([
        "## LLM comparison",
        markdown_table(comparison),
        "API time counts only time spent waiting for model responses; wall time also includes "
        "waiting for free-tier rate limits. ROUGE values are mean ± standard deviation over lectures.",
        "### ROUGE details (per lecture)",
        markdown_table(rouge_rows),
        "### Runs",
        markdown_table(run_rows),
        *(["### Notes", "\n".join(notes_md)] if notes_md else []),
    ])


# --------------------------------------------------- transcription WER


def prepare_audio(sample: dict) -> Path:
    """Download (once) and trim the sample to `seconds`, as 16 kHz mono WAV."""
    out = RUNS / "audio" / f"{slug(sample['name'])}.wav"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if sample.get("youtube"):
            source = download_audio(extract_video_id(sample["youtube"]), Path(tmp))
        else:
            source = (EVAL_DIR / sample["file"]).resolve()
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-t", str(sample["seconds"]),
             "-ac", "1", "-ar", "16000", str(out)],
            check=True,
        )
    return out


def run_engine(engine: dict, sample: dict, audio: Path, fresh: bool) -> dict:
    cache = RUNS / "wer" / f"{slug(sample['name'])}__{slug(engine['name'])}.json"
    if cache.exists() and not fresh:
        return load_json(cache)
    settings = get_settings()
    print(f"  > {engine['name']} ...", flush=True)
    started = time.perf_counter()
    try:
        if engine["engine"] == "groq":
            if not settings.has_groq:
                return {"skipped": "GROQ_API_KEY is not set"}
            segments, _ = GroqWhisperTranscriber(settings.groq_api_key, engine["model"]).transcribe(audio, sample.get("language"))
        else:
            transcriber = LocalWhisperTranscriber(engine["model"], settings.local_whisper_device, settings.local_whisper_compute_type)
            segments, _ = transcriber.transcribe(audio, sample.get("language"))
    except GroqWhisperError as exc:
        return {"skipped": exc.reason}
    record = {
        "hypothesis": " ".join(s.text for s in segments),
        "seconds": round(time.perf_counter() - started, 2),
    }
    save_json(cache, record)
    return record


def evaluate_wer(config: dict, fresh: bool) -> str:
    print("\n== Transcription accuracy (WER / CER) ==")
    rows = []
    for sample in config["wer_samples"]:
        reference_path = EVAL_DIR / sample["reference"]
        if not reference_path.exists():
            print(f"  ! missing reference transcript {reference_path}; skipping {sample['name']}")
            continue
        reference = reference_path.read_text(encoding="utf-8")
        audio = prepare_audio(sample)
        for engine in config["wer_engines"]:
            record = run_engine(engine, sample, audio, fresh)
            if "skipped" in record:
                print(f"    skipped: {record['skipped']}")
                continue
            raw = transcription_score(reference, record["hypothesis"])
            score = transcription_score(reference, record["hypothesis"], normalise=True)
            rows.append({
                "Sample": sample["name"],
                "Engine": engine["name"],
                "WER raw (%)": round(100 * raw.wer, 1),
                "WER (%)": round(100 * score.wer, 1),
                "CER (%)": round(100 * score.cer, 1),
                "Substitutions": score.substitutions,
                "Deletions": score.deletions,
                "Insertions": score.insertions,
                "Reference words": score.reference_words,
                "Time (s)": record["seconds"],
                "Real-time factor": round(record["seconds"] / sample["seconds"], 3),
            })

    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "wer.csv", rows)
    if rows:
        engines = list(dict.fromkeys(r["Engine"] for r in rows))
        def avg(metric: str, engine: str) -> float:
            return mean_std([r[metric] for r in rows if r["Engine"] == engine])[0]
        charts.grouped_bars(
            RESULTS / "wer_cer.png",
            "Transcription errors vs human transcript (lower is better)",
            [e.replace(" (", "\n(") for e in engines],
            [("WER", [avg("WER (%)", e) for e in engines], False), ("CER", [avg("CER (%)", e) for e in engines], False)],
            ylabel="Error rate (%)",
            fmt="{:.1f}%",
            # At least 0-5% so that differences of a few words don't look dramatic.
            ymax=max(5.0, 1.2 * max(max(r["WER (%)"], r["CER (%)"]) for r in rows)),
        )
    print(markdown_table(rows))
    sources = "\n".join(f"- {s['name']}: {s.get('reference_source', 'reference written by hand')}" for s in config["wer_samples"])
    return "\n\n".join([
        "## Transcription accuracy",
        markdown_table(rows),
        "WER = (substitutions + deletions + insertions) / reference words. *WER raw* only ignores case and "
        "punctuation; *WER* and *CER* also normalise writing style (\"28x28\" = \"28 by 28\", \"3\" = \"three\", "
        "hyphenated words split), as is standard in ASR evaluation. The error counts refer to the normalised WER. "
        "Real-time factor = processing time / audio length (below 1 = faster than real time).",
        "Reference transcripts:\n" + sources,
    ])


# ------------------------------------------------------------------ main


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Lectura evaluation")
    parser.add_argument("what", nargs="?", choices=["all", "llm", "wer"], default="all")
    parser.add_argument("--fresh", action="store_true", help="Ignore cached runs and regenerate everything")
    parser.add_argument("--config", type=Path, default=EVAL_DIR / "config.json", help="Alternative config file")
    parser.add_argument("--out", type=Path, help="Alternative results folder (default: evaluation/results)")
    args = parser.parse_args()
    setup_logging("WARNING")

    global RESULTS, RUNS
    if args.out:
        RESULTS = args.out.resolve()
        RUNS = RESULTS / "runs"
    config = load_json(args.config)
    sections = [f"# Lectura evaluation results\n\nGenerated {datetime.now():%Y-%m-%d %H:%M}."]
    if args.what in ("all", "llm"):
        sections.append(evaluate_llms(config, args.fresh))
    if args.what in ("all", "wer"):
        sections.append(evaluate_wer(config, args.fresh))

    report = RESULTS / ("results.md" if args.what == "all" else f"results_{args.what}.md")
    report.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"\nTables, charts and {report.name} saved in {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
