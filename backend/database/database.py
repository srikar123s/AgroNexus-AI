"""SQLite database initialization and connection helpers for AgroNexus AI."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = DATABASE_DIR / "agronexus.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"


def connect(database_path: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Return a SQLite connection configured for referential integrity."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Path:
    """Create every AgroNexus table and index if it does not already exist."""
    destination = Path(database_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with connect(destination) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Idempotent additive migrations keep existing local demo databases usable.
        for statement in (
            "ALTER TABLE farms ADD COLUMN owner_id TEXT REFERENCES users(user_id)",
            "ALTER TABLE users ADD COLUMN username TEXT",
            "ALTER TABLE users ADD COLUMN phone TEXT",
        ):
            try:
                connection.execute(statement)
            except sqlite3.OperationalError as error:
                if "duplicate column" not in str(error).lower():
                    raise
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (2)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone IS NOT NULL"
        )

    return destination


if __name__ == "__main__":
    created_database = initialize_database()
    print(f"Initialized AgroNexus database at {created_database}")
