"""SQLite backup/restore helpers and PostgreSQL migration guidance."""
from __future__ import annotations

import shutil
from pathlib import Path

from database.database import connect, initialize_database


def backup(source: str | Path, destination: str | Path) -> Path:
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(source)
    with connect(source) as db, sqlite3_connection(destination) as target:
        db.backup(target)
    return destination


def sqlite3_connection(path: Path):
    import sqlite3
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def restore(backup_path: str | Path, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, destination)
    initialize_database(destination)
    return destination
