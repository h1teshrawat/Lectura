"""Tests for the evaluation metrics.

Run from the project root:  backend\\.venv\\Scripts\\python -m pytest evaluation
"""

import math

import pytest

from metrics import UnicodeTokenizer, lead_baseline, mean_std, rouge, transcription_score


def test_identical_text_scores_one() -> None:
    scores = rouge("Neurons hold an activation.", "Neurons hold an activation.")
    assert all(scores[name]["f1"] == pytest.approx(1.0) for name in ("rouge1", "rouge2", "rougeL"))


def test_unrelated_text_scores_zero() -> None:
    assert rouge("gradient descent minimises loss", "cricket match in mumbai")["rouge1"]["f1"] == 0.0


def test_stemming_matches_word_forms() -> None:
    assert rouge("neural networks", "neural network")["rouge1"]["f1"] == pytest.approx(1.0)


def test_hindi_text_is_not_dropped() -> None:
    # The default rouge-score tokenizer would turn this into an empty list.
    assert UnicodeTokenizer().tokenize("न्यूरॉन एक संख्या रखता है") != []
    assert rouge("न्यूरॉन एक संख्या रखता है", "न्यूरॉन संख्या रखता है")["rouge1"]["f1"] > 0.8


def test_lead_baseline_takes_first_words() -> None:
    assert lead_baseline("one two three four five", 3) == "one two three"


@pytest.mark.parametrize(
    ("hypothesis", "expected_s_d_i"),
    [
        ("The cat sit on the mat!", (1, 0, 0)),          # "sat" -> "sit": substitution
        ("the cat sat on mat", (0, 1, 0)),               # second "the" missing: deletion
        ("the cat sat on the mat today", (0, 0, 1)),     # extra "today": insertion
    ],
)
def test_wer_counts_each_error_type(hypothesis, expected_s_d_i) -> None:
    score = transcription_score("the cat sat on the mat", hypothesis)
    assert (score.substitutions, score.deletions, score.insertions) == expected_s_d_i
    assert score.reference_words == 6
    assert score.wer == pytest.approx(1 / 6)


def test_perfect_transcript_ignores_case_and_punctuation() -> None:
    score = transcription_score("Hello, world.", "hello world")
    assert score.wer == 0.0 and score.cer == 0.0


def test_normalisation_removes_writing_style_differences() -> None:
    reference = "It's rendered at 28x28 pixels, this 3 is crazy-smart."
    hypothesis = "it's rendered at 28 by 28 pixels this three is crazy smart"
    assert transcription_score(reference, hypothesis).wer > 0.3  # raw: many "errors"
    assert transcription_score(reference, hypothesis, normalise=True).wer == 0.0


def test_mean_std() -> None:
    assert mean_std([0.5]) == (0.5, 0.0)
    mean, std = mean_std([0.2, 0.4])
    assert mean == pytest.approx(0.3) and std == pytest.approx(0.1414, abs=1e-3)
    assert all(math.isnan(v) for v in mean_std([]))
