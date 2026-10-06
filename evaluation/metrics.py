"""Evaluation metrics: ROUGE for summaries, WER/CER for transcription.

ROUGE (Recall-Oriented Understudy for Gisting Evaluation) measures how much
a generated summary overlaps with a human reference summary:
  - ROUGE-1: overlap of single words (unigrams) -> covers the right content?
  - ROUGE-2: overlap of word pairs (bigrams)     -> similar phrasing?
  - ROUGE-L: longest common subsequence          -> similar order/structure?
Each has precision (how much of the generated text is in the reference),
recall (how much of the reference was covered) and F1 (their balance).

WER (Word Error Rate) = (Substitutions + Deletions + Insertions) / words in reference.
CER is the same at character level (fairer for Hindi, where word boundaries vary).
Lower is better; 0.0 means a perfect transcript.
"""

import re
import statistics
from dataclasses import dataclass

import jiwer
from nltk.stem import porter
from rouge_score import rouge_scorer

ROUGE_TYPES = ("rouge1", "rouge2", "rougeL")


class UnicodeTokenizer:
    """Tokenizer for rouge-score that keeps non-English letters.

    rouge-score's default tokenizer deletes every character outside a-z/0-9,
    so a Hindi (Devanagari) summary would score 0 no matter how good it is.
    We keep all Unicode letters/digits and apply the Porter stemmer to
    English words only ("networks" and "network" then count as a match).
    """

    def __init__(self, stem: bool = True) -> None:
        self.stemmer = porter.PorterStemmer() if stem else None

    def tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if self.stemmer:
            tokens = [self.stemmer.stem(t) if t.isascii() and len(t) > 3 else t for t in tokens]
        return tokens


_SCORER = rouge_scorer.RougeScorer(list(ROUGE_TYPES), tokenizer=UnicodeTokenizer())


def rouge(reference: str, candidate: str) -> dict[str, dict[str, float]]:
    """ROUGE-1/2/L precision, recall and F1 of `candidate` against `reference`."""
    scores = _SCORER.score(reference, candidate)
    return {
        name: {"precision": s.precision, "recall": s.recall, "f1": s.fmeasure}
        for name, s in scores.items()
    }


def lead_baseline(transcript_text: str, n_words: int) -> str:
    """A classic summarisation baseline: simply the first `n_words` of the transcript.

    A useful summariser must beat this, otherwise it adds nothing over reading
    the start of the lecture.
    """
    return " ".join(transcript_text.split()[:n_words])


# Normalise both texts the same way before comparing, so capitalisation and
# punctuation differences don't count as errors.
_WORDS = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
    jiwer.ReduceToListOfListOfWords(),
])
_CHARS = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
    jiwer.ReduceToListOfListOfChars(),
])


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def _number_to_words(match: re.Match) -> str:
    n = int(match.group())
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens - 2] + ("" if ones == 0 else f" {_ONES[ones]}")
    return match.group()  # larger numbers are rare in speech-vs-caption mismatches; leave as is


def normalise_transcript(text: str) -> str:
    """Remove writing-style differences that are not recognition errors.

    Human captions and ASR output often write the same speech differently:
    "28x28" vs "28 by 28", "3" vs "three", "crazy-smart" vs "crazy smart".
    Standard ASR evaluation (e.g. the Whisper paper) normalises both sides
    before computing WER; we apply a small, transparent set of such rules.
    """
    text = re.sub(r"(\d)\s*[x×]\s*(\d)", r"\1 by \2", text)  # 28x28 -> 28 by 28
    text = re.sub(r"[-‐‑–—/]", " ", text)                   # split hyphenated/slashed words
    text = re.sub(r"\b\d{1,2}\b", _number_to_words, text)   # 3 -> three, 28 -> twenty eight
    return text


@dataclass
class TranscriptionScore:
    wer: float
    cer: float
    substitutions: int
    deletions: int
    insertions: int
    reference_words: int


def transcription_score(reference: str, hypothesis: str, normalise: bool = False) -> TranscriptionScore:
    """WER, CER and the error breakdown of `hypothesis` against `reference`.

    With `normalise=True`, writing-style differences are removed first (see
    `normalise_transcript`); case and punctuation are always ignored.
    """
    if normalise:
        reference, hypothesis = normalise_transcript(reference), normalise_transcript(hypothesis)
    words = jiwer.process_words(reference, hypothesis, reference_transform=_WORDS, hypothesis_transform=_WORDS)
    cer = jiwer.cer(reference, hypothesis, reference_transform=_CHARS, hypothesis_transform=_CHARS)
    return TranscriptionScore(
        wer=words.wer,
        cer=cer,
        substitutions=words.substitutions,
        deletions=words.deletions,
        insertions=words.insertions,
        reference_words=words.hits + words.substitutions + words.deletions,
    )


def mean_std(values: list[float]) -> tuple[float, float]:
    """Mean and (sample) standard deviation; std is 0 for a single value."""
    if not values:
        return float("nan"), float("nan")
    return statistics.fmean(values), statistics.stdev(values) if len(values) > 1 else 0.0
