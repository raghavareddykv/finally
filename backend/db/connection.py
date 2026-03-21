"""Database connection management and lazy initialization.

The database file lives at {project_root}/db/finally.db. On first access,
the schema is created and default data is seeded automatically.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .schema import DEFAULT_WATCHLIST_TICKERS, SCHEMA_SQL

# Resolve db path: DB_PATH env var, or {project_root}/db/finally.db
_DEFAULT_DB_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "db" / "finally.db"
)
DB_PATH: str = os.environ.get("FINALLY_DB_PATH", _DEFAULT_DB_PATH)

_initialized: bool = False


async def get_connection() -> aiosqlite.Connection:
    """Open a connection to the SQLite database, initializing if needed."""
    await _ensure_initialized()
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def _ensure_initialized() -> None:
    """Lazily create the schema and seed data on first access."""
    global _initialized
    if _initialized:
        return

    # Ensure the directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = await aiosqlite.connect(DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row

        # Check if tables already exist
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users_profile'"
        )
        row = await cursor.fetchone()

        if row is None:
            # Fresh database — create schema and seed
            await conn.executescript(SCHEMA_SQL)
            await _seed_data(conn)
        else:
            # Tables exist — ensure schema is up to date (CREATE IF NOT EXISTS is safe)
            await conn.executescript(SCHEMA_SQL)

        await conn.commit()
    finally:
        await conn.close()

    _initialized = True


async def _seed_data(conn: aiosqlite.Connection) -> None:
    """Insert default user and watchlist entries."""
    now = datetime.now(timezone.utc).isoformat()

    # Default user
    await conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", 10000.0, now),
    )

    # Default watchlist
    for ticker in DEFAULT_WATCHLIST_TICKERS:
        await conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, now),
        )


def reset_initialization() -> None:
    """Reset the initialization flag. Used for testing."""
    global _initialized
    _initialized = False
