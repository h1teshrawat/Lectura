# Lectura evaluation

Three experiments for the project report, all run by one script:

| Experiment | Question | Metrics |
|---|---|---|
| **Summary quality** | How close are AI summaries to a human summary? | ROUGE-1, ROUGE-2, ROUGE-L (precision, recall, F1), vs. a *Lead-N* baseline |
| **LLM comparison** | Which model is best for Lectura? | ROUGE F1, generation time, tokens, MCQ validity rate |
| **Transcription accuracy** | How accurate is each Whisper engine? | WER (raw and normalised), CER, error breakdown, real-time factor |

## Setup (once)

```powershell
cd C:\Projects\LectureLens
backend\.venv\Scripts\python -m pip install -r evaluation\requirements.txt
```

## Run

```powershell
backend\.venv\Scripts\python evaluation\run_eval.py          # everything
backend\.venv\Scripts\python evaluation\run_eval.py llm      # LLM comparison + ROUGE only
backend\.venv\Scripts\python evaluation\run_eval.py wer      # transcription only
backend\.venv\Scripts\python evaluation\run_eval.py --fresh  # regenerate instead of using the cache
backend\.venv\Scripts\python -m pytest evaluation            # tests for the metrics
```

LLM generations and transcriptions are **cached** in `results/runs/`, so re-running
after writing a reference summary takes seconds and costs no API quota.
A system whose API key is missing (e.g. Gemini) is skipped and retried next time.

## Outputs (`results/`)

| File | Contents |
|---|---|
| `results.md` | All tables in Markdown, ready to paste into the report |
| `llm_comparison.csv`, `llm_runs.csv` | Per-system summary and per-lecture runs |
| `rouge_scores.csv` | ROUGE precision/recall/F1 per lecture and system |
| `wer.csv` | WER/CER per sample and engine |
| `rouge_f1.png`, `api_time.png`, `mcq_validity.png`, `wer_cer.png` | Charts (200 dpi) |

## Adding your own data

Edit `config.json`:

- **Reference summaries** (`references/summaries/*.md`): watch the lecture and write
  150–250 words **yourself**, in the same language as the notes. Never generate them
  with AI: ROUGE only means something against an independent human reference.
- **More lectures**: add `{ "name", "lecture_id", "reference_summary" }`. The
  `lecture_id` is in the browser address bar (`/lectures/<id>`).
- **WER samples**: add a `{ "name", "youtube" or "file", "seconds", "language", "reference" }`
  entry. The reference must be a human transcript of exactly the first `seconds` of audio.
  A 1–2 minute **Hindi** sample is the most informative addition: small models
  struggle much more with Hindi than with English.
- **Systems / engines**: add another `{ "name", "provider", "model" }` or Whisper engine.

## Method notes (for the report)

- **ROUGE** uses a Unicode-aware tokenizer (the default one deletes Hindi text) and
  Porter stemming for English words. The *Lead-N baseline* is the first N words of
  the transcript, N = length of the reference; a useful summariser must beat it.
- **Summaries compared** = the notes' overview + key takeaways.
- **Times**: *API time* is the time spent in model calls; *wall time* also includes
  waiting for free-tier rate limits, so API time is the fair speed comparison.
- **MCQ validity** = share of generated questions passing every quality check
  (4 distinct options, exactly one correct answer, no "all of the above", no duplicates).
- **WER normalisation**: raw WER only ignores case and punctuation. The normalised WER
  also treats "28x28" = "28 by 28", "3" = "three" and splits hyphenated words, because
  human captions and ASR output often write the same speech differently. Report both.
- **Sample size**: a few lectures and clips give indicative, not statistically
  significant, results. Report mean ± standard deviation and say so in the limitations.
