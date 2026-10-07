# Lectura evaluation results

Generated 2026-10-07 19:16.

## LLM comparison

| System | Lectures | Avg API time (s) | Avg wall time (s) | Avg tokens | MCQs valid / generated | MCQ validity (%) | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b (Groq) | 2 | 64.3 | 64.5 | 16137 | 48/48 | 100.0 | - | - | - |
| gpt-oss-20b (Groq) | 2 | 62.8 | 62.8 | 14935 | 46/48 | 95.8 | - | - | - |

API time counts only time spent waiting for model responses; wall time also includes waiting for free-tier rate limits. ROUGE values are mean ± standard deviation over lectures.

### ROUGE details (per lecture)

_No data._

### Runs

| system | lecture | wall_seconds | api_seconds | llm_calls | prompt_tokens | completion_tokens | sections | mcq_generated | mcq_valid |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b (Groq) | Neural networks (English) | 87.8 | 87.7 | 9 | 13411 | 5519 | 11 | 24 | 24 |
| gpt-oss-20b (Groq) | Neural networks (English) | 76.9 | 76.9 | 9 | 13465 | 4467 | 11 | 24 | 24 |
| gpt-oss-120b (Groq) | Software engineering (Hindi) | 41.1 | 41.0 | 7 | 8597 | 4747 | 9 | 24 | 24 |
| gpt-oss-20b (Groq) | Software engineering (Hindi) | 48.6 | 48.6 | 7 | 8606 | 3332 | 9 | 24 | 22 |

### Notes

- No reference summary yet for **Neural networks (English)** (`references/summaries/neural_networks.md`), so it has no ROUGE scores.
- **Gemini Flash** skipped on Neural networks (English): GEMINI_API_KEY is not set.
- No reference summary yet for **Software engineering (Hindi)** (`references/summaries/software_engineering_hindi.md`), so it has no ROUGE scores.
- **Gemini Flash** skipped on Software engineering (Hindi): GEMINI_API_KEY is not set.

## Transcription accuracy

| Sample | Engine | WER raw (%) | WER (%) | CER (%) | Substitutions | Deletions | Insertions | Reference words | Time (s) | Real-time factor |
|---|---|---|---|---|---|---|---|---|---|---|
| Neural networks, first 2 min (English) | Whisper large-v3 (Groq) | 4.9 | 2.1 | 1.7 | 2 | 3 | 3 | 375 | 2.12 | 0.018 |
| Neural networks, first 2 min (English) | Whisper large-v3-turbo (Groq) | 4.7 | 1.3 | 1.2 | 0 | 3 | 2 | 375 | 1.2 | 0.01 |
| Neural networks, first 2 min (English) | Whisper small (local, int8) | 3.3 | 0.8 | 0.7 | 1 | 0 | 2 | 375 | 19.17 | 0.163 |

WER = (substitutions + deletions + insertions) / reference words. *WER raw* only ignores case and punctuation; *WER* and *CER* also normalise writing style ("28x28" = "28 by 28", "3" = "three", hyphenated words split), as is standard in ASR evaluation. The error counts refer to the normalised WER. Real-time factor = processing time / audio length (below 1 = faster than real time).

Reference transcripts:
- Neural networks, first 2 min (English): Manual (human-written) English captions uploaded by 3Blue1Brown
