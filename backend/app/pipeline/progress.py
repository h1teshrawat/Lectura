"""Live progress of running jobs, kept in memory for fast SSE updates.

The background worker writes here many times per second; the SSE endpoint
reads from here. Progress is also saved to SQLite (less often), so it
survives a page refresh and shows up in the lecture details.
"""

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

# The stages shown in the frontend stepper, in order.
STAGES = ("queued", "fetching", "transcribing", "notes", "flashcards", "quiz", "indexing", "done")

# Share of the overall progress bar each stage covers: (start, end).
STAGE_RANGES: dict[str, tuple[float, float]] = {
    "queued": (0.0, 0.0),
    "fetching": (0.0, 0.05),
    "transcribing": (0.05, 0.30),
    "notes": (0.30, 0.60),
    "flashcards": (0.60, 0.75),
    "quiz": (0.75, 0.93),
    "indexing": (0.93, 1.0),
    "done": (1.0, 1.0),
}


def overall_progress(stage: str, stage_fraction: float) -> float:
    """Convert progress *within* a stage (0..1) into overall progress (0..1)."""
    start, end = STAGE_RANGES.get(stage, (0.0, 0.0))
    return start + (end - start) * min(max(stage_fraction, 0.0), 1.0)


@dataclass
class ProgressState:
    status: str = "queued"      # queued | processing | done | failed
    stage: str = "queued"
    progress: float = 0.0       # overall, 0..1
    message: str = "Waiting to start..."
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    hint: str | None = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        elapsed = time.time() - self.started_at
        data["elapsed_seconds"] = round(elapsed, 1)
        # Simple ETA: if 25% took 60 s, the remaining 75% should take ~180 s.
        if self.status == "processing" and self.progress >= 0.05:
            data["eta_seconds"] = round(elapsed * (1 - self.progress) / self.progress)
        else:
            data["eta_seconds"] = None
        return data


class ProgressStore:
    """Thread-safe dictionary: lecture_id -> latest ProgressState."""

    def __init__(self) -> None:
        self._states: dict[str, ProgressState] = {}
        self._lock = threading.Lock()

    def update(self, lecture_id: str, **fields: Any) -> ProgressState:
        with self._lock:
            state = self._states.setdefault(lecture_id, ProgressState())
            for name, value in fields.items():
                setattr(state, name, value)
            state.updated_at = time.time()
            # Return a copy so callers can't change the stored state by accident.
            return ProgressState(**asdict(state))

    def get(self, lecture_id: str) -> ProgressState | None:
        with self._lock:
            state = self._states.get(lecture_id)
            return ProgressState(**asdict(state)) if state else None

    def remove(self, lecture_id: str) -> None:
        with self._lock:
            self._states.pop(lecture_id, None)
