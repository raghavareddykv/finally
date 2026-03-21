"""Tests for database schema creation and lazy initialization."""

import os

import aiosqlite
import pytest

from db.connection import get_connection, reset_initialization
from db.schema import DEFAULT_WATCHLIST_TICKERS

EXPECTED_TABLES = sorted([
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
])


class TestLazyInitialization:
    async def test_creates_database_file(self, isolated_db):
        assert not os.path.exists(isolated_db)
        conn = await get_connection()
        await conn.close()
        assert os.path.exists(isolated_db)

    async def test_creates_all_tables(self, isolated_db):
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            assert tables == EXPECTED_TABLES
        finally:
            await conn.close()

    async def test_seeds_default_user(self, isolated_db):
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT id, cash_balance FROM users_profile"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "default"
            assert row[1] == 10000.0
        finally:
            await conn.close()

    async def test_seeds_default_watchlist(self, isolated_db):
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker"
            )
            tickers = [row[0] for row in await cursor.fetchall()]
            assert tickers == sorted(DEFAULT_WATCHLIST_TICKERS)
            assert len(tickers) == 10
        finally:
            await conn.close()

    async def test_idempotent_initialization(self, isolated_db):
        """Calling get_connection twice does not duplicate seed data."""
        conn1 = await get_connection()
        await conn1.close()

        # Force re-initialization
        reset_initialization()

        conn2 = await get_connection()
        try:
            cursor = await conn2.execute(
                "SELECT COUNT(*) FROM users_profile"
            )
            count = (await cursor.fetchone())[0]
            assert count == 1

            cursor = await conn2.execute(
                "SELECT COUNT(*) FROM watchlist"
            )
            count = (await cursor.fetchone())[0]
            assert count == 10
        finally:
            await conn2.close()

    async def test_wal_journal_mode(self, isolated_db):
        conn = await get_connection()
        try:
            cursor = await conn.execute("PRAGMA journal_mode")
            mode = (await cursor.fetchone())[0]
            assert mode == "wal"
        finally:
            await conn.close()

    async def test_row_factory_returns_dict_like(self, isolated_db):
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                "SELECT id, cash_balance FROM users_profile WHERE id = 'default'"
            )
            row = await cursor.fetchone()
            # aiosqlite.Row supports key access
            assert row["id"] == "default"
            assert row["cash_balance"] == 10000.0
        finally:
            await conn.close()
