"""Ready-made demo lectures, bundled with the code as JSON files.

The live demo runs on a free server whose disk is wiped on every restart, and
YouTube blocks downloads from cloud servers. So a few lectures are processed
locally, exported with `python -m cli.export_demo`, and loaded on startup.
Their chat index is built the first time someone asks a question.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from app.config import BACKEND_DIR
from app.db.models import Lecture

logger = logging.getLogger(__name__)

DEMO_DIR = BACKEND_DIR / "demo_lectures"


def export_lecture(lecture: Lecture, folder: Path = DEMO_DIR) -> Path:
    """Save a finished lecture as `<folder>/<source id>.json`."""
    if lecture.status != "done":
        raise ValueError(f"Lecture {lecture.id} is not finished (status: {lecture.status}).")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{lecture.source_id}.json"
    path.write_text(json.dumps(lecture.model_dump(mode="json"), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def seed_demo_lectures(engine: Engine, folder: Path = DEMO_DIR) -> int:
    """Add the bundled lectures that aren't in the database yet. Returns how many were added."""
    added = 0
    with Session(engine) as session:
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if session.get(Lecture, data["id"]) is None:
                session.add(Lecture.model_validate(data))
                added += 1
        session.commit()
    if added:
        logger.info("Loaded %d demo lecture(s).", added)
    return added
