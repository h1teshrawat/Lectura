"""Offline speech-to-text with faster-whisper (no API key or internet needed).

faster-whisper is a re-implementation of OpenAI's Whisper using CTranslate2,
an inference engine that runs ~4x faster than the original on CPU and uses
less memory, especially with int8 quantisation (storing weights as 8-bit
integers instead of 32-bit floats).

The first run downloads the model from Hugging Face (~480 MB for "small")
and caches it, so later runs start quickly.
"""

import logging
import os
from collections.abc import Callable
from pathlib import Path

# Windows can't create symlinks without Developer Mode; Hugging Face then copies
# files instead and prints a harmless warning. Hide that warning.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

from faster_whisper import WhisperModel  # noqa: E402

from app.transcription.models import TranscriptSegment

logger = logging.getLogger(__name__)

# Loading a model takes a few seconds, so keep loaded models in memory.
_MODEL_CACHE: dict[tuple[str, str, str], WhisperModel] = {}


class LocalWhisperTranscriber:
    """Runs a Whisper model on this computer."""

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def _get_model(self) -> WhisperModel:
        key = (self.model_size, self.device, self.compute_type)
        if key not in _MODEL_CACHE:
            logger.info(
                "Loading faster-whisper '%s' on %s (first time downloads the model)...",
                self.model_size,
                self.device,
            )
            _MODEL_CACHE[key] = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return _MODEL_CACHE[key]

    def transcribe(
        self,
        path: Path,
        language: str | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[list[TranscriptSegment], str | None]:
        """Transcribe an audio file.

        Args:
            path: Audio file.
            language: ISO code like "en" or "hi", or None to auto-detect.
            on_progress: Optional callback receiving progress (0..1) for this file.

        Returns:
            (segments with times relative to this file, detected language)
        """
        model = self._get_model()
        segments_iter, info = model.transcribe(
            str(path),
            language=language,
            beam_size=5,
            # VAD = Voice Activity Detection: skips silent parts, which makes
            # transcription faster and prevents hallucinated text in silences.
            vad_filter=True,
            # Stops Whisper from getting stuck repeating the same sentence.
            condition_on_previous_text=False,
        )

        segments: list[TranscriptSegment] = []
        # `segments_iter` is a generator: the actual transcription happens
        # while we loop over it, which is why we can report progress here.
        for seg in segments_iter:
            text = seg.text.strip()
            if text:
                segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=text))
            if on_progress and info.duration:
                on_progress(min(seg.end / info.duration, 1.0))

        return segments, info.language
