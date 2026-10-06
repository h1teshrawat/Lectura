"""Database engine and per-request sessions."""

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from app.db import models  # noqa: F401  (registers the tables with SQLModel)

logger = logging.getLogger(__name__)


DB_FILENAME = "lectura.db"
# The project was renamed from "LectureLens"; older installs have this file.
_LEGACY_DB_FILENAME = "lecturelens.db"


def _lecture_count(path: Path) -> int:
    """Number of lectures stored in a database file (0 if it can't be read)."""
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            return connection.execute("SELECT COUNT(*) FROM lecture").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error:
        return 0


def resolve_db_path(data_dir: Path) -> Path:
    """Path of the SQLite file, moving a database from the project's old name if needed.

    The old database also replaces a new one that holds no lectures yet (for
    example one created by a server restart that happened mid-rename).
    """
    db_path = data_dir / DB_FILENAME
    legacy = data_dir / _LEGACY_DB_FILENAME
    if not legacy.exists():
        return db_path
    if db_path.exists() and (_lecture_count(db_path) > 0 or _lecture_count(legacy) == 0):
        return db_path
    try:
        # Move the main file plus SQLite's write-ahead-log companions (-wal, -shm),
        # removing any leftovers of the empty new database first.
        for suffix in ("", "-wal", "-shm"):
            db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
        for suffix in ("", "-wal", "-shm"):
            old = legacy.with_name(legacy.name + suffix)
            if old.exists():
                old.replace(db_path.with_name(db_path.name + suffix))
        logger.info("Renamed database %s -> %s", legacy.name, db_path.name)
        return db_path
    except OSError:
        # e.g. the old file is still open in another process: keep using it.
        logger.warning("Could not rename %s; using it as is.", legacy.name)
        return legacy


def create_db_engine(db_path: Path) -> Engine:
    """Create the SQLite engine and make sure all tables exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        # The background worker thread and request threads share the engine.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        # WAL mode lets the API read while the worker is writing progress.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with Session(request.app.state.engine) as session:
        yield session
