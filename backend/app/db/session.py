"""Database engine and per-request sessions."""

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from app.db import models  # noqa: F401  (registers the tables with SQLModel)


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
