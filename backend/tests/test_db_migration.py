"""The database is moved from the project's old name ("LectureLens") on startup."""

import sqlite3

from app.db.session import DB_FILENAME, resolve_db_path


def test_legacy_database_is_renamed_with_wal_files(tmp_path) -> None:
    (tmp_path / "lecturelens.db").write_text("main")
    (tmp_path / "lecturelens.db-wal").write_text("wal")

    path = resolve_db_path(tmp_path)

    assert path == tmp_path / DB_FILENAME
    assert path.read_text() == "main"
    assert (tmp_path / f"{DB_FILENAME}-wal").read_text() == "wal"
    assert not (tmp_path / "lecturelens.db").exists()


def _db_with_lectures(path, count: int) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE lecture (id TEXT)")
    connection.executemany("INSERT INTO lecture VALUES (?)", [(str(i),) for i in range(count)])
    connection.commit()
    connection.close()


def test_new_database_with_lectures_is_left_alone(tmp_path) -> None:
    _db_with_lectures(tmp_path / DB_FILENAME, 2)
    _db_with_lectures(tmp_path / "lecturelens.db", 5)
    assert resolve_db_path(tmp_path) == tmp_path / DB_FILENAME
    assert (tmp_path / "lecturelens.db").exists()  # untouched


def test_empty_new_database_is_replaced_by_legacy_data(tmp_path) -> None:
    # A restart during the rename created an empty new database: the old data must win.
    _db_with_lectures(tmp_path / DB_FILENAME, 0)
    _db_with_lectures(tmp_path / "lecturelens.db", 4)
    path = resolve_db_path(tmp_path)
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM lecture").fetchone()[0] == 4
    connection.close()
    assert not (tmp_path / "lecturelens.db").exists()


def test_fresh_install_uses_new_name(tmp_path) -> None:
    assert resolve_db_path(tmp_path) == tmp_path / DB_FILENAME
